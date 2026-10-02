from __future__ import annotations

import datetime

import pandas as pd
from reportlab.lib import colors

from configs.veg_config import VegQAReportConfig
from data_summary import qa_outliers
from lib.pdf_qa_report import (
    build_change_log_table_data,
    format_summary_dataframe,
    prepare_summary_table_data,
)


def test_vegetation_change_log_is_converted_to_pdf_table_rows() -> None:
    config = VegQAReportConfig()

    result = build_change_log_table_data(config.change_log, today=datetime.date(2026, 10, 1))

    assert result[0] == ["Date", "Changes"]
    assert result[1][0].getPlainText() == f"{config.change_log[0]['date']} NEW!"
    assert 'color="red"' in result[1][0].text
    assert result[1][1].getPlainText() == " ".join(config.change_log[0]["changes"][0].split())
    continuation_rows = result[2 : 1 + len(config.change_log[0]["changes"])]
    assert [row[0].getPlainText() for row in continuation_rows] == [
        "NEW!" for _ in config.change_log[0]["changes"][1:]
    ]
    assert all('color="red"' in row[0].text for row in continuation_rows)
    assert [row[1].getPlainText() for row in continuation_rows] == [
        " ".join(change.split()) for change in config.change_log[0]["changes"][1:]
    ]
    assert result[-1][0].getPlainText() == config.change_log[1]["date"]
    assert result[-1][1].getPlainText() == config.change_log[1]["changes"][0]


def test_recent_change_log_dates_get_a_red_new_badge() -> None:
    result = build_change_log_table_data(
        [
            {"date": "15 May 2026", "changes": ["First recent change", "Second recent change"]},
            {"date": "29 Mar 2026", "changes": ["Six month boundary"]},
            {"date": "February 2026", "changes": ["Older release"]},
            {"date": "October 2026", "changes": ["Future release"]},
        ],
        today=datetime.date(2026, 9, 29),
    )

    recent_date = result[1][0]
    assert recent_date.getPlainText() == "15 May 2026 NEW!"
    assert 'color="red"' in recent_date.text
    assert result[2][0].getPlainText() == "NEW!"
    assert 'color="red"' in result[2][0].text
    assert result[2][1].getPlainText() == "Second recent change"
    assert result[3][0].getPlainText() == "29 Mar 2026"
    assert result[4][0].getPlainText() == "February 2026"
    assert result[5][0].getPlainText() == "October 2026"


def test_format_summary_dataframe_distinguishes_small_values_from_zero() -> None:
    source = pd.DataFrame(
        {
            "value": [0.0, 0.009, -0.005, 0.01, -0.01, 1.234],
            "label": [
                "zero",
                "small positive",
                "small negative",
                "positive",
                "negative",
                "rounded",
            ],
        }
    )
    source_before = source.copy(deep=True)

    result = format_summary_dataframe(source)

    assert result["value"].tolist() == ["0.0", "<0.01", ">-0.01", "0.01", "-0.01", "1.23"]
    assert result["label"].tolist() == source["label"].tolist()
    pd.testing.assert_frame_equal(source, source_before)


def test_prepare_summary_table_data_omits_iqr_outlier_columns_in_any_position() -> None:
    source = pd.DataFrame(
        {
            "QA Check\nTotalCount\nmean\noutliers IQR\n[0.0, 10.0]": ["\u2713"],
            "ScientificName": ["Acrocephalus australis"],
            "TotalCount\nrecords": [68],
            "QA Check\nTotalCount\nrecords\noutliers IQR\n[0.0, 73.0]": ["\u2713"],
            "TotalCount\nmean": [5.09],
        }
    )

    result, _ = prepare_summary_table_data(source)

    assert result.columns.tolist() == [
        "ScientificName",
        "TotalCount\nrecords\nL/H [0.0, 73.0]",
        "TotalCount\nmean\nL/H [0.0, 10.0]",
    ]


def test_prepare_summary_table_data_moves_iqr_range_to_source_heading() -> None:
    outlier_column = "QA Check\nvalue\noutliers IQR\n[-8.1, 27.2]"
    source = pd.DataFrame({"value": [10], outlier_column: ["\u2713"]})

    result, _ = prepare_summary_table_data(source)

    assert result.columns.tolist() == ["value\nL/H [-8.1, 27.2]"]


def test_prepare_summary_table_data_highlights_source_cells_from_iqr_flags() -> None:
    source = pd.DataFrame(
        {
            "TotalCount\nrecords": [92, 1, 20],
            "ScientificName": ["Anas gracilis", "Ardea plumifera", "Anhinga novaehollandiae"],
            "QA Check\nTotalCount\nrecords\noutliers IQR\n[0.0, 73.0]": [
                "high\nTotalCount\nrecords",
                "low\nTotalCount\nrecords",
                "\u2713",
            ],
        }
    )

    _, backgrounds = prepare_summary_table_data(source)

    assert backgrounds == [
        ("BACKGROUND", (0, 1), (0, 1), colors.lightcoral),
        ("BACKGROUND", (0, 2), (0, 2), colors.lightblue),
    ]


def test_prepare_summary_table_data_highlights_no_data_iqr_flags() -> None:
    outlier_column = "QA Check\nTotalCount\nrecords\noutliers IQR\n[0.0, 73.0]"
    source = pd.DataFrame(
        {
            "TotalCount\nrecords": [0, 20],
            outlier_column: ["no data", "\u2713"],
        }
    )

    _, backgrounds = prepare_summary_table_data(source)

    assert backgrounds == [("BACKGROUND", (0, 1), (0, 1), colors.yellow)]


def test_prepare_summary_table_data_handles_skewed_outlier_columns() -> None:
    outlier_column = "QA Check\nTotalCount\nrecords\noutliers skewed"
    source = pd.DataFrame(
        {
            "TotalCount\nrecords": [1, 1000],
            outlier_column: ["low\nTotalCount\nrecords", "high\nTotalCount\nrecords"],
        }
    )

    result, backgrounds = prepare_summary_table_data(source)

    assert result.columns.tolist() == ["TotalCount\nrecords"]
    assert backgrounds == [
        ("BACKGROUND", (0, 1), (0, 1), colors.lightblue),
        ("BACKGROUND", (0, 2), (0, 2), colors.lightcoral),
    ]


def test_skewed_outlier_range_is_moved_to_pdf_source_heading() -> None:
    summary = pd.DataFrame({"value": [1, 2, 2, 2, 1000]})
    qa_outliers("value", summary, method="skewed")

    result, _ = prepare_summary_table_data(summary)

    assert result.columns.tolist() == ["value\nL/H [2.0, 2.0]"]


def test_prepare_summary_table_data_does_not_modify_source_dataframe() -> None:
    outlier_column = "QA Check\nvalue\noutliers IQR\n[0.0, 2.0]"
    source = pd.DataFrame({"value": [3], outlier_column: ["high\nvalue"]})
    source_before = source.copy(deep=True)

    prepare_summary_table_data(source)

    pd.testing.assert_frame_equal(source, source_before)
