from dataclasses import dataclass, field
from typing import Dict, List, Any
from configs.config_base import BaseQAReportConfig



@dataclass
class WaterbirdQAReportConfig(BaseQAReportConfig):
    group_name_source_sheet: str = "WaterbirdSurveys"  # The sheet name to look for GroupName values. Adjust if your grouping variable is in a different sheet.
    report_title: str = "Waterbird QA Report"

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
            "table": "WaterbirdSurveys",
            "group_by": ["SamplePointName",],
            "summary": {
                "SurveyNumber": "nunique",
              },
        },
        
        "Effort: SampleDates and the number of sites visited on each": {
            "table": "WaterbirdSurveys",
            "group_by": ["VisitDate"],
            "summary": {
                "SamplePointName": "nunique",
            },
        },
        
        
        "Effort: Number of dates recorded for each survey": {
            
            "table": "WaterbirdSurveys",
            "group_by": ["SamplePointName","SurveyNumber"],
            "summary": {
                "VisitDate": "nunique",
              },
        },


        "Counts: Species counts and richness per survey": {
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
            "note": "BreedingNotes is a free text field to record evidence of breeding. The text should be meaningful and descriptive. Check you can interpret your notes.  If you see a bunch of numbers in this table you may have entered data in the wrong column!",
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
        
      
        
        "Most common 15 taxa in each site survey": {
            "note": "Guidance: Scan for outliers and oddballs e.g. species with high counts that you know to be rare. Use the plots to visualise the proportional distribution of species at each site to compare to your knowledge (and data) for the sites.",
            "type": "scatter",
            "table": "WaterbirdCounts", 
            "group_by": ["SamplePointName","SurveyNumber"],
            "x": "TotalCount",
            "y": "ScientificName",
            "color": "ScientificName",
            "Legend": False,
            "aggregate_function": "sum", #may also want min, max, count
        },
        "Your assessment of count accuracy by site (SamplePointName) and SurveyNumber": {
            #"note": "Top 5 species by count for each survey. Scan for oddballs/outliers.",
            "type": "pie",
            "table": "WaterbirdCounts",
            "group_by": ["SamplePointName","SurveyNumber"],
            "category": "CountAccuracy",
            "value": "CountAccuracy",
        },

    })