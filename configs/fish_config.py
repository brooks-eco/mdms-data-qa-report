from dataclasses import dataclass, field
from typing import Any

from config import BaseQAReportConfig


@dataclass
class FishQAReportConfig(BaseQAReportConfig):
    """
    Configuration class for the Fish QA Report. This class holds all the configuration settings for the report, including file paths, sheet names, column names, join definitions, summary definitions, and plot definitions. This allows us to easily manage and update the configuration settings in one place without changing the code structure of the report generation.
    """

    # --- Configuration ---
    report_title: str = "Fish Data QA"
    change_log: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "date": "29 Sept 2026",
                "changes": [
                    "Added Summary table to expose zero count samples that should use pseudo-taxon NO FISH",
                    "Added Alert for zero values for counts and measures",
                ],
            },
            {
                "date": "23 Feb 2026",
                "changes": ["Initial release"],
            },
        ]
    )

    data_url = "https://mdms.essolutions.com.au/workbooks/download/4"

    mdms_reports = {
        # table_name: report_API_shortcode
        "FishSurveyEffort": "fish-survey-effort-qa",
        "FishAdultCatch": "fish-adult-catch",
        "FishLengthWeight": "fish-length-weight",
        "FishAge": "fish-age",
    }

    # Prepare data table  - need a generic python way to define these joins (e.g. dictionary) and a function to do the joins based on the dictionary. This will allow us to easily add more tables and joins in the future without changing the code structure.
    # FishSurveyEffort: SamplePointName	SampleDate	SampleType	SampleNumber	StartDateTime	EndDateTime	TotalTripSamples	Pooled	SampleDurationSec	SeineArea	CompDataID	Comment
    # FishAdultCatch: SamplePointName	SampleDate	SampleType	SampleNumber	ScientificName	Count	ObservedCount	Comment
    # FishAge: SamplePointName	SampleDate	SampleType	SampleNumber	IndividualID	ScientificName	TotalLength	ForkLength	Weight	AgeAdult	AgeLarvae	Comment
    # FishLengthWeight: SamplePointName	SampleDate	SampleType	SampleNumber	ScientificName	FishNumber	IndividualID	TotalLength	ForkLength	Weight	Comment

    # Join definitions are applied in list order; later joins use earlier results.
    joins_required: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "left": "FishSurveyEffort",
                "right": "SamplePoints",
                "on": ["SamplePointName"],
                "how": "left",
            },
            {
                "left": "FishSurveyEffort",
                "right": "FishAdultCatch",
                "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
                "how": "left",
                "summary": {"CatchRecordCount": {"Count": "count"}},
            },
            {
                "left": "FishAdultCatch",
                "right": "FishSurveyEffort",
                "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
                "how": "left",
            },
            {
                "left": "FishLengthWeight",
                "right": "FishSurveyEffort",
                "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
                "how": "left",
            },
            {
                "left": "FishAge",
                "right": "FishSurveyEffort",
                "on": ["SamplePointName", "SampleDate", "SampleType", "SampleNumber"],
                "how": "left",
            },
        ]
    )

    # Summaries required - per joined table, we will define the summaries we want to generate. This will be a dictionary where keys are the summary names and values are the logic to generate them. This will allow us to easily add more summaries in the future without changing the code structure.
    # 1. Sampling Occasions and Effort - to check that all expected data was supplied and identify gaps in the data.
    #   Sampling units, Year, Month, count of Unique SampleDates, number of records per SampleDate

    data_summary_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Effort: Number of samples per site, date, and type": {
                "table": "FishSurveyEffort",
                "group_by": [
                    "SampleType",
                    "SamplePointName",
                    "SampleDate",
                ],
                "summary": {"SampleNumber": "nunique", "SampleDurationSec": "sum"},
            },
            "Effort: Number of sampling events per site": {
                "table": "FishSurveyEffort",
                "group_by": [
                    "SampleType",
                    "SamplePointName",
                ],
                "summary": {"SampleDate": "nunique"},
            },
            "Alert: Survey efforts with no FishAdultCatch species catch data": {
                "note": "There should be no data here. Any displayed rows are a survey effort that has no matching `Fish Adult Catch` data records. If a sample was taken but no fish were counted record the species as `No Fish` with count = 0. If the sample was not collected (e.g. no site access) remove the Fish Survey Effort record.",
                "table": "FishSurveyEffort",
                "group_by": ["SampleType", "SamplePointName", "SampleDate", "SampleNumber"],
                "summary": {"CatchRecordCount": ["sum"]},
                "filter": {"CatchRecordCount": {"==": 0}},
            },
            "Catch: Species counts and richness per sample event": {
                "table": "FishAdultCatch",
                "group_by": ["SamplePointName", "SampleDate", "SampleType"],
                "summary": {"Count": "sum", "ScientificName": "nunique"},
            },
            "Species with ZERO count in a Sample x SamplePointName x SampleDate": {
                "note": "This table lists any fish species that were loaded with zero counts.  This table exposes `No Fish` records.  Check any valid ScientificName with zero counts",
                "table": "FishAdultCatch",
                "group_by": [
                    "SampleDate",
                    "SamplePointName",
                    "SampleType",
                    "SampleNumber",
                    "ScientificName",
                ],
                "summary": {"Count": ["sum"]},
                "filter": {"Count": {"==": 0}},
            },
            "LengthWeight (field-measures): Count of records for measured fish per sample event ": {
                "table": "FishLengthWeight",
                "group_by": [
                    "SamplePointName",
                    "SampleType",
                    "SampleDate",
                ],
                "summary": {
                    "IndividualID": "nunique",
                    "TotalLength": "count",
                    "ForkLength": "count",
                    "Weight": "count",
                },
                "skip_missmatch": True,
            },
            "LengthWeight (field-measures): Total Length summary per species": {
                "note": "Zero records with TotalLength nan (not a number) are expected for species for forked tails (see  Fork-Length table below)",
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "summary": {
                    "TotalLength": ["count", "min", "mean", "max"],
                },
            },
            "LengthWeight (field-measures): Fork Length summary per species": {
                "note": "Zero records with ForkLength nan (not a number) are expected for species for rounded tails (see  Total-Length table above)",
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "summary": {
                    "ForkLength": ["count", "min", "mean", "max"],
                },
            },
            "LengthWeight (Field-measures): Weights summary per species": {
                "table": "FishLengthWeight",
                "group_by": ["ScientificName"],
                "summary": {
                    "Weight": ["count", "min", "mean", "max"],
                },
            },
            "Age (lab-measures): Cross-check FishNumber records vs IndividualID records per species ": {
                "table": "FishAge",
                "group_by": ["ScientificName"],
                "summary": {
                    "SampleNumber": ["nunique", "count"],
                    "IndividualID": ["nunique", "count"],
                },
            },
            "Age (lab-measures): Age data summary per species": {
                "table": "FishAge",
                "group_by": ["ScientificName"],
                "summary": {
                    "AgeAdult": ["min", "mean", "max", "count"],
                    "AgeLarvae": ["count"],
                },
            },
            "Age (lab-measures): length and weights from aged fish": {
                "table": "FishAge",
                "group_by": ["ScientificName"],
                "summary": {
                    "IndividualID": "nunique",
                    "TotalLength": "count",
                    "ForkLength": "count",
                    "Weight": "count",
                },
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: dict[str, dict[str, Any]] = field(
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
                "sort_y": True,
                "y_axis_title": False,
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
