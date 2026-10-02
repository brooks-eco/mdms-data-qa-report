import logging
from copy import deepcopy

import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.stats.stattools import medcouple

from utils import filter_df

logger = logging.getLogger(__name__)


class SummaryInputError(ValueError):
    """Raised when loaded tables cannot satisfy the configured summaries."""

    def __init__(self, issues):
        self.issues = tuple(issues)
        details = "\n".join(f"- {issue}" for issue in self.issues)
        super().__init__(f"Loaded data does not satisfy the summary configuration:\n{details}")


def validate_summary_inputs(loaded_tables, summaries_config):
    """Validate all source tables and columns required by summary definitions."""
    issues = []

    for summary_name, config in summaries_config.items():
        table_name = config["table"]
        if table_name not in loaded_tables:
            issues.append(f"summary '{summary_name}': table '{table_name}' was not loaded")
            continue

        required_columns = set(config.get("group_by", []))
        required_columns.update(config.get("filter", {}))
        required_columns.update(config.get("sum_columns", []))

        summary_columns = set(config.get("summary", {}))
        derived_column = config.get("new_column_name") if config.get("sum_columns") else None
        if derived_column:
            summary_columns.discard(derived_column)
        required_columns.update(summary_columns)

        missing_columns = sorted(required_columns.difference(loaded_tables[table_name].columns))
        if missing_columns:
            issues.append(
                f"summary '{summary_name}', table '{table_name}': missing columns "
                f"{', '.join(missing_columns)}"
            )

    if issues:
        raise SummaryInputError(issues)


def generate_effort_summaries(joined_dfs, summaries_config, group_name):
    """Generate configured summary tables and their QA annotations."""
    logger.info("Generating effort summaries for %s...", group_name)
    summary_tables = {}

    for summary_name, config in summaries_config.items():
        table_name = config["table"]
        group_by_cols = list(config["group_by"])
        summary_funcs = deepcopy(config["summary"])
        sort_specification = config.get("sort", [])

        if table_name not in joined_dfs:
            logger.error("Table '%s' not found for summary '%s'.", table_name, summary_name)
            continue

        df = joined_dfs[table_name].copy()
        if "filter" in config:
            df = filter_df(config["filter"], df, task_type="summary", task_name=summary_name)
            if df.empty:
                logger.warning(
                    "Filtering resulted in empty dataframe for summary '%s'.",
                    summary_name,
                )
                summary_tables[summary_name] = (table_name, df)
                continue

        missing_cols = [col for col in group_by_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Columns {missing_cols} not found in table '{table_name}' "
                f"for summary '{summary_name}'."
            )

        df[group_by_cols] = df[group_by_cols].fillna("Missing")

        if "sum_columns" in config and "new_column_name" in config:
            df[config["new_column_name"]] = df[config["sum_columns"]].sum(axis=1)

        grouping_for_count = list(dict.fromkeys(group_by_cols))
        if "SamplingUnitID" in df.columns:
            grouping_for_count.append("SamplingUnitID")
        num_groups = df.groupby(grouping_for_count).ngroups
        logger.debug("Summary '%s' has %s groups.", summary_name, num_groups)
        if num_groups > 500:
            logger.warning(
                "Summary '%s' has a large number of groups (%s). This may indicate that the grouping is too granular or that there are many unique sampling units.",
                summary_name,
                num_groups,
            )
            if (
                "SamplingUnitID" in group_by_cols
                and "SamplePointName" in df.columns
                and "TransectID" in df.columns
            ):
                logger.info(
                    "Replacing 'SamplingUnitID' with ['SamplePointName', 'TransectID'] in grouping for summary '%s'.",
                    summary_name,
                )
                group_by_cols = [col for col in group_by_cols if col != "SamplingUnitID"] + [
                    "SamplePointName",
                    "TransectID",
                ]
                for column, functions in summary_funcs.items():
                    if "sum" in functions:
                        summary_funcs[column] = ["min", "max", "mean"]

        summary_df = df.groupby(group_by_cols).agg(summary_funcs).reset_index()

        if isinstance(summary_df.columns, pd.MultiIndex):
            summary_df.columns = [
                f"{column[0]}\n{'records' if column[1] == 'count' else column[1]}"
                if column[1]
                else column[0]
                for column in summary_df.columns
            ]
        else:
            summary_df.columns = [
                (
                    f"{column}\n{'records' if function == 'count' else function}"
                    if column in summary_funcs and isinstance(function, str) and function != "first"
                    else column
                )
                for column, function in zip(
                    summary_df.columns,
                    [summary_funcs.get(column, "") for column in summary_df.columns],
                    strict=True,
                )
            ]

        for column in summary_df.columns:
            if str(column).endswith("\nunique"):
                summary_df[column] = summary_df[column].apply(
                    lambda values: (
                        "; ".join(
                            sorted(
                                str(value)
                                for value in values
                                if pd.notna(value) and str(value) != ""
                            )
                        )
                        if hasattr(values, "__iter__") and not isinstance(values, (str, bytes))
                        else values
                    )
                )

        column_functions = _map_generated_columns(summary_df, summary_funcs)
        _apply_qa_checks(summary_df, column_functions, config)
        summary_df = _sort_summary(summary_df, sort_specification, summary_name)
        summary_tables[summary_name] = (table_name, summary_df)

    return summary_tables


