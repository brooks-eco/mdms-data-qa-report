from __future__ import annotations

import pandas as pd

from utils import filter_df


def test_filter_df_applies_multiple_public_filter_conditions() -> None:
    data = pd.DataFrame(
        {
            "value": [1, 5, 10, 20],
            "status": ["draft", "ready", "ready", None],
        }
    )

    result = filter_df(
        {"value": {">": 4, "<": 20}, "status": "is not null"},
        data,
        task_type="summary",
        task_name="fixture",
    )

    assert result.to_dict("records") == [
        {"value": 5, "status": "ready"},
        {"value": 10, "status": "ready"},
    ]
