import logging

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL
import os
import csv
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

from app.arkham.services.db.models import ExtractedTable, Document

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_extracted_tables(limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    Fetch a list of extracted tables with metadata and total count.
    """
    session = SessionLocal()
    try:
        query = session.query(ExtractedTable, Document).join(
            Document, ExtractedTable.doc_id == Document.id
        )

        total_count = query.count()

        tables = (
            query.order_by(ExtractedTable.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        results = []
        for table, doc in tables:
            headers = []
            if table.headers:
                try:
                    headers = json.loads(table.headers)
                except (json.JSONDecodeError, TypeError):
                    headers = []

            results.append(
                {
                    "id": table.id,
                    "doc_id": doc.id,
                    "doc_title": doc.title or f"Document {doc.id}",
                    "page_num": table.page_num,
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                    "headers": headers,
                    "created_at": table.created_at.strftime("%Y-%m-%d %H:%M"),
                    "csv_path": table.csv_path,
                }
            )
        return {"items": results, "total": total_count}
    except Exception as e:
        logger.error(f"Error fetching tables: {e}")
        return {"items": [], "total": 0}
    finally:
        session.close()


def get_table_content(table_id: int) -> Dict[str, Any]:
    """
    Fetch the content of a specific table.
    Returns a dictionary with 'headers' and 'rows'.
    """
    session = SessionLocal()
    try:
        table = session.query(ExtractedTable).get(table_id)
        if not table:
            return {"error": "Table not found"}

        # Try to read from CSV if available
        if table.csv_path and os.path.exists(table.csv_path):
            try:
                rows = []
                with open(table.csv_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    headers = next(reader, [])
                    for row in reader:
                        rows.append(row)
                return {
                    "headers": headers,
                    "rows": rows,
                    "csv_path": table.csv_path,
                }
            except Exception as e:
                logger.error(f"Error reading CSV: {e}")
                # Fallback to text content parsing or return error
                pass

        # Fallback: if headers are stored in DB
        headers = []
        if table.headers:
            try:
                headers = json.loads(table.headers)
            except:
                pass

        return {
            "headers": headers,
            "rows": [],
            "message": "Full content not available (CSV missing). Showing metadata only.",
            "csv_path": table.csv_path,
        }

    except Exception as e:
        logger.error(f"Error fetching table content: {e}")
        return {"error": str(e)}
    finally:
        session.close()