def _sort_summary(summary_df, sort_specification, summary_name):
    if not sort_specification:
        return summary_df

    sort_columns = []
    ascending = []
    for sort_item in sort_specification:
        if not isinstance(sort_item, (list, tuple)) or len(sort_item) != 3:
            raise ValueError(
                f"Invalid sort specification for summary '{summary_name}': expected "
                "[column, aggregation, direction]."
            )

        source_column, aggregation, direction = sort_item
        display_aggregation = "records" if aggregation == "count" else aggregation
        output_column = f"{source_column}\n{display_aggregation}"
        if output_column not in summary_df.columns:
            raise ValueError(
                f"Invalid sort specification for summary '{summary_name}': "
                f"output column '{output_column}' does not exist."
            )

        normalized_direction = str(direction).lower()
        if normalized_direction not in {"asc", "desc"}:
            raise ValueError(
                f"Invalid sort direction '{direction}' for summary '{summary_name}'; "
                "expected 'asc' or 'desc'."
            )
        sort_columns.append(output_column)
        ascending.append(normalized_direction == "asc")

    return summary_df.sort_values(
        by=sort_columns,
        ascending=ascending,
        kind="stable",
    ).reset_index(drop=True)


def _map_generated_columns(summary_df, summary_funcs):
    column_functions = {}
    for original_column, functions in summary_funcs.items():
        if isinstance(functions, str):
            functions = [functions]
        for function in functions:
            if function == "first":
                if original_column in summary_df.columns:
                    column_functions[original_column] = function
            else:
                display_function = "records" if function == "count" else function
                generated_column = f"{original_column}\n{display_function}"
                if generated_column in summary_df.columns:
                    column_functions[generated_column] = function
    return column_functions


def _apply_qa_checks(summary_df, column_functions, config):
    # if "CatchRecordCount\nsum" in column_functions:
    #     return

    count_columns = [column for column, function in column_functions.items() if function == "count"]
    first_count_column = count_columns[0] if count_columns else None
    comparison_count_columns = count_columns[1:]

    zero_check_done = False
    for column, function in column_functions.items():
        original_column = column.split("\n")[0]
        _check_cover_range(summary_df, column, original_column, function)
        _check_date_range(summary_df, column, original_column, function)
        if not config.get("skip_missmatch"):
            _check_unique_count(summary_df, column, original_column, function)

            if function == "count" and column in comparison_count_columns:
                qa_column = f"QA Check\n{column} = {first_count_column}"
                summary_df[qa_column] = ""
                summary_df.loc[summary_df[column] != summary_df[first_count_column], qa_column] = (
                    "mismatched"
                )
                summary_df.loc[
                    summary_df[column].notna()
                    & (summary_df[column] == summary_df[first_count_column]),
                    qa_column,
                ] = "\u2713"

        _check_soil_moisture_count(summary_df, column, original_column, function)

        if function == "nunique" and "ScientificName" in column:
            qa_outliers(column, summary_df)
        if function in {"count", "sum", "mean"}:
            if not zero_check_done and "ScientificName" in summary_df.columns:
                zero_check_done = _check_zero_species_count(
                    summary_df, column, original_column, function
                )
            qa_outliers(column, summary_df, mark_no_data=config.get("mark_no_data", True))
        if "Date\n" in column:
            if function == "count":
                qa_outliers(column, summary_df)
            if f"{original_column}\nnunique" in summary_df.columns:
                qa_outliers(column, summary_df)


