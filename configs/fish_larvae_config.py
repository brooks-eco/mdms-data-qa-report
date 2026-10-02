from dataclasses import dataclass, field
from typing import Any

from config import BaseQAReportConfig


@dataclass
class FishLarvaeQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Fish Larvae QA Report. Holds all configuration settings
    including file paths, sheet names, column names, join definitions, summary definitions,
    and plot definitions to allow easy management without changing the report generation code structure.
    """

    # --- Configuration ---
    report_title: str = "Fish Larvae Data QA"
    change_log: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "date": "29 Sept 2026",
                "changes": [
                    "Check there is a count record for every sample. "
                    "Use `No Fish` with count 0 not blanks or missing rows",
                    "Check zero count samples use pseudo-taxon NO FISH",
                ],
            },
            {
                "date": "23 Feb 2026",
                "changes": ["Initial release"],
            },
        ]
    )

    data_url = "https://mdms.essolutions.com.au/workbooks/download/14"

    mdms_reports = {
        # table_name: report_API_shortcode
        "LarvaeSurveyEffort": "fish-larvae-effort",
        "FishLarvaeCounts": "fish-larvae",
    }

    # Prepare data table  - need a generic python way to define these joins (e.g. dictionary) and a function to do the joins based on the dictionary. This will allow us to easily add more tables and joins in the future without changing the code structure.
    # LarvaeSurveyEffort: GroupName	SamplePointName	SampleDate	SampleType	SampleNumber	StartDateTime	EndDateTime	TotalTripSamples	Pooled	SampleDurationSec	VolumeFiltered	QualityVolumeFiltered	Turbidity	QualityTurbidity	CompDataID	Comment
    # FishLarvaeCounts: SamplePointName	SampleDate	SampleType	SampleNumber	ScientificName	Count	Comment

    # Join definitions are applied in list order; later joins use earlier results.
    joins_required: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "left": "FishLarvaeCounts",
                "right": "LarvaeSurveyEffort",
                "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
                "how": "left",
            },
            {
                "left": "LarvaeSurveyEffort",
                "right": "FishLarvaeCounts",
                "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
                "how": "left",
                "summary": {"CatchRecordCount": {"Count": "count"}},
            },
        ]
    )

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   Sampling units, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Drift Net and Trawls - effort: unique sample id's (sample number) and count for each site": {
                "note": (
                    "Look for outliers. Uneven sample counts or mismatched id counts "
                    "may indicate missing data for some replicates."
                ),
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate"],
                "summary": {"SampleNumber": ["nunique", "count"]},
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            "Drift Net and Trawls - effort: sample duration": {
                "note": (
                    "Durations will vary but should be similar among gear types. "
                    "Check sample pooled indicator is correct."
                ),
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate", "SampleNumber"],
                "summary": {
                    "SampleDurationSec": "sum",
                    "Pooled": "unique",
                },
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            "Drift Nets - Volume filtered completeness per site": {
                "note": "There should be a volume filtered for every drift net sample.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SamplePointName", "SampleType"],
                "summary": {"SampleDate": "count", "VolumeFiltered": "count"},
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            "Light Traps: unique sample id's (sample number) and count for each site": {
                "note": (
                    "Look for outliers. Uneven sample counts or mismatched id counts may indicate "
                    "missing data for some replicates. Light Trap replicates are often pooled into a single sample."
                ),
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate", "Pooled"],
                "summary": {
                    "SampleNumber": ["nunique", "count"],
                },
                "filter": {"SampleType": {"!=": "DriftNet"}},
            },
            "Light Traps - effort: duration per sample": {
                "note": (
                    "Durations will vary but should be similar among gear types. "
                    "Check sample pooled or not indicator is correct."
                ),
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate", "SampleNumber"],
                "summary": {
                    "SampleDurationSec": "sum",
                    "Pooled": "unique",
                },
                "filter": {"SampleType": {"!=": "DriftNet"}},
            },
            "Light Trap - Turbidity completeness per site": {
                "note": "There should be a turbidity reading for every light trap sample.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SamplePointName", "SampleType"],
                "summary": {"SampleDate": "count", "Turbidity": "count"},
                "filter": {"SampleType": {"==": "LightTrap"}},
            },
            "Alert: Survey efforts with no catch data": {
                "note": (
                    "There should be no data here. Any displayed rows are survey effort samples "
                    "that have no matching catch data. If no fish larvae were found there should be "
                    "a single `No Fish` entry for the sample with count = 0. If the sample was not "
                    "collected remove the Larvae Survey Effort record."
                ),
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate", "SampleNumber"],
                "summary": {"CatchRecordCount": ["sum"]},
                "filter": {"CatchRecordCount": {"==": 0}},
            },
            "Alert: Check Zero count ScientificName uses pseudo-taxon `No Fish`": {
                "note": (
                    "This table only lists taxa with count = 0. Rows may include `No Fish` records. "
                    "Rows that are not `No Fish` may indicate errors."
                ),
                "table": "FishLarvaeCounts",
                "group_by": [
                    "SampleType",
                    "SamplePointName",
                    "SampleDate",
                    "SampleNumber",
                    "ScientificName",
                ],
                "summary": {"Count": ["sum"]},
                "filter": {"Count": {"==": 0}},
            },
            "Drift Net Catch - Species counts per site across all dates": {
                "note": "Look for outliers or oddballs results that may indicate data quality issues.",
                "table": "FishLarvaeCounts",
                "group_by": ["ScientificName", "SamplePointName"],
                "summary": {"Count": ["count", "sum"]},
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            "Light Trap Catch - Species counts per site across all dates": {
                "note": "Look for outliers or oddballs results that may indicate data quality issues.",
                "table": "FishLarvaeCounts",
                "group_by": ["ScientificName", "SamplePointName"],
                "summary": {"Count": ["count", "sum"]},
                "filter": {"SampleType": {"!=": "DriftNet"}},
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Species Catch Composition - Individual Replicate Samples": {
                "note": (
                    "Guidance: The dots are individual replicate counts for any dates. "
                    "This will expose outliers in individual replicates that may not be obvious "
                    "once replicates are combined. Look for higher or lower than expected counts for each species."
                ),
                "type": "scatter",
                "table": "FishLarvaeCounts",
                "group_by": ["SamplePointName", "SampleType"],
                "x": "Count",
                "y": "ScientificName",
                "color": "ScientificName",
                "Legend": False,
                "sort_y": True,
                "y_axis_title": False,
            },
            "Catch Composition: Top 5 species by count": {
                "note": "Welcome to the pie shop. Colours are individual species. Scan for oddballs/outliers",
                "type": "pie",
                "table": "FishLarvaeCounts",
                "group_by": ["SamplePointName", "SampleDate", "SampleType"],
                "category": "ScientificName",
                "value": "Count",
            },
        }
    )
