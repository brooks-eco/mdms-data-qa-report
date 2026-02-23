from dataclasses import dataclass, field
from typing import Dict, List, Any
from config import BaseQAReportConfig


@dataclass
class VegQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Vegetation QA Report. This class holds all the configuration settings for the report, including file paths, sheet names, column names, join definitions, summary definitions, and plot definitions. This allows us to easily manage and update the configuration settings in one place without changing the code structure of the report generation.
    """

    # --- Configuration ---
    group_name_source_sheet: str = "VegTripGrouping"  # The sheet name to look for GroupName values. Adjust if your grouping variable is in a different sheet.
    report_title: str = "Vegetation QA Report"
    data_url = "https://mdms.essolutions.com.au/workbooks/download/5"

    # VegTripGrouping: TripID	startDate	endDate	totalPlotsSampled	totalTransectsSampled
    # VegCommunitySurvey: TripID	SamplingUnitID	SampleDate	CanopyCover	LitterCover	LichenMossesCover	BareGroundCover	DeadTreeCover	LogCover	PlantBases	PercentInundated	WaterDepth	QualityDepth	SoilMoisture	DurationDry	QualityDurationDry	MaxDepthPrev	QualityMaxDepthPrev	DurationPrevInundation	QualityPrevInundation	Comment
    # VegSpeciesAbundance: SamplingUnitID	SampleDate	Stratum	ScientificName	PercentCover	Comment
    # VegRecruitment: SamplingUnitID	SampleDate	ScientificName	Stage0Recruit	Stage1Recruit	Stage2Recruit	Stage3Recruit	Stage4Recruit	Comment
    # VegSamplingUnits: SamplingUnitID	SamplePointName	TransectID	QuadratPlotID	SamplingUnitType	Elevation	ANAEType	LatitudeCentroid	LongitudeCentroid	Active	Comment

    # worksheet names and their expected columns based on the provided Excel file structure.
    # adjust to the commented columns above.
    workbook: List[str] = field(
        default_factory=lambda: [
            "VegTripGrouping",
            "VegCommunitySurvey",
            "VegSpeciesAbundance",
            "VegRecruitment",
            "VegSamplingUnits",
        ]
    )

    # Join definitions - this will be a dictionary where keys are the target table names and values are dictionaries that specify the join( right) table, the columns to join on, and the type of join. This will allow us to easily add more joins in the future without changing the code structure.

    joins_required: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "VegCommunitySurvey": {
            "right": "VegSamplingUnits",
            "on": ["SamplingUnitID"],
            "how": "left",
        },
        "VegSpeciesAbundance": {
            "right": "VegCommunitySurvey",
            "on": ["SamplingUnitID", "SampleDate"],
            "how": "left",
        },
        "VegRecruitment": {
            "right": "VegCommunitySurvey",
            "on": ["SamplingUnitID", "SampleDate"],
            "how": "left",
        },
    })

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   SamplingUnitID, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "Count of Transects per SamplePoint": {
            "table": "VegCommunitySurvey",
            "group_by": [
                "SamplePointName",
            ],
            "summary": {"TransectID": "nunique"},
            "filter": {"TransectID": "is not null"},
        },
        "Count of plots (SamplingUnitID not on transects) per SamplePoint": {
            "table": "VegCommunitySurvey",
            "group_by": [
                "SamplePointName",
            ],
            "summary": {"SamplingUnitID": ["nunique", "count"]},
            "filter": {"TransectID": "is null"},

        },

        "Transect Effort - Unique SamplingUnitID per transect per SamplePointName x SampleDate": {
            "table": "VegCommunitySurvey",
            "group_by": ["Year", "Month","SamplePointName", "TransectID"],
            "summary": {"SamplingUnitID": ["nunique", "count"]},
            "filter": {"TransectID": "is not null"},
        },
        "Plot Effort Unique SamplingUnitID per transect per SamplePointName x SampleDate": {
            "table": "VegCommunitySurvey",
            "group_by": ["Year", "Month","SamplePointName"],
            "summary": {"SamplingUnitID": ["nunique", "count"]},
            "filter": {"TransectID": "is null"},
        },

        "Water depth per transect/plot x SampleDate": {
            "table": "VegCommunitySurvey",
            "group_by": ["SamplingUnitID", "SampleDate"],
            "summary": {
                "WaterDepth": ["min", "mean", "max"],
            },
        },
        
        "Duration Dry per transect/plot x SampleDate": {
            "table": "VegCommunitySurvey",
            "group_by": ["SamplingUnitID", "SampleDate"],
            "summary": {
                "DurationDry": ["min", "mean", "max"],
            },
        },
        
        
        "Count of Soil Moisture records per transect/plot x SampleDate": {
            "table": "VegCommunitySurvey",
            "group_by": ["SamplingUnitID", "SampleDate"],
            "summary": {"QuadratPlotID": "count","SoilMoisture": "count"},
        },
        "Sum of non-plant ground-cover metrics per SamplingUnitID x SampleDate": {
            "table": "VegCommunitySurvey",
            "group_by": ["SamplingUnitID", "SampleDate"],
            "sum_columns": [
                "LitterCover",
                "LichenMossesCover",
                "BareGroundCover",
                "DeadTreeCover",
                "LogCover",
                "PlantBases",
            ],
            "new_column_name": "sumCommunityGrndCover",
            "summary": {"sumCommunityGrndCover": "sum"},
        },
        "Total percent cover of plants per SamplingUnitID x SampleDate": {
            "table": "VegSpeciesAbundance",
            "group_by": ["SamplingUnitID", "SampleDate"],
            "summary": {"PercentCover": "sum"},
        },
        "Total Recruitment per SamplingUnitID x SampleDate": {
            "table": "VegRecruitment",
            "group_by": ["SamplingUnitID", "SampleDate"],
            "sum_columns": [
                "Stage0Recruit",
                "Stage1Recruit",
                "Stage2Recruit",
                "Stage3Recruit",
                "Stage4Recruit",
            ],
            "new_column_name": "TotalRecruitment",
            "summary": {"TotalRecruitment": "sum"},
        },
        "Total Recruitment by Species per SamplingUnitID x SampleDate": {
            "table": "VegRecruitment",
            "group_by": ["SamplingUnitID", "SampleDate", "ScientificName"],
            "sum_columns": [
                "Stage0Recruit",
                "Stage1Recruit",
                "Stage2Recruit",
                "Stage3Recruit",
                "Stage4Recruit",
            ],
            "new_column_name": "TotalRecruitment",
            "summary": {"TotalRecruitment": "sum"},
        },
    })

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "PLOTS: most common 5 taxa x SamplingUnitID x SampleDate": {
                "note:": "",
                "type": "pie",
                "table": "VegSpeciesAbundance",
                "group_by": ["SamplePointName", "QuadratPlotID", "SampleDate"],
                "category": "ScientificName",
                "value": "PercentCover",
                "filter": {"TransectID": "is null"},
            },
            "TRANSECTS: most common 5 taxa x TransectID x SampleDate": {
                "note:": "",
                "type": "pie",
                "table": "VegSpeciesAbundance",
                "group_by": ["SamplePointName", "TransectID", "SampleDate"],
                "category": "ScientificName",
                "value": "PercentCover",
                "filter": {"TransectID": "is not null"},
            },
        }
    )
