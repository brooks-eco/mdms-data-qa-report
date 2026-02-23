from pathlib import Path
import datetime

class MarkdownQAReport:
    """
    Handles the generation of the Markdown QA Report.
    """
    def __init__(self, output_path, group_name, report_title_str):
        """
        Initializes the Markdown report generator.

        Args:
            output_path (Path): Directory to save the Markdown report.
            group_name (str): Name of the group.
            report_title_str (str): Title of the report.
        """
        self.output_path = output_path
        self.group_name = group_name
        self.report_title_str = report_title_str
        date_stamp = datetime.datetime.now().strftime("%Y%m%d")
        self.filename = self._make_safe(f"{group_name}_{report_title_str}_{date_stamp}.md")
        self.report_path = output_path / self.filename
        self.content = ""

    def _make_safe(self, filename):
        """Sanitizes a filename string."""
        return filename.replace(" ", "_").replace("'", "").replace(":", "").replace("/", "-")

    def create_report(self, data_summaries, plot_collection, input_filename, start_dt, end_dt, plot_definitions, data_summary_definitions, group_id, data_date, data_url=None, left_justify_columns=None):
        """
        Assembles and writes the Markdown report.

        Args:
            data_summaries (dict): Dictionary of summary DataFrames.
            plot_collection (dict): Dictionary of generated plot filenames.
            input_filename (str): Name of the input data file.
            start_dt (datetime): Start date of the data range.
            end_dt (datetime): End date of the data range.
            plot_definitions (dict): Configuration for plots.
            data_summary_definitions (dict): Configuration for summaries.
            group_id (str): ID of the group.
            data_date (str): Date string of when the data was exported.
            data_url (str, optional): URL to download the data.
            left_justify_columns (set, optional): Not used in Markdown but kept for signature compatibility.
        """
        start_year = start_dt.year
        end_year = end_dt.year

        self.content = f"# {self.group_name} {self.report_title_str}\n\n"
        self.content += f"**{start_year}/{end_year} water-year.**\n\n"
        self.content += f"*Data from: {input_filename}*\n\n"

        self.content += "This report reflects your data back to you in summaries that are intended to help you identify data quality issues including missing values, inconsistent sampling effort and/or outliers. QA Checks in the summary tables indicate issues for you to investigate, noting that these may reflect valid properties of the data (e.g. multi-layered vegetation can have > 100% cover).\n\n"

        self.content += "**ACTION REQUIRED: Confirm via email that this data summary has been reviewed and found to be a complete and an accurate representation of the data you provided. Email to confirm any data quality issues and upload your corrections to the MDMS as soon as possible.**\n\n"

        self.content += "If you have any questions about how to interpret the summaries or plots, or feedback to improve the process, please reach out to discuss.\n\n"

        if data_url:
            self.content += f"[Download current matching data from the Flow-MER MDMS]({data_url}) or obtain from your area team data manager. *Current data may have changed. This report was generated on MDMS data exported {data_date}.*\n\n"

        self._add_glossary()
        self._add_summary_tables(data_summaries, data_summary_definitions)
        self._add_plots(plot_collection, plot_definitions)

        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(self.content)
        print(f"QA Report saved to {self.report_path}")

    def _add_glossary(self):
        """Adds the glossary section to the Markdown content."""
        self.content += "## Glossary\n\n"
        self.content += "| Term | Definition |\n|---|---|\n"
        self.content += "| **nunique** | Count of unique values for a column (e.g. number of unique species, number of unique sampling units, etc.) |\n"
        self.content += "| **Outliers IQR** | Uses the Inter-Quartile Range (distance between 25th and 75th percentiles) to identify outliers. Values more than 1.5 IQR below the 25th percentile or above the 75th percentile are flagged for review. |\n"
        self.content += "| **range check 0-100% +1** | Checks that percent cover values are within a valid range (0-100%) allowing an extra 1% margin for rounding errors. Values greater than 101% are flagged for review, as well as any missing values. |\n"
        self.content += "| **missmatched** | Count of records in one column that does not match another column (e.g. count of samples vs count of unique SamplingUnitsIDs. Flagged for review but can be a valid outcome of the sampling design. |\n"
        self.content += "| **records** | records is a count of the number of data records in the column. This will include counts of 0 (zero) therefore it is possible to have a record count that exceeds the sum. |\n"
        self.content += "| **NaN** | Not a Number (i.e. missing value). Flagged for review. |\n\n"

    def _add_summary_tables(self, data_summaries, data_summary_definitions):
        """Adds summary tables to the Markdown content, converting DataFrames to Markdown table syntax."""
        self.content += "## Review Tabular Summaries\n\n"
        table_counter = 1
        for summary_name, (table_name, summary_df) in data_summaries.items():
            self.content += f"### Table {table_counter}: {summary_name}\n\n"
            table_counter += 1

            if summary_df.empty:
                self.content += "No data supplied that supports this summary.\n\n"
                continue
            elif summary_name in data_summary_definitions and "note" in data_summary_definitions[summary_name]:
                self.content += f"{data_summary_definitions[summary_name]['note']}\n\n"
            self.content += f"*Source Table: {table_name}*\n\n"
            
            headers = [str(c).replace("\n", "<br>") for c in summary_df.columns]
            self.content += "| " + " | ".join(headers) + " |\n"
            self.content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            for _, row in summary_df.iterrows():
                row_vals = [
                    str(x).replace("|", "\|").replace("\n", "<br>") for x in row.values
                ]
                self.content += "| " + " | ".join(row_vals) + " |\n"
            
            self.content += f"\nDownload CSV\n\n"

    def _add_plots(self, plot_collection, plot_definitions):
        """Adds plot images to the Markdown content."""
        self.content += "## Review Graphical Summaries\n\n"
        if plot_collection:
            self.content += "Look for any unusual patterns in the plots, including abnormally dominant taxa, unexpected species composition, outliers, or missing data for certain sampling units or dates.\n\n"
            plot_counter = 1
            for plot_series_name in plot_collection:
                self.content += f"### Figure {plot_counter}: {plot_series_name}\n\n"
                plot_counter += 1
                if plot_series_name in plot_definitions and "note" in plot_definitions[plot_series_name]:
                    self.content += f"{plot_definitions[plot_series_name]['note']}\n\n"

                if plot_collection[plot_series_name] is None:
                    self.content += "No plots were generated for this series.\n\n"
                    continue
                for plot_filename in plot_collection[plot_series_name]:
                    self.content += f"!{plot_series_name}\n\n"