def _check_cover_range(summary_df, column, original_column, function):
    if function not in {"sum", "max", "min"} or "cover\n" not in column.lower():
        return

    qa_column = "QA Check\nrange check\n0-100% +1"
    summary_df[qa_column] = ""
    summary_df.loc[(summary_df[column] >= 0) & (summary_df[column] <= 101.0), qa_column] = "\u2713"
    summary_df.loc[summary_df[column] < 0, qa_column] = f"{original_column}_{function} negative"
    summary_df.loc[summary_df[column] > 101.0, qa_column] = f"{original_column}_{function} > 101%"
    summary_df.loc[summary_df[column].isnull(), qa_column] = f"{original_column}_{function} missing"
    if function == "max":
        summary_df.loc[summary_df[column] == 0, qa_column] = f"{original_column}_{function} is 0"


def _check_date_range(summary_df, column, original_column, function):
    minimum_column = f"{original_column}\nmin"
    if not (
        function == "max"
        and "Date" in column
        and minimum_column in summary_df.columns
        and pd.api.types.is_datetime64_any_dtype(summary_df[column])
    ):
        return

    qa_column = "QA Check\ndate range\n> 7d"
    summary_df[qa_column] = ""
    duration = summary_df[column] - summary_df[minimum_column]
    long_survey = duration > pd.Timedelta(days=7)
    summary_df.loc[long_survey, qa_column] = (
        "long survey (" + duration[long_survey].dt.days.astype(str) + " days)"
    )
    summary_df.loc[duration <= pd.Timedelta(days=7), qa_column] = "\u2713"


def _check_unique_count(summary_df, column, original_column, function):
    unique_column = f"{original_column}\nnunique"
    if not (
        function == "count"
        and unique_column in summary_df.columns
        and pd.api.types.is_numeric_dtype(summary_df[column])
    ):
        return

    qa_column = f"QA Check\n{unique_column} = {column}"
    summary_df[qa_column] = ""
    summary_df.loc[summary_df[column] != summary_df[unique_column], qa_column] = "mismatched"
    summary_df.loc[
        summary_df[column].notna() & (summary_df[column] == summary_df[unique_column]),
        qa_column,
    ] = "\u2713"


def _check_zero_species_count(summary_df, column, original_column, function):
    # if the count, sum or mean is 0 the ScientificName should begin with "no " as in "no plants", "no fish", "no waterbirds"
    if function not in {"count", "sum", "mean"} or "ScientificName" not in summary_df.columns:
        return False
    qa_column = f"QA Check\n{column}\nzero values\nfor species"
    summary_df[qa_column] = ""
    starts_with_no = summary_df["ScientificName"].str.lower().str.startswith("no ")
    summary_df.loc[(summary_df[column] == 0) & starts_with_no, qa_column] = "\u2713"
    summary_df.loc[(summary_df[column] > 0) & ~starts_with_no, qa_column] = "\u2713"
    summary_df.loc[(summary_df[column] == 0) & ~starts_with_no, qa_column] = (
        f"zero {original_column}"
    )
    mask = (summary_df[column] > 0) & starts_with_no
    summary_df.loc[mask, qa_column] = (
        "non-zero\n"
        + original_column
        + "\nbut ScientificName is\n'"
        + summary_df.loc[mask, "ScientificName"]
        + "'"
    )
    return True


def _check_soil_moisture_count(summary_df, column, original_column, function):
    plot_count_column = "QuadratPlotID\nrecords"
    if not (
        function == "count" and "SoilMoisture" in column and plot_count_column in summary_df.columns
    ):
        return

    qa_column = "QA Check\nSoilMoisture count\nvs QuadratPlotID count"
    summary_df[qa_column] = ""
    summary_df.loc[summary_df[column] != summary_df[plot_count_column], qa_column] = (
        f"{original_column} missing"
    )
    summary_df.loc[
        summary_df[column].notna() & (summary_df[column] == summary_df[plot_count_column]),
        qa_column,
    ] = "\u2713"


def apply_no_data_markup(summary_df, column, qa_column):
    """Mark missing and zero source values as no data in an existing QA column."""
    numeric_values = pd.to_numeric(summary_df[column], errors="coerce")
    summary_df.loc[numeric_values.isna() | numeric_values.eq(0), qa_column] = "no data"


