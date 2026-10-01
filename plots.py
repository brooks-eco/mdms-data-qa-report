import logging

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from utils import filter_df, make_safe

logger = logging.getLogger(__name__)


def create_single_pie_plot(ax, df, label_col, value_col, title_str, color_map=None):
    """Draw one aggregated pie chart on the supplied axes."""
    if not is_numeric_dtype(df[value_col]) or label_col == value_col:
        grouped = df.groupby(label_col, dropna=False).size().reset_index(name="count")
        value_col = "count"
    else:
        grouped = df.groupby(label_col, as_index=False, dropna=False)[value_col].sum()

    plot_data = grouped.sort_values(by=value_col, ascending=False).head(5)
    plot_data = plot_data[plot_data[value_col] > 0].copy()

    pie_colors = None
    if color_map:
        raw_labels = plot_data[label_col].fillna("missing/not provided").astype(str)
        pie_colors = [color_map.get(label, "#808080") for label in raw_labels]

    plot_data[label_col] = (
        plot_data[label_col].fillna("missing/not provided").astype(str).str.replace(" ", "\n")
    )

    if not plot_data.empty:
        _, label_texts, _ = ax.pie(
            plot_data[value_col],
            labels=plot_data[label_col],
            autopct="%1.1f%%",
            colors=pie_colors,
        )
        for text in label_texts:
            text.set_linespacing(0.8)
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
    ax,
    df,
    x_col,
    y_col,
    color_col,
    title_str,
    *,
    show_legend=True,
    wrap_legend=False,
    color_map=None,
    y_axis_title=True,
):
    """Draw one scatter plot on the supplied axes."""
    if color_col and color_col in df.columns:
        categories = df[color_col].dropna().unique()
        if not color_map:
            colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

        for index, category in enumerate(categories):
            subset = df[df[color_col] == category]
            color = (
                color_map.get(str(category), "#808080")
                if color_map
                else colors[index % len(colors)]
            )
            ax.scatter(subset[x_col], subset[y_col], label=str(category), color=color, alpha=0.8)

        if show_legend:
            legend_items = (
                [item.replace(" ", "\n").replace("_", "\n") for item in categories]
                if wrap_legend
                else categories
            )
            ax.legend(legend_items, title=color_col, bbox_to_anchor=(1.05, 1), loc="upper left")
    else:
        ax.scatter(df[x_col], df[y_col], alpha=0.8)

    if pd.api.types.is_datetime64_any_dtype(df[x_col]):
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y-%m-%d"))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    ax.set_xlabel(x_col)
    if y_axis_title:
        ax.set_ylabel(y_col)
    ax.set_title(title_str)
    ax.grid(linestyle="--", alpha=0.7)


def delete_existing_plots(output_path):
    """Delete existing PNG plot files from the output directory."""
    if output_path.exists() and output_path.is_dir():
        for filename in output_path.iterdir():
            if filename.suffix == ".png":
                try:
                    filename.unlink()
                except Exception as error:
                    logger.error("Error deleting file %s: %s", filename, error)


def get_global_color_map(df, column_name):
    """Build a stable category-to-color mapping for a plot series."""
    if not column_name or column_name not in df.columns:
        return None
    unique_values = sorted(df[column_name].dropna().unique().astype(str))
    color_map = plt.get_cmap("tab20")
    colors = [color_map(index % 20) for index in range(len(unique_values))]
    return dict(zip(unique_values, colors, strict=True))


