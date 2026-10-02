from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from data_summary import (
    SummaryInputError,
    apply_no_data_markup,
    generate_effort_summaries,
    qa_outliers,
    validate_summary_inputs,
)


def test_validate_summary_inputs_reports_all_missing_tables_and_columns() -> None:
    tables = {
        "survey": pd.DataFrame(
            {
                "SamplingUnitID": ["A-1"],
                "Existing": [1],
            }
        )
    }
    definitions = {
        "Calculated cover": {
            "table": "survey",
            "group_by": ["Site"],
            "filter": {"Status": "is not null"},
            "sum_columns": ["CoverA", "CoverB"],
            "new_column_name": "TotalCover",
            "summary": {"TotalCover": "sum", "Existing": "count"},
        },
        "Missing source": {
            "table": "observations",
            "group_by": ["Site"],
            "summary": {"Count": "sum"},
        },
    }

    with pytest.raises(SummaryInputError) as error:
        validate_summary_inputs(tables, definitions)

    message = str(error.value)
    assert (
        "summary 'Calculated cover', table 'survey': missing columns CoverA, CoverB, Site, Status"
        in message
    )
    assert "summary 'Missing source': table 'observations' was not loaded" in message
    assert "TotalCover" not in message


def test_generate_effort_summaries_returns_qa_annotated_table_without_mutating_inputs() -> None:
    source = pd.DataFrame(
        {
            "Site": ["A", "A", None],
            "SamplingUnitID": ["A-1", "A-2", "B-1"],
            "CanopyCover": [10.0, 110.0, 5.0],
        }
    )
    source_before = source.copy(deep=True)
    specification = {
        "Canopy cover range": {
            "table": "survey",
            "group_by": ["Site"],
            "summary": {"CanopyCover": ["min", "max"]},
        }
    }
    specification_before = deepcopy(specification)

    result = generate_effort_summaries({"survey": source}, specification, group_name="LAC")

    table_name, summary = result["Canopy cover range"]
    assert table_name == "survey"
    assert summary[["Site", "CanopyCover\nmin", "CanopyCover\nmax"]].to_dict("records") == [
        {"Site": "A", "CanopyCover\nmin": 10.0, "CanopyCover\nmax": 110.0},
        {"Site": "Missing", "CanopyCover\nmin": 5.0, "CanopyCover\nmax": 5.0},
    ]
    assert "CanopyCover_max > 101%" in set(summary["QA Check\nrange check\n0-100% +1"])
    pd.testing.assert_frame_equal(source, source_before)
    assert specification == specification_before


def test_generate_effort_summaries_sorts_by_multiple_aggregated_columns() -> None:
    source = pd.DataFrame(
        {
            "ScientificName": ["Species A", "Species A", "Species B", "Species C"],
            "SamplingUnitID": ["A-1", "A-2", "B-1", "C-1"],
            "PercentCover": [10.0, 10.0, 20.0, 20.0],
            "Count": [1, 1, 1, 3],
        }
    )
    specification = {
        "Most common taxa": {
            "table": "survey",
            "group_by": ["ScientificName"],
            "summary": {
                "PercentCover": "mean",
                "Count": "sum",
            },
            "sort": [
                ["PercentCover", "mean", "desc"],
                ["Count", "sum", "asc"],
            ],
        }
    }

    result = generate_effort_summaries({"survey": source}, specification, group_name="LAC")

    summary = result["Most common taxa"][1]
    assert summary["ScientificName"].tolist() == ["Species B", "Species C", "Species A"]
    assert summary.index.tolist() == [0, 1, 2]


def test_validate_summary_inputs_uses_only_configured_columns_for_fish_tables():
    tables = {
        "FishSurveyEffort": pd.DataFrame(
            {
                "SampleType": ["electrofishing"],
                "SamplePointName": ["A"],
                "SampleDate": ["2025-01-01"],
                "SampleNumber": [1],
            }
        )
    }
    definitions = {
        "Fish effort": {
            "table": "FishSurveyEffort",
            "group_by": ["SampleType", "SamplePointName", "SampleDate"],
            "summary": {"SampleNumber": "nunique"},
        }
    }

    validate_summary_inputs(tables, definitions)


