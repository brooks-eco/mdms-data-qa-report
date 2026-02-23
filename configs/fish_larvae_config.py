from dataclasses import dataclass, field
from typing import Dict, List, Any
from config import BaseQAReportConfig


@dataclass
class FishLarvaeQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Fish Larvae QA Report. This class holds all the configuration settings for the report, including file paths, sheet names, column names, join definitions, summary definitions, and plot definitions. This allows us to easily manage and update the configuration settings in one place without changing the code structure of the report generation.
    """

    # --- Configuration ---
    group_name_source_sheet: str = "LarvaeSurveyEffort"  # The sheet name to look for GroupName values. Adjust if your grouping variable is in a different sheet.
    report_title: str = "Fish Larvae QA Report"
    data_url = "https://mdms.essolutions.com.au/workbooks/download/14"

    # Prepare data table  - need a generic python way to define these joins (e.g. dictionary) and a function to do the joins based on the dictionary. This will allow us to easily add more tables and joins in the future without changing the code structure.
    # LarvaeSurveyEffort: GroupName	SamplePointName	SampleDate	SampleType	SampleNo	StartDateTime	EndDateTime	TotalTripSamples	Pooled	SampleDurationSec	VolumeFiltered	QualityVolumeFiltered	Turbidity	QualityTurbidity	CompDataID	Comment
    # FishLarvaeCounts: SamplePointName	SampleDate	SampleType	SampleNo	ScientificName	Count	Comment

    # worksheet names and their expected columns based on the provided Excel file structure.
    # adjust to the commented columns above.
    workbook: List[str] = field(
        default_factory=lambda: [
            "LarvaeSurveyEffort",
            "FishLarvaeCounts",
        ]
    )

    # Join definitions - this will be a dictionary where keys are the target table names and values are dictionaries that specify the join( right) table, the columns to join on, and the type of join. This will allow us to easily add more joins in the future without changing the code structure.

    joins_required: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "FishLarvaeCounts": {
            "right": "LarvaeSurveyEffort",
            "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNo"],
            "how": "left",
        },
    })

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   SamplingUnitID, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "Effort: Drift Net and Trawls: unique sample id's (sample number) and count for each site": {
                "note" : "look for outliers. Uneven sample counts or mismatched id counts may indicate missing data for some replicates.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate"],
                "summary": {"SampleNo": ["nunique", "count"]},
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            
            "Effort: Light Traps: unique sample id's (sample number) and count for each site": {
                "note" : "look for outliers. Uneven sample counts or mismatched id counts may indicate missing data for some replicates.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate"],
                "summary": {"SampleNo": ["nunique", "count"],},
                "filter": {"SampleType": {"!=": "DriftNet"}},
            },
            "Effort: Sample count and duration per gear type for each site": {
                "note" : "Durations will vary but should be similar among gear types.  Check sample pooled or not indicator is correct.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SampleType", "SamplePointName","SampleDate"],
                "summary": {"SampleNo": "count", "SampleDurationSec": "sum", "Pooled": "unique"},
                #"filter": {"SampleType": {"!=": "DriftNet"}},
            },
            

            "Drift Nets - Volume filtered completeness per site": {
                "note" : "There should be a volumne filtered for every drift net sample.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SamplePointName", "SampleType"],
                "summary": {"SampleDate": "count", "VolumeFiltered": "count"},
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            
            "Light Trap - Turbidity completeness per site": {
                "note": "There should be a turbidity reading for every light trap sample.",
                "table": "LarvaeSurveyEffort",
                "group_by": ["SamplePointName", "SampleType"],
                "summary": {"SampleDate": "count", "Turbidity": "count"},
                "filter": {"SampleType": {"==": "LightTrap"}},
            },
            "Drift Net Catch - Species counts per site across all dates": {
                "note": "Look for outliers or oddballs results that may indicate data quality issues.",
                "table": "FishLarvaeCounts",
                "group_by": ["ScientificName", "SamplePointName"],
                "summary": {"Count": ["count", "sum"] },
                "filter": {"SampleType": {"==": "DriftNet"}},
            },
            "Light Trap Catch - Species counts per site across all dates": {
                "note": "Look for outliers or oddballs results that may indicate data quality issues.",
                "table": "FishLarvaeCounts",
                "group_by": ["ScientificName", "SamplePointName"],
                "summary": {"Count": ["count", "sum"] },
                "filter": {"SampleType": {"!=": "DriftNet"}},
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "Species Catch Composition - Individual Replicate Samples": {
                "note": "Guidance: The dots are individual replicate counts for any dates.  This will expose outliers in individual replicates that may not be obvious once replicates are combined. Look for higher or lower than expected counts for each species.",
                "type": "scatter",
                "table": "FishLarvaeCounts",
                "group_by": ["SamplePointName", "SampleType"],
                "x": "Count",
                "y": "ScientificName",
                "color": "ScientificName",
                "Legend": False,
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
