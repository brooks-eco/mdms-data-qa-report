import datetime
import logging
from html import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    CondPageBreak,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


def format_summary_dataframe(summary_df):
    """Format summary values for display without modifying the source dataframe."""
    formatted = summary_df.copy()
    numeric_columns = formatted.select_dtypes(include=["number"]).columns

    def format_number(value):
        if pd.isna(value):
            return str(value)
        if 0 < value < 0.01:
            return "<0.01"
        if -0.01 < value < 0:
            return ">-0.01"
        return str(round(value, 2))

    for column in numeric_columns:
        formatted[column] = formatted[column].map(format_number)

    return formatted.astype(str)


def prepare_summary_table_data(summary_df):
    """Remove IQR QA columns and create source-cell background style commands."""
    outlier_sources = {}
    for column in summary_df.columns:
        heading_lines = [line.strip() for line in str(column).splitlines()]
        marker_positions = [
            index
            for index, line in enumerate(heading_lines)
            if line.lower() in {"outliers iqr", "outliers skewed"}
        ]
        if not marker_positions:
            continue

        marker_position = marker_positions[0]
        source_lines = heading_lines[:marker_position]
        if source_lines and source_lines[0].lower() == "qa check":
            source_lines = source_lines[1:]
        range_text = next(
            (
                line
                for line in heading_lines[marker_position + 1 :]
                if line.startswith("[") and line.endswith("]")
            ),
            None,
        )
        outlier_sources[column] = ("\n".join(source_lines), range_text)

    visible_df = summary_df.drop(columns=list(outlier_sources))
    formatted_df = format_summary_dataframe(visible_df)
    visible_column_positions = {
        str(column): index for index, column in enumerate(visible_df.columns)
    }
    background_commands = []

    for outlier_column, (source_column, _) in outlier_sources.items():
        column_position = visible_column_positions.get(source_column)
        if column_position is None:
            continue

        normalized_source = " ".join(source_column.split())
        for row_position, flag in enumerate(summary_df[outlier_column], start=1):
            normalized_flag = " ".join(str(flag).split())
            if normalized_flag == f"high {normalized_source}":
                background_commands.append(
                    (
                        "BACKGROUND",
                        (column_position, row_position),
                        (column_position, row_position),
                        colors.lightcoral,
                    )
                )
            elif normalized_flag == f"low {normalized_source}":
                background_commands.append(
                    (
                        "BACKGROUND",
                        (column_position, row_position),
                        (column_position, row_position),
                        colors.lightblue,
                    )
                )
            elif normalized_flag == "no data":
                background_commands.append(
                    (
                        "BACKGROUND",
                        (column_position, row_position),
                        (column_position, row_position),
                        colors.yellow,
                    )
                )
    display_headings = {
        source_column: f"{source_column}\nL/H {range_text}"
        for source_column, range_text in outlier_sources.values()
        if source_column in visible_column_positions and range_text is not None
    }
    formatted_df = formatted_df.rename(columns=display_headings)

    return formatted_df, background_commands


def build_change_log_table_data(change_log, today=None):
    """Convert grouped thematic changelog entries to PDF table rows."""
    rows = [["Date", "Changes"]]
    today = today or datetime.datetime.now(tz=datetime.UTC).date()
    cutoff = pd.Timestamp(today) - pd.DateOffset(months=6)
    old_date_style = ParagraphStyle("ChangeLogDate", fontSize=9, alignment=1)
    new_date_style = ParagraphStyle("ChangeLogDate", fontSize=9, alignment=2)
    changelog_style = ParagraphStyle("ChangeLogEntry", fontSize=9)

    for release in change_log:
        release_date = _parse_change_log_date(release["date"])
        is_new = release_date is not None and cutoff.date() < release_date <= today
        for index, change in enumerate(release["changes"]):
            date_style = old_date_style
            display_date = release["date"] if index == 0 else ""
            if is_new:
                date_text = f"{escape(display_date)} " if display_date else ""
                display_date = f'{date_text}<font color="red"><b>NEW!</b></font>'
                date_style = new_date_style
            rows.append([Paragraph(display_date, date_style), Paragraph(change, changelog_style)])
    return rows


