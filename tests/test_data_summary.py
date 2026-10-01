from __future__ import annotations

from copy import deepcopy

import pandas as pd
import pytest

from data_summary import SummaryInputError, generate_effort_summaries, validate_summary_inputs


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
