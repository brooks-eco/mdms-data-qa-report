"""Example code using vegetation workbook to generate a summary table and plots similar to the provided R code.
This will be a template that will be adjusted using config (dict or json) to specify the columns and logic for the summary and plots. The code is structured to be modular and easily adaptable for different datasets and requirements.
Make sure to adjust column names and logic as needed based on your actual data structure.
"""

from itertools import count
from shlex import join
import pandas as pd
from pandas.api.types import is_numeric_dtype
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path
from configs.config_base import get_config

input_file: str = "Fish_20260219173914.xlsx"
#input_file: str = "Vegetation_20260219153548.xlsx"
input_file:str = "waterbirdsurvey_20260220153534.xlsx"
testing_group_name: str = "LAC"#None#"MMY"#None #"LAC"

def ensure_path_exists(directory):
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)

def make_safe(filename):
    return filename.replace(" ", "_").replace("'", "").replace(":", "").replace("/", "-")


def load_data(filepath, group_name_source, workbook_def, testing_group, filter_date, start, end):
    print(f"Loading data from {filepath}...")
    try:
        xls = pd.ExcelFile(filepath)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return {}
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return {}
    workbook_data = {}
    if testing_group is not None:
        relevant_group_names = [testing_group]
    else:
        relevant_group_names = ["QA"]  # Default for area-scale books or if groups can't be found.

        # For multi-group workbooks, try to extract unique "GroupName" values from "FishSurveyEffort".
        if group_name_source in xls.sheet_names:
            trip_grouping_df = pd.read_excel(xls, sheet_name=group_name_source)
            if "GroupName" in trip_grouping_df.columns:
                groups = trip_grouping_df["GroupName"].dropna().unique()
                if groups.size > 0:
                    relevant_group_names = groups

    print(f"Processing report for Group(s): {', '.join(map(str, relevant_group_names))}")
    
    dfs = {}
    for sheet_name in workbook_def.keys():
        if sheet_name in xls.sheet_names:
            print(f"Reading sheet: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name)
            # filter data to the specified date range if the date column exists
            date_col = (
                "SampleDate"
                if "SampleDate" in df.columns
                else "date" if "date" in df.columns else None
            )
            if filter_date and date_col:
                df[date_col] = pd.to_datetime(df[date_col])
                df = df[(df[date_col] >= start) & (df[date_col] <= end)]
                df["Year"] = df[date_col].dt.year
                df["Month"] = df[date_col].dt.month

            
            dfs[sheet_name] = df
            
            
        else:
            print(f"Warning: Sheet '{sheet_name}' not found in the Excel file.")
    
    #filter to the groupname if GroupName column exists. "QA" is the default group name assigned for area-scale project books where GroupName is not a column.
    for group_name in relevant_group_names:
        print(f"Filtering to group: {group_name}")
        grp_dfs = dfs.copy()
        for sheet in grp_dfs:
            if "GroupName" in grp_dfs[sheet].columns:
                grp_dfs[sheet] = grp_dfs[sheet][grp_dfs[sheet]["GroupName"] == group_name]
        workbook_data[group_name] = grp_dfs

    return workbook_data




def join_tables_generic(dfs, joins_required):
    joined_dfs = {}

    for left_df_name, join_info in joins_required.items():
        right_df_name = join_info["right"]
        on_cols = join_info["on"]
        how = join_info["how"]

        if left_df_name not in dfs or right_df_name not in dfs:
            print(
                f"Error: DataFrame for '{left_df_name}' or '{right_df_name}' not found."
            )
            continue

        if (
            left_df_name in joined_dfs
        ):  # already joints, so we want to use the joined version of the left table for any subsequent joins to ensure we are retaining all the additional columns from previous joins. 
            # This is important for cases where there are multiple joins that build on each other (e.g. VegCommunitySurvey is joined with VegSamplingUnits, and then VegSpeciesAbundance is joined with the result of that join). If we don't use the joined version of the left table for subsequent joins, we will lose the additional columns from the previous joins and end up with incorrect results.
            left_df = joined_dfs[left_df_name]
        else:
            left_df = dfs[left_df_name]

        if (
            right_df_name in joined_dfs
        ):  # already joints, so we want to use the joined version of the right table for any subsequent joins to ensure we are retaining all the additional columns from previous joins. 
            # This is important for cases where there are multiple joins that build on each other (e.g. VegCommunitySurvey is joined with VegSamplingUnits, and then VegSpeciesAbundance is joined with the result of that join). If we don't use the joined version of the right table for subsequent joins, we will lose the additional columns from the previous joins and end up with incorrect results.
            right_df = joined_dfs[right_df_name]
        else:
            right_df = dfs[right_df_name]

        joined_df = pd.merge(left_df, right_df, on=on_cols, how=how)
        joined_dfs[left_df_name] = joined_df
        print(
                f"Using the join enhanced version of table '{left_df_name}' for summaries and plots."
            )

    # if table name in joined_dfs, use the joined version of the table, otherwise use the original version of the table. If neither exists, print an error and skip this summary.
    for table_name in dfs.keys():
        if table_name not in joined_dfs:
            joined_dfs[table_name] = dfs[table_name]
            print(
                f"Using the workbook version of table '{table_name}' for summaries and plots."
            )
           
    return joined_dfs


def filter_df(filter, df, task_type=None, task_name=None):
    for filter_col, filter_condition in filter.items():
        if filter_col in df.columns:
            if (
                isinstance(filter_condition, str)
                and filter_condition.lower() == "is not null"
            ):
                df = df[df[filter_col].notna()]
            elif (
                isinstance(filter_condition, str)
                and filter_condition.lower() == "is null"
            ):
                df = df[df[filter_col].isna()]
            # e.g. col_name: {"<": value} or {">": value} or {"==": value} or {"!=": value}
        elif isinstance(filter_condition, dict):
            for op, val in filter_condition.items():
                if op == "<":
                    df = df[df[filter_col] < val]
                elif op == ">":
                    df = df[df[filter_col] > val]
                elif op == "==":
                    df = df[df[filter_col] == val]
                elif op == "!=":
                    df = df[df[filter_col] != val]
                elif op == "in" and isinstance(val, (list, tuple, set)):
                    df = df[df[filter_col].isin(val)]
                elif op == "not in" and isinstance(val, (list, tuple, set)):
                    df = df[~df[filter_col].isin(val)]
                else:
                    print(
                        f"Warning: Unsupported operator '{op}' in filter condition for column '{filter_col}' in {task_type} definition '{task_name}'. Skipping this filter."
                    )
            else:
                print(
                    f"Warning: Unsupported filter condition type '{type(filter_condition)}' for column '{filter_col}' in {task_type} definition '{task_name}'. Skipping this filter."
                )
        else:
            print(
                f"Warning: Unsupported filter condition '{filter_condition}' for column '{filter_col}' in {task_type} definition '{task_name}'. Skipping this filter."
            )
    else:
        print(
            f"Warning: Filter column '{filter_col}' not found in table. Skipping this filter."
        )
    return df


def create_single_pie_plot(ax, df, label_col, value_col, title_str):
    """Generates a single pie chart on the provided axes."""
    # Aggregate values by label_col to combine multiple entries (e.g. strata) for the same category
    # if value_col is not a number or is the same as the category then aggregate by count
    if not is_numeric_dtype(df[value_col]) or label_col == value_col:
        group_df_agg = df.groupby(label_col, dropna=False).size().reset_index(name="count")
        value_col = "count"
    else:
        group_df_agg = df.groupby(label_col, as_index=False, dropna=False)[value_col].sum()
    
    # Filter for top 5 species for clarity
    group_df = group_df_agg.sort_values(by=value_col, ascending=False).head(5)

    plot_data = group_df[group_df[value_col] > 0].copy()
    
    #word break category labels by replacing the " " character with \n
    plot_data[label_col] = plot_data[label_col].fillna("missing/not provided").astype(str).str.replace(" ", "\n")
    
    if not plot_data.empty:
        ax.pie(
            plot_data[value_col],
            labels=plot_data[label_col],
            autopct="%1.1f%%",
        )
        ax.set_title(title_str)
    else:
        ax.text(
            0.5,
            0.5,
            "No positive data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_title(f"{title_str}\n(No data to plot)")


def create_single_scatter_plot(ax, df, x_col, y_col, color_col, title_str, show_legend=True):
    """Generates a single scatter plot on the provided axes."""
    if color_col and color_col in df.columns:
        # Simple categorical coloring
            
        categories = df[color_col].dropna().unique()
        # Get default color cycle
        prop_cycle = plt.rcParams['axes.prop_cycle']
        colors = prop_cycle.by_key()['color']
        
        for i, cat in enumerate(categories):
            subset = df[df[color_col] == cat]
            color = colors[i % len(colors)]
            ax.scatter(subset[x_col], subset[y_col], label=str(cat), color=color, alpha=0.7)
        
        # Add legend
        if show_legend:
            ax.legend(title=color_col, bbox_to_anchor=(1.05, 1), loc='upper left')
    else:
        ax.scatter(df[x_col], df[y_col], alpha=0.7)
    
    # Set labels and title
    #trim long x and y labels > 30 characters
    #x_col = x_col[:30]
    #y_col = y_col[:30]
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(title_str)
    ax.grid(True, linestyle='--', alpha=0.7)

def delete_existing_plots(output_path):
    """Deletes existing plot files in the output directory to prevent confusion with new plots."""
    if output_path.exists() and output_path.is_dir():
    # delete all plots in the output folder before creating new ones to avoid confusion and ensure we are only looking at the plots from the current run. We will only delete files that match the .png extension to avoid accidentally deleting other files in the output folder.
        for filename in output_path.iterdir():
            if filename.suffix == ".png":
                try:
                    filename.unlink() 
                except Exception as e:
                    print(f"Error deleting file {filename}: {e}")
                    continue

def create_plots(joined_dfs, data_summaries, PLOTS_DEFINITION, output_path) -> list[str]:
    """
    Generates plots based on the provided definitions and saves them to the output directory.

    Args:
        joined_dfs (dict): Dictionary of joined pandas DataFrames.
        PLOTS_DEFINITION (dict): Configuration for the plots to be generated.
        output_path (str): Directory to save the plots in.

    Returns:
        list[str]: A list of filenames for the generated plots.
    """
    print("Creating plots...")

        
    
    plot_collection = {}
    for plot_series_name, config in PLOTS_DEFINITION.items():
        plot_series = []
        
        # Determine plot type
        plot_type = config.get("type")
        if not plot_type:
             # Fallback for legacy keys if 'type' is missing
             if "pie-chart" in config: 
                 config = config["pie-chart"]
                 plot_type = "pie"
             elif "scatter-chart" in config:
                 config = config["scatter-chart"]
                 plot_type = "scatter"
             else:
                 print(f"Warning: Unknown plot type for '{plot_series_name}'. Skipping.")
                 continue

        table_name = config.get("table")
        group_by_cols = config.get("group_by")
        
        df = None
        if table_name in joined_dfs:
            df = joined_dfs[table_name]
        elif table_name in data_summaries:
            df = data_summaries[table_name][1]
        else:
            print(f"Error: Table '{table_name}' not found in joined data or summaries for plot '{plot_series_name}'.")
            continue

        if "filter" in config:
            df = filter_df(config["filter"], df, task_type="plot", task_name=plot_series_name)

        # Grouping
        if group_by_cols:
            groups = df.groupby(group_by_cols)
        else:
            groups = [("All Data", df)]

        if len(groups) == 0:
            print(f"    No data to plot for '{plot_series_name}'.")
            plot_collection[plot_series_name] = None
            continue

        for group_key, group_df in groups:
            fig_size=(4, 3) if len(groups) > 4 else (8,6)
            fig, ax = plt.subplots(figsize=fig_size)

            # Title logic
            group_key_tuple = group_key if isinstance(group_key, tuple) else (group_key,)
            group_key_tuple = tuple(
                d.strftime("%Y-%m-%d") if isinstance(d, pd.Timestamp) else d
                for d in group_key_tuple
            )
            title_parts = group_key_tuple
            title_str = " | ".join(map(str, title_parts))
            
            # Dispatch
            if plot_type == "pie":
                create_single_pie_plot(
                    ax, 
                    group_df, 
                    label_col=config.get("category"), 
                    value_col=config.get("value"), 
                    title_str=title_str
                )
            elif plot_type == "scatter":
                x_col = config.get("x")
                y_col = config.get("y")
                color_col = config.get("color")
                
                # Filter: Remove rows where both x and y are NaN
                plot_df = group_df.dropna(subset=[x_col, y_col], how='all').copy()
                
                if plot_df.empty:
                    plt.close(fig)
                    continue

                # Replace NaN with 0 in x and y columns
                plot_df[x_col] = plot_df[x_col].fillna(0)
                plot_df[y_col] = plot_df[y_col].fillna(0)

                # Aggregation logic: Aggregate if specified in config
                agg_func = config.get("aggregate_function")
                if agg_func:
                    is_x_numeric = is_numeric_dtype(plot_df[x_col])
                    is_y_numeric = is_numeric_dtype(plot_df[y_col])

                    if is_x_numeric and not is_y_numeric:
                        agg_cols = [y_col]
                        if color_col and color_col in plot_df.columns and color_col != y_col:
                            agg_cols.append(color_col)
                        plot_df = plot_df.groupby(agg_cols, as_index=False)[x_col].agg(agg_func)
                        #trim long species/site names
                        if plot_df[y_col].dtype == "str":
                            plot_df[y_col] = plot_df[y_col].str[:25]
                            plot_df = plot_df.sort_values(by=x_col, ascending=True).tail(15)
                    elif is_y_numeric and not is_x_numeric:
                        agg_cols = [x_col]
                        if color_col and color_col in plot_df.columns and color_col != x_col:
                            agg_cols.append(color_col)
                        plot_df = plot_df.groupby(agg_cols, as_index=False)[y_col].agg(agg_func)
                        #trim long species/site names
                        if plot_df[x_col].dtype == "str":
                            plot_df[x_col] = plot_df[x_col].str[:25]
                            plot_df = plot_df.sort_values(by=y_col, ascending=True).tail(15)
                        
                        
                create_single_scatter_plot(
                    ax, 
                    plot_df, 
                    x_col=x_col, 
                    y_col=y_col, 
                    color_col=color_col, 
                    title_str=title_str,
                    show_legend=config.get("Legend", True)
                )

            plt.tight_layout()

            # Filename logic
            safe_plot_name = make_safe(plot_series_name)
            sanitized_key_parts = [make_safe(str(p)) for p in title_parts]
            sanitized_key = "_".join(sanitized_key_parts)
            output_filename = f"{safe_plot_name}_{sanitized_key}.png"
            output_plot_path = output_path / output_filename

            plt.savefig(output_plot_path, bbox_inches='tight')
            plt.close(fig)
            print(f"Plot saved to {output_plot_path}")
            plot_series.append(output_filename)
            
        plot_collection[plot_series_name] = plot_series
    return plot_collection


def generate_effort_summaries(joined_dfs, summaries_config):
    print("Generating effort summaries...")
    summary_tables = {}

    for summary_name, config in summaries_config.items():
        table_name = config["table"]
        group_by_cols = config["group_by"]
        summary_funcs = config["summary"]

        if table_name not in joined_dfs:
            print(
                f"Error: Table '{table_name}' not found for summary '{summary_name}'."
            )
            continue

        df = joined_dfs[table_name]
        # filter the dataframe based on the filter specified in the config if it exists
        if "filter" in config:
            df = filter_df(
                config["filter"], df, task_type="summary", task_name=summary_name
            )

        # fill NaNs in grouping columns with a placeholder to avoid losing data in the groupby
        df[group_by_cols] = df[group_by_cols].fillna("Missing")

        # If there are sum_columns specified, create the new column before grouping
        if "sum_columns" in config and "new_column_name" in config:
            df[config["new_column_name"]] = df[config["sum_columns"]].sum(axis=1)

        # if there are any columns in group_by_cols that are not in the dataframe, print an error and raise exception
        missing_cols = [col for col in group_by_cols if col not in df.columns]
        if missing_cols:
            raise Exception(
                f"Error: Columns {missing_cols} not found in table '{table_name}' for summary '{summary_name}'."
            )

        # First we need to check a count of the number of groups to distinguish data sampling methods that are charactersised by large plot SampleUnitID vs (SamplePointName, TransectID) and many tiny quadrat SamplingUnitIDs
        num_groups = df.groupby(group_by_cols).ngroups
        print(f"Summary '{summary_name}' has {num_groups} groups.")
        if num_groups > 50:
            print(
                f"Warning: Summary '{summary_name}' has a large number of groups ({num_groups}). This may indicate that the grouping is too granular or that there are many unique sampling units. Consider adjusting the grouping columns or checking for data quality issues."
            )
            # replace SamplingUnitID with [SamplePointName, TransectID] if SamplingUnitID is in group_by_cols and those columns are in the dataframe and print a message about the replacement. This is to address the issue of having too many unique SamplingUnit IDs that may be due to having many small quadrats, which can make it difficult to identify
            if (
                "SamplingUnitID" in group_by_cols
                and "SamplePointName" in df.columns
                and "TransectID" in df.columns
            ):
                print(
                    f"Replacing 'SamplingUnitID' with ['SamplePointName', 'TransectID'] in grouping for summary '{summary_name}' to reduce the number of groups and better reflect the sampling design."
                )
                group_by_cols = [
                    col for col in group_by_cols if col != "SamplingUnitID"
                ] + ["SamplePointName", "TransectID"]
                #Check summary functions. if sum in summary functions for any column  we need to replace with min and max
                # this is because if we have many unique SamplingUnitIDs that are being summed together, we want to check the range of values for the new column to identify any potential data quality issues (e.g. if the sum is much higher than expected, it may indicate that there are many small quadrats with non-zero values that are being summed together, which could be a data quality issue or it could be a valid property of the data). By replacing the sum with min and max, we can check the range of values for the new column and identify any potential outliers or data quality issues.
                for col in list(summary_funcs.keys()):
                    if summary_funcs[col] == "sum":
                        summary_funcs[col] = ["min", "max"]


        # Group by specified columns and apply summary functions
        summary_df = df.groupby(group_by_cols).agg(summary_funcs).reset_index()

        # rename any summary_func columns to include the function name (e.g. SampleDate_nunique, SampleDate_count) to avoid confusion if there are multiple summary functions applied to the same column
        # Flatten MultiIndex columns if they exist (happens when multiple summary functions are used)
        
        if isinstance(summary_df.columns, pd.MultiIndex):
            summary_df.columns = [
                f"{col[0]}\n{'records' if col[1] == 'count' else col[1]}" if col[1] else col[0]
                for col in summary_df.columns
            ]
        else:
            # Handle single level columns (renaming based on the single function applied)
            # This logic assumes a simple mapping where we want to append the function name
            # rename count to records to make clearer
            summary_df.columns = [
                (
                    f"{col}\n{'records' if func == 'count' else func}"
                    if col in summary_funcs
                    and isinstance(func, str)
                    and func != "first"
                    else col
                )
                for col, func in zip(
                    summary_df.columns,
                    [summary_funcs.get(c, "") for c in summary_df.columns],
                )
            ]

        # Post-process "unique" columns to format lists as strings, removing NaNs
        for col in summary_df.columns:
            if str(col).endswith("\nunique"):
                summary_df[col] = summary_df[col].apply(
                    lambda x: "; ".join(sorted([str(v) for v in x if pd.notna(v) and str(v) != ''])) if hasattr(x, '__iter__') and not isinstance(x, (str, bytes)) else x
                )

        # Initialize QA Check column
        

        for col, funcs in summary_funcs.items():
            if isinstance(funcs, str):
                funcs = [funcs]

            # Map functions to column names in the flattened dataframe
            col_map = {}
            for func in funcs:
                target_func = "records" if func == "count" else func
                target_col = f"{col}\n{target_func}"
                if target_col in summary_df.columns:
                    col_map[func] = target_col
                elif col in summary_df.columns:
                    col_map[func] = col

            # Apply QA Checks
            # if sum, max, min in summary functions for a column that includes "cover" in the name, we want to check that the values are within a valid range (e.g. 0-100% for percent cover data) and flag any values that are outside of this range as potential data quality issues. This is because if we have many unique SamplingUnitIDs that are being summed together, we want to check the range of values for the new column to identify any potential data quality issues (e.g. if the sum is much higher than expected, it may indicate that there are many small quadrats with non-zero values that are being summed together, which could be a data quality issue or it could be a valid property of the data). By checking the range of values for the new column, we can identify any potential outliers or data quality issues.
            
            func_map = col_map.get("sum", col_map.get("max",col_map.get("min")))
            if func_map is not None and col.lower().endswith("cover"):
                # Extract function name from column name
                for f in ["sum", "max", "min"]:
                    if f in func_map:
                        func = f.split("\n")[-1]  # Get the function name from the column name  
                        break
                

                #explicit check mark for valid range
                qa_check_col = "QA Check\nrange check\n0-100% +1"
                summary_df[qa_check_col] = ""
                summary_df.loc[(summary_df[func_map] >= 0) & (summary_df[func_map] <= 101.0), qa_check_col] = "\u2713"
                summary_df.loc[summary_df[func_map] > 101.0, qa_check_col] = f"{col}_{func} > 101%"
                summary_df.loc[summary_df[func_map].isnull(), qa_check_col] = (
                    f"{col}_{func} missing"
                )
                #swap to the min if its in the 
                if func == "max" and "min" in col_map:
                    func = "min"
                summary_df.loc[summary_df[func_map] < 0, qa_check_col] = f"{col}_{func} negative"
                
            if "count" in col_map and "nunique" in col_map:
                func_map = col_map["count"]
                nunique_func_map = col_map["nunique"]
                if pd.api.types.is_numeric_dtype(summary_df[func_map]):
                    qa_check_col = "QA Check\nequality\nunique = count"
                    # Initialize the column to prevent ValueError if the first assignment is to an empty slice
                    summary_df[qa_check_col] = ""
                    summary_df.loc[summary_df[func_map] != summary_df[nunique_func_map], qa_check_col] = "mismatched"
                    #explicit check mark for valid range
                    summary_df.loc[summary_df[func_map] == summary_df[nunique_func_map], qa_check_col] = "\u2713"
                

            if "max" in col_map and not col.lower().endswith("cover"):
                func_map = col_map["max"]
                if pd.api.types.is_numeric_dtype(summary_df[func_map]):
                    qa_check_col = "QA Check\nmax > 0"
                    summary_df[qa_check_col] = ""   
                    summary_df.loc[summary_df[func_map] == 0, qa_check_col] = f"{func_map} is 0"
                    #explicit check mark for valid range
                    summary_df.loc[summary_df[func_map] > 0, qa_check_col] = "\u2713"
                
                    #mark rows where max is nan values in the max column as potential data quality issues, since if all values for that group were missing, the max would be nan, which could indicate a data quality issue or it could be a valid property of the data. By flagging these as potential data quality issues, we can review them and determine if they are valid or if there may be an issue with the data.
                    summary_df.loc[summary_df[func_map].isnull(), qa_check_col] = f"missing"

            
            #find any columns in summary_funcs.items() that are also in group_by_cols and check that the count of those columns is equal to the count of QuadratPlotID for the same group_by. This is to check for any potential data quality issues where there may be multiple records for some sampling units that have soil moisture data, which could indicate a data quality issue or it could be a valid property of the data. By checking for values greater than the count of QuadratPlotID, we can identify any potential outliers or data quality issues.
            
            if "SoilMoisture" in col and "QuadratPlotID" in summary_funcs:
                #should be equal to the count of QuadratPlotID for the same group_by (which should be the number of records that have soil moisture data), if there are more records than that, it may indicate that there are multiple soil moisture records for some sampling units, which could be a data quality issue or it could be a valid property of the data. By checking for values greater than the count of QuadratPlotID, we can identify any potential outliers or data quality issues.
                func_map = col_map["count"]
                qa_check_col = "QA Check\nSoilMoisture count\nvs QuadratPlotID count"
                summary_df[qa_check_col] = ""
                summary_df.loc[summary_df[func_map] != summary_df["QuadratPlotID\ncount"], qa_check_col] = f"{col} missing for QuadratPlotID"
                #explicit check mark for valid range
                summary_df.loc[summary_df[func_map] == summary_df["QuadratPlotID\ncount"], qa_check_col] = "\u2713"
                
            if "Count" in col and "Count" in summary_funcs and "sum" in summary_funcs["Count"]:
                qa_outliers("sum", col, summary_df, col_map)
            if "ScientificName" in col and "ScientificName" in summary_funcs and "nunique" in summary_funcs["ScientificName"]:
                qa_outliers("nunique", col, summary_df, col_map)
                
            if "count" in col_map:
                qa_outliers("count", col, summary_df, col_map)
            if "sum" in col_map:
                qa_outliers("sum", col, summary_df, col_map)
            if "Date" in col:
                if "count" in col_map:
                    # func_map = col_map["count"]
                    # mode = summary_df[func_map].mode()
                    # if not mode.empty:
                    #     mode_val = mode.iloc[0]
                    #     qa_check_col = "QA Check\nmode check"
                    #     summary_df[qa_check_col] = ""
                    #     summary_df.loc[summary_df[func_map] > mode_val, qa_check_col] = (
                    #         f"{col} count > mode ({mode_val})"
                    #     )
                    #     summary_df.loc[summary_df[func_map] < mode_val, qa_check_col] = (
                    #         f"{col} count < mode ({mode_val})"
                    #     )
                    #     #explicit check mark for valid range
                    #     summary_df.loc[summary_df[func_map] == mode_val, qa_check_col] = "\u2713"
                    qa_outliers("count", col, summary_df, col_map)

                if "nunique" in col_map:
                    qa_outliers("nunique", col, summary_df, col_map)

        summary_tables[summary_name] = (table_name, summary_df)

    return summary_tables

def qa_outliers(func, col, summary_df, col_map):
    func_map = col_map[func]  # Get the column name corresponding to the function (e.g. "Count\nsum" or "ScientificName\nnunique")
    
    q1 = summary_df[func_map].quantile(0.25)
    q3 = summary_df[func_map].quantile(0.75)
    iqr = q3 - q1

    if pd.notna(iqr):
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        func = "records" if func == "count" else func   
        if pd.api.types.is_integer_dtype(summary_df[func_map]):
            qa_check_col = f"QA Check\n{col}_{func}\noutliers IQR\n[{lower_bound:.1f}, {upper_bound:.1f}]"
        else:
            qa_check_col = f"QA Check\n{col}_{func}\noutliers IQR\n[{lower_bound:.2f}, {upper_bound:.2f}]"

        summary_df[qa_check_col] = ""
        summary_df.loc[summary_df[func_map] > upper_bound, qa_check_col] = (
                            f"high {col}_{func}"
                        )
        summary_df.loc[summary_df[func_map] < lower_bound, qa_check_col] = (
                            f"low {col}_{func}"
                        )
                        #explicit check mark for valid range
        summary_df.loc[(summary_df[func_map] >= lower_bound) & (summary_df[func_map] <= upper_bound), qa_check_col] = "\u2713"

def create_markdown_report(data_summaries, plot_collection, output_path, group_name, input_filename, report_title_str, plot_definitions, data_summary_definitions):
        # now create a report (e.g. markdown or HTML) that includes the summary tables and plots. This will be a template that can be adjusted based on the specific requirements of the report (e.g. which summaries and plots to include, formatting, etc.). The report should be saved in the output_path.
    # For simplicity, we will create a markdown report to review that includes links to the summary tables and plots.
    report_content = f"# QA Report for {input_filename}\n\n"

    # Add summary tables to the report
    report_content += "## Summary Tables\n\n"
    for summary_name, (table_name, summary_df) in data_summaries.items():
        report_content += f"### {summary_name}\n\n"
        if summary_name in data_summary_definitions and "note" in data_summary_definitions[summary_name]:
            report_content += f"{data_summary_definitions[summary_name]['note']}\n\n"
        if summary_df.empty:
            report_content += "No data available for this summary.\n\n"
            continue
        report_content += f"Source Table: `{table_name}`\n\n"
        # Convert DataFrame to Markdown table
        headers = [str(c) for c in summary_df.columns]
        report_content += "| " + " | ".join(headers) + " |\n"
        report_content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for _, row in summary_df.iterrows():
            row_vals = [
                str(x).replace("|", "\|").replace("\n", "<br>") for x in row.values
            ]
            report_content += "| " + " | ".join(row_vals) + " |\n"
            summary_name = make_safe(summary_name)
        report_content += f"\n[Download CSV](b_{summary_name}.csv)\n\n"

    # Add plots to the report
    if plot_collection:
        for plot_series_name in plot_collection:
            report_content += f"## Plots of {plot_series_name}\n\n"
            if plot_series_name in plot_definitions and "note" in plot_definitions[plot_series_name]:
                report_content += f"{plot_definitions[plot_series_name]['note']}\n\n"

            if plot_collection[plot_series_name] is None:
                report_content += "No plots were generated for this series.\n\n"
                continue
            for plot_filename in plot_collection[plot_series_name]:
                plot_title = Path(plot_filename).stem.replace("_", " ").title()
                report_content += (
                    f"### {plot_title}\n\n![{plot_title}]({plot_filename})\n\n"
                )

    # Save the markdown report
    report_path = output_path / make_safe(f"{group_name}_{report_title_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"QA Report saved to {report_path}")

def create_pdf_report(data_summaries, plot_collection, output_path, group_name, input_filename, report_title_str, start_dt, end_dt, plot_definitions, data_summary_definitions):
    # Generate a PDF report using ReportLab that includes the summary tables and plots. This will be a more formal report that can be shared with stakeholders. The PDF report should be saved in the output_path.
    # For simplicity, we will create a PDF report that includes the same content as the markdown report, but formatted for PDF. This will include the summary tables and plots, with appropriate formatting and layout for a PDF document. We will use the ReportLab library to create the PDF report.
    # No cover page, just a title and then the content with an introductory paragraph. We will include the summary tables as images (e.g. using matplotlib to create a table plot) and the plots as they are. The report should be saved in the output_path with a filename like "qa_report.pdf".
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Image,
        Table,
        TableStyle,
        CondPageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER

    pdf_report_path = output_path / make_safe(f"{group_name}_{report_title_str}.pdf")
    doc = SimpleDocTemplate(str(pdf_report_path), pagesize=A4,rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Centered', alignment=TA_CENTER))
    h1 = styles['Heading1']
    h1.spaceBefore = 20
    title_style = styles["Title"]
    title_style.spaceBefore = 10
    title_style.spaceAfter = 10
    # Re-define styles using built in names but with specific font settings to ensure compatibility across different environments without relying on external font files.
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=9,
    )
    bold_style = ParagraphStyle(
        'Bold',
        parent=styles['Normal'],
        fontName="Helvetica-Bold", # Use the specific font name
        fontSize=9,
    )
 
    
    elements = []
    #add banner as header on the first page only above the title. We will use the CEWH crest and FLOW-MER logo from the project folder as the banner. The banner should be scaled to fit the width of the page and maintain its aspect ratio.
    elements.append(Image("resources//CEWH crest and FLOW-MER-inline_CMYK.png", width=13.0*cm, height=2.5*cm, kind="proportional", hAlign="CENTER"))
    elements.append(Spacer(1, 9))
    # Title
    title = Paragraph(f"{group_name} {report_title_str}", title_style)
    elements.append(title)
      #get year from start_date
    start_year = start_dt.year
    end_year = end_dt.year

    elements.append(Paragraph(f"{start_year}/{end_year} water-year.", styles["Centered"]))
    elements.append(Spacer(1, 9))
    elements.append(Paragraph(f"Data from: {input_filename}", styles["Italic"]))
    elements.append(Spacer(1, 9))
    # Introductory paragraph
    intro = Paragraph(
        "This report reflects your data back to you in summaries that are intended to help you "
        "identify data quality issues including missing values, inconsistent sampling effort "
        "and/or outliers.  QA Checks in the summary tables indicate issues for you to investigate, "
        "noting that these may reflect valid properties of the data (e.g. multi-layered vegetation "
        "can have > 100% cover).",
        normal_style,
    )
    elements.append(intro)
    elements.append(Spacer(1, 9))
    action = Paragraph(
        "ACTION REQUIRED: Confirm via email that this data summary has been reviewed and found to be a complete and an accurate representation of the data you provided. "
        "Email to confirm any data quality issues and upload your corrections to the MDMS as soon as possible.",
        bold_style
    )
    elements.append(action)
    elements.append(Spacer(1, 9))
    contact = Paragraph(
        "If you have any questions about how to interpret the summaries or plots, or feedback to improve the process, please reach out to discuss.",
        normal_style,
    )
    elements.append(contact)
    elements.append(Paragraph("Glossary", styles["Heading2"]))
 
    glossary_data = [
        [Paragraph('nunique:', bold_style), 
         Paragraph('Count of unique values for a column (e.g. number of unique species, number of unique sampling units, etc.)', normal_style)],
        [Paragraph('Outliers IQR:', bold_style), 
         Paragraph('Uses the Inter-Quartile Range (distance between 25th and 75th percentiles) to identify outliers. Values more than 1.5 IQR below the 25th percentile or above the 75th percentile are flagged for review.', normal_style)],
        [Paragraph('range check 0-100% +1:', bold_style),
         Paragraph('Checks that percent cover values are within a valid range (0-100%) allowing an extra 1% margin for rounding errors. Values greater than 101% are flagged for review, as well as any missing values.', normal_style)],
        [Paragraph('missmatched:', bold_style),
         Paragraph('Count of records in one column that does not match another column (e.g. count of samples vs count of unique SamplingUnitsIDs.  Flagged for review but can be a valid outcome of the sampling design.', normal_style)],
        [Paragraph('records', bold_style), 
         Paragraph('records is a count of the number of data records in the column.  Some, many or all of those records may be a Species Count of 0 (zero) therefore you can have a higher than expected count when comparing to the to the sum.', normal_style)],
        [Paragraph('NaN:', bold_style),
         Paragraph('Not a Number (i.e. missing value).  Flagged for review.', normal_style)],
    ]
    glossary_table = Table(glossary_data, colWidths=[3*cm, None])
    glossary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        
    ]))
    elements.append(glossary_table)
    elements.append(
        Paragraph(f"Review Tabular Summaries", h1)
    )
    elements.append(Spacer(1, 9))
    # Add summary tables to the PDF report
    for summary_name, (table_name, summary_df) in data_summaries.items():
        elements.append(CondPageBreak(8*cm))
        elements.append(Paragraph(f"{summary_name}", styles["Heading2"]))
        if summary_name in data_summary_definitions and "note" in data_summary_definitions[summary_name]:
            elements.append(Paragraph(data_summary_definitions[summary_name]["note"], normal_style))
            elements.append(Spacer(1, 6))

        if summary_df.empty:
            elements.append(Paragraph("      No data available for this summary.", styles["Italic"]))
            continue
        
        
        elements.append(Paragraph(f"Source Table: {table_name}", styles["Italic"]))
        elements.append(Spacer(1, 6))
        # Convert DataFrame to ReportLab Table, rounding numeric values to 4 decimal places for better readability. We will also add some styling to the table to make it more readable in the PDF report (e.g. alternating row colors, bold headers, grid lines, etc.).
        #need to handle integer and string columns separately to avoid rounding non-numeric values. We will round only the numeric columns to 2 decimal places and leave the non-numeric columns as they are.
        numeric_cols = summary_df.select_dtypes(include=["number"]).columns
        summary_df[numeric_cols] = summary_df[numeric_cols].round(4)
        data = [summary_df.columns.tolist()] + summary_df.astype(str).values.tolist()
        t = Table(data)
        t.setStyle(
            TableStyle(
                [
                    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.whitesmoke]),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightslategrey),
                    # padding of 0 points for all cells (default is 5)
                    ("TOPPADDING", (0, 0), (-1, -1), 1,),  
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 9))

    #force new page if vertical position is less than 100mm from the bottom of the page to avoid cutting off plots. We will check the vertical position of the elements list and if it is less than 100mm from the bottom of the page, we will add a page break before adding the next plot.
    elements.append(CondPageBreak(10*cm))
            
    # Add plots to the PDF report
    elements.append(Spacer(1, 9))
    elements.append(
        Paragraph(f"Review Graphical Summaries", h1)
    )
    
    
    if plot_collection:
        plot_instructions = Paragraph(  
            "Look for any unusual patterns in the plots, including abnormally dominant taxa, unexpected species composition, outliers, or missing data for certain sampling units or dates.",
            styles["Normal"],
        )
        elements.append(plot_instructions)
        elements.append(Spacer(1, 9))
        for plot_series_name in plot_collection:
            elements.append(CondPageBreak(10*cm))
            elements.append(
                Paragraph(f"{plot_series_name}", styles["Heading2"])
            )
            if plot_series_name in plot_definitions and "note" in plot_definitions[plot_series_name]:
                elements.append(Paragraph(plot_definitions[plot_series_name]["note"], styles["Normal"]))
                elements.append(Spacer(1, 6))

            plot_files = plot_collection[plot_series_name]
            if not plot_files:
                elements.append(Paragraph(f"No plots for this {plot_series_name}.", styles["Italic"]))
                continue

            # Determine number of columns for the plot grid (1, 2, or 3)
            num_plots = len(plot_files)
            if num_plots == 1:
                num_cols = 1
            elif num_plots <= 4:  # 2x2 grid is nice for 2-4 plots
                num_cols = 2
            else:
                num_cols = 3

            # Create Image flowables, scaling them to fit the column width
            col_width = doc.width / num_cols
            images = [
                Image(output_path / f, width=col_width * 0.95, height=col_width * 0.75, kind="proportional")
                for f in plot_files
            ]

            # Chunk the list of images into rows for the table
            table_data = []
            for i in range(0, len(images), num_cols):
                table_data.append(images[i : i + num_cols])

            if table_data:
                # Create a ReportLab Table to arrange the images in a grid
                image_table = Table(table_data, colWidths=[col_width] * num_cols)
                image_table.setStyle(
                    TableStyle(
                        [("VALIGN", (0, 0), (-1, -1), "TOP"),
                         ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]
                    )
                )
                elements.append(image_table)

            elements.append(Spacer(1, 9))

    # Build the PDF document
    doc.build(elements)
    print(f"PDF QA Report saved to {pdf_report_path}")


