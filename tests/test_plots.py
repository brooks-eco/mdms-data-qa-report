from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from plots import create_single_pie_plot


def test_create_single_pie_plot_aggregates_categories_and_sets_title() -> None:
    data = pd.DataFrame(
        {
            "ScientificName": ["Species one", "Species one", "Species two"],
            "PercentCover": [10.0, 20.0, 30.0],
        }
    )
    figure, axis = plt.subplots()

    create_single_pie_plot(
        axis,
        data,
        label_col="ScientificName",
        value_col="PercentCover",
        title_str="Test site",
    )

    assert axis.get_title() == "Test site"
    assert len(axis.patches) == 2
    plt.close(figure)
