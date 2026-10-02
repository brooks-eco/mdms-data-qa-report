import datetime
import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from mdmsio import MDMSClient

logger = logging.getLogger(__name__)


def _data_timestamp(input_file):
    try:
        timestamp = str(input_file).split("_")[1].split(".")[0]
        return (
            datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
            .replace(tzinfo=datetime.timezone.utc)
            .strftime("%Y-%m-%d %H:%M:%S")
        )
    except (IndexError, ValueError):
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def normalize_dataframe(df, filter_date, start, end, data_name=None):
    """Normalize source-specific columns and optionally restrict rows by date."""
    df = df.copy()
    if "Group" in df.columns and "GroupName" not in df.columns:
        df = df.rename(columns={"Group": "GroupName"})

    string_columns = df.select_dtypes(include=["object", "string"]).columns
    for column in string_columns:
        df[column] = df[column].mask(df[column].eq(""), pd.NA)

    date_col = next(
        (c for c in ("SampleDate", "DateFirstDayOfQuarter", "date") if c in df.columns), None
    )

    if not df.empty and date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        if filter_date:
            date_mask = (df[date_col] >= start) & (df[date_col] <= end)
            if "GroupName" in df.columns:
                for group_name in df["GroupName"].drop_duplicates():
                    group_mask = (
                        df["GroupName"].isna()
                        if pd.isna(group_name)
                        else df["GroupName"].eq(group_name)
                    )
                    group_df = df.loc[group_mask]
                    if not date_mask.loc[group_mask].any():
                        _log_empty_date_filter(
                            group_df,
                            date_col,
                            start,
                            end,
                            data_name=data_name,
                            group_name=group_name,
                        )
            elif not date_mask.any():
                _log_empty_date_filter(df, date_col, start, end, data_name=data_name)

            df = df.loc[date_mask].copy()
        df["Year"] = df[date_col].dt.year
        df["Month"] = df[date_col].dt.month
    return df


def _log_empty_date_filter(df, date_col, start, end, data_name=None, group_name=None):
    """Log when date filtering excludes every row in a dataframe or group."""
    source_start = df[date_col].min()
    source_end = df[date_col].max()
    source_range = (
        f"{source_start:%Y-%m-%d} - {source_end:%Y-%m-%d}"
        if pd.notna(source_start) and pd.notna(source_end)
        else "no valid dates"
    )
    data_context = f" in '{data_name}'" if data_name else ""
    group_context = f" for group '{group_name}'" if pd.notna(group_name) else ""
    logger.warning(
        "Date filter removed all %s rows%s%s: source date range (%s); requested filter (%s - %s).",
        len(df),
        data_context,
        group_context,
        source_range,
        pd.Timestamp(start).strftime("%Y-%m-%d"),
        pd.Timestamp(end).strftime("%Y-%m-%d"),
    )


def join_tables_generic(dfs, joins_required):
    """Join workbook tables according to the theme configuration."""
    joined_dfs = {}

    for join_info in joins_required:
        left_df_name = join_info["left"]
        right_df_name = join_info["right"]
        on_cols = list(dict.fromkeys(join_info["on"]))
        how = join_info["how"]

        if left_df_name not in dfs or right_df_name not in dfs:
            logger.error(
                "Aborting processing because data frames for sheet names '%s' or '%s' were not found.",
                left_df_name,
                right_df_name,
            )
            return None

        left_df = joined_dfs.get(left_df_name, dfs[left_df_name])
        right_df = joined_dfs.get(right_df_name, dfs[right_df_name])
        if (
            "GroupName" in left_df.columns
            and "GroupName" in right_df.columns
            and "GroupName" not in on_cols
        ):
            on_cols.append("GroupName")
        if "summary" in join_info:
            aggregations = {
                output_name: pd.NamedAgg(column=source_name, aggfunc=function)
                for output_name, specification in join_info["summary"].items()
                for source_name, function in specification.items()
            }
            right_df = right_df.groupby(on_cols, dropna=False).agg(**aggregations).reset_index()
        joined_dfs[left_df_name] = pd.merge(left_df, right_df, on=on_cols, how=how)
        if "summary" in join_info:
            for output_name, specification in join_info["summary"].items():
                if "count" in specification.values():
                    joined_dfs[left_df_name][output_name] = (
                        joined_dfs[left_df_name][output_name].fillna(0).astype(int)
                    )
        logger.debug(
            "Using the join-enhanced version of table '%s' for summaries and plots.", left_df_name
        )

    for table_name, dataframe in dfs.items():
        if table_name not in joined_dfs:
            joined_dfs[table_name] = dataframe
            logger.debug(
                "Using the workbook version of table '%s' for summaries and plots.", table_name
            )

    return joined_dfs