def test_qa_outliers_defaults_to_iqr_detection() -> None:
    summary = pd.DataFrame({"value": [1, 2, 2, 2, 1000]})

    qa_outliers("value", summary)

    qa_column = "QA Check\nvalue\noutliers IQR\n[2.0, 2.0]"
    assert summary[qa_column].tolist() == ["low value", "\u2713", "\u2713", "\u2713", "high value"]


def test_qa_outliers_uses_explicit_skewed_detection() -> None:
    summary = pd.DataFrame({"value": [1, 2, 2, 2, 1000]})

    qa_outliers("value", summary, method="skewed")

    qa_column = "QA Check\nvalue\noutliers skewed\n[2.0, 2.0]"
    assert summary[qa_column].tolist() == ["low value", "\u2713", "\u2713", "\u2713", "high value"]


def test_iqr_outliers_use_skewness_adjusted_boxplot_fences() -> None:
    summary = pd.DataFrame({"value": [1, 2, 2, 2, 3, 3, 4, 5, 20, 100]})

    qa_outliers("value", summary, method="iqr", mark_no_data=False)

    qa_column = "QA Check\nvalue\noutliers IQR\n[0.9, 16.0]"
    assert summary[qa_column].tolist() == [
        "\u2713",
        "\u2713",
        "\u2713",
        "\u2713",
        "\u2713",
        "\u2713",
        "\u2713",
        "\u2713",
        "high value",
        "high value",
    ]


def test_skewed_outlier_header_reports_raw_value_bounds() -> None:
    summary = pd.DataFrame({"value": [1.0, np.e, np.e**2, np.e**3, np.e**4]})

    qa_outliers("value", summary, method="skewed", alpha=0.05)

    qa_column = "QA Check\nvalue\noutliers skewed\n[0.2, 336.6]"
    assert summary[qa_column].tolist() == ["\u2713"] * 5


def test_qa_outliers_rejects_unknown_detection_method() -> None:
    summary = pd.DataFrame({"value": [1, 2, 3]})

    with pytest.raises(ValueError, match="Unknown outlier detection method 'unknown'"):
        qa_outliers("value", summary, method="unknown")


def test_apply_no_data_markup_marks_zero_and_missing_values() -> None:
    summary = pd.DataFrame(
        {
            "value": [0.0, float("nan"), 2.0],
            "QA Check": ["low value", "", "\u2713"],
        }
    )

    apply_no_data_markup(summary, "value", "QA Check")

    assert summary["QA Check"].tolist() == ["no data", "no data", "\u2713"]


def test_qa_outliers_marks_zero_as_no_data_by_default() -> None:
    summary = pd.DataFrame({"value": [0, 1, 2, 3]})

    qa_outliers("value", summary)

    qa_column = "QA Check\nvalue\noutliers IQR\n[-1.5, 4.5]"
    assert summary.loc[0, qa_column] == "no data"


def test_qa_outliers_applies_no_data_markup_after_skewed_detection() -> None:
    summary = pd.DataFrame({"value": [float("nan"), 0, 1, 2, 2, 2, 1000]})

    qa_outliers("value", summary, method="skewed")

    qa_column = "QA Check\nvalue\noutliers skewed\n[2.0, 2.0]"
    assert summary.loc[[0, 1], qa_column].tolist() == ["no data", "no data"]


def test_qa_outliers_can_leave_missing_and_zero_values_for_outlier_detection() -> None:
    summary = pd.DataFrame({"value": [float("nan"), 0, 1, 2, 3]})

    qa_outliers("value", summary, method="iqr", mark_no_data=False)

    qa_column = next(column for column in summary.columns if "outliers IQR" in column)
    assert summary.loc[[0, 1], qa_column].tolist() == ["", "\u2713"]
