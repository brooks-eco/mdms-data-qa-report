from __future__ import annotations

import datetime

import pandas as pd

from configs.veg_config import VegQAReportConfig
from lib.pdf_qa_report import build_change_log_table_data, format_summary_dataframe


def test_vegetation_change_log_is_converted_to_pdf_table_rows() -> None:
    config = VegQAReportConfig()

    result = build_change_log_table_data(config.change_log, today=datetime.date(2026, 9, 29))

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
