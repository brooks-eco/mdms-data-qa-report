from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    CondPageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from html import escape
import datetime


class PDFQAReport:
    """
    Handles the generation of the PDF QA Report using ReportLab.
    """
    def __init__(self, output_path, group_name, report_title_str):
        """
        Initializes the PDF report generator.

        Args:
            output_path (Path): Directory to save the PDF report.
            group_name (str): Name of the group (e.g., "MAC", "LAC").
            report_title_str (str): Title of the report.
        """
        self.output_path = output_path
        self.group_name = group_name
        self.report_title_str = report_title_str
        # get date-time stamp to include in filename
        date_stamp = datetime.datetime.now().strftime("%Y%m%d")
        self.filename = self._make_safe(f"{group_name}_{report_title_str}_{date_stamp}.pdf")
        self.pdf_report_path = output_path / self.filename
        
        self.doc = SimpleDocTemplate(
            str(self.pdf_report_path),
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
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
        self.styles.add(ParagraphStyle(name='Centered', alignment=TA_CENTER))
        self.h1 = self.styles['Heading1']
        self.h1.spaceBefore = 20
        
        self.title_style = self.styles["Title"]
        self.title_style.spaceBefore = 10
        self.title_style.spaceAfter = 10
        
        self.normal_style = ParagraphStyle(
            'Normal',
            parent=self.styles['Normal'],
            fontSize=9,
        )
        self.bold_style = ParagraphStyle(
            'Bold',
            parent=self.styles['Normal'],
            fontName="Helvetica-Bold",
            fontSize=9,
        )

    def create_report(self, data_summaries, plot_collection, input_filename, start_dt, end_dt, plot_definitions, data_summary_definitions, group_id, data_date, data_url=None, left_justify_columns=None):
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
        """
        # Header and Title
        self.elements.append(Image("resources//CEWH crest and FLOW-MER-inline_CMYK.png", width=13.0*cm, height=2.5*cm, kind="proportional", hAlign="CENTER"))
        self.elements.append(Spacer(1, 9))
        
        title = Paragraph(f"{self.group_name} {self.report_title_str}", self.title_style)
        self.elements.append(title)
        
        start_year = start_dt.year
        end_year = end_dt.year
        self.elements.append(Paragraph(f"{start_year}/{end_year} water-year.", self.styles["Centered"]))
        self.elements.append(Spacer(1, 9))
        self.elements.append(Paragraph(f"Data from: {input_filename}", self.styles["Italic"]))
        self.elements.append(Spacer(1, 9))

        # Intro
        self._add_intro_text(data_url, data_date)
        
        # Glossary
        self._add_glossary()

        # Summaries
        self.elements.append(Paragraph(f"Review Tabular Summaries", self.h1))
        self.elements.append(Spacer(1, 9))
        self._add_summary_tables(data_summaries, data_summary_definitions, left_justify_columns)

        # Plots
        self.elements.append(CondPageBreak(10*cm))
        self.elements.append(Spacer(1, 9))
        self.elements.append(Paragraph(f"Review Graphical Summaries", self.h1))
        self._add_plots(plot_collection, plot_definitions)

        # Build
        self.doc.build(self.elements, onFirstPage=self._footer, onLaterPages=self._footer)
        print(f"PDF QA Report saved to {self.pdf_report_path}")

    def _add_intro_text(self, data_url, data_date):
        """
        Adds the introductory text, action required notice, and contact information to the report.
        """
        intro = Paragraph(
            "This report reflects your data back to you in summaries that are intended to help you "
            "identify data quality issues including missing values, inconsistent sampling effort "
            "and/or outliers.  QA Checks in the summary tables indicate issues for you to investigate, "
            "noting that these may reflect valid properties of the data (e.g. multi-layered vegetation "
            "can have > 100% cover).",
            self.normal_style,
        )
        self.elements.append(intro)
        self.elements.append(Spacer(1, 9))
        
        action = Paragraph(
            "ACTION REQUIRED: Confirm via email that this data summary has been reviewed and found to be a complete and an accurate representation of the data you provided. "
            "Email to confirm any data quality issues and upload your corrections to the MDMS as soon as possible.",
            self.bold_style
        )
        self.elements.append(action)
        self.elements.append(Spacer(1, 9))
        
        contact = Paragraph(
            "If you have any questions about how to interpret the summaries or plots, or feedback to improve the process, please reach out to discuss.",
            self.normal_style,
        )
        self.elements.append(contact)
        
        if data_url:
            self.elements.append(Spacer(1, 9))
            self.elements.append(Paragraph(f'<a href="{data_url}" color="blue">Download current matching data from the Flow-MER MDMS</a> or obtain from your area team data manager. <i>Current data may have changed. This report was generated on MDMS data exported {data_date}</i>.', self.normal_style))
        self.elements.append(Spacer(1, 9))

    def _add_glossary(self):
        """
        Adds a glossary table explaining common terms used in the report (e.g., nunique, IQR).
        """
        self.elements.append(Paragraph("Glossary", self.styles["Heading2"]))
        glossary_data = [
            [Paragraph('nunique:', self.bold_style), Paragraph('Count of unique values for a column (e.g. number of unique species, number of unique sampling units, etc.)', self.normal_style)],
            [Paragraph('Outliers IQR:', self.bold_style), Paragraph('Uses the Inter-Quartile Range (distance between 25th and 75th percentiles) to identify outliers. Values more than 1.5 IQR below the 25th percentile or above the 75th percentile are flagged for review.', self.normal_style)],
            [Paragraph('range check 0-100% +1:', self.bold_style), Paragraph('Checks that percent cover values are within a valid range (0-100%) allowing an extra 1% margin for rounding errors. Values greater than 101% are flagged for review, as well as any missing values.', self.normal_style)],
            [Paragraph('missmatched:', self.bold_style), Paragraph('Count of records in one column that does not match another column (e.g. count of samples vs count of unique SamplingUnitsIDs.  Flagged for review but can be a valid outcome of the sampling design.', self.normal_style)],
            [Paragraph('records', self.bold_style), Paragraph('records is a count of the number of data records in the column. This will include counts of 0 (zero) therefore it is possible to have a record count that exceeds the sum.', self.normal_style)],
            [Paragraph('NaN:', self.bold_style), Paragraph('Not a Number (i.e. missing value).  Flagged for review.', self.normal_style)],
            [Paragraph('numbers:', self.bold_style), Paragraph('are printed to 2 decimal places for display; summaries use the full precision.', self.normal_style)],
        ]
        glossary_table = Table(glossary_data, colWidths=[3*cm, None])
        glossary_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        self.elements.append(glossary_table)

    def _add_summary_tables(self, data_summaries, data_summary_definitions, left_justify_columns):
        """
        Iterates through the generated data summaries and adds them as formatted tables to the report.
        Handles column width calculation, text wrapping, and alignment.
        """
        table_counter = 1
        for summary_name, (table_name, summary_df) in data_summaries.items():
            self.elements.append(CondPageBreak(8*cm))
            self.elements.append(Paragraph(f"Table {table_counter}: {summary_name}", self.styles["Heading2"]))
            table_counter += 1
            if summary_df.empty:
                self.elements.append(Paragraph("      No data supplied that supports this summary.", self.styles["Italic"]))
                continue
            elif summary_name in data_summary_definitions and "note" in data_summary_definitions[summary_name]:
                self.elements.append(Paragraph(data_summary_definitions[summary_name]["note"], self.normal_style))
                self.elements.append(Spacer(1, 6))

            
            self.elements.append(Paragraph(f"Source Table: {table_name}", self.styles["Italic"]))
            self.elements.append(Spacer(1, 6))
            
            numeric_cols = summary_df.select_dtypes(include=["number"]).columns
            summary_df[numeric_cols] = summary_df[numeric_cols].round(2)
            
            df_str = summary_df.astype(str)
            available_width = self.doc.width
            
            col_alignments = []
            raw_col_widths = []
            for col in df_str.columns: 
                header_lines = str(col).split('\n')
                max_width = max([pdfmetrics.stringWidth(line, 'Helvetica-Bold', 8) for line in header_lines]) if header_lines else 0
                for val in df_str[col].head(50):
                    lines = str(val).split('\n')
                    for line in lines:
                        w = pdfmetrics.stringWidth(line, 'Helvetica', 8)
                        if w > max_width: max_width = w
                raw_col_widths.append(max_width+8)
                
                if left_justify_columns and any(sub.lower() in col.lower() for sub in left_justify_columns):
                    col_alignments.append(0) 
                else:
                    col_alignments.append(1)

            if sum(raw_col_widths) <= available_width:
                col_widths = raw_col_widths
            else:
                capped_widths = [min(w, available_width * 0.6) for w in raw_col_widths]
                total_capped_width = sum(capped_widths)
                scale_factor = available_width / total_capped_width
                col_widths = [w * scale_factor for w in capped_widths]
            
            header_para_style = ParagraphStyle('HeaderPara', parent=self.styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1)
            cell_para_centre_style = ParagraphStyle('CellPara', parent=self.styles['Normal'], fontSize=8, alignment=1)
            cell_para_left_style = ParagraphStyle('CellPara', parent=self.styles['Normal'], fontSize=8, alignment=0)
            
            data = []
            headers = [Paragraph(escape(str(col)).replace("\n", "<br/>"), header_para_style) for col in summary_df.columns]
            data.append(headers)
            
            for _, row in df_str.iterrows():
                row_data = []
                for i, cell in enumerate(row):
                    style = cell_para_left_style if col_alignments[i] == 0 else cell_para_centre_style
                    # if cell type is a string
                    if isinstance(cell, str):
                        row_data.append(Paragraph(escape(cell).replace("\n", "<br/>"), style))
                    else:
                        row_data.append(Paragraph(str(cell), style))
                data.append(row_data)

            t = Table(data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.whitesmoke]),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightslategrey),
                ("TOPPADDING", (0, 0), (-1, -1), 1),  
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            self.elements.append(t)
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
                self.elements.append(CondPageBreak(10*cm))
                self.elements.append(Paragraph(f"Figure {plot_counter}: {plot_series_name}", self.styles["Heading2"]))
                plot_counter += 1
                if plot_series_name in plot_definitions and "note" in plot_definitions[plot_series_name]:
                    self.elements.append(Paragraph(plot_definitions[plot_series_name]["note"], self.styles["Normal"]))
                    self.elements.append(Spacer(1, 6))

                plot_files = plot_collection[plot_series_name]
                if not plot_files:
                    self.elements.append(Paragraph(f"No plots for this {plot_series_name}.", self.styles["Italic"]))
                    continue

                num_plots = len(plot_files)
                if num_plots == 1: num_cols = 1
                elif num_plots <= 4: num_cols = 2
                else: num_cols = 3

                col_width = self.doc.width / num_cols
                images = [Image(self.output_path / f, width=col_width * 0.95, height=col_width * 0.75, kind="proportional") for f in plot_files]

                table_data = []
                for i in range(0, len(images), num_cols):
                    table_data.append(images[i : i + num_cols])

                if table_data:
                    image_table = Table(table_data, colWidths=[col_width] * num_cols)
                    image_table.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), 
                        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)
                    ]))
                    self.elements.append(image_table)
                self.elements.append(Spacer(1, 9))

    def _footer(self, canvas, doc):
        """Draws the page number footer on each page."""
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(cm, 0.75 * cm, "Page %d" % doc.page)
        canvas.restoreState()