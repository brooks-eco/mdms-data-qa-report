import logging

logger = logging.getLogger(__name__)


def ensure_path_exists(directory):
    """Ensure that a directory exists."""
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)


def make_safe(filename):
    """Return a string that is safe to use as a filename."""
    return filename.replace(" ", "_").replace("'", "").replace(":", "").replace("/", "-")


def filter_df(filters, df, task_type=None, task_name=None):
    """Filter a DataFrame using the conditions in a configuration dictionary."""
    for filter_col, filter_condition in filters.items():
        if filter_col in df.columns:
            if isinstance(filter_condition, str) and filter_condition.lower() == "is not null":
                df = df[df[filter_col].notna()]
            elif isinstance(filter_condition, str) and filter_condition.lower() == "is null":
                df = df[df[filter_col].isna()]
            elif isinstance(filter_condition, dict):
                for operator, value in filter_condition.items():
                    if operator == "<":
                        df = df[df[filter_col] < value]
                    elif operator == ">":
                        df = df[df[filter_col] > value]
                    elif operator == "<=":
                        df = df[df[filter_col] <= value]
                    elif operator == ">=":
                        df = df[df[filter_col] >= value]
                    elif operator == "==":
                        df = df[df[filter_col] == value]
                    elif operator == "!=":
                        df = df[df[filter_col] != value]
                    elif operator == "in" and isinstance(value, (list, tuple, set)):
                        df = df[df[filter_col].isin(value)]
                    elif operator == "not in" and isinstance(value, (list, tuple, set)):
                        df = df[~df[filter_col].isin(value)]
                    else:
                        logger.warning(
                            "Unsupported operator '%s' in filter condition for column '%s' in %s definition '%s'. Skipping this filter.",
                            operator,
                            filter_col,
                            task_type,
                            task_name,
                        )
            else:
                logger.warning(
                    "Unsupported filter condition '%s' for column '%s' in %s definition '%s'. Skipping this filter.",
                    filter_condition,
                    filter_col,
                    task_type,
                    task_name,
                )
        else:
            logger.warning(
                "Filter column '%s' not found in table. Skipping this filter.", filter_col
            )
    return df