def _group_tables(dfs, testing_group):
    groups = set()
    for dataframe in dfs.values():
        if "GroupName" in dataframe.columns:
            groups.update(dataframe["GroupName"].dropna().unique())

    if testing_group is not None:
        requested_groups = {testing_group} if isinstance(testing_group, str) else set(testing_group)
        missing_groups = requested_groups.difference(groups)
        groups = groups.intersection(requested_groups)
        if missing_groups:
            logger.warning(
                "No data for specified test group(s) %s: required %s, found %s",
                missing_groups,
                testing_group,
                groups,
            )
            return None

    if not groups:
        logger.warning("No groups found in loaded data")
        return {"QA": {name: df.copy() for name, df in dfs.items()}}

    grouped_data = {}
    for group_name in groups:
        grouped_data[group_name] = {
            name: (
                df[df["GroupName"] == group_name].copy() if "GroupName" in df.columns else df.copy()
            )
            for name, df in dfs.items()
        }
    return grouped_data


def load_workbook_data(
    filepath,
    group_name,
    filter_date,
    start,
    end,
    joins_required=None,
):
    """Load, normalize, group, and join tables from an Excel workbook."""
    logger.info("Loading data from %s...", filepath)
    try:
        workbook = pd.ExcelFile(filepath)
    except FileNotFoundError:
        logger.error("File '%s' not found.", filepath)
        return {}
    except Exception as error:
        logger.error("Error loading Excel file: %s", error)
        return {}

    tables = {}
    for sheet_name in workbook.sheet_names:
        if sheet_name.lower() == "metadata":
            continue
        logger.debug("Reading sheet: %s", sheet_name)
        dataframe = pd.read_excel(workbook, sheet_name=sheet_name)
        tables[sheet_name] = normalize_dataframe(
            dataframe, filter_date, start, end, data_name=sheet_name
        )

    grouped_data = _group_tables(tables, group_name)
    if not grouped_data or not joins_required:
        return grouped_data

    for group_name, group_tables in grouped_data.items():
        joined_tables = join_tables_generic(group_tables, joins_required)
        if joined_tables is None:
            logger.error("Unable to join workbook tables for group '%s'.", group_name)
            return None
        grouped_data[group_name] = joined_tables
    return grouped_data


def load_mdms_data(group_name, group_id, filter_date, start, end, mdms_reports):
    """Load pre-joined API reports from MDMS and normalize their dataframes."""
    load_dotenv()
    api_key = os.getenv("API_KEY", "")
    tables = {}

    with MDMSClient(api_key) as mdms:
        for report_name, shortcode in mdms_reports.items():
            logger.info("Loading report data for %s from MDMS...", report_name)
            dataframe = mdms.get_report_dataframe(
                shortcode=shortcode,
                group_id=group_id,
                date_start=start,
                date_end=end,
            )
            tables[report_name] = normalize_dataframe(
                dataframe, filter_date, start, end, data_name=report_name
            )

    return _group_tables(tables, group_name)


def load_data(
    filepath,
    group_name,
    group_id,
    filter_date,
    start,
    end,
    mdms_reports,
    joins_required=None,
):
    """Load normalized data through the workbook or MDMS pathway."""
    filepath = Path(filepath)
    if filepath.suffix.startswith(".xls"):
        data_date = _data_timestamp(filepath)
        return load_workbook_data(
            filepath,
            group_name,
            filter_date,
            start,
            end,
            joins_required,
        ), data_date
    data_date = (
        datetime.datetime.now(tz=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    )
    return load_mdms_data(group_name, group_id, filter_date, start, end, mdms_reports), data_date
