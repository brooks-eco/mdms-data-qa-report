from itertools import count
from shlex import join
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_datetime64_any_dtype
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path
from config import get_config
from pdf_qa_report import PDFQAReport
from md_qa_report import MarkdownQAReport
import datetime

# base configuration in configs\config.base.py
# workbooks exported from the MDMS go in a folder called "workbooks"
# individual reports are configured in the configs folder


def ensure_path_exists(directory):
    """
    Ensures that the specified directory exists, creating it if necessary.
    """
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)

def make_safe(filename):
    """
    Sanitizes a string to be safe for use as a filename by replacing potentially problematic characters.
    """
    return filename.replace(" ", "_").replace("'", "").replace(":", "").replace("/", "-")


def load_data(filepath, group_name_source, workbook_def, testing_group, filter_date, start, end):
    """
    Loads data from an Excel workbook, filtering by group and date if specified.

    Args:
        filepath (Path): Path to the Excel file.
        group_name_source (str): Sheet name to check for 'GroupName' to determine relevant groups.
        workbook_def (list): A list of sheet names to load from the workbook.
        testing_group (str): Specific group name to filter for (optional).
        filter_date (bool): Whether to filter data by date.
        start (datetime): Start date for filtering.
        end (datetime): End date for filtering.

    Returns:
        dict: A dictionary where keys are group names and values are dictionaries of DataFrames for that group.
    """
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
    for sheet_name in workbook_def:
        if sheet_name in xls.sheet_names:
            print(f"Reading sheet: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name)
            # Clean column names (strip whitespace) to prevent mismatch errors
            #df.columns = df.columns.astype(str).str.strip()
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
    """
    Joins tables based on the configuration provided in `joins_required`.

    Args:
        dfs (dict): Dictionary of DataFrames loaded from the workbook.
        joins_required (dict): Configuration dictionary specifying left/right tables, join columns, and join type.

    Returns:
        dict: A dictionary containing the joined DataFrames, plus any original DataFrames that weren't involved in a join.
    """
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
    """
    Filters a DataFrame based on a dictionary of conditions.

    Args:
        filter (dict): Dictionary where keys are column names and values are conditions (e.g., "is not null", {">": 5}).
        df (pd.DataFrame): The DataFrame to filter.
        task_type (str): Description of the task (e.g., "plot", "summary") for logging.
        task_name (str): Name of the specific task for logging.

    Returns:
        pd.DataFrame: The filtered DataFrame.
    """
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
                    f"Warning: Unsupported filter condition '{filter_condition}' for column '{filter_col}' in {task_type} definition '{task_name}'. Skipping this filter."
                )
        else:
            print(
                f"Warning: Filter column '{filter_col}' not found in table. Skipping this filter."
            )
    return df