def _parse_change_log_date(date_text):
    """Parse supported human-readable change-log dates, returning None if unknown."""
    normalized_text = date_text.replace("Sept ", "Sep ")
    for date_format in (
        "%d %b %Y",
        "%d %B %Y",
        "%b %Y",
        "%B %Y",
        "%Y-%m-%d",
    ):
        try:
            return (
                datetime.datetime.strptime(normalized_text, date_format)
                .replace(tzinfo=datetime.UTC)
                .date()
            )
        except ValueError:
            continue
    return None


class PDFQAReport:
    """
    Handles the generation of the PDF QA Report using ReportLab.
    """

    def __init__(self, output_path, group_name, group_long_name, report_title_str):
        """
        Initializes the PDF report generator.

        Args:
            output_path (Path): Directory to save the PDF report.
            group_name (str): Name of the group (e.g., "MAC", "LAC").
            report_title_str (str): Title of the report.
        """
        self.output_path = output_path
        self.group_name = group_name
        self.group_long_name = group_long_name
        self.report_title_str = report_title_str
        # get date-time stamp to include in filename
        date_stamp = datetime.datetime.now(tz=datetime.UTC).astimezone().strftime("%Y%m%d")
        self.filename = self._make_safe(f"{group_name}_{report_title_str}_{date_stamp}.pdf")
        self.pdf_report_path = output_path / self.filename

        self.doc = SimpleDocTemplate(
            str(self.pdf_report_path),
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20,
        )

        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.elements = []

    def _make_safe(self, filename):
        """Sanitizes a filename string."""
        return filename.replace(" ", "_").replace("'", "").replace(":", "").replace("/", "-")

    def _setup_styles(self):
        """
        Configures the paragraph styles used in the report.
        Defines custom styles for headers, titles, and normal text to ensure consistent formatting.
        """
        self.styles.add(ParagraphStyle(name="Centered", alignment=TA_CENTER))
        self.h1 = self.styles["Heading1"]
        self.h1.spaceBefore = 20

        self.title_style = self.styles["Title"]
        self.title_style.spaceBefore = 10
        self.title_style.spaceAfter = 10

        self.normal_style = ParagraphStyle(
            "Normal",
            parent=self.styles["Normal"],
            fontSize=9,
        )
        self.centred_italics_style = ParagraphStyle(
            "CenteredItalics",
            parent=self.styles["Italic"],
            alignment=TA_CENTER,
        )
        self.bold_style = ParagraphStyle(
            "Bold",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
        )

    def create_report(
        self,
        data_summaries,
        plot_collection,
        data_source,
        start_dt,
        end_dt,
        plot_definitions,
        data_summary_definitions,
        data_date,
        data_url=None,
        left_justify_columns=None,
        change_log=None,
    ):
        """
        Assembles and builds the PDF report.

        Args:
            data_summaries (dict): Dictionary of summary DataFrames.
            plot_collection (dict): Dictionary of generated plot filenames.
            input_filename (str): Name of the input data file.
            start_dt (datetime): Start date of the data range.
            end_dt (datetime): End date of the data range.
            plot_definitions (dict): Configuration for plots (includes notes).
            data_summary_definitions (dict): Configuration for summaries (includes notes).
            group_id (str): ID of the group for URL generation.
            data_date (str): Date string of when the data was exported.
            data_url (str, optional): URL to download the data.
            left_justify_columns (set, optional): Set of column names to left-justify in tables.
            change_log (list, optional): Thematic report changes grouped by release date.
        """
        # Header and Title
        self.elements.append(
            Image(
                "resources//CEWH crest and FLOW-MER-inline_CMYK.png",
                width=13.0 * cm,
                height=2.5 * cm,
                kind="proportional",
                hAlign="CENTER",
            )
        )
        self.elements.append(Spacer(1, 9))

        title = Paragraph(f"{self.report_title_str} - {self.group_long_name}", self.title_style)
        self.elements.append(title)

        start_year = start_dt.year
        end_year = end_dt.year
        self.elements.append(
            Paragraph(f"{start_year}/{end_year} water-year", self.centred_italics_style)
        )

        self.elements.append(Spacer(1, 9))

        source_data = [
            [
                Paragraph("Data Source:", self.normal_style),
                Paragraph(data_source, self.normal_style),
                Image(
                    f"resources//{self.group_name}.png",
                    width=3.5 * cm,
                    height=3.5 * cm,
                    kind="proportional",
                    hAlign="CENTER",
                ),
            ],
            [
                Paragraph("Exported from MDMS:", self.normal_style),
                Paragraph(f"<b>{data_date}</b>", self.normal_style),
            ],
            [
                Paragraph("Date Range:", self.normal_style),
                Paragraph(
                    f"<b>{start_dt.strftime('%Y-%m-%d')}</b> to <b>{end_dt.strftime('%Y-%m-%d')}</b>",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("This QA report generated:", self.normal_style),
                Paragraph(
                    f"<b>{datetime.datetime.now(tz=datetime.UTC).astimezone().strftime('%Y-%m-%d %H:%M:%S')}</b>",
                    self.normal_style,
                ),
            ],
        ]
        source_table = Table(source_data, colWidths=[4.5 * cm, 11 * cm, None])
        source_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("GRID", (0, 0), (1, -1), 0.5, colors.grey),
                    ("SPAN", (-1, 0), (-1, -1)),
                    ("LEFTPADDING", (-1, 0), (-1, -1), 15),
                    ("TOPPADDING", (-1, 0), (-1, -1), -35),
                    ("VALIGN", (-1, 0), (-1, -1), "BOTTOM"),
                ]
            )
        )
        self.elements.append(source_table)
        self.elements.append(Spacer(1, 9))
        # Intro
        self._add_intro_text(data_url)

        if change_log:
            self._add_change_log(change_log)
        # Glossary
        self._add_glossary()

        # Summaries
        self.elements.append(CondPageBreak(15 * cm))
        self.elements.append(Paragraph("Review Tabular Summaries", self.h1))
        self.elements.append(Spacer(1, 9))
        self._add_summary_tables(data_summaries, data_summary_definitions, left_justify_columns)

        # Plots
        self.elements.append(CondPageBreak(15 * cm))
        self.elements.append(Paragraph("Review Graphical Summaries", self.h1))
        self._add_plots(plot_collection, plot_definitions)

        # Build
        self.doc.build(self.elements, onFirstPage=self._footer, onLaterPages=self._footer)
        logger.info("PDF QA Report saved to %s", self.pdf_report_path)

    def _add_intro_text(self, data_url):
        """
        Adds the introductory text, action required notice, and contact information to the report.
        """
        intro = Paragraph(
            "This report summarises your data to highlight potential quality issues including missing values, "
            "inconsistent sampling effort and outliers. QA Checks in the summary tables are to direct your review. "
            "Some checks may be triggered by the sampling design or valid properties of the data.",
            self.normal_style,
        )
        self.elements.append(intro)

        self.elements.append(Spacer(1, 9))

        self.elements.append(Paragraph("Action Required", self.styles["Heading2"]))
        actions_required = [
            [
                Paragraph("(1) Review", self.bold_style),
                Paragraph(
                    "Check the provided table summaries and plots. Use the provided notes and glossary below to help interpret table columns or reach out to the Basin-scale data team for assistance.",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("(2) Correct if necessary", self.bold_style),
                Paragraph(
                    'Work with your area Data Manager to upload any identified corrections to the MDMS. When corrections are complete Area Data Managers should re-mark the data as `provided` in the <a href="https://mdms.essolutions.com.au/tracker" color="blue">MDMS Tracker</a> and <b>a new QA report will be issued</b>.',
                    self.normal_style,
                ),
            ],
            [
                Paragraph("(3) Confirm Complete", self.bold_style),
                Paragraph(
                    'If no issues are found Data Managers please mark data as `complete` in the <a href="https://mdms.essolutions.com.au/tracker" color="blue">MDMS Tracker</a>.',
                    self.normal_style,
                ),
            ],
        ]
        actions_table = Table(actions_required, colWidths=[4 * cm, None])
        actions_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        self.elements.append(actions_table)
        self.elements.append(Spacer(1, 9))

        # if data_url:
        #     self.elements.append(Spacer(1, 9))
        #     self.elements.append(
        #         Paragraph(
        #             f'<a href="{data_url}" color="blue">Download current matching data from the Flow-MER MDMS</a> or obtain from your area team data manager. <i>Current data may have changed - refer export date above.</i>',
        #             self.normal_style,
        #         )
        #     )
        self.elements.append(Spacer(1, 9))

    def _add_change_log(self, change_log):
        """
        Adds a changelog table to the report, showing version history and changes.
        """
        self.elements.append(Paragraph("Recent Changes", self.styles["Heading2"]))
        self.elements.append(
            Paragraph(
                "New QA tests and data summaries may have been added since your last data review",
                self.normal_style,
            )
        )
        changelog_data = build_change_log_table_data(change_log)
        changelog_table = Table(changelog_data, colWidths=[3.5 * cm, None])
        changelog_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        self.elements.append(changelog_table)
        self.elements.append(Spacer(1, 9))

    def _add_glossary(self):
        """
        Adds a glossary table explaining common terms used in the report (e.g., nunique, IQR).
        """
        self.elements.append(Paragraph("Glossary", self.styles["Heading2"]))
        glossary_data = [
            [
                Paragraph("nunique:", self.bold_style),
                Paragraph(
                    "Count of unique values for a column (e.g. number of unique species, number of unique sampling units, etc.)",
                    self.normal_style,
                ),
            ],
            # [
            #     Paragraph("Outliers IQR:", self.bold_style),
            #     Paragraph(
            #         "Uses the Inter-Quartile Range (distance between 25th and 75th percentiles) to identify outliers. Values more than 1.5 IQR below the 25th percentile or above the 75th percentile are flagged for review.",
            #         self.normal_style,
            #     ),
            # ],
            [
                Paragraph("range check 0-100% +1:", self.bold_style),
                Paragraph(
                    "Checks that percent cover values are within a valid range (0-100%) allowing an extra 1% margin for rounding errors. Values greater than 101% are flagged for review, as well as any missing values.",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("missmatched:", self.bold_style),
                Paragraph(
                    "Count of records in one column that does not match another column (e.g. count of samples vs count of unique SamplingUnitsIDs.  Flagged for review but can be a valid outcome of the sampling design.",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("records:", self.bold_style),
                Paragraph(
                    "records is a count of the number of data records in the column. This will include counts of 0 (zero) therefore it is possible to have a record count that exceeds the sum.",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("NaN:", self.bold_style),
                Paragraph(
                    "Not a Number (i.e. missing value).  Flagged for review.", self.normal_style
                ),
            ],
            [
                Paragraph("numbers:", self.bold_style),
                Paragraph(
                    "are printed to 2 decimal places for display; summaries use the full precision.",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("zero count for species:", self.bold_style),
                Paragraph(
                    "Alert to zero values for counts, mean or sum.  Check if valid.",
                    self.normal_style,
                ),
            ],
            [
                Paragraph("high value", self.styles["Centered"]),
                Paragraph(
                    'High and low outliers are flagged for review. Outlier detection uses a skewness-adjusted interquartile range (IQR) method to apply asymmetric thresholds based on the data’s distribution (<a href="https://doi.org/10.1002/cem.1123" color="blue">Hubert & Vandervieren 2008</a>). Thresholds are in column headers as <b>L/H [Low, High]</b>.',
                    self.normal_style,
                ),
            ],
            [
                Paragraph("low value", self.styles["Centered"]),
                # Paragraph(
                #     "Low values - thresholds are in column headers as <b>L/H [Low, High]</b>. Uses threshold more than 1.5 IQR below the 25th percentile or in bottom 1.5% of values.",
                #     self.normal_style,
                # ),
            ],
            [
                Paragraph("0", self.styles["Centered"]),
                Paragraph(
                    "Zero values can indicate missing data when counting numbers of samples or sampling units",
                    self.normal_style,
                ),
            ],
        ]
        glossary_table = Table(glossary_data, colWidths=[3 * cm, None])
        glossary_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("BACKGROUND", (0, 7), (0, 7), colors.lightcoral),
                    ("BACKGROUND", (0, 8), (0, 8), colors.lightblue),
                    ("BACKGROUND", (0, 9), (0, 9), colors.yellow),
                    ("SPAN", (-1, 7), (-1, 8)),
                ]
            )
        )
        self.elements.append(glossary_table)

    def _summary_column_layout(self, summary_df, left_justify_columns):
        """Calculate PDF column widths and cell alignments for a summary table."""
        available_width = self.doc.width
        col_alignments = []
        raw_col_widths = []

        for column in summary_df.columns:
            header_lines = str(column).split("\n")
            max_width = max(
                pdfmetrics.stringWidth(line, "Helvetica-Bold", 8) for line in header_lines
            )
            for value in summary_df[column].head(50):
                for line in str(value).split("\n"):
                    max_width = max(max_width, pdfmetrics.stringWidth(line, "Helvetica", 8))
            raw_col_widths.append(max_width + 8)

            is_left_aligned = left_justify_columns and any(
                substring.lower() in str(column).lower() for substring in left_justify_columns
            )
            col_alignments.append(0 if is_left_aligned else 1)

        if sum(raw_col_widths) <= available_width:
            return raw_col_widths, col_alignments

        capped_widths = [min(width, available_width * 0.6) for width in raw_col_widths]
        scale_factor = available_width / sum(capped_widths)
        return [width * scale_factor for width in capped_widths], col_alignments

    def _summary_table_rows(self, summary_df, col_alignments):
        """Convert a formatted summary DataFrame into ReportLab table rows."""
        header_style = ParagraphStyle(
            "HeaderPara",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            alignment=1,
        )
        centred_style = ParagraphStyle(
            "CellPara", parent=self.styles["Normal"], fontSize=8, alignment=1
        )
        left_style = ParagraphStyle(
            "CellPara", parent=self.styles["Normal"], fontSize=8, alignment=0
        )
        rows = [
            [
                Paragraph(escape(str(column)).replace("\n", "<br/>"), header_style)
                for column in summary_df.columns
            ]
        ]

        for _, row in summary_df.iterrows():
            rows.append(
                [
                    Paragraph(
                        escape(str(cell)).replace("\n", "<br/>"),
                        left_style if col_alignments[index] == 0 else centred_style,
                    )
                    for index, cell in enumerate(row)
                ]
            )
        return rows

    def _build_summary_table(self, summary_df, background_commands, left_justify_columns):
        """Build a styled ReportLab table and return it with its column widths."""
        col_widths, col_alignments = self._summary_column_layout(summary_df, left_justify_columns)
        table = Table(self._summary_table_rows(summary_df, col_alignments), colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.whitesmoke]),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    *background_commands,
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightslategrey),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        return table, col_widths

    def _add_summary_tables(self, data_summaries, data_summary_definitions, left_justify_columns):
        """
        Iterates through the generated data summaries and adds them as formatted tables to the report.
        Handles column width calculation, text wrapping, and alignment.
        """
        table_counter = 1
        for summary_name, (table_name, summary_df) in data_summaries.items():
            self.elements.append(CondPageBreak(8 * cm))
            self.elements.append(
                Paragraph(f"Table {table_counter}: {summary_name}", self.styles["Heading2"])
            )
            table_counter += 1
            if (
                summary_name in data_summary_definitions
                and "note" in data_summary_definitions[summary_name]
            ):
                self.elements.append(
                    Paragraph(data_summary_definitions[summary_name]["note"], self.normal_style)
                )
                self.elements.append(Spacer(1, 6))
            if summary_df.empty:
                self.elements.append(
                    Paragraph(
                        "      No data supplied that supports this summary.", self.styles["Italic"]
                    )
                )
                continue

            self.elements.append(Paragraph(f"Source Table: {table_name}", self.styles["Italic"]))
            self.elements.append(Spacer(1, 6))

            formatted_df, background_commands = prepare_summary_table_data(summary_df)
            table, col_widths = self._build_summary_table(
                formatted_df, background_commands, left_justify_columns
            )
            self.elements.append(table)
            table_footer_style = ParagraphStyle(
                "table_footer",
                parent=self.styles["Normal"],
                fontSize=5,
                leftIndent=(self.doc.width - sum(col_widths)) / 2 + sum(col_widths) - 30,
            )
            self.elements.append(Paragraph(f"{len(formatted_df)} rows", table_footer_style))
            self.elements.append(Spacer(1, 9))

    def _add_plots(self, plot_collection, plot_definitions):
        """
        Iterates through the generated plots and adds them to the report.
        Arranges plots in a grid layout (1, 2, or 3 columns) depending on the number of plots in a series.
        """
        if plot_collection:
            plot_instructions = Paragraph(
                "Look for any unusual patterns in the plots, including abnormally dominant taxa, unexpected species composition, outliers, or missing data for certain sampling units or dates.",
                self.styles["Normal"],
            )
            self.elements.append(plot_instructions)
            self.elements.append(Spacer(1, 9))
            plot_counter = 1
            for plot_series_name in plot_collection:
                self.elements.append(CondPageBreak(10 * cm))
                self.elements.append(
                    Paragraph(f"Figure {plot_counter}: {plot_series_name}", self.styles["Heading2"])
                )
                plot_counter += 1
                if (
                    plot_series_name in plot_definitions
                    and "note" in plot_definitions[plot_series_name]
                ):
                    self.elements.append(
                        Paragraph(plot_definitions[plot_series_name]["note"], self.normal_style)
                    )
                    self.elements.append(Spacer(1, 6))

                plot_files = plot_collection[plot_series_name]
                if not plot_files:
                    self.elements.append(
                        Paragraph(f"No plots for this {plot_series_name}.", self.styles["Italic"])
                    )
                    continue

                num_plots = len(plot_files)
                if num_plots == 1:
                    num_cols = 1
                elif num_plots <= 4:
                    num_cols = 2
                else:
                    num_cols = 3

                col_width = self.doc.width / num_cols
                images = [
                    Image(
                        self.output_path / f,
                        width=col_width * 0.95,
                        height=col_width * 0.75,
                        kind="proportional",
                    )
                    for f in plot_files
                ]

                table_data = []
                for i in range(0, len(images), num_cols):
                    table_data.append(images[i : i + num_cols])

                if table_data:
                    image_table = Table(table_data, colWidths=[col_width] * num_cols)
                    image_table.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ]
                        )
                    )
                    self.elements.append(image_table)
                self.elements.append(Spacer(1, 9))

    def _footer(self, canvas, doc):
        """Draws the page number footer on each page."""
        canvas.saveState()
        footer_y = 0.5 * cm
        footer_style = ParagraphStyle("footer", fontSize=8)
        p = Paragraph(
            "For help interpreting summaries or plots, or to provide feedback, "
            '<a href="mailto:data@flow-mer.org.au" color="blue">email the data team</a>',
            footer_style,
        )
        p.wrapOn(canvas, doc.width * 0.75, 20)
        p.drawOn(canvas, doc.leftMargin, footer_y)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(doc.leftMargin + doc.width, footer_y, f"Page {doc.page}")
        canvas.restoreState()
