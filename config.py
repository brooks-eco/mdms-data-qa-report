from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class BaseQAReportConfig:
    # -----------------------------------------------------------------
    # None to produce reports for every GroupName in a global workbook
    # or can limit to just one group e.g. "LAC", MBG"

    testing_group_name: str | tuple[str] = "GNT"  # None for all

    # -----------------------------------------------------------------
    # workbooks are downloaded from MDMS manually and placed in the workbooks folder
    # -----------------------------------------------------------------

    # input_file:str = "waterbirdsurvey_20260220153534.xlsx"
    # input_file:str = "Fish_20260223111704.xlsx"
    # input_file ="FishLarvae_20260223230007.xlsx"
    # input_file ="waterbirdsurvey_20260224100311.xlsx"
    # input_file = "Vegetation_20260219153548.xlsx"
    # input_file:str = "Vegetation_20260303135639.xlsx"
    input_file: str = "vegetation"
    # input_file: str = "fish"
    # input_file: str = "fishlarvae"
    # input_file: str = "waterbirdsurvey"
    # input_file: str = "lignumdrone"

    start_date: pd.Timestamp = pd.to_datetime("2025-07-01")
    end_date: pd.Timestamp = pd.to_datetime("2026-07-31")

    filter_by_date: bool = True
    create_markdown_report: bool = False
    workbooks_path: Path = Path("workbooks")
    output_path: Path = Path("outputs")
    group_id: dict[str, tuple[int, str]] = field(
        default_factory=lambda: {
            "BBN": (16, "Border Barwon Namoi Area"),
            "DWG": (18, "Darling Warrego Area"),
            "GNT": (23, "Goulburn & Northern Tributaries Area"),
            "GWY": (17, "Gwydir Area"),
            "LAC": (20, "Lachlan Area"),
            "LBN": (15, "Lower Balonne Area"),
            "LWM": (24, "Lower Murray & CLLMM Area"),
            "MAC": (19, "Macquarie Area"),
            "MBG": (21, "Murrumbidgee Area"),
            "MMY": (22, "Mid-Murray Area"),
            "MDB": (14, "Basin-scale Project"),
            # deprecated area codes
            # "BAL": (15, "Lower Balonne Area"),
            # "DAR": (18,"Darling Warrego Area"),
            # "LMY": (24,"Lower Murray & CLLMM Area"),
        }
    )


def _config_types() -> dict[str, type[BaseQAReportConfig]]:
    # Import specific configs here to avoid circular dependency
    from configs.fish_config import FishQAReportConfig
    from configs.fish_larvae_config import FishLarvaeQAReportConfig
    from configs.lignum_drone_config import LignumDroneQAReportConfig
    from configs.veg_config import VegQAReportConfig
    from configs.waterbird_config import WaterbirdQAReportConfig

    return {
        "vegetation": VegQAReportConfig,
        "fish": FishQAReportConfig,
        "waterbirdsurvey": WaterbirdQAReportConfig,
        "fishlarvae": FishLarvaeQAReportConfig,
        "lignumdrone": LignumDroneQAReportConfig,
    }


def get_config(**kwargs) -> BaseQAReportConfig:
    """Choose a theme from a data type or workbook basename, applying overrides."""
    input_file = kwargs.get("input_file", BaseQAReportConfig.input_file)
    filename = Path(input_file).stem.lower()
    config_map = _config_types()

    for prefix, config_class in config_map.items():
        if filename.split("_")[0].lower() == prefix.lower():
            return config_class(**kwargs)

    raise ValueError(
        f"Error: Unrecognized input file prefix for '{input_file}'. Please ensure the filename starts with one of {list(config_map.keys())}."
    )


def _read_choice(prompt: str) -> str:
    choice = input(prompt).strip()
    if choice.lower() == "q":
        raise KeyboardInterrupt
    return choice


def _select_workbook(group_name: str) -> BaseQAReportConfig:
    while True:
        value = _read_choice("Workbook filename or path (q to quit): ").strip("\"'")
        path = Path(value).expanduser()
        if path.suffix.lower() not in {".xls", ".xlsx", ".xlsm"}:
            print("Enter an Excel workbook filename or path (.xls, .xlsx, .xlsm).")
            continue
        # Bare filenames are loaded from workbooks_path; explicit paths use the working directory.
        if path.parent != Path() or "/" in value or "\\" in value:
            path = path.resolve()
        try:
            return get_config(testing_group_name=group_name, input_file=str(path))
        except ValueError as error:
            print(error)


def select_config() -> BaseQAReportConfig:
    """Prompt for a monitoring group and an MDMS data type or local workbook."""
    groups = BaseQAReportConfig().group_id
    group_choices = {str(number): name for number, name in enumerate(groups, start=1)}
    print("MDMS QA Report Generator")
    print("-" * 24)
    print(f"Start date: {BaseQAReportConfig().start_date:%Y-%m-%d}")
    print(f"End date: {BaseQAReportConfig().end_date:%Y-%m-%d}")
    print("\nSelect monitoring group (q to quit):")
    for number, name in group_choices.items():
        print(f"  {number}. {name} - {groups[name][1]}")
    while True:
        choice = _read_choice("Group number or code: ").upper()
        group_name = group_choices.get(choice, choice)
        if group_name in groups:
            break
        print("Invalid group. Choose a listed number or group code.")

    data_choices = {str(number): name for number, name in enumerate(_config_types(), start=1)}
    workbook_choice = str(len(data_choices) + 1)
    print("\nSelect data source (q to quit):")
    for number, name in data_choices.items():
        print(f"  {number}. {name} (MDMS)")
    print(f"  {workbook_choice}. Excel workbook")
    while True:
        choice = _read_choice("Data source number or type: ").lower()
        if choice == workbook_choice:
            return _select_workbook(group_name)
        data_type = data_choices.get(choice, choice)
        if data_type in data_choices.values():
            return get_config(testing_group_name=group_name, input_file=data_type)
        print("Invalid data source. Choose a listed number or data type.")
