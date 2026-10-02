from dataclasses import dataclass, field
from typing import Any

from config import BaseQAReportConfig


@dataclass
class VegQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Vegetation QA Report. Holds all configuration settings
    including file paths, sheet names, column names, join definitions, summary definitions,
    and plot definitions to allow easy management without changing the report generation code structure.
    """

    # --- Configuration ---
    report_title: str = "Vegetation Data QA"
    change_log: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "date": "1 Oct 2026",
                "changes": [
                    "Check for Sampling Units that are missing Quarterly Inundation with/without CEW",
                    "ScientificName sorted by mean percent cover (descending) across all provided samples - easier check for common/rare taxa",  # noqa: E501
                    "Check for missing NO PLANTS records. A percent cover record should exist for all "
                    "monitored sampling units x date. Use `NO PLANTS` with PercentCover = 0 not blanks or missing rows",
                    "Tabulate taxa with ZERO percent cover (cover = 0). Should be empty. Also checking for taxa with 100 cover",
                ],
            },
            {
                "date": "20 Jan 2026",
                "changes": ["Initial release"],
            },
        ]
    )

    mdms_reports = {
        # table_name: report_API_shortcode
        "VegCommunitySurvey": "qa-veg-community-structure",
        "VegSpeciesAbundance": "veg-species-abundance",
        "VegRecruitment": "veg-recruitment",
        "VegInundationHistory": "veg-quarterly-inundation",
    }

    data_url = "https://mdms.essolutions.com.au/workbooks/download/5"

    # VegTripGrouping: TripID	startDate	endDate	totalPlotsSampled	totalTransectsSampled
    # VegCommunitySurvey: TripID	SamplingUnitID	SampleDate	CanopyCover	LitterCover	LichenMossesCover	BareGroundCover	DeadTreeCover	LogCover	PlantBases	PercentInundated	WaterDepth	QualityDepth	SoilMoisture	DurationDry	QualityDurationDry	MaxDepthPrev	QualityMaxDepthPrev	DurationPrevInundation	QualityPrevInundation	Comment
    # VegSpeciesAbundance: SamplingUnitID	SampleDate	Stratum	ScientificName	PercentCover	Comment
    # VegRecruitment: SamplingUnitID	SampleDate	ScientificName	Stage0Recruit	Stage1Recruit	Stage2Recruit	Stage3Recruit	Stage4Recruit	Comment
    # VegSamplingUnits: SamplingUnitID	SamplePointName	TransectID	QuadratPlotID	SamplingUnitType	Elevation	ANAEType	LatitudeCentroid	LongitudeCentroid	Active	Comment
    # VegInundationHistory: SamplingUnitID	WaterYear	Quarter	Inundation	IncludesCew	Comment

    # Join definitions are applied in list order; later joins use earlier results.
    # joined tables use the left table name as identifier
    joins_required: list[dict[str, Any]] = field(
        default_factory=lambda: [
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
            {
                "left": "VegSpeciesAbundance",
                "right": "VegCommunitySurvey",
                "on": ["SamplingUnitID", "SampleDate"],
                "how": "left",
            },
            {
                "left": "VegRecruitment",
                "right": "VegCommunitySurvey",
                "on": ["SamplingUnitID", "SampleDate"],
                "how": "left",
            },
            {
                "left": "VegInundationHistory",
                "right": "VegSamplingUnits",
                "on": ["SamplingUnitID"],
                "how": "left",
            },
            {
                "left": "VegInundationHistory",
                "right": "Quarters",
                "on": ["WaterYear", "Quarter"],
                "how": "inner",
            },
            {
                "left": "VegCommunitySurvey",
                "right": "VegInundationHistory",
                "on": ["SamplingUnitID"],
                "how": "left",
                "summary": {"InundationRecordCount": {"Inundation": "count"}},
            },
        ]
    )

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   SamplingUnitID, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
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
                "summary": {"SamplingUnitID": ["nunique"]},
                "filter": {"TransectID": "is null"},
            },
            "Transect Effort - Unique SamplingUnitID per transect per SamplePointName x SampleDate": {
                "table": "VegCommunitySurvey",
                "group_by": ["Year", "Month", "SamplePointName", "TransectID"],
                "summary": {"SamplingUnitID": ["nunique", "count"]},
                "filter": {"TransectID": "is not null"},
            },
            "Plot Effort - Unique SamplingUnitID per SamplePointName x SampleDate": {
                "table": "VegCommunitySurvey",
                "group_by": ["Year", "Month", "SamplePointName"],
                "summary": {"SamplingUnitID": ["nunique", "count"]},
                "filter": {"TransectID": "is null"},
            },
            "Water depth measured in each SamplingUnitID on the SampleDate": {
                "table": "VegCommunitySurvey",
                "group_by": ["SamplingUnitID", "SampleDate"],
                "summary": {
                    "WaterDepth": ["min", "mean", "max"],
                },
                "mark_no_data": False
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
                "summary": {"QuadratPlotID": "count", "SoilMoisture": "count"},
            },
            "Sum of non-plant ground-cover metrics per SamplingUnitID x SampleDate": {
                "note": (
                    "sum of [LitterCover, LichenMossesCover, BareGroundCover, DeadTreeCover, LogCover, PlantBases]. "
                    "Look for outliers or excessive percent cover > 100"
                ),
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
                "new_column_name": "notplantGndCover",
                "summary": {"notplantGndCover": "sum"},
            },
            "ScientificName sorted by mean percent cover (descending) across all provided samples": {
                "note": "Check max value and ranking matches your expectations - Most common taxa at the top, rare at the bottom",
                "table": "VegSpeciesAbundance",
                "group_by": ["ScientificName"],
                "summary": {"PercentCover": ["mean", "min", "max"]},
                "sort": [["PercentCover", "mean", "desc"]],
            },
            "Taxa with ZERO percent cover per SamplingUnitID x SampleDate": {
                "note": (
                    "This table lists any plant species recorded with zero percent cover. "
                    "Rows may include `No Plants` records. Rows that are not `No Plants` may indicate errors. "
                    "Investigate any zero count records"
                ),
                "table": "VegSpeciesAbundance",
                "group_by": ["SamplingUnitID", "SampleDate", "ScientificName"],
                "summary": {"PercentCover": ["sum"]},
                "filter": {"PercentCover": {"==": 0}},
            },
            "Taxa with 100 percent cover per SamplingUnitID x SampleDate": {
                "note": (
                    "This table lists any plant species that were loaded with >=100 percent cover "
                    "- may include NO PLANTS. Check values > 100"
                ),
                "table": "VegSpeciesAbundance",
                "group_by": ["SamplingUnitID", "SampleDate", "ScientificName"],
                "summary": {"PercentCover": ["sum"]},
                "filter": {"PercentCover": {">=": 100}},
            },
            "Total sum of percent cover of plants per SamplingUnitID x SampleDate": {
                "note": (
                    "Sorted high to low. Look for outliers or excessive percent cover > 100. "
                    "Consistently small sum may indicate data loaded as proportion (0-1) not percent (0-100)"
                ),
                "table": "VegSpeciesAbundance",
                "group_by": ["SamplingUnitID", "SampleDate"],
                "summary": {"PercentCover": ["sum", "min", "max"]},
                "sort": [["PercentCover", "sum", "desc"]],
            },
            "Alert: Survey efforts with no vegetation abundance records": {
                "note": (
                    "There should be no data here unless the Community Survey was explicitly done "
                    "without recording ground cover. Any displayed rows indicate a survey effort "
                    "(SamplingUnitID x SampleDate) that has no matching `Vegetation Species Abundance` "
                    "ground cover data. If no plants were found there should be a single `No Plants` "
                    "entry for the sample with percent_cover = 0. If no Community or Abundance sampling "
                    "was done (e.g. no site access) remove the Veg Survey Effort record."
                ),
                "table": "VegCommunitySurvey",
                "group_by": ["SamplingUnitID", "SampleDate"],
                "summary": {"SpeciesRecordCount": ["sum"]},
                "filter": {"SpeciesRecordCount": {"==": 0}},
            },
            "Total Recruitment per SamplingUnitID x SampleDate": {
                "note": "Checking SamplingUnit sum of Stage 0, 1, 2, 3, 4 recruits. Look for outliers",
                "table": "VegRecruitment",
                "group_by": ["SamplingUnitID", "SampleDate"],
                "sum_columns": [
                    "Stage0Recruit",
                    "Stage1Recruit",
                    "Stage2Recruit",
                    "Stage3Recruit",
                    "Stage4Recruit",
                ],
                "new_column_name": "totRecruitment",
                "summary": {"totRecruitment": "sum"},
            },
            "Total Recruitment by Species per SamplingUnitID x SampleDate": {
                "note": "Checking Species x sample sum of Stage 0, 1, 2, 3, 4 recruits. Look for outliers",
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
            # "VegInundationHistory: Completeness check for quarterly data": {
            #     "note": "There should be 4 quarterly inundation records per SamplingUnitID in the water-year",
            #     "table": "VegInundationHistory",
            #     "group_by": ["SamplePointName", "SamplingUnitID"],
            #     "summary": {
            #         "Inundation": "count",
            #     },
            # },
            "VegInundationHistory completeness check. Sampling Units with < 4 records of quarterly inundation": {
                "note": (
                    "This table should be empty. Any records displayed are Veg Sampling Units that "
                    "were monitored (the effort record exists) but there are < 4 quarterly "
                    "`Veg Inundation History` records for the SamplingUnitID."
                ),
                "table": "VegCommunitySurvey",
                "group_by": ["SamplePointName", "SamplingUnitID"],
                "summary": {
                    "InundationRecordCount": "min",
                },
                "filter": {"InundationRecordCount": {"<": 4}},
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Species Composition - Individual Replicate Sample Dates": {
                "note": (
                    "Guidance: The dots are individual sampling dates in the water-year. For slow growing "
                    "taxa you might expect to see dots close together because cover does not change a lot "
                    "during the year - unless there is a recruitment event. The x axis shows the range of "
                    "vegetation cover for species in that SamplingUnit - check that this matches your "
                    "expectation and investigate unexpectedly high and low values. "
                    "(Limited to showing the most abundant 15 species per Sampling Unit)"
                ),
                "type": "scatter",
                "table": "VegSpeciesAbundance",
                "group_by": ["SamplePointName", "SamplingUnitID"],
                "x": "PercentCover",
                "y": "ScientificName",
                "color": "ScientificName",
                "Legend": False,
                "sort_y": True,
                "y_axis_title": False,
            },
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
