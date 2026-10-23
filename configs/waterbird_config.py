from dataclasses import dataclass, field
from typing import Any

from config import BaseQAReportConfig


@dataclass
class WaterbirdQAReportConfig(BaseQAReportConfig):
    report_title: str = "Waterbird Data QA"
    change_log: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "date": "29 Sept 2026",
                "changes": [
                    "Check for missing data (surveys with no counts)",
                    "Check zero count samples use pseudo-taxon NO WATERBIRDS",
                    "improved method to flag high and low outliers",
                ],
            },
            {
                "date": "23 Feb 2026",
                "changes": ["Initial release"],
            },
        ]
    )
    left_justify_columns: set[str] = field(
        default_factory=lambda: {"BreedingNotes", "SamplePointName\nunique"}
    )
    data_url = "https://mdms.essolutions.com.au/workbooks/download/8"

    mdms_reports = {
        # table_name: report_API_shortcode
        "WaterbirdSurveys": "qa-waterbird-survey",
        "WaterbirdCounts": "waterbird-survey",
    }

    # WaterbirdTripGrouping GroupName	TripID	StartDate	EndDate
    # WaterbirdSurveys GroupName	TripID	SamplePointName	VisitDate	ReplicateNumber	StartTime	EndTime	Observers	SurveyMethod	WateringStage	InundatedArea	InundationSource	IncludesCew	AirTemp	Rain	CloudCoverPercent	WindSpeed	WindDirection	SurveyCoverage	Disturbance	CompDataID	Comment
    # WaterbirdCounts GroupName	SamplePointName	VisitDate	ReplicateNumber	ScientificName	ObsType	TotalCount	BroodsNests	BreedingNotes	CountAccuracy	Comment

    joins_required: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "left": "WaterbirdSurveys",
                "right": "WaterbirdTripGrouping",
                "on": ["TripID"],
                "how": "left",
            },
            {
                "left": "WaterbirdCounts",
                "right": "WaterbirdSurveys",
                "on": ["SamplePointName", "VisitDate", "ReplicateNumber"],
                "how": "left",
            },
            {
                "left": "WaterbirdSurveys",
                "right": "WaterbirdCounts",
                "on": ["SamplePointName", "VisitDate", "ReplicateNumber"],
                "how": "left",
                "summary": {"SpeciesRecordCount": {"TotalCount": "count"}},
            },
        ]
    )

    data_summary_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Effort: Ground survey - Number of sampling dates per site with max, min coverage": {
                "note": "Check this matches your field program.",
                "table": "WaterbirdSurveys",
                "group_by": ["SurveyMethod", "SamplePointName"],
                "summary": {"VisitDate": ["nunique"], "SurveyCoverage": ["min", "max"]},
                "filter": {"SurveyMethod": {"==": "ground"}},
            },
            "Alert: Survey efforts with no waterbird abundance records": {
                "note": (
                    "There should be no data here. Any displayed rows indicate missing data where a `Waterbird Survey` effort "
                    "(SamplePointName x VisitDate x ReplicateNumber)  has no matching `Waterbird Counts`. "
                    "If no waterbirds were counted there should be a single `No Waterbirds` "
                    "entry for the sample with count = 0. If the Survey could not be conducted "
                    "(poor weather or no access) then remove the Veg Survey Effort record."
                ),
                "table": "WaterbirdSurveys",
                "group_by": ["SamplePointName", "VisitDate", "ReplicateNumber"],
                "summary": {"SpeciesRecordCount": ["sum"]},
                "filter": {"SpeciesRecordCount": {"==": 0}},
            },
            "Effort: Acoustic survey - Number of sampling dates per site with max, min coverage": {
                "note": "Check this matches your field program.",
                "table": "WaterbirdSurveys",
                "group_by": ["SurveyMethod", "SamplePointName"],
                "summary": {"VisitDate": ["nunique"], "SurveyCoverage": ["min", "max"]},
                "filter": {"SurveyMethod": {"==": "acoustic"}},
            },
            "Counts: Species counts and richness per survey": {
                "note": "Look for outliers or oddballs results that may indicate data quality issues.",
                "table": "WaterbirdCounts",
                "group_by": ["SamplePointName", "SurveyMethod", "VisitDate", "ReplicateNumber"],
                "summary": {"TotalCount": "sum", "ScientificName": "nunique"},
            },
            "Ground Survey: Summary counts per species across all sites": {
                "note": (
                    "Sorted by mean abundance from high to low. Check ranking of common and rare species is correct. "
                    "Zero counts for individual species are generally not recorded so min is the minimum of a count&nbsp;>&nbsp;0. If there are no birds of any species present "
                    "at a site a 'No Waterbirds' entry with count=0 is required to ensure the survey effort is retained."
                ),
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "TotalCount": ["count", "min", "mean", "max", "sum"],
                },
                "filter": {"SurveyMethod": {"==": "ground"}},
                "sort": [["TotalCount", "mean", "desc"]],
            },
            "Acoustic surveys: Summary counts per species across all sites": {
                "note": (
                    "Zero counts are generally not included in the data apart from a 'No Waterbirds' "
                    "entry so the min is the minimum of the loaded records."
                ),
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "TotalCount": ["count", "min", "mean", "max", "sum"],
                },
                "filter": {"SurveyMethod": {"==": "acoustic"}},
            },
            "Taxa with ZERO count across all surveys and methods": {
                "note": (
                    "This table lists any Waterbird Species recorded with zero count. "
                    "Rows may include `No Waterbirds` records. Investigate any valid scientific species names that were recorded with zero counts."
                ),
                "table": "WaterbirdCounts",
                "group_by": [
                    "SamplePointName",
                    "SurveyMethod",
                    "VisitDate",
                    "ReplicateNumber",
                    "ScientificName",
                ],
                "summary": {"TotalCount": ["sum"]},
                "filter": {"TotalCount": {"==": 0}},
            },
            "Breeding: Broods/Nests summary per species pooling all samples": {
                "note": "High record count with low sum is because many zero counts are included in the rows.",
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "BroodsNests": ["count", "sum"],
                },
                "mark_no_data": False,
            },
            "Breeding Notes": {
                "note": (
                    "BreedingNotes is a free text field to record evidence of breeding. The text should "
                    "be meaningful and descriptive evidence of breeding or breeding related. Check the "
                    "data matches your notes, clearly interpretable and not ambiguous."
                ),
                "table": "WaterbirdCounts",
                "group_by": ["ScientificName"],
                "summary": {
                    "BreedingNotes": "unique",
                },
                # "filter": {"BreedingNotes": "is not null"},
            },
        }
    )

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time.
    # This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "Timing of site surveys (VisitDate) and SurveyCoverage for each SamplePointName": {
                "note": (
                    "Check this matches your field program and there are no surveys out of place or "
                    "missing (may be hard to see in plots but you can check against Table 3 above)."
                ),
                "type": "scatter",
                "table": "WaterbirdSurveys",
                # "group_by": ["SamplePointName","ReplicateNumber"], #dont group
                "x": "VisitDate",
                "y": "SurveyCoverage",
                "color": "SamplePointName",
                "Legend": True,
            },
            "Most common 15 taxa at each site (SamplePointName) across all dates": {
                "note": (
                    "Guidance: Dots are individual replicates across all dates. This allows you to visualise variability "
                    "in abundance through time at the site. Check for rare species with high counts and common species with "
                    "unexpectedly low counts. The x-axis reveals the combined range that will "
                    "vary among sampling locations. Compare to your knowledge (and data) for the sites. "
                    "Limited to 15 most common for display purposes."
                ),
                "type": "scatter",
                "table": "WaterbirdCounts",
                "group_by": [
                    "SamplePointName",
                ],  # removed ReplicateNumber - display as multiple dots
                "x": "TotalCount",
                "y": "ScientificName",
                "color": "ScientificName",
                "Legend": False,
                "y_axis_title": False,
                # "aggregate_function": "mean",  # may also want min, max, count
            },
            "Summary of 'InundatedArea' and eWaterTiming for each site survey": {
                "note": (
                    "Check that your pre, during, and post water delivery samples are represented. "
                    "Each Survey_Number is represented as a separate coloured dot."
                ),
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
                "note": (
                    "If you know you had variable accuracy in your sampling "
                    "check you can see it reflected in the pie segments"
                ),
                "type": "pie",
                "table": "WaterbirdCounts",
                "group_by": ["SamplePointName", "SurveyMethod"],
                "category": "CountAccuracy",
                "value": "CountAccuracy",
            },
        }
    )