def main():
    try:
        # The factory function in config.py determines the correct config class
        # based on the default input_file or one passed as a kwarg.
        config = get_config(input_file=input_file, testing_group_name=testing_group_name)
    except ValueError as e:
        print(e)
        return

    output_path = Path(__file__).parent / "Outputs"
    ensure_path_exists(output_path)


    workbook_data = load_data(
        config.workbooks_path / config.input_file,
        config.group_name_source_sheet,
        config.workbook,
        config.testing_group_name,
        config.filter_by_date,
        config.start_date,
        config.end_date
    )
    if not workbook_data:
        print("No data loaded. Please check the input file and configuration.")
        return
    

    for group_name in workbook_data:
        dfs = workbook_data[group_name]
        # Join tables based on the defined joins_required
        joined_dfs = join_tables_generic(dfs, config.joins_required)

        # Generate data summaries based on the defined DATA_SUMMARIES
        data_summaries = generate_effort_summaries(joined_dfs, config.data_summary_definitions)
        plot_collection = create_plots(joined_dfs, data_summaries, config.plot_definitions, output_path)


        if config.create_markdown_report:
            # Save data summary tables
            for summary_name, (_, summary_df) in data_summaries.items():
                output_csv = output_path / f"b_{make_safe(summary_name)}.csv"
                summary_df.to_csv(output_csv, index=False)
                print(f"Data summary table '{summary_name}' saved to {output_csv}")
            create_markdown_report(
                data_summaries,
                plot_collection,
                output_path,
                group_name,
                config.input_file,
                config.report_title,
                config.plot_definitions,
                config.data_summary_definitions
            )

        create_pdf_report(
            data_summaries,
            plot_collection,
            output_path,
            group_name,
            config.input_file,
            config.report_title,
            config.start_date,
            config.end_date,
            config.plot_definitions,
            config.data_summary_definitions
        )
        
        if not config.create_markdown_report:
            delete_existing_plots(output_path)

if __name__ == "__main__":
    main()