def create_plots(joined_dfs, data_summaries, plots_definition, output_path):
    """Generate the configured plot collections and save them to disk."""
    logger.info("Creating plots...")
    plot_collection = {}

    for plot_series_name, original_config in plots_definition.items():
        config = original_config
        plot_series = []
        plot_type = config.get("type")
        if not plot_type:
            if "pie-chart" in config:
                config = config["pie-chart"]
                plot_type = "pie"
            elif "scatter-chart" in config:
                config = config["scatter-chart"]
                plot_type = "scatter"
            else:
                logger.warning("Unknown plot type for '%s'. Skipping.", plot_series_name)
                continue

        table_name = config.get("table")
        group_by_cols = config.get("group_by")
        if table_name in joined_dfs:
            dataframe = joined_dfs[table_name]
        elif table_name in data_summaries:
            dataframe = data_summaries[table_name][1]
        else:
            logger.error(
                "Table '%s' not found in joined data or summaries for plot '%s'.",
                table_name,
                plot_series_name,
            )
            continue

        if "filter" in config:
            dataframe = filter_df(
                config["filter"], dataframe, task_type="plot", task_name=plot_series_name
            )

        color_map = None
        if plot_type == "pie":
            color_map = get_global_color_map(dataframe, config.get("category"))
        elif plot_type == "scatter":
            color_map = get_global_color_map(dataframe, config.get("color"))

        groups = dataframe.groupby(group_by_cols) if group_by_cols else [("All Data", dataframe)]
        if len(groups) == 0:
            logger.warning("No data to plot for '%s'.", plot_series_name)
            plot_collection[plot_series_name] = None
            continue

        for group_key, group_df in groups:
            figure_size = (4, 3) if len(groups) > 4 else (6, 4)
            figure, axis = plt.subplots(figsize=figure_size)
            group_key_tuple = group_key if isinstance(group_key, tuple) else (group_key,)

            all_numeric_groups = (
                all(is_numeric_dtype(dataframe[column]) for column in group_by_cols)
                if group_by_cols
                else False
            )
            if all_numeric_groups and group_by_cols:
                title_parts = [
                    f"{column}: {value}"
                    for column, value in zip(group_by_cols, group_key_tuple, strict=True)
                ]
                title = " | ".join(title_parts)
            else:
                group_key_tuple = tuple(
                    value.strftime("%Y-%m-%d") if isinstance(value, pd.Timestamp) else value
                    for value in group_key_tuple
                )
                title = " | ".join(map(str, group_key_tuple))

            #title = title + f" (n={len(group_df)})"

            if plot_type == "pie":
                create_single_pie_plot(
                    axis,
                    group_df,
                    label_col=config.get("category"),
                    value_col=config.get("value"),
                    title_str=title,
                    color_map=color_map,
                )
            elif plot_type == "scatter":
                plotted = _prepare_scatter_data(group_df, config)
                if plotted is None:
                    logger.debug("No data to plot for '%s'.", title)
                    plt.close(figure)
                    continue
                create_single_scatter_plot(
                    axis,
                    plotted,
                    x_col=config.get("x"),
                    y_col=config.get("y"),
                    color_col=config.get("color"),
                    title_str=title,
                    show_legend=config.get("Legend", True),
                    wrap_legend=len(groups) > 4,
                    color_map=color_map,
                    y_axis_title = config.get("y_axis_title", True),
                )

            plt.tight_layout()
            safe_plot_name = make_safe(plot_series_name)
            safe_group_key = "_".join(make_safe(str(part)) for part in group_key_tuple)
            output_filename = f"{safe_plot_name}_{safe_group_key}.png"
            output_plot_path = output_path / output_filename
            plt.savefig(output_plot_path, bbox_inches="tight")
            plt.close(figure)
            logger.info("Plot saved to %s", output_plot_path)
            plot_series.append(output_filename)

        plot_collection[plot_series_name] = plot_series

    return plot_collection


def _prepare_scatter_data(group_df, config):
    x_column = config.get("x")
    y_column = config.get("y")
    color_column = config.get("color")
    dataframe = group_df.dropna(subset=[x_column, y_column], how="all").copy()
    if dataframe.empty or dataframe[x_column].isna().all() or dataframe[y_column].isna().all():
        return None

    x_is_numeric = is_numeric_dtype(dataframe[x_column])
    y_is_numeric = is_numeric_dtype(dataframe[y_column])
    x_is_datetime = is_datetime64_any_dtype(dataframe[x_column])
    y_is_datetime = is_datetime64_any_dtype(dataframe[y_column])

    aggregate_function = config.get("aggregate_function")
    if aggregate_function:
        if x_is_numeric and not y_is_numeric:
            aggregate_columns = [y_column]
            if color_column and color_column in dataframe.columns and color_column != y_column:
                aggregate_columns.append(color_column)
            dataframe = dataframe.groupby(aggregate_columns, as_index=False)[x_column].agg(
                aggregate_function
            )
        elif y_is_numeric and not x_is_numeric:
            aggregate_columns = [x_column]
            if color_column and color_column in dataframe.columns and color_column != x_column:
                aggregate_columns.append(color_column)
            dataframe = dataframe.groupby(aggregate_columns, as_index=False)[y_column].agg(
                aggregate_function
            )

    if not x_is_numeric and not x_is_datetime:
        dataframe[x_column] = dataframe[x_column].astype(str).str[:25]
        if y_is_numeric:
            dataframe = dataframe.sort_values(by=y_column).tail(15)
        else:
            dataframe = dataframe.sort_values(by=x_column)

    if not y_is_numeric and not y_is_datetime:
        dataframe[y_column] = dataframe[y_column].astype(str).str[:25]
        if x_is_numeric:
            dataframe = dataframe.sort_values(by=x_column).tail(15)
        elif x_is_datetime:
            dataframe = dataframe.sort_values(by=y_column)
        else:
            dataframe = dataframe.sort_values(by=y_column)

    if config.get("sort_y", False):
        dataframe = dataframe.sort_values(by=y_column, ascending=False)

    return dataframe
