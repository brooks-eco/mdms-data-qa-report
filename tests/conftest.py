from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def vegetation_workbook(tmp_path: Path) -> Path:
    """Create a minimal workbook shaped like an MDMS vegetation export."""
    workbook = tmp_path / "Vegetation_fixture.xlsx"
    survey = pd.DataFrame(
        [
            {
                "GroupName": "LAC",
                "SamplingUnitID": "LAC-P1",
                "SampleDate": pd.Timestamp("2025-06-20"),
                "CanopyCover": 10,
            },
            {
                "GroupName": "LAC",
                "SamplingUnitID": "LAC-OLD",
                "SampleDate": pd.Timestamp("2024-06-20"),
                "CanopyCover": 20,
            },
            {
                "GroupName": "BBN",
                "SamplingUnitID": "BBN-P1",
                "SampleDate": pd.Timestamp("2025-06-20"),
                "CanopyCover": 30,
            },
        ]
    )
    species = pd.DataFrame(
        [{"ScientificName": "Eucalyptus camaldulensis", "NativeExotic": "native"}]
    )
    sampling_units = pd.DataFrame(
        [
            {
                "GroupName": "LAC",
                "SamplingUnitID": "LAC-P1",
                "SamplePointName": "Lachlan test site",
            },
            {
                "GroupName": "BBN",
                "SamplingUnitID": "BBN-P1",
                "SamplePointName": "Bidgee test site",
            },
        ]
    )

    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame({"Description": ["Fixture metadata"]}).to_excel(
            writer, sheet_name="Metadata", index=False
        )
        survey.to_excel(writer, sheet_name="VegCommunitySurvey", index=False)
        sampling_units.to_excel(writer, sheet_name="VegSamplingUnits", index=False)
        species.to_excel(writer, sheet_name="VegSpeciesList", index=False)

    return workbook
