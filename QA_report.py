import logging
from pathlib import Path

from config import get_config
from data_summary import SummaryInputError, generate_effort_summaries, validate_summary_inputs
from lib.md_qa_report import MarkdownQAReport
from lib.pdf_qa_report import PDFQAReport
from load_data import load_data
from plots import create_plots, delete_existing_plots
from utils import ensure_path_exists, make_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _write_reports(
    config,
    output_path,
    group_name,
    group_id,
    group_long_name,
    data_source,
    data_summaries,
    plot_collection,
    data_date,
):
    if config.create_markdown_report:
        for summary_name, (_, summary_df) in data_summaries.items():
            output_csv = output_path / f"b_{make_safe(summary_name)}.csv"
            summary_df.to_csv(output_csv, index=False)
            logger.info("Data summary table '%s' saved to %s", summary_name, output_csv)

        markdown_report = MarkdownQAReport(output_path, group_name, group_long_name, config.report_title)
        markdown_report.create_report(
            data_summaries,
            plot_collection,
            data_source,
            config.start_date,
            config.end_date,
            config.plot_definitions,
            config.data_summary_definitions,
            group_id,
            data_date,
            data_url=f"{config.data_url}?group_id={group_id}",
            left_justify_columns=getattr(config, "left_justify_columns", None),
        )

    pdf_report = PDFQAReport(output_path, group_name, group_long_name, config.report_title)
    pdf_report.create_report(
        data_summaries,
        plot_collection,
        data_source,
        config.start_date,
        config.end_date,
        config.plot_definitions,
        config.data_summary_definitions,
        data_date,
        data_url=f"{config.data_url}?group_id={group_id}",
        left_justify_columns=getattr(config, "left_justify_columns", None),
        change_log=getattr(config, "change_log", None),
    )


def main():
    """Load configured data and generate its QA reports."""
    try:
        config = get_config()
    except ValueError as error:
        logger.error("%s", error)
        return

    output_path = Path(__file__).parent / config.output_path
    ensure_path_exists(output_path)
    group_name = config.testing_group_name
    (group_id, group_long_name) = (
        config.group_id.get(group_name, (None, None))
        if isinstance(group_name, str)
        else (None, None)
    )
    grouped_data, data_date = load_data(
        config.workbooks_path / config.input_file,
        group_name,
        group_id,
        config.filter_by_date,
        config.start_date,
        config.end_date,
        config.mdms_reports,
        joins_required=config.joins_required,
    )
    if not grouped_data:
        logger.error("No data loaded. Please check the input file and configuration.")
        return

    # generate a separate QA report for each group in the input data
    for group_name, tables in grouped_data.items():
        try:
            validate_summary_inputs(tables, config.data_summary_definitions)
        except SummaryInputError as error:
            logger.error("Cannot generate a report for group '%s': %s", group_name, error)
            continue

        data_summaries = generate_effort_summaries(
            tables, config.data_summary_definitions, group_name
        )
        plot_collection = create_plots(tables, data_summaries, config.plot_definitions, output_path)

        data_source = (
            f"<b>{config.input_file}</b>"
            if Path(config.input_file).suffix.startswith(".xls")
            else "MDMS data reports: "
            + ", ".join([f"<b>{shortcode}</b>" for shortcode in config.mdms_reports.values()])
        )

        _write_reports(
            config,
            output_path,
            group_name,
            group_id,
            group_long_name,
            data_source,
            data_summaries,
            plot_collection,
            data_date,
        )

        if not config.create_markdown_report:
            delete_existing_plots(output_path)


if __name__ == "__main__":
    main()
