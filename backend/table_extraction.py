"""
Table Extraction Service

Extracts tables from PDF documents using pdfplumber.
Converts tables to CSV and structured data for analysis.
"""

import os
import logging
import pdfplumber
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TableExtractor:
    """
    Extracts tables from PDF files.
    """

    def __init__(self, min_rows=2, min_cols=2):
        """
        Args:
            min_rows: Minimum number of rows to consider a valid table
            min_cols: Minimum number of columns to consider a valid table
        """
        self.min_rows = min_rows
        self.min_cols = min_cols

    def extract_tables_from_pdf(
        self, pdf_path: str, output_dir: Optional[str] = None
    ) -> List[Dict]:
        """
        Extract all tables from a PDF file.

        Args:
            pdf_path: Path to PDF file
            output_dir: Optional directory to save CSV files

        Returns:
            List of dicts with table metadata:
            {
                "page_num": int,
                "table_index": int (0-based index on page),
                "dataframe": pandas DataFrame,
                "csv_path": str (if output_dir specified),
                "row_count": int,
                "col_count": int
            }
        """
        tables_data = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    logger.info(f"Scanning page {page_num} for tables...")

                    # Extract tables from page
                    page_tables = page.extract_tables()

                    if not page_tables:
                        continue

                    for table_idx, table in enumerate(page_tables):
                        if not table or len(table) < self.min_rows:
                            logger.debug(
                                f"Skipping table on page {page_num} (too few rows)"
                            )
                            continue

                        # Convert to DataFrame
                        try:
                            df = self._table_to_dataframe(table)

                            if df.shape[1] < self.min_cols:
                                logger.debug(
                                    f"Skipping table on page {page_num} (too few columns)"
                                )
                                continue

                            table_info = {
                                "page_num": page_num,
                                "table_index": table_idx,
                                "dataframe": df,
                                "row_count": len(df),
                                "col_count": len(df.columns),
                            }

                            # Save to CSV if output directory specified
                            if output_dir:
                                csv_filename = f"table_p{page_num}_t{table_idx}.csv"
                                csv_path = os.path.join(output_dir, csv_filename)
                                df.to_csv(csv_path, index=False)
                                table_info["csv_path"] = csv_path
                                logger.info(f"Saved table to {csv_path}")

                            tables_data.append(table_info)

                        except Exception as e:
                            logger.error(
                                f"Failed to process table {table_idx} on page {page_num}: {e}"
                            )

        except Exception as e:
            logger.error(f"Failed to extract tables from {pdf_path}: {e}")
            raise

        logger.info(f"Extracted {len(tables_data)} tables from {pdf_path}")
        return tables_data

    def _table_to_dataframe(self, table: List[List[str]]) -> pd.DataFrame:
        """
        Convert pdfplumber table to pandas DataFrame.

        Args:
            table: List of lists (rows) from pdfplumber

        Returns:
            pandas DataFrame
        """
        # First row is usually headers
        if len(table) > 1:
            headers = table[0]
            data = table[1:]

            # Clean headers (remove None, empty strings)
            cleaned_headers = []
            for i, h in enumerate(headers):
                if h and str(h).strip():
                    cleaned_headers.append(str(h).strip())
                else:
                    cleaned_headers.append(f"Column_{i}")

            df = pd.DataFrame(data, columns=cleaned_headers)
        else:
            # No headers, just data
            df = pd.DataFrame(table)

        # Clean data: strip whitespace, replace None with empty string
        df = df.apply(lambda col: col.map(lambda x: str(x).strip() if x else ""))

        # Drop completely empty rows
        df = df[df.any(axis=1)]

        return df

    def extract_table_text(self, table_info: Dict) -> str:
        """
        Convert table DataFrame to plain text for indexing.

        Args:
            table_info: Dict with 'dataframe' key

        Returns:
            Plain text representation of table
        """
        df = table_info["dataframe"]

        # Create text with headers and values
        lines = []
        lines.append(f"TABLE (Page {table_info['page_num']}):")
        lines.append(" | ".join(df.columns))
        lines.append("-" * 50)

        for _, row in df.iterrows():
            lines.append(" | ".join([str(val) for val in row.values]))

        return "\n".join(lines)

    def summarize_table(self, table_info: Dict) -> str:
        """
        Generate a summary of the table structure.

        Args:
            table_info: Dict with 'dataframe' key

        Returns:
            Human-readable summary
        """
        df = table_info["dataframe"]

        summary_parts = [
            f"Table on page {table_info['page_num']}:",
            f"  - Size: {table_info['row_count']} rows × {table_info['col_count']} columns",
            f"  - Columns: {', '.join(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}",
        ]

        # Add sample data (first 2 rows)
        if len(df) > 0:
            summary_parts.append("  - Sample data:")
            for i, row in df.head(2).iterrows():
                row_str = " | ".join([str(val)[:20] for val in row.values[:3]])
                summary_parts.append(f"    Row {i+1}: {row_str}...")

        return "\n".join(summary_parts)
