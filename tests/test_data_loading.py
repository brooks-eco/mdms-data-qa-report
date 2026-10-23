from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from dotenv import load_dotenv

from load_data import join_tables_generic, load_data, load_workbook_data, normalize_dataframe
from utils import filter_df


def test_normalize_dataframe_preserves_missing_or_existing_group_column() -> None:
    ungrouped = normalize_dataframe(
        pd.DataFrame({"SampleNumber": [1]}), filter_date=False, start=None, end=None
    )
    legacy_group = normalize_dataframe(
        pd.DataFrame({"Group": ["LAC"]}), filter_date=False, start=None, end=None
    )
    named_group = normalize_dataframe(
        pd.DataFrame({"GroupName": ["LAC"]}), filter_date=False, start=None, end=None
    )

    assert "GroupName" not in ungrouped.columns
    assert legacy_group["GroupName"].tolist() == ["LAC"]
    assert named_group["GroupName"].tolist() == ["LAC"]


def test_normalize_dataframe_treats_empty_strings_as_missing_for_filters() -> None:
    api_data = pd.DataFrame({"RecordID": [1, 2, 3], "ScientificName": ["Species A", "", None]})
    workbook_data = pd.DataFrame(
        {"RecordID": [1, 2, 3], "ScientificName": ["Species A", pd.NA, pd.NA]}
    )

    normalized_api = normalize_dataframe(api_data, filter_date=False, start=None, end=None)
    normalized_workbook = normalize_dataframe(
        workbook_data, filter_date=False, start=None, end=None
    )

    api_result = filter_df({"ScientificName": "is not null"}, normalized_api)
    workbook_result = filter_df({"ScientificName": "is not null"}, normalized_workbook)
    assert api_result["RecordID"].tolist() == workbook_result["RecordID"].tolist() == [1]


def test_normalize_dataframe_warns_when_date_filter_removes_all_rows(caplog) -> None:
    source = pd.DataFrame({"SampleDate": ["2025-03-17", "2025-03-23"]})

    result = normalize_dataframe(
        source,
        filter_date=True,
        start=pd.Timestamp("2025-06-01"),
        end=pd.Timestamp("2026-07-31"),
    )

    assert result.empty
    assert "source date range (2025-03-17 - 2025-03-23)" in caplog.text
    assert "requested filter (2025-06-01 - 2026-07-31)" in caplog.text


def test_normalize_dataframe_warns_for_group_filtered_out_while_other_groups_remain(
    caplog,
) -> None:
    source = pd.DataFrame(
        {
            "GroupName": ["LAC", "LAC", "BBN"],
            "SampleDate": ["2025-03-17", "2025-03-23", "2025-06-10"],
        }
    )

    result = normalize_dataframe(
        source,
        filter_date=True,
        start=pd.Timestamp("2025-06-01"),
        end=pd.Timestamp("2026-07-31"),
    )

    assert result["GroupName"].tolist() == ["BBN"]
    assert "Date filter removed all 2 rows for group 'LAC'" in caplog.text
    assert "source date range (2025-03-17 - 2025-03-23)" in caplog.text