def create_single_pie_plot(ax, df, label_col, value_col, title_str, color_map=None):
    """
    Generates a single pie chart on the provided axes.

    Args:
        ax (matplotlib.axes.Axes): The axes to draw the plot on.
        df (pd.DataFrame): The data for the plot.
        label_col (str): Column name for the pie slice labels.
        value_col (str): Column name for the pie slice values.
        title_str (str): Title for the plot.
        color_map (dict): Optional dictionary mapping labels to colors.
    """
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

    # Determine colors before mutating labels for display
    pie_colors = None
    if color_map:
        labels_raw = plot_data[label_col].fillna("missing/not provided").astype(str)
        pie_colors = [color_map.get(lbl, "#808080") for lbl in labels_raw]

    # word break category labels by replacing the " " character with \n
    plot_data[label_col] = plot_data[label_col].fillna("missing/not provided").astype(str).str.replace(" ", "\n")

    if not plot_data.empty:
        ax.pie(
            plot_data[value_col],
            labels=plot_data[label_col],
            autopct="%1.1f%%",
            colors=pie_colors,
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


def create_single_scatter_plot(
    ax, df, x_col, y_col, color_col, title_str, show_legend=True, wrap_legend=False,color_map=None
):
    """
    Generates a single scatter plot on the provided axes.

    Args:
        ax (matplotlib.axes.Axes): The axes to draw the plot on.
        df (pd.DataFrame): The data for the plot.
        x_col (str): Column name for the x-axis.
        y_col (str): Column name for the y-axis.
        color_col (str): Column name for categorical coloring (optional).
        title_str (str): Title for the plot.
        show_legend (bool): Whether to display the legend.
        color_map (dict): Optional dictionary mapping categories to colors.
    """
    if color_col and color_col in df.columns:
        # Simple categorical coloring

        categories = df[color_col].dropna().unique()

        if not color_map:
            # Get default color cycle if no map provided
            prop_cycle = plt.rcParams["axes.prop_cycle"]
            colors = prop_cycle.by_key()["color"]

        for i, cat in enumerate(categories):
            subset = df[df[color_col] == cat]
            if color_map:
                color = color_map.get(str(cat), "#808080")
            else:
                color = colors[i % len(colors)]
            ax.scatter(subset[x_col], subset[y_col], label=str(cat), color=color, alpha=0.8)

        # Add legend
        if show_legend:
            #wrap long legend items on " " and "_" by replacing with  \n
            legend_items = [l.replace(" ", "\n").replace("_", "\n") for l in categories] if wrap_legend else categories
            ax.legend(legend_items, title=color_col, bbox_to_anchor=(1.05, 1), loc='upper left')

            #ax.legend(title=color_col, bbox_to_anchor=(1.05, 1), loc='upper left')
    else:
        ax.scatter(df[x_col], df[y_col], alpha=0.8)

    # Set labels and title
    # trim long x and y labels > 30 characters
    # x_col = x_col[:30]
    # y_col = y_col[:30]

    # Format x-axis dates if needed
    if pd.api.types.is_datetime64_any_dtype(df[x_col]):
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(title_str)
    ax.grid(True, linestyle='--', alpha=0.7)


def delete_existing_plots(output_path):
    """
    Deletes existing .png plot files in the output directory to prevent confusion with new plots from the current run.
    """
    if output_path.exists() and output_path.is_dir():
        # delete all plots in the output folder before creating new ones to avoid confusion and ensure we are only looking at the plots from the current run. We will only delete files that match the .png extension to avoid accidentally deleting other files in the output folder.
        for filename in output_path.iterdir():
            if filename.suffix == ".png":
                try:
                    filename.unlink() 
                except Exception as e:
                    print(f"Error deleting file {filename}: {e}")
                    continue


def get_global_color_map(df, column_name):
    if not column_name or column_name not in df.columns:
        return None
    unique_vals = sorted(df[column_name].dropna().unique().astype(str))
    # Use tab20 for better distinction than default tab10
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % 20) for i in range(len(unique_vals))]
    return dict(zip(unique_vals, colors))


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

        # Generate global color map for consistency across groups
        color_map = None
        if plot_type == "pie":
            color_map = get_global_color_map(df, config.get("category"))
        elif plot_type == "scatter":
            color_map = get_global_color_map(df, config.get("color"))

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
            fig_size=(4, 3) if len(groups) > 4 else (6,4)
            fig, ax = plt.subplots(figsize=fig_size)

            # Title logic
            group_key_tuple = group_key if isinstance(group_key, tuple) else (group_key,)

            # Check if all group_by columns are numeric to decide on title format
            all_numeric_groups = all(is_numeric_dtype(df[col]) for col in group_by_cols) if group_by_cols else False

            if all_numeric_groups and group_by_cols:
                title_parts = [f"{col}: {val}" for col, val in zip(group_by_cols, group_key_tuple)]
                title_str = " | ".join(title_parts)
            else:
                group_key_tuple = tuple(
                    d.strftime("%Y-%m-%d") if isinstance(d, pd.Timestamp) else d
                    for d in group_key_tuple
                )
                title_str = " | ".join(map(str, group_key_tuple))

            # Dispatch
            if plot_type == "pie":
                create_single_pie_plot(
                    ax,
                    group_df,
                    label_col=config.get("category"),
                    value_col=config.get("value"),
                    title_str=title_str,
                    color_map=color_map,
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

                is_x_numeric = is_numeric_dtype(plot_df[x_col])
                is_y_numeric = is_numeric_dtype(plot_df[y_col])
                is_x_datetime = is_datetime64_any_dtype(plot_df[x_col])
                is_y_datetime = is_datetime64_any_dtype(plot_df[y_col])
   

                # Aggregation logic: Aggregate if specified in config
                agg_func = config.get("aggregate_function")
                if agg_func:
                    if is_x_numeric and not is_y_numeric:
                        agg_cols = [y_col]
                        if color_col and color_col in plot_df.columns and color_col != y_col:
                            agg_cols.append(color_col)
                        plot_df = plot_df.groupby(agg_cols, as_index=False)[x_col].agg(agg_func)

                    elif is_y_numeric and not is_x_numeric:
                        agg_cols = [x_col]
                        if color_col and color_col in plot_df.columns and color_col != x_col:
                            agg_cols.append(color_col)
                        plot_df = plot_df.groupby(agg_cols, as_index=False)[y_col].agg(agg_func)

                # Trim long species/site names and Sort
                if not is_x_numeric and not is_x_datetime:
                    plot_df[x_col] = plot_df[x_col].astype(str).str[:25]
                    if is_y_numeric:
                        plot_df = plot_df.sort_values(by=y_col, ascending=True).tail(15)
                    else:
                        plot_df = plot_df.sort_values(by=x_col, ascending=True)

                if not is_y_numeric and not is_y_datetime:
                    plot_df[y_col] = plot_df[y_col].astype(str).str[:25]
                    if is_x_numeric:
                        plot_df = plot_df.sort_values(by=x_col, ascending=True).tail(15)
                    elif is_x_datetime:
                        plot_df = plot_df.sort_values(by=y_col, ascending=True)
                    else:
                        plot_df = plot_df.sort_values(by=y_col, ascending=True)

                create_single_scatter_plot(
                    ax,
                    plot_df,
                    x_col=x_col,
                    y_col=y_col,
                    color_col=color_col,
                    title_str=title_str,
                    show_legend=config.get("Legend", True),
                    wrap_legend = len(groups) > 4,
                    color_map=color_map,
                )

            plt.tight_layout()

            # Filename logic
            safe_plot_name = make_safe(plot_series_name)
            sanitized_key_parts = [make_safe(str(p)) for p in group_key_tuple]
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
    """
    Generates summary tables based on the provided configuration.

    Args:
        joined_dfs (dict): Dictionary of joined DataFrames.
        summaries_config (dict): Configuration for the summaries to be generated.

    Returns:
        dict: A dictionary where keys are summary names and values are tuples of (source_table_name, summary_DataFrame).
    """
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
        col_map = {}
        # This loop is to build the map from the generated column name back to the original function.
        for original_col, funcs in summary_funcs.items():
            if isinstance(funcs, str):
                funcs = [funcs]

            for func in funcs:
                if func == 'first':
                    # 'first' does not rename the column
                    if original_col in summary_df.columns:
                        col_map[original_col] = func
                else:
                    target_func_display = "records" if func == "count" else func
                    generated_col_name = f"{original_col}\n{target_func_display}"
                    if generated_col_name in summary_df.columns:
                        col_map[generated_col_name] = func

        # make a list of all columns that have a function of "count"
        count_cols = [col for col, func in col_map.items() if func == "count"]
        first_count_col = count_cols[0] if count_cols else None
        try:
            count_cols.remove(first_count_col)
        except (ValueError,TypeError):
            pass

        
            




        # Apply QA Checks
        for col, func in col_map.items():
            # Extract original col name from column name
            col_name = col.split("\n")[0]
           
            #cover percentages
            if func in ["sum", "max", "min"] and "cover\n" in col.lower():

                #explicit check mark for valid range
                qa_check_col = "QA Check\nrange check\n0-100% +1"
                summary_df[qa_check_col] = ""
                summary_df.loc[(summary_df[col] >= 0) & (summary_df[col] <= 101.0), qa_check_col] = "\u2713"
                summary_df.loc[summary_df[col] < 0, qa_check_col] = f"{col_name}_{func} negative"
                summary_df.loc[summary_df[col] > 101.0, qa_check_col] = f"{col_name}_{func} > 101%"
                summary_df.loc[summary_df[col].isnull(), qa_check_col] = (
                    f"{col_name}_{func} missing"
                )
                if func == "max":
                    summary_df.loc[summary_df[col] == 0, qa_check_col] = f"{col_name}_{func} is 0"
                    
            #Date Range > 7 days
            min_col_name = f"{col_name}\nmin"
            if func == "max" and "Date" in col and min_col_name in summary_df.columns:
                if pd.api.types.is_datetime64_any_dtype(summary_df[col]):
                    qa_check_col = "QA Check\ndate range\n> 7d"
                    # Initialize the column to prevent ValueError if the first assignment is to an empty slice
                    summary_df[qa_check_col] = ""
                    duration = summary_df[col] - summary_df[min_col_name]
                    mask = duration > pd.Timedelta(days=7)
                    summary_df.loc[mask, qa_check_col] = "long survey (" + duration[mask].dt.days.astype(str) + " days)"
                    #explicit check mark for valid range
                    summary_df.loc[duration <= pd.Timedelta(days=7), qa_check_col] = "\u2713"
                 
            nunique_col_name = f"{col_name}\nnunique"
            if func == "count" and nunique_col_name in summary_df.columns:
                if pd.api.types.is_numeric_dtype(summary_df[col]):
                    qa_check_col = f"QA Check\n{nunique_col_name} = {col}"
                    # Initialize the column to prevent ValueError if the first assignment is to an empty slice
                    summary_df[qa_check_col] = ""
                    summary_df.loc[summary_df[col] != summary_df[nunique_col_name], qa_check_col] = "mismatched"
                    #explicit check mark for valid range
                    summary_df.loc[summary_df[col].notna() & (summary_df[col] == summary_df[nunique_col_name]), qa_check_col] = "\u2713"
                    
            if func == "count" and col in count_cols:
                qa_check_col = f"QA Check\n{col} = {first_count_col}"
                summary_df[qa_check_col] = ""
                summary_df.loc[summary_df[col] != summary_df[first_count_col], qa_check_col] = "mismatched"
                summary_df.loc[summary_df[col].notna() & (summary_df[col] == summary_df[first_count_col]), qa_check_col] = "\u2713"

            
            #find any columns in summary_funcs.items() that are also in group_by_cols and check that the count of those columns is equal to the count of QuadratPlotID for the same group_by. This is to check for any potential data quality issues where there may be multiple records for some sampling units that have soil moisture data, which could indicate a data quality issue or it could be a valid property of the data. By checking for values greater than the count of QuadratPlotID, we can identify any potential outliers or data quality issues.
            
            #soilmoisture missing from quadrat
            plot_id_count_col = "QuadratPlotID\nrecords"
            if func == "count" and "SoilMoisture" in col and plot_id_count_col in summary_df.columns:
                #should be equal to the count of QuadratPlotID for the same group_by (which should be the number of records that have soil moisture data), if there are more records than that, it may indicate that there are multiple soil moisture records for some sampling units, which could be a data quality issue or it could be a valid property of the data. By checking for values greater than the count of QuadratPlotID, we can identify any potential outliers or data quality issues.
                qa_check_col = "QA Check\nSoilMoisture count\nvs QuadratPlotID count"
                summary_df[qa_check_col] = ""
                summary_df.loc[summary_df[col] != summary_df[plot_id_count_col], qa_check_col] = f"{col_name} missing for QuadratPlotID"
                #explicit check mark for valid range
                summary_df.loc[summary_df[col].notna() & (summary_df[col] == summary_df[plot_id_count_col]), qa_check_col] = "\u2713"
                
            # check if needed if "Count" in col and "Count" in summary_funcs and "sum" in summary_funcs["Count"]:
            #     qa_outliers("sum", col, summary_df, col_map)
            if func == "nunique" and "ScientificName" in col:
                qa_outliers(func, col, summary_df)
            
            #if "count" appears in col_map.items() more than once assume all counts should be the same.  To add QA check, skip over the 1st count column, then for the 2nd, 3rd and subsequent count columns we compare the count to the 1st column and flag any missmatch
            
            
                
            if func == "count":
                qa_outliers(func, col, summary_df)
            if func == "sum":
                qa_outliers(func, col, summary_df)
            if func == "mean":
                qa_outliers(func, col, summary_df)
            if "Date\n" in col:
                if func == "count":
                    # col = col_map["count"]
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
                    qa_outliers(func, col, summary_df)

                if f"{col_name}\nnunique" in summary_df.columns:
                    qa_outliers(func, col, summary_df)

        summary_tables[summary_name] = (table_name, summary_df)

    return summary_tables

def qa_outliers(func, col, summary_df):
    """
    Performs outlier detection using the Interquartile Range (IQR) method and flags outliers in the summary DataFrame.

    Args:
        func (str): The aggregation function used (e.g., "sum", "count", "nunique").
        col (str): The original column name.
        summary_df (pd.DataFrame): The summary DataFrame to modify.
        col_map (dict): Mapping from function names to the actual column names in summary_df.
    """
    
    q1 = summary_df[col].quantile(0.25)
    q3 = summary_df[col].quantile(0.75)
    iqr = q3 - q1

    if pd.notna(iqr):
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
 
        qa_check_col = f"QA Check\n{col}\noutliers IQR\n[{lower_bound:.1f}, {upper_bound:.1f}]"
  

        summary_df[qa_check_col] = ""
        summary_df.loc[summary_df[col] > upper_bound, qa_check_col] = (
                            f"high {col}"
                        )
        summary_df.loc[summary_df[col] < lower_bound, qa_check_col] = (
                            f"low {col}"
                        )
        if func == "count":
            summary_df.loc[summary_df[col].isna() | (summary_df[col] == 0), qa_check_col] = "no data"
            #explicit check mark for valid range only
            summary_df.loc[summary_df[col].notna() & (summary_df[col] > 0) & (summary_df[col] >= lower_bound) & (summary_df[col] <= upper_bound), qa_check_col] = "\u2713"
        else:
            summary_df.loc[summary_df[col].isna(), qa_check_col] = "no data"
            #explicit check mark for valid range only
            summary_df.loc[summary_df[col].notna() & (summary_df[col] >= lower_bound) & (summary_df[col] <= upper_bound), qa_check_col] = "\u2713"
        


def main():
    """
    Main execution function. Loads config, loads data, generates summaries and plots, and creates PDF/Markdown reports.
    """
    try:
        # The factory function in config.py determines the correct config class
        # based on the default input_file or one passed as a kwarg.
        config = get_config()
    except ValueError as e:
        print(e)
        return

    output_path = Path(__file__).parent / config.output_path
    ensure_path_exists(output_path)
    #input_file:str = "waterbirdsurvey_20260220153534.xlsx"
    #decode time-stamp from input_file
    try:
        timestamp_str = config.input_file.split("_")[1].split(".")[0]
        data_date = datetime.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except (IndexError, ValueError):
        data_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    


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
            
            md_report = MarkdownQAReport(output_path, group_name, config.report_title)
            md_report.create_report(
                data_summaries, plot_collection,
                config.input_file,
                config.start_date,
                config.end_date,
                config.plot_definitions,
                config.data_summary_definitions,
                config.group_id[group_name],
                data_date,
                data_url = f"{config.data_url}?group_id={config.group_id[group_name]}",
                left_justify_columns = getattr(config, "left_justify_columns", None),
            )

        pdf_report = PDFQAReport(output_path, group_name, config.report_title)
        pdf_report.create_report(
            data_summaries, plot_collection, config.input_file,
            config.start_date,
            config.end_date,
            config.plot_definitions,
            config.data_summary_definitions,
            config.group_id[group_name],
            data_date,
            data_url = f"{config.data_url}?group_id={config.group_id[group_name]}",
            left_justify_columns = getattr(config, "left_justify_columns", None),
        )
        
        if not config.create_markdown_report:
            delete_existing_plots(output_path)

if __name__ == "__main__":
    main()