def qa_outliers(
    column,
    summary_df,
    *,
    method="iqr",
    mark_no_data=True,
    **method_options,
):
    """Apply the explicitly selected outlier detection method."""
    normalized_method = method.lower()
    if normalized_method == "iqr":
        qa_column = qa_outliers_iqr(column, summary_df, **method_options)
    elif normalized_method == "skewed":
        qa_column = qa_outliers_skewed(column, summary_df, **method_options)
    else:
        raise ValueError(f"Unknown outlier detection method '{method}'")

    if mark_no_data and qa_column is not None:
        apply_no_data_markup(summary_df, column, qa_column)
    return qa_column


def qa_outliers_iqr(column, summary_df):  # noqa: N802
    """Annotate outliers using skewness-adjusted IQR fences."""
    valid_values = pd.to_numeric(summary_df[column], errors="coerce").dropna()
    if valid_values.empty:
        return None

    q1, q3 = np.percentile(valid_values, [25, 75])
    iqr = q3 - q1
    skewness = medcouple(valid_values.to_numpy(), use_fast=len(valid_values) >= 10)
    if skewness >= 0:
        lower_bound = q1 - (1.5 * np.exp(-4 * skewness) * iqr)
        upper_bound = q3 + (1.5 * np.exp(3 * skewness) * iqr)
    else:
        lower_bound = q1 - (1.5 * np.exp(-3 * skewness) * iqr)
        upper_bound = q3 + (1.5 * np.exp(4 * skewness) * iqr)
    qa_column = f"QA Check\n{column}\noutliers IQR\n[{lower_bound:.1f}, {upper_bound:.1f}]"

    summary_df[qa_column] = ""
    summary_df.loc[summary_df[column] > upper_bound, qa_column] = f"high {column}"
    summary_df.loc[summary_df[column] < lower_bound, qa_column] = f"low {column}"
    valid = (
        summary_df[column].notna()
        & (summary_df[column] >= lower_bound)
        & (summary_df[column] <= upper_bound)
    )
    summary_df.loc[valid, qa_column] = "\u2713"
    return qa_column


def qa_outliers_skewed(column: str, summary_df: pd.DataFrame, alpha=0.05):
    """
    Vectorized QA check for skewed count data.
    Separates zero counts from positive values and applies Log-MAD scoring.
    alpha = expected detections rate (proportion of series length)
    """
    # previous used z_threshold was 3.5
    n = len(summary_df)
    z_threshold = norm.ppf(1 - alpha / (2 * n))  # Šidák/Bonferroni-style

    # 1. Parse numeric values preserving pandas index alignment
    s = pd.to_numeric(summary_df[column], errors="coerce")

    valid_mask = s.notna()
    valid_series = s[valid_mask]

    if (valid_series < 0).any():
        raise ValueError(f"Skewed outlier method requires non-negative values: {column}")

    if len(valid_series) < 5:
        qa_column = f"QA Check\n{column}\noutliers skewed\n[not assessed]"
        summary_df[qa_column] = "not assessed"
        return qa_column

    # Initialize results series matching the valid index
    results = pd.Series("\u2713", index=valid_series.index)

    # 2. Handle Zero Counts
    zero_mask = valid_series == 0
    zero_count = zero_mask.sum()
    total_valid = len(valid_series)

    if zero_count > 0:
        # Zero fraction evaluated globally across observed values
        zero_fraction = (zero_count - 1) / (total_valid - 1) if total_valid > 1 else 0
        if zero_fraction < 0.025:
            results[zero_mask] = f"low {column}"

    # 3. Handle Positive Counts (Log-MAD)
    pos_mask = valid_series > 0
    pos_series = valid_series[pos_mask]
    range_text = "not assessed"

    if len(pos_series) >= 5:
        # Standard natural log on positive values (X >= 1)
        log_pos = np.log(pos_series)
        center = log_pos.median()
        mad = (log_pos - center).abs().median()

        if mad == 0 or np.isclose(mad, 0):
            # Evaluate exact matches vs deviation when MAD is 0
            scores = pd.Series(0.0, index=pos_series.index)
            dev_mask = ~np.isclose(log_pos, center)
            scores[dev_mask] = np.sign(log_pos[dev_mask] - center) * np.inf
            lower_bound = upper_bound = np.exp(center)
        else:
            scaled_mad = 1.4826 * mad
            scores = (log_pos - center) / scaled_mad
            lower_bound = np.exp(center - (z_threshold * scaled_mad))
            upper_bound = np.exp(center + (z_threshold * scaled_mad))

        range_text = f"{lower_bound:.1f}, {upper_bound:.1f}"

        # Assign flags
        results[pos_mask & (scores > z_threshold)] = f"high {column}"
        results[pos_mask & (scores < -z_threshold)] = f"low {column}"
    else:
        results[pos_mask] = "not assessed"

    qa_column = f"QA Check\n{column}\noutliers skewed\n[{range_text}]"
    summary_df[qa_column] = "not assessed"

    # Write back aligned by index
    summary_df.loc[valid_series.index, qa_column] = results
    return qa_column


