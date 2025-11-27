"""
Extract Tables from Documents

Scans all PDF documents and extracts tables using pdfplumber.
Saves tables as CSV files and indexes them in the database.

Usage:
    python extract_tables.py [--doc-id DOC_ID]
"""

import os
import json
import logging
import argparse
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from backend.db.models import Document, ExtractedTable
from backend.table_extraction import TableExtractor

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def extract_tables_for_document(doc_id: int, output_base_dir: str = "data/tables"):
    """
    Extract tables from a specific document.

    Args:
        doc_id: Document ID
        output_base_dir: Base directory for CSV output
    """
    session = Session()

    try:
        doc = session.query(Document).get(doc_id)
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return

        if not doc.path or not os.path.exists(doc.path):
            logger.error(f"Document path not found: {doc.path}")
            return

        # Only process PDFs
        if not doc.path.lower().endswith(".pdf"):
            logger.info(f"Skipping non-PDF document: {doc.path}")
            return

        logger.info(f"Extracting tables from: {doc.title or doc.path}")

        # Create output directory for this document
        output_dir = os.path.join(output_base_dir, f"doc_{doc_id}")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Extract tables
        extractor = TableExtractor()
        tables = extractor.extract_tables_from_pdf(doc.path, output_dir)

        if not tables:
            logger.info(f"No tables found in document {doc_id}")
            return

        # Save to database
        for table_info in tables:
            # Check if table already exists
            existing = (
                session.query(ExtractedTable)
                .filter_by(
                    doc_id=doc_id,
                    page_num=table_info["page_num"],
                    table_index=table_info["table_index"],
                )
                .first()
            )

            if existing:
                logger.info(
                    f"Table already exists: doc={doc_id}, page={table_info['page_num']}, index={table_info['table_index']}"
                )
                continue

            # Get table text
            text_content = extractor.extract_table_text(table_info)

            # Create database record
            extracted_table = ExtractedTable(
                doc_id=doc_id,
                page_num=table_info["page_num"],
                table_index=table_info["table_index"],
                row_count=table_info["row_count"],
                col_count=table_info["col_count"],
                headers=json.dumps(list(table_info["dataframe"].columns)),
                csv_path=table_info.get("csv_path"),
                text_content=text_content,
            )

            session.add(extracted_table)

        session.commit()
        logger.info(f"✓ Extracted and saved {len(tables)} tables from document {doc_id}")

    except Exception as e:
        logger.error(f"Failed to extract tables from document {doc_id}: {e}")
        session.rollback()
    finally:
        session.close()


def extract_all_tables():
    """
    Extract tables from all documents in the database.
    """
    session = Session()

    try:
        # Get all complete documents
        documents = session.query(Document).filter_by(status="complete").all()

        logger.info(f"Found {len(documents)} complete documents")

        for doc in documents:
            extract_tables_for_document(doc.id)

        logger.info("✓ Table extraction complete!")

        # Print stats
        total_tables = session.query(ExtractedTable).count()
        logger.info(f"Total tables in database: {total_tables}")

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract tables from PDF documents")
    parser.add_argument(
        "--doc-id",
        type=int,
        help="Extract tables from specific document ID (optional)",
    )

    args = parser.parse_args()

    if args.doc_id:
        extract_tables_for_document(args.doc_id)
    else:
        extract_all_tables()
