from dataclasses import dataclass, field
from typing import Dict, List, Set, Any
from configs.config_base import BaseQAReportConfig



@dataclass
class WaterbirdQAReportConfig(BaseQAReportConfig):
    group_name_source_sheet: str = "WaterbirdSurveys"  # The sheet name to look for GroupName values. Adjust if your grouping variable is in a different sheet.
    report_title: str = "Waterbird QA Report"
    left_justify_columns: Set[str] = field(default_factory=lambda: {"BreedingNotes"})
    data_url = "https://mdms.essolutions.com.au/workbooks/download/8"
    

    # WaterbirdSurveys: SamplePointName	VisitDate	SurveyNumber	StartTime	EndTime	Observers	SurveyMethod	eWaterTiming	InundatedArea	AirTemp	Rain	CloudCoverPercent	WindSpeed	WindDirection	SurveyCoverage	Disturbance	CompDataID	Comment
    # WaterbirdCounts: SamplePointName	VisitDate	SurveyNumber	ScientificName	ObsType	TotalCount	BroodsNests	BreedingNotes	CountAccuracy	Comment

    workbook: Dict[str, List[str]] = field(default_factory=lambda: {
        "WaterbirdSurveys": [
            "SamplePointName", "VisitDate", "SurveyNumber", "StartTime", "EndTime", 
            "Observers", "SurveyMethod", "eWaterTiming", "InundatedArea", "AirTemp", 
            "Rain", "CloudCoverPercent", "WindSpeed", "WindDirection", "SurveyCoverage", 
            "Disturbance", "CompDataID", "Comment"
        ],
        "WaterbirdCounts": [
            "SamplePointName", "VisitDate", "SurveyNumber", "ScientificName", "ObsType", 
            "TotalCount", "BroodsNests", "BreedingNotes", "CountAccuracy", "Comment"
        ],
    })


    joins_required: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "WaterbirdCounts": {
            "right": "WaterbirdSurveys",
            "on": ["SamplePointName", "VisitDate", "SurveyNumber"],
            "how": "left",
        },
    })

    data_summary_definitions: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "Effort: Number of survey events per SamplePointName": {
            "note": "Check this matches your field program and that all surveys are recorded for each site.",
            "table": "WaterbirdSurveys",
            "group_by": ["SamplePointName",],
            "summary": {
                "VisitDate": "nunique",
                "SurveyNumber": "count",
                #"SurveyCoverage": ["min","max",],
              },
        },
        
        "Effort: SampleDates and the number of sites visited on each": {
            "note": "Check this matches your field program.  Dates are important for accurate temporal analyses and alignment of observations to watering actions.",
            "table": "WaterbirdSurveys",
            "group_by": ["VisitDate"],
            "summary": {
                "SamplePointName": "nunique",
            },
        },
        
        "Effort: Number of dates recorded for each survey": {
            "note": "Check this matches your field program. Should each survey have multiple dates?. Long durations may indicate issue with SurveyNumber assignment. Dates are important for accurate temporal analyses and alignment of observations to watering actions.",
            "table": "WaterbirdSurveys",
            "group_by": ["SamplePointName","SurveyNumber"],
            "summary": {
                "VisitDate": ["count","min","max"],
              },
        },


        "Counts: Species counts and richness per survey": {
            "note": "Look for outliers or oddballs results that may indicate data quality issues.",
            "table": "WaterbirdCounts",
            "group_by": ["SamplePointName", "SurveyNumber"],
            "summary": {
                "TotalCount": "sum",
                "ScientificName": "nunique"
            },
        },
        "Counts: Summary per species": {
            "note": "Zero counts are generally not included in the data apart from a 'No Waterbirds' entry so the min is the minimum of the loaded records.",
            "table": "WaterbirdCounts",
            "group_by": ["ScientificName"],
            "summary": {
                "TotalCount": ["count", "min", "mean", "max", "sum"],
            },
        },
        "Breeding: Broods/Nests summary per species": {
            "note": "High record count with low sum is because many zero counts are included in the rows.",
            "table": "WaterbirdCounts",
            "group_by": ["ScientificName"],
            "summary": {
                "BroodsNests": ["count","sum"],
            },
            "filter": {"BroodsNests": {">": 0}},
        },
        "Breeding Notes": {
            "note": "BreedingNotes is a free text field to record evidence of breeding. The text should be meaningful and descriptive. Check you can interpret your notes.  If you see a bunch of numbers in this table you have entered data in the wrong column and a correction is required!",
            "table": "WaterbirdCounts",
            "group_by": ["ScientificName"],
            "summary": {
                "BreedingNotes": "unique",
            },
            "filter": {"BreedingNotes": {"!=": ""}},
        },
        
        
    })

    # plot of multiple pie charts showing species composition (percent cover) by plot and sampling time. This will help identify if there are any plots or sampling times that have unusual species composition that may indicate data quality issues.
    plot_definitions: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        
        "Timing of site surveys (SamplePointName x SurveyNumber)": {
            "note": "Check this matches your field program and there are no surveys out of place or missing (may be hard to see in plots but should be visible in tables above).",
            "type": "scatter",
            "table": "WaterbirdSurveys",
            #"group_by": ["SamplePointName","SurveyNumber"], #dont group
            "x": "VisitDate",
            "y": "SurveyCoverage",
            "color": "SamplePointName",
            "Legend": True,
        },
        "Survey coverage (SamplePointName x SurveyNumber)": {
            "note": "Check this matches your field program and there are no surveys out of place or missing (may be hard to see in plots but should be visible in tables above).",
            "type": "scatter",
            "table": "WaterbirdSurveys",
            "group_by": ["SurveyNumber"], #dont group
            "x": "SurveyCoverage",
            "y": "SamplePointName",
            "color": "SamplePointName",
            "Legend": True,
            #"aggregate_function": "median"
        },
        
        "Most common 15 taxa in each site survey (SamplePointName x SurveyNumber)": {
            "note": "Guidance: LImited to 15 for display purposes. Scan for outliers and oddballs e.g. species with high counts that you know to be rare. Use the plots to visualise the proportional distribution of species at each site to compare to your knowledge (and data) for the sites.",
            "type": "scatter",
            "table": "WaterbirdCounts", 
            "group_by": ["SamplePointName","SurveyNumber"],
            "x": "TotalCount",
            "y": "ScientificName",
            "color": "ScientificName",
            "Legend": False,
            "aggregate_function": "sum", #may also want min, max, count
        },
        "Summary of 'eWaterTiming' for each site survey (SamplePointName x SurveyNumber)": {
            "note": "Knowing the alignment of waterbird observations to eWater management is a critical requirement of the program. Unknowns should need to be populated through desktop analysis or input from water managers.",
            "type": "pie",
            "table": "WaterbirdSurveys",
            "group_by": ["SamplePointName","SurveyNumber"],
            "category": "eWaterTiming",
            "value": "eWaterTiming",
        },
        "Summary of 'InundatedArea' for each site survey (SamplePointName x SurveyNumber)": {
            "note": "The pies will only have segments if there were multiple sample dates with different inundation conditions per survey.",
            "type": "pie",
            "table": "WaterbirdSurveys",
            "group_by": ["SamplePointName","SurveyNumber"],
            "category": "InundatedArea",
            "value": "InundatedArea",
        },
        "Summary of your 'count_accuracy' for each site (pooling across any multiple surveys)": {
            "note": "If you know you had variable accuracy in your sampling check you can see it reflected in the pie segments",
            "type": "pie",
            "table": "WaterbirdCounts",
            "group_by": ["SamplePointName"],
            "category": "CountAccuracy",
            "value": "CountAccuracy",
        },
        
        "Summary of your 'count_accuracy' for each site (pooling across any multiple surveys)": {
            "note": "If you know you had variable accuracy in your sampling check you can see it reflected in the pie segments",
            "type": "pie",
            "table": "WaterbirdCounts",
            "group_by": ["SamplePointName"],
            "category": "CountAccuracy",
            "value": "CountAccuracy",
        },
        
    })