from dataclasses import dataclass, field
from typing import Dict, List, Any
from config import BaseQAReportConfig


@dataclass
class FishQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Fish QA Report. This class holds all the configuration settings for the report, including file paths, sheet names, column names, join definitions, summary definitions, and plot definitions. This allows us to easily manage and update the configuration settings in one place without changing the code structure of the report generation.
    """

    # --- Configuration ---
    group_name_source_sheet: str = "FishSurveyEffort"  # The sheet name to look for GroupName values. Adjust if your grouping variable is in a different sheet.
    report_title: str = "Fish QA Report"
    data_url = "https://mdms.essolutions.com.au/workbooks/download/4"

    # Prepare data table  - need a generic python way to define these joins (e.g. dictionary) and a function to do the joins based on the dictionary. This will allow us to easily add more tables and joins in the future without changing the code structure.
    # FishSurveyEffort: SamplePointName	SampleDate	SampleType	SampleNumber	StartDateTime	EndDateTime	TotalTripSamples	Pooled	SampleDurationSec	SeineArea	CompDataID	Comment
    # FishAdultCatch: SamplePointName	SampleDate	SampleType	SampleNumber	ScientificName	Count	ObservedCount	Comment
    # FishAge: SamplePointName	SampleDate	SampleType	SampleNumber	IndividualID	ScientificName	TotalLength	ForkLength	Weight	AgeAdult	AgeLarvae	Comment
    # FishLengthWeight: SamplePointName	SampleDate	SampleType	SampleNumber	ScientificName	FishNumber	IndividualID	TotalLength	ForkLength	Weight	Comment

    # worksheet names and their expected columns based on the provided Excel file structure.
    # adjust to the commented columns above.
    workbook: List[str] = field(
        default_factory=lambda: [
            "FishSurveyEffort",
            "FishAdultCatch",
            "FishAge",
            "FishLengthWeight",
        ]
    )

    # Join definitions - this will be a dictionary where keys are the target table names and values are dictionaries that specify the join( right) table, the columns to join on, and the type of join. This will allow us to easily add more joins in the future without changing the code structure.

    joins_required: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "FishAdultCatch": {
            "right": "FishSurveyEffort",
            "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
            "how": "left",
        },
        "FishLengthWeight": {
            "right": "FishSurveyEffort",
            "on": ["SamplePointName", "SampleDate", "SampleType","SampleNumber"],
            "how": "left",
        },
        "FishAge": {
            "right": "FishSurveyEffort",
            "on": ["SamplePointName", "SampleDate", "SampleType","SampleNumber"],
            "how": "left",
        },
    })

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   SamplingUnitID, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "Effort: Number of samples per site, date, and type": {
                "table": "FishSurveyEffort",
                "group_by": ["SampleType","SamplePointName", "SampleDate", ],
                "summary": {"SampleNumber": "nunique", "SampleDurationSec": "sum"},
            },
            "Effort: Number of sampling events per site": {
                "table": "FishSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", ],
                "summary": {"SampleDate": "nunique"},
            },
            "Catch: Species counts and richness per sample event": {
                "table": "FishAdultCatch",
                "group_by": ["SamplePointName", "SampleDate", "SampleType"],
                "summary": {"Count": "sum", "ScientificName": "nunique"},
            },
            "LW: Count of measured fish per sample event": {
                "table": "FishLengthWeight",
                "group_by": ["SamplePointName", "SampleType", "SampleDate", ],
                "summary": {
                    "IndividualID": "nunique",
                    "TotalLength": "count",
                    "Weight": "count",
                },
            },
            "LW: Total Length summary per species": {
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "summary": {
                    "TotalLength": ["count", "min", "mean", "max"],
                },
            },
            "LW: Fork Length summary per species": {
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "summary": {
                    "ForkLength": ["count", "min", "mean", "max"],
                },
            },
            "LW: Weight summary per species": {
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "summary": {
                    "Weight": ["count", "min", "mean", "max"],
                },
            },
            "Age: Age data summary per species": {
                "table": "FishAge",
                "group_by": ["ScientificName"],
                "summary": {
                    "AgeAdult": ["min", "mean", "max", "count"],
                },
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "Species Catch Composition - Individual Replicate Samples": {
                "note": "Guidance: The dots are individual replicate counts for any dates.  This will expose outliers in individual replicates that may not be obvious once replicates are combined. (Limited to most abundant 15 species per plot)",
                "type": "scatter",
                "table": "FishAdultCatch",
                "group_by": ["SamplePointName", "SampleType"],
                "x": "Count",
                "y": "ScientificName",
                "color": "ScientificName",
                "Legend": False,
            },
            "Distribution of species among sites": {
                "note": "Guidance: Shows SamplePoints where each species was caught from the most abundant site to the least abundant site pooling all gear types. This may expose transcription errors in assigning counts to sites if memorable tallies are not present or sites that are known to support a particular species are not shown.",
                "type": "scatter",
                "table": "FishAdultCatch",
                "group_by": ["ScientificName"],
                "x": "Count",
                "y": "SamplePointName",
                "color": "SamplePointName",
                "Legend": False,
                "aggregate_function": "sum",
            },
            "TotalLength x Weight": {
                "note": "Guidance: Scan for outliers and unexpected weights without lengths ",
                "type": "scatter",
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "x": "TotalLength",
                "y": "Weight",
                "color": "ScientificName",
                "Legend": False,
            },
            "ForkLength x Weight": {
                "note": "Guidance: Scan for outliers and unexpected weights without lengths ",
                "type": "scatter",
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "x": "ForkLength",
                "y": "Weight",
                "color": "ScientificName",
                "Legend": True,
            },
            "Catch Composition: Top 5 species by count": {
                "note": "Welcome to the pie shop. Scan for oddballs/outliers",
                "type": "pie",
                "table": "FishAdultCatch",
                "group_by": ["SamplePointName", "SampleDate", "SampleType"],
                "category": "ScientificName",
                "value": "Count",
            },
        }
    )
