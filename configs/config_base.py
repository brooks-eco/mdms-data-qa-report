from dataclasses import dataclass, field
from typing import Dict, List, Any
import pandas as pd
from pathlib import Path


@dataclass
class BaseQAReportConfig:
    testing_group_name: str = "LAC"
    start_date: pd.Timestamp = pd.to_datetime("2025-06-01")
    end_date: pd.Timestamp = pd.to_datetime("2026-07-31")
    filter_by_date: bool = True
    input_file: str = None
    create_markdown_report: bool = False
    workbooks_path: Path = Path("workbooks")
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

    filename = input_file.lower()

    config_map = {
        "veg": VegQAReportConfig,
        "fish": FishQAReportConfig,
        "waterbird": WaterbirdQAReportConfig,
    }

    for prefix, config_class in config_map.items():
        if filename.startswith(prefix):
            return config_class(**kwargs)

    raise ValueError(
        f"Error: Unrecognized input file prefix for '{input_file}'. Please ensure the filename starts with one of {list(config_map.keys())}."
    )
