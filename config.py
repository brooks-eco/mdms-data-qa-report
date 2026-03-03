from dataclasses import dataclass, field
from typing import Dict, List, Any
import pandas as pd
from pathlib import Path


@dataclass
class BaseQAReportConfig:
    # -----------------------------------------------------------------
    # None to produce reports for every GroupName in a global workbook
    # or can limit to just one group e.g. "LAC", MBG"

    testing_group_name: str = "GWY" #None for all

    # -----------------------------------------------------------------
    # workbooks are downloaded from MDMS manually and placed in the workbooks folder
    # -----------------------------------------------------------------

    # input_file:str = "waterbirdsurvey_20260220153534.xlsx"
    #input_file:str = "Fish_20260223111704.xlsx"
    # input_file ="FishLarvae_20260223230007.xlsx"
    # input_file ="waterbirdsurvey_20260224100311.xlsx"
    #input_file = "Vegetation_20260219153548.xlsx"
    #input_file:str = "Vegetation_20260303135639.xlsx"
    input_file:str = "Fish_20260304020619.xlsx"
    
    
    

    start_date: pd.Timestamp = pd.to_datetime("2024-06-01")
    end_date: pd.Timestamp = pd.to_datetime("2025-07-31")

    filter_by_date: bool = True
    create_markdown_report: bool = False
    workbooks_path: Path = Path("workbooks")
    output_path: Path = Path("outputs")
    group_id: Dict[str, int] = field(
        default_factory=lambda: {
            "BAL": 15,
            "BBN": 16,
            "DAR": 18,
            "GNT": 23,
            "GWY": 17,
            "LAC": 20,
            "LMY": 24,
            "MAC": 19,
            "MBG": 21,
            "MMY": 22,
        }
    )


def get_config(**kwargs) -> BaseQAReportConfig:
    """
    Factory function to get the correct configuration object.
    It determines the config type from 'input_file' kwarg or the default.
    Any provided kwargs will override the defaults in the chosen config class.
    """
    if "input_file" in kwargs:
        input_file = kwargs["input_file"]
    else:
        input_file = BaseQAReportConfig.input_file  # Get default from class

    # Import specific configs here to avoid circular dependency
    from configs.fish_config import FishQAReportConfig
    from configs.veg_config import VegQAReportConfig
    from configs.waterbird_config import WaterbirdQAReportConfig
    from configs.fish_larvae_config import FishLarvaeQAReportConfig


    filename = input_file.lower()

    config_map = {
        "vegetation": VegQAReportConfig,
        "fish": FishQAReportConfig,
        "waterbirdsurvey": WaterbirdQAReportConfig,
        "fishlarvae": FishLarvaeQAReportConfig,
    }

    for prefix, config_class in config_map.items():
        if filename.split("_")[0].lower() == prefix.lower():
            return config_class(**kwargs)


    raise ValueError(
        f"Error: Unrecognized input file prefix for '{input_file}'. Please ensure the filename starts with one of {list(config_map.keys())}."
    )
