from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

from plots import create_single_pie_plot, create_single_scatter_plot, prepare_scatter_data


def test_create_single_pie_plot_aggregates_categories_and_sets_title() -> None:
    data = pd.DataFrame(
        {
            "ScientificName": ["Species one", "Species one", "Species two"],
            "PercentCover": [10.0, 20.0, 30.0],
        }
    )
    figure, axis = plt.subplots()

    create_single_pie_plot(
        axis,
        data,
        label_col="ScientificName",
        value_col="PercentCover",
        title_str="Test site",
    )

    assert axis.get_title() == "Test site"
    assert len(axis.patches) == 2
    plt.close(figure)


def test_prepare_scatter_data_selects_top_y_values_by_mean_and_keeps_raw_rows() -> None:
    data = pd.DataFrame(
        {
            "Species": ["A", "A", "B", "B", "C", "C", "D", "D"],
            "Count": [1, 3, 4, 4, 10, 0, 100, -100],
        }
    )

    result = prepare_scatter_data(data, {"x": "Count", "y": "Species"}, y_limit=2)

    assert set(result["Species"]) == {"B", "C"}
    assert result.groupby("Species").size().to_dict() == {"B": 2, "C": 2}


def test_raw_scatter_places_highest_mean_category_at_top_of_y_axis() -> None:
    data = pd.DataFrame(
        {
            "Species": ["A", "A", "B", "B", "C", "C", "D", "D"],
            "Count": [1, 3, 4, 4, 10, 0, 100, -100],
        }
    )
    prepared = prepare_scatter_data(
        data,
        {"x": "Count", "y": "Species", "sort_y": True},
        y_limit=2,
    )
    figure, axis = plt.subplots()

    create_single_scatter_plot(
        axis,
        prepared,
        x_col="Count",
        y_col="Species",
        color_col=None,
        title_str="Mean abundance order",
    )

    assert [label.get_text() for label in axis.get_yticklabels()] == ["B", "C"]
    plt.close(figure)


def test_prepare_scatter_data_does_not_limit_numeric_y_values() -> None:
    data = pd.DataFrame({"X": range(20), "Y": range(100, 120)})

    result = prepare_scatter_data(data, {"x": "X", "y": "Y"}, y_limit=2)

    pd.testing.assert_frame_equal(result, data)


def test_scatter_treats_string_y_values_as_explicit_categories(caplog) -> None:
    data = pd.DataFrame({"Count": [3, 7], "Species": ["1", "2"]})
    figure, axis = plt.subplots()
    caplog.set_level(logging.INFO, logger="matplotlib.category")

    create_single_scatter_plot(
        axis,
        data,
        x_col="Count",
        y_col="Species",
        color_col=None,
        title_str="Numeric-looking species",
    )

    assert [label.get_text() for label in axis.get_yticklabels()] == ["1", "2"]
    assert not [record for record in caplog.records if record.name == "matplotlib.category"]
    plt.close(figure)


def test_scatter_treats_string_x_values_as_explicit_categories(caplog) -> None:
    data = pd.DataFrame({"SamplePoint": ["1", "2"], "Count": [3, 7]})
    figure, axis = plt.subplots()
    caplog.set_level(logging.INFO, logger="matplotlib.category")

    create_single_scatter_plot(
        axis,
        data,
        x_col="SamplePoint",
        y_col="Count",
        color_col=None,
        title_str="Numeric-looking sample points",
    )

    assert [label.get_text() for label in axis.get_xticklabels()] == ["1", "2"]
    assert not [record for record in caplog.records if record.name == "matplotlib.category"]
    plt.close(figure)


def test_scatter_parses_and_orders_date_strings_on_continuous_axis() -> None:
    data = pd.DataFrame(
        {
            "VisitDate": ["2026-01-10", "2026-01-01", "2026-01-02"],
            "Count": [10, 1, 2],
        }
    )

    prepared = prepare_scatter_data(data, {"x": "VisitDate", "y": "Count"})
    figure, axis = plt.subplots()
    create_single_scatter_plot(
        axis,
        prepared,
        x_col="VisitDate",
        y_col="Count",
        color_col=None,
        title_str="Visit dates",
    )

    assert prepared["VisitDate"].tolist() == list(
        pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-10"])
    )
    plotted_x = axis.collections[0].get_offsets()[:, 0]
    assert (plotted_x[1] - plotted_x[0], plotted_x[2] - plotted_x[1]) == (1, 8)
    plt.close(figure)
