from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class BaseQAReportConfig:
    # -----------------------------------------------------------------
    # None to produce reports for every GroupName in a global workbook
    # or can limit to just one group e.g. "LAC", MBG"

    testing_group_name: str | tuple[str] = "LAC"  # None for all

    # -----------------------------------------------------------------
    # workbooks are downloaded from MDMS manually and placed in the workbooks folder
    # -----------------------------------------------------------------

    # input_file:str = "waterbirdsurvey_20260220153534.xlsx"
    # input_file:str = "Fish_20260223111704.xlsx"
    # input_file ="FishLarvae_20260223230007.xlsx"
    # input_file ="waterbirdsurvey_20260224100311.xlsx"
    # input_file = "Vegetation_20260219153548.xlsx"
    # input_file:str = "Vegetation_20260303135639.xlsx"
    # input_file:str = "Fish_20260316170814.xlsx"
    # input_file: str = "Fish_20260602105327.xlsx"
    input_file: str = "Vegetation_20260930020958.xlsx"
    # input_file: str = "vegetation"
    #input_file: str = "fish"
    # input_file: str = "fishlarvae"
    # input_file: str = "FishLarvae_20260929165520.xlsx"
    # input_file: str = "Fish_20260930222835.xlsx"
    # input_file: str = "waterbirdsurvey_20261001182845.xlsx"
    #input_file: str = "waterbirdsurvey"

    start_date: pd.Timestamp = pd.to_datetime("2025-06-01")
    end_date: pd.Timestamp = pd.to_datetime("2026-07-31")

    filter_by_date: bool = True
    create_markdown_report: bool = False
    workbooks_path: Path = Path("workbooks")
    output_path: Path = Path("outputs")
    group_id: dict[str, tuple[int, str]] = field(
        default_factory=lambda: {
            # "BAL": (15, "Lower Balonne Area"),
            "BBN": (16, "Border Barwon Namoi Area"),
            # "DAR": (18,"Darling Warrego Area"),
            "DWG": (18, "Darling Warrego Area"),
            "GNT": (23, "Goulburn & Northern Tributaries Area"),
            "GWY": (17, "Gwydir Area"),
            "LAC": (20, "Lachlan Area"),
            "LBN": (15, "Lower Balonne Area"),
            "LWM": (24, "Lower Murray & CLLMM Area"),
            # "LMY": (24,"Lower Murray & CLLMM Area"),
            "MAC": (19, "Macquarie Area"),
            "MBG": (21, "Murrumbidgee Area"),
            "MMY": (22, "Mid-Murray Area"),
            "MDB": (14, "Basin-scale Project"),
        }
    )


def get_config(**kwargs) -> BaseQAReportConfig:
    """
    Factory function to get the correct configuration object.
    It determines the config type from 'input_file' kwarg or the default.
    Any provided kwargs will override the defaults in the chosen config class.
    """
    input_file = kwargs.get("input_file", BaseQAReportConfig.input_file)

    # Import specific configs here to avoid circular dependency
    from configs.fish_config import FishQAReportConfig
    from configs.fish_larvae_config import FishLarvaeQAReportConfig
    from configs.veg_config import VegQAReportConfig
    from configs.waterbird_config import WaterbirdQAReportConfig

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