def qa_outliers_test(
    function,
    column,
    summary_df,
    group_col=None,
    iqr_mult_high=1.5,
    iqr_mult_low=1.5,
    low_percentile=2.5,
):
    """
    Annotate review alerts for numeric summary columns with tunable threshold parameters.

    Parameters:
    -----------
    function : str
        Metric type ('count' vs. continuous like 'mean', 'sum', 'std').
    column : str
        Name of the column in summary_df to check for outliers.
    summary_df : pd.DataFrame
        DataFrame containing the summary metrics.
    group_col : str or None, default "ScientificName"
        Column used for species/group stratification. Set to None to run globally.
    iqr_mult_high : float, default 1.0
        Multiplier for Q3 + (iqr_mult_high * IQR) upper bound.
    iqr_mult_low : float, default 1.5
        Multiplier for Q1 - (iqr_mult_low * IQR) lower bound (used for continuous metrics).
    low_percentile : float, default 2.5
        Percentile cutoff (0-100) applied to non-zero values for count low-bound checks.
    """
    s = pd.to_numeric(summary_df[column], errors="coerce")

    # Return early if column contains no valid data
    if s.dropna().empty:
        return

    # Check if a species/group column exists for stratified grouping
    has_group = (
        group_col is not None
        and group_col in summary_df.columns
        and summary_df[group_col].nunique() > 1
    )

    def flag_sub_series(sub_s):
        """Processes a single group or full series."""
        res = pd.Series("\u2713", index=sub_s.index)

        # Filter valid observations according to metric type
        valid = sub_s[
            sub_s.notna() & (sub_s > 0 if function in ("count", "nunique", "sum") else True)
        ]
        if len(valid) < 3:
            return res

        q1 = valid.quantile(0.25)
        q3 = valid.quantile(0.75)
        iqr = q3 - q1

        # 1. High-value review boundary (tunable upper multiplier)
        upper_bound = q3 + (iqr_mult_high * iqr)
        res[sub_s > upper_bound] = f"high {column}"

        # 2. Low-value review boundary
        if function in ("count", "nunique", "sum"):
            # For counts: flag non-zero counts at or below low_percentile
            pos_counts = valid[valid > 0]
            if len(pos_counts) >= 5 and pos_counts.nunique() > 1:
                low_cutoff = np.percentile(pos_counts, low_percentile)
                res[(sub_s > 0) & (sub_s <= low_cutoff) & (sub_s <= upper_bound)] = f"low {column}"
        else:
            # For continuous metrics (e.g. mean, std): tunable lower IQR bound
            lower_bound = q1 - (iqr_mult_low * iqr)
            res[sub_s < lower_bound] = f"low {column}"

        return res

    # Run grouped analysis if group_col is present; otherwise run globally
    if has_group:
        results = pd.Series("\u2713", index=summary_df.index)
        for _, group in summary_df.groupby(group_col):
            results.loc[group.index] = flag_sub_series(s.loc[group.index])
    else:
        results = flag_sub_series(s)

    # Values excluded from this detector are not assessed as outliers.
    if function in ("count", "nunique", "sum"):
        results[s.isna() | (s == 0)] = "not assessed"
    else:
        results[s.isna()] = "not assessed"

    # Compute dynamic header bounds for formatting consistency
    overall_valid = s[s.notna() & (s >= 0 if function in ("count", "nunique", "sum") else True)]
    q1_o, q3_o = overall_valid.quantile(0.25), overall_valid.quantile(0.75)
    iqr_o = q3_o - q1_o
    ub_o = q3_o + (iqr_mult_high * iqr_o)
    lb_o = (
        max(0.0, q1_o - (iqr_mult_low * iqr_o))
        if function == "count"
        else (q1_o - (iqr_mult_low * iqr_o))
    )

    qa_column = f"QA Check\n{column}\noutliers IQR\n[{lb_o:.1f}, {ub_o:.1f}]"
    summary_df[qa_column] = results