def test_load_workbook_data_preserves_group_name_when_joined_tables_both_have_it(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "fish.xlsx"
    effort = pd.DataFrame([{"GroupName": "LAC", "SamplePointName": "LAC-P", "SampleNumber": 1}])
    sample_points = pd.DataFrame(
        [{"GroupName": "LAC", "SamplePointName": "LAC-P", "SiteName": "Lachlan"}]
    )
    with pd.ExcelWriter(workbook) as writer:
        effort.to_excel(writer, sheet_name="FishSurveyEffort", index=False)
        sample_points.to_excel(writer, sheet_name="SamplePoints", index=False)

    result = load_workbook_data(
        filepath=workbook,
        group_name="LAC",
        filter_date=False,
        start=None,
        end=None,
        joins_required=[
            {
                "left": "FishSurveyEffort",
                "right": "SamplePoints",
                "on": ["SamplePointName"],
                "how": "left",
            }
        ],
    )

    joined = result["LAC"]["FishSurveyEffort"]
    assert not joined.empty
    assert joined["GroupName"].tolist() == ["LAC"]
    assert "GroupName_x" not in joined.columns
    assert "GroupName_y" not in joined.columns


def test_join_tables_generic_matches_within_group_and_preserves_configured_join_keys() -> None:
    joins = [
        {
            "left": "FishSurveyEffort",
            "right": "SamplePoints",
            "on": ["SamplePointName"],
            "how": "left",
        }
    ]
    left = pd.DataFrame([{"GroupName": "LAC", "SamplePointName": "Shared", "SampleNumber": 1}])
    right = pd.DataFrame([{"GroupName": "BBN", "SamplePointName": "Shared", "SiteName": "Bidgee"}])

    result = join_tables_generic({"FishSurveyEffort": left, "SamplePoints": right}, joins)[
        "FishSurveyEffort"
    ]

    assert result["GroupName"].tolist() == ["LAC"]
    assert pd.isna(result.loc[0, "SiteName"])
    assert joins[0]["on"] == ["SamplePointName"]


def test_join_tables_generic_returns_no_rows_for_different_groups_with_inner_join() -> None:
    result = join_tables_generic(
        {
            "FishSurveyEffort": pd.DataFrame([{"GroupName": "LAC", "SamplePointName": "Shared"}]),
            "SamplePoints": pd.DataFrame([{"GroupName": "grp", "SamplePointName": "Shared"}]),
        },
        [
            {
                "left": "FishSurveyEffort",
                "right": "SamplePoints",
                "on": ["SamplePointName"],
                "how": "inner",
            }
        ],
    )["FishSurveyEffort"]

    assert result.empty


def test_join_tables_generic_does_not_add_group_key_when_one_table_is_ungrouped() -> None:
    result = join_tables_generic(
        {
            "FishSurveyEffort": pd.DataFrame([{"GroupName": "LAC", "SamplePointName": "Shared"}]),
            "SamplePoints": pd.DataFrame(
                [{"SamplePointName": "Shared", "SiteName": "Shared site"}]
            ),
        },
        [
            {
                "left": "FishSurveyEffort",
                "right": "SamplePoints",
                "on": ["SamplePointName"],
                "how": "left",
            }
        ],
    )["FishSurveyEffort"]

    assert result["GroupName"].tolist() == ["LAC"]
    assert result["SiteName"].tolist() == ["Shared site"]


def test_join_tables_generic_counts_nonblank_catch_values_per_effort_sample() -> None:
    effort = pd.DataFrame(
        {
            "SamplePointName": ["A", "A", "B", "C"],
            "SampleDate": ["2025-01-01"] * 4,
            "SampleType": ["DriftNet"] * 4,
            "SampleNumber": [1, 2, 1, 1],
        }
    )
    catch = pd.DataFrame(
        {
            "SamplePointName": ["A", "A", "A", "A", "B"],
            "SampleDate": ["2025-01-01"] * 5,
            "SampleType": ["DriftNet"] * 5,
            "SampleNumber": [1, 1, 1, 2, 1],
            "Count": [0, 3, None, None, 5],
        }
    )
    joins = [
        {
            "left": "LarvaeSurveyEffort",
            "right": "FishLarvaeCounts",
            "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
            "how": "left",
            "summary": {"CatchRecordCount": {"Count": "count"}},
        }
    ]

    result = join_tables_generic({"LarvaeSurveyEffort": effort, "FishLarvaeCounts": catch}, joins)[
        "LarvaeSurveyEffort"
    ]

    assert result["CatchRecordCount"].tolist() == [2, 0, 1, 0]
    assert len(result) == len(effort)


def test_join_tables_generic_applies_second_join_to_first_join_result() -> None:
    survey = pd.DataFrame(
        {
            "SamplingUnitID": ["A", "B"],
            "SampleDate": ["2025-01-01", "2025-01-01"],
        }
    )
    units = pd.DataFrame({"SamplingUnitID": ["A", "B"], "SamplePointName": ["North", "South"]})
    abundance = pd.DataFrame(
        {
            "SamplingUnitID": ["A", "A", "A", "B"],
            "SampleDate": ["2025-01-01"] * 4,
            "PercentCover": [0, 15, None, None],
        }
    )
    joins = [
        {
            "left": "VegCommunitySurvey",
            "right": "VegSamplingUnits",
            "on": ["SamplingUnitID"],
            "how": "left",
        },
        {
            "left": "VegCommunitySurvey",
            "right": "VegSpeciesAbundance",
            "on": ["SamplingUnitID", "SampleDate"],
            "how": "left",
            "summary": {"SpeciesRecordCount": {"PercentCover": "count"}},
        },
    ]

    result = join_tables_generic(
        {
            "VegCommunitySurvey": survey,
            "VegSamplingUnits": units,
            "VegSpeciesAbundance": abundance,
        },
        joins,
    )["VegCommunitySurvey"]

    assert result[["SamplingUnitID", "SamplePointName", "SpeciesRecordCount"]].to_dict(
        "records"
    ) == [
        {"SamplingUnitID": "A", "SamplePointName": "North", "SpeciesRecordCount": 2},
        {"SamplingUnitID": "B", "SamplePointName": "South", "SpeciesRecordCount": 0},
    ]
    assert len(result) == len(survey)


def test_load_data_reads_and_filters_an_excel_workbook(vegetation_workbook: Path) -> None:
    result, data_date = load_data(
        filepath=vegetation_workbook,
        group_name="LAC",
        filter_date=True,
        start=pd.Timestamp("2025-01-01"),
        end=pd.Timestamp("2025-12-31"),
        mdms_reports={},
        group_id=20,
        joins_required=[
            {
                "left": "VegCommunitySurvey",
                "right": "VegSamplingUnits",
                "on": ["SamplingUnitID", "GroupName"],
                "how": "left",
            }
        ],
    )

    assert result is not None
    assert data_date
    assert set(result) == {"LAC"}
    assert set(result["LAC"]) == {
        "VegCommunitySurvey",
        "VegSamplingUnits",
        "VegSpeciesList",
    }

    survey = result["LAC"]["VegCommunitySurvey"]
    assert survey[["GroupName", "SamplingUnitID", "SamplePointName", "Year", "Month"]].to_dict(
        "records"
    ) == [
        {
            "GroupName": "LAC",
            "SamplingUnitID": "LAC-P1",
            "SamplePointName": "Lachlan test site",
            "Year": 2025,
            "Month": 6,
        }
    ]


@pytest.mark.mdms
def test_load_data_reads_known_recruitment_data_from_mdms() -> None:
    if os.getenv("RUN_MDMS_INTEGRATION_TESTS") != "1":
        pytest.skip("set RUN_MDMS_INTEGRATION_TESTS=1 to query the live MDMS database")
    load_dotenv()
    if not os.getenv("API_KEY"):
        pytest.skip("API_KEY is required to query the live MDMS database")

    result, data_date = load_data(
        filepath=Path("mdms"),
        group_name="LAC",
        filter_date=True,
        start=pd.Timestamp("2025-06-15"),
        end=pd.Timestamp("2026-07-18"),
        mdms_reports={"VegRecruitment": "veg-recruitment"},
        group_id=20,
    )

    assert result is not None
    assert data_date
    recruitment = result["LAC"]["VegRecruitment"]
    known_rows = recruitment.loc[
        (recruitment["SamplePointName"] == "LBU-P")
        & (recruitment["SampleDate"] == pd.Timestamp("2026-05-24"))
        & (recruitment["ScientificName"] == "Eucalyptus camaldulensis")
    ]
    assert not known_rows.empty
    assert "Group" not in recruitment.columns
    assert set(recruitment["GroupName"]) == {"LAC"}
    assert recruitment["SampleDate"].between("2025-06-15", "2026-07-18").all()
