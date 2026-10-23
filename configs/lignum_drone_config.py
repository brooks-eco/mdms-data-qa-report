from dataclasses import dataclass, field
from typing import Any

from config import BaseQAReportConfig


@dataclass
class LignumDroneQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Fish Larvae QA Report. Holds all configuration settings
    including file paths, sheet names, column names, join definitions, summary definitions,
    and plot definitions to allow easy management without changing the report generation code structure.
    """

    # --- Configuration ---
    report_title: str = "Lignum Drone Data QA"
    change_log: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "date": "5 Oct 2026",
                "changes": ["Initial release"],
            },
        ]
    )

    data_url = "https://mdms.essolutions.com.au/workbooks/download/15"

    mdms_reports = {
        # table_name: report_API_shortcode
        "LignumDroneSurvey": "lignum-drone-survey",
    }

    # Prepare data table  - need a generic python way to define these joins (e.g. dictionary) and a function to do the joins based on the dictionary. This will allow us to easily add more tables and joins in the future without changing the code structure.
    # GroupName	SamplingUnitID	SampleDate	DroneModel	FlightSetHeight	FlightSetOverlap	FieldWeather	FieldVigorousLignumPct	FieldDormantLignumPct	FieldAllLignumPct	FieldOtherShrubsPct	FieldWaterPct	DateRawShared	DateOrthomosaicShared	ClassVigorousLignumPct	ClassDormantLignum	ClassTrees	ClassGroundVeg	ClassBlackRolypoly	ClassNitreGoosfoot	ClassWater	ClassDirtSticksLitter	ClassTrash	Comment
    # VegSamplingUnits: SamplingUnitID	SamplePointName	TransectID	QuadratPlotID	SamplingUnitType	Elevation	ANAEType	LatitudeCentroid	LongitudeCentroid	Active	Comment

    # Join definitions are applied in list order; later joins use earlier results.
    joins_required: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "left": "LignumDroneSurvey",
                "right": "VegSamplingUnits",
                "on": ["SamplingUnitID"],
                "how": "left",
            },
        ]
    )

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   Sampling units, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Field Obs - Check Sum of field measures >100% per SamplingUnitID x SampleDate": {
                "note": (
                    "sum of [FieldVigorousLignumPct, FieldDormantLignumPct, FieldAllLignumPct, FieldOtherShrubsPct, FieldWaterPct]. "
                    "Look for outliers or excessive percent cover > 100"
                ),
                "table": "LignumDroneSurvey",
                "group_by": ["SamplingUnitID", "SampleDate"],
                "sum_columns": [
                    "FieldVigorousLignumPct",
                    "FieldDormantLignumPct",
                    "FieldAllLignumPct",
                    "FieldOtherShrubsPct",
                    "FieldWaterPct",
                ],
                "new_column_name": "FieldTotalCover",
                "summary": {"FieldTotalCover": "sum"},
            },
            "Derived Obs - Check Sum of field measures >100% per SamplingUnitID x SampleDate": {
                "note": (
                    "sum of [FieldVigorousLignumPct, FieldDormantLignumPct, FieldAllLignumPct, FieldOtherShrubsPct, FieldWaterPct]. "
                    "Look for outliers or excessive percent cover > 100"
                ),
                "table": "LignumDroneSurvey",
                "group_by": ["SamplingUnitID", "SampleDate"],
                "sum_columns": [
                    "ClassVigorousLignumPct",
                    "ClassDormantLignum",
                    "ClassTrees",
                    "ClassGroundVeg",
                    "ClassBlackRolypoly",
                    "ClassNitreGoosfoot",
                    "ClassWater",
                    "ClassDirtSticksLitter",
                    "ClassTrash",
                ],
                "new_column_name": "MLTotalCover",
                "summary": {"MLTotalCover": "sum"},
            },

        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            # "Species Catch Composition - Individual Replicate Samples": {
            #     "note": (
            #         "Guidance: The dots are individual replicate counts for any dates. "
            #         "This will expose outliers in individual replicates that may not be obvious "
            #         "once replicates are combined. Look for higher or lower than expected counts for each species."
            #     ),
            #     "type": "scatter",
            #     "table": "FishLarvaeCounts",
            #     "group_by": ["SamplePointName", "SampleType"],
            #     "x": "Count",
            #     "y": "ScientificName",
            #     "color": "ScientificName",
            #     "Legend": False,
            #     "sort_y": True,
            #     "y_axis_title": False,
            # },
        }
    )
