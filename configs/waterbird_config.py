from dataclasses import dataclass, field
from typing import Dict, List, Set, Any
from config import BaseQAReportConfig


@dataclass
class WaterbirdQAReportConfig(BaseQAReportConfig):
    group_name_source_sheet: str = "WaterbirdSurveys"  # The sheet name to look for GroupName values. Adjust if your grouping variable is in a different sheet.
    report_title: str = "Waterbird QA Report"
    left_justify_columns: Set[str] = field(
        default_factory=lambda: {"BreedingNotes", "SamplePointName\nunique"}
    )
    data_url = "https://mdms.essolutions.com.au/workbooks/download/8"

    # WaterbirdSurveys: SamplePointName	VisitDate	SurveyNumber	StartTime	EndTime	Observers	SurveyMethod	eWaterTiming	InundatedArea	AirTemp	Rain	CloudCoverPercent	WindSpeed	WindDirection	SurveyCoverage	Disturbance	CompDataID	Comment
    # WaterbirdCounts: SamplePointName	VisitDate	SurveyNumber	ScientificName	ObsType	TotalCount	BroodsNests	BreedingNotes	CountAccuracy	Comment

    workbook: List[str] = field(
        default_factory=lambda: [
            "WaterbirdSurveys",
            "WaterbirdCounts",
        ]
    )

    joins_required: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "WaterbirdCounts": {
            "right": "WaterbirdSurveys",
            "on": ["SamplePointName", "VisitDate", "SurveyNumber"],
            "how": "left",
        },
    })

    data_summary_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "Effort: Ground survey - Number of sampling dates per site with max, min coverage": {
                "note": "Check this matches your field program. ",
                "table": "WaterbirdSurveys",
                "group_by": ["SurveyMethod", "SamplePointName"],
                "summary": {"VisitDate": ["nunique"], "SurveyCoverage": ["min", "max"]},
                "filter": {"SurveyMethod": {"==": "ground"}},
            },
            "Effort: Acoustic survey - Number of sampling dates per site with max, min coverage": {
                "note": "Check this matches your field program. ",
                "table": "WaterbirdSurveys",
                "group_by": ["SurveyMethod", "SamplePointName"],
                "summary": {"VisitDate": ["nunique"], "SurveyCoverage": ["min", "max"]},
                "filter": {"SurveyMethod": {"==": "acoustic"}},
            },
            "Counts: Species counts and richness per survey": {
                "note": "Look for outliers or oddballs results that may indicate data quality issues.",
                "table": "WaterbirdCounts",
                "group_by": ["SamplePointName", "SurveyMethod", "SurveyNumber"],
                "summary": {"TotalCount": "sum", "ScientificName": "nunique"},
            },
            "Ground Survey: Summary counts per species across all sites": {
                "note": "Zero counts are generally not included in the data apart from a 'No Waterbirds' entry so the min is the minimum of the loaded records.",
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "TotalCount": ["count", "min", "mean", "max", "sum"],
                },
                "filter": {"SurveyMethod": {"==": "ground"}},
            },
            "Acoustic surveys: Summary counts per species across all sites": {
                "note": "Zero counts are generally not included in the data apart from a 'No Waterbirds' entry so the min is the minimum of the loaded records.",
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "TotalCount": ["count", "min", "mean", "max", "sum"],
                },
                "filter": {"SurveyMethod": {"==": "acoustic"}},
            },
            "Breeding: Broods/Nests summary per species pooling all samples": {
                "note": "High record count with low sum is because many zero counts are included in the rows.",
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "BroodsNests": ["count", "sum"],
                },
            },
            "Breeding Notes": {
                "note": "BreedingNotes is a free text field to record evidence of breeding. The text should be meaningful and descriptive evidence of breeding or breeding related. Check the data matches your notes, clearly interpretable and not ambiguous.",
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "BreedingNotes": "unique",
                },
                "filter": {"BreedingNotes": {"!=": ""}},
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "Timing of site surveys (VisitDate) and SurveyCoverage for each SamplePointName": {
                "note": "Check this matches your field program and there are no surveys out of place or missing (may be hard to see in plots but should be visible Table 2 above).",
                "type": "scatter",
                "table": "WaterbirdSurveys",
                # "group_by": ["SamplePointName","SurveyNumber"], #dont group
                "x": "VisitDate",
                "y": "SurveyCoverage",
                "color": "SamplePointName",
                "Legend": True,
            },
            "Most common 15 taxa in each site survey (SamplePointName x SurveyNumber)": {
                "note": "Guidance: LImited to 15 for display purposes. Scan for outliers and oddballs e.g. species with high counts that you know to be rare. Use the plots to visualise the proportional distribution of species at each site to compare to your knowledge (and data) for the sites.",
                "type": "scatter",
                "table": "WaterbirdCounts",
                "group_by": ["SamplePointName", "SurveyNumber"],
                "x": "TotalCount",
                "y": "ScientificName",
                "color": "ScientificName",
                "Legend": False,
                "aggregate_function": "sum",  # may also want min, max, count
            },
            "Summary of 'InundatedArea' and eWaterTiming for each site survey": {
                "note": "Check that your pre, during, and post water delivery samples are represented. Each Survey_Number is represented as a separate coloured dot. ",
                "type": "scatter",
                "table": "WaterbirdSurveys",
                "group_by": [
                    "SamplePointName",
                ],
                "x": "VisitDate",
                "y": "InundatedArea",
                "color": "eWaterTiming",
                "Legend": True,
            },
            "Summary of your 'count_accuracy' for each site and sampling method (pooling across any multiple surveys)": {
                "note": "If you know you had variable accuracy in your sampling check you can see it reflected in the pie segments",
                "type": "pie",
                "table": "WaterbirdCounts",
                "group_by": ["SamplePointName", "SurveyMethod"],
                "category": "CountAccuracy",
                "value": "CountAccuracy",
            },
        }
    )
