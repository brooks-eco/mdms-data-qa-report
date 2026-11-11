from __future__ import annotations

import io
from pathlib import Path

import pytest

import config
from QA_report import main


@pytest.fixture
def menu_input(monkeypatch):
    def supply(*answers: str) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(answers) + "\n"))

    return supply


@pytest.mark.parametrize(
    ("choice", "expected"),
    [("1", "BBN"), ("5", "LAC"), ("11", "MDB"), (" mbg ", "MBG")],
)
def test_menu_selects_group(menu_input, choice: str, expected: str) -> None:
    menu_input(choice, "vegetation")

    selected = config.select_config()

    assert selected.testing_group_name == expected


def test_menu_displays_all_configured_groups(menu_input, capsys) -> None:
    menu_input("LAC", "fish")

    config.select_config()

    output = capsys.readouterr().out
    for shortcode, (_, description) in config.BaseQAReportConfig().group_id.items():
        assert f"{shortcode} - {description}" in output


@pytest.mark.parametrize(
    ("choice", "expected", "title"),
    [
        ("1", "vegetation", "Vegetation Data QA"),
        ("2", "fish", "Fish Data QA"),
        ("3", "waterbirdsurvey", "Waterbird Data QA"),
        ("4", "fishlarvae", "Fish Larvae Data QA"),
        ("5", "lignumdrone", "Lignum Drone Data QA"),
        (" FISH ", "fish", "Fish Data QA"),
    ],
)
def test_menu_selects_data_type(menu_input, choice: str, expected: str, title: str) -> None:
    menu_input("LAC", choice)

    selected = config.select_config()

    assert selected.input_file == expected
    assert selected.report_title == title


@pytest.mark.parametrize("invalid", ["", "0", "12", "unknown"])
def test_menu_retries_invalid_group(menu_input, invalid: str) -> None:
    menu_input(invalid, "LAC", "fish")

    selected = config.select_config()

    assert selected.testing_group_name == "LAC"


@pytest.mark.parametrize("invalid", ["", "0", "7", "unknown", "Fish_bad.csv"])
def test_menu_retries_invalid_data_source(menu_input, invalid: str) -> None:
    menu_input("LAC", invalid, "vegetation")

    selected = config.select_config()

    assert selected.input_file == "vegetation"


def test_menu_accepts_workbook_filename(menu_input) -> None:
    menu_input("LAC", "6", "Fish_20260223111704.xlsx")

    selected = config.select_config()

    assert selected.input_file == "Fish_20260223111704.xlsx"
    assert selected.report_title == "Fish Data QA"


def test_menu_accepts_quoted_absolute_workbook_path(menu_input, tmp_path: Path) -> None:
    workbook = tmp_path / "folder with spaces" / "Vegetation_export.xlsx"
    menu_input("LAC", "6", f'"{workbook}"')

    selected = config.select_config()

    assert Path(selected.input_file) == workbook
    assert selected.report_title == "Vegetation Data QA"


def test_menu_resolves_relative_workbook_path(menu_input) -> None:
    menu_input("LAC", "6", "workbooks/Fish_export.xlsx")

    selected = config.select_config()

    assert Path(selected.input_file) == Path("workbooks/Fish_export.xlsx").resolve()


def test_menu_resolves_explicit_current_directory_path(menu_input) -> None:
    menu_input("LAC", "6", "./Fish_export.xlsx")

    selected = config.select_config()

    assert Path(selected.input_file) == Path("Fish_export.xlsx").resolve()


def test_menu_retries_invalid_workbook_prefix(menu_input) -> None:
    menu_input("LAC", "6", "Unknown_export.xlsx", "Fish_export.xlsx")

    selected = config.select_config()

    assert selected.input_file == "Fish_export.xlsx"


def test_config_infers_theme_from_workbook_basename(tmp_path: Path) -> None:
    workbook = tmp_path / "other_exports" / "Fish.xlsx"

    selected = config.get_config(input_file=str(workbook))

    assert selected.report_title == "Fish Data QA"
    assert selected.input_file == str(workbook)


@pytest.mark.parametrize("answers", [("q",), ("LAC", "q"), ("LAC", "6", "q")])
def test_main_allows_cancelling_menu(menu_input, capsys, answers: tuple[str, ...]) -> None:
    menu_input(*answers)

    main()

    assert "Cancelled" in capsys.readouterr().out


def test_main_handles_closed_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    main()

    assert "Cancelled" in capsys.readouterr().out
