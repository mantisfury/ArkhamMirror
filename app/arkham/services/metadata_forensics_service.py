"""
Metadata Forensics Service

Analyzes PDF metadata, file forensics, and document authenticity indicators
for investigative journalism and document verification.
"""

import os
import sys
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import logging

from config.settings import DATABASE_URL

from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.arkham.services.db.models import Document

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection



class MetadataForensicsService:
    """Service for document metadata analysis and forensics."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_metadata_summary(self) -> Dict:
        """
        Get comprehensive metadata summary for all documents.

        Returns:
            Dictionary with metadata statistics and forensic insights
        """
        session = self.Session()
        summary = {
            "total_documents": 0,
            "with_metadata": 0,
            "pdf_producers": {},
            "pdf_creators": {},
            "authors": {},
            "encrypted_count": 0,
            "missing_metadata": {
                "no_creation_date": 0,
                "no_modification_date": 0,
                "no_author": 0,
                "no_producer": 0,
                "no_creator": 0
            },
            "date_anomalies": {
                "backdated": 0,
                "future_dates": 0,
                "very_old": 0,
                "same_create_modify": 0
            },
            "software_analysis": {
                "common_producers": [],
                "suspicious_producers": [],
                "producer_diversity": 0
            },
            "temporal_analysis": {
                "oldest_document": None,
                "newest_document": None,
                "creation_date_range_days": 0,
                "avg_age_days": 0
            }
        }

        try:
            # Get all documents
            docs = session.query(Document).filter(
                Document.status == "complete"
            ).all()

            summary["total_documents"] = len(docs)

            # Counters
            producer_counter = Counter()
            creator_counter = Counter()
            author_counter = Counter()
            creation_dates = []

            for doc in docs:
                # Check for metadata presence
                has_metadata = any([
                    doc.pdf_author,
                    doc.pdf_creator,
                    doc.pdf_producer,
                    doc.pdf_creation_date,
                    doc.pdf_modification_date
                ])

                if has_metadata:
                    summary["with_metadata"] += 1

                # Count missing metadata
                if not doc.pdf_creation_date:
                    summary["missing_metadata"]["no_creation_date"] += 1
                if not doc.pdf_modification_date:
                    summary["missing_metadata"]["no_modification_date"] += 1
                if not doc.pdf_author:
                    summary["missing_metadata"]["no_author"] += 1
                if not doc.pdf_producer:
                    summary["missing_metadata"]["no_producer"] += 1
                if not doc.pdf_creator:
                    summary["missing_metadata"]["no_creator"] += 1

                # Count software
                if doc.pdf_producer:
                    producer_counter[doc.pdf_producer] += 1
                if doc.pdf_creator:
                    creator_counter[doc.pdf_creator] += 1
                if doc.pdf_author:
                    author_counter[doc.pdf_author] += 1

                # Encryption
                if doc.is_encrypted:
                    summary["encrypted_count"] += 1

                # Date anomalies
                if doc.pdf_creation_date and doc.pdf_modification_date:
                    # Backdated (modification before creation)
                    if doc.pdf_modification_date < doc.pdf_creation_date:
                        summary["date_anomalies"]["backdated"] += 1

                    # Same create and modify time (suspicious)
                    if doc.pdf_creation_date == doc.pdf_modification_date:
                        summary["date_anomalies"]["same_create_modify"] += 1

                if doc.pdf_creation_date:
                    creation_dates.append(doc.pdf_creation_date)

                    # Future dates
                    if doc.pdf_creation_date > datetime.utcnow():
                        summary["date_anomalies"]["future_dates"] += 1

                    # Very old (> 20 years)
                    age_years = (datetime.utcnow() - doc.pdf_creation_date).days / 365
                    if age_years > 20:
                        summary["date_anomalies"]["very_old"] += 1

            # Software analysis
            summary["pdf_producers"] = dict(producer_counter.most_common(10))
            summary["pdf_creators"] = dict(creator_counter.most_common(10))
            summary["authors"] = dict(author_counter.most_common(10))
            summary["software_analysis"]["producer_diversity"] = len(producer_counter)
            summary["software_analysis"]["common_producers"] = [
                {"name": name, "count": count}
                for name, count in producer_counter.most_common(5)
            ]

            # Identify suspicious producers (generic/unknown names)
            suspicious_keywords = ["unknown", "untitled", "none", "acrobat elements", "pdflib"]
            suspicious = [
                {"name": name, "count": count}
                for name, count in producer_counter.items()
                if any(kw in name.lower() for kw in suspicious_keywords)
            ]
            summary["software_analysis"]["suspicious_producers"] = suspicious

            # Temporal analysis
            if creation_dates:
                creation_dates.sort()
                summary["temporal_analysis"]["oldest_document"] = creation_dates[0].isoformat()
                summary["temporal_analysis"]["newest_document"] = creation_dates[-1].isoformat()
                date_range = (creation_dates[-1] - creation_dates[0]).days
                summary["temporal_analysis"]["creation_date_range_days"] = date_range

                # Average age
                avg_age = sum((datetime.utcnow() - d).days for d in creation_dates) / len(creation_dates)
                summary["temporal_analysis"]["avg_age_days"] = round(avg_age, 1)

        except Exception as e:
            logger.error(f"Metadata summary failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        return summary

    def get_document_metadata(self, doc_id: int) -> Optional[Dict]:
        """
        Get detailed metadata for a specific document.

        Args:
            doc_id: Document ID

        Returns:
            Dictionary with comprehensive metadata and forensic analysis
        """
        session = self.Session()
        result = None

        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                return None

            result = {
                "id": doc.id,
                "title": doc.title,
                "filename": doc.title,  # Use title as filename
                "file_path": doc.path,
                "file_hash": doc.file_hash,
                "file_size_bytes": doc.file_size_bytes,
                "num_pages": doc.num_pages,
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,

                # Flatten PDF Metadata for easier UI access
                "author": doc.pdf_author or "N/A",
                "pdf_creator": doc.pdf_creator or "N/A",
                "pdf_producer": doc.pdf_producer or "N/A",
                "pdf_subject": doc.pdf_subject or "N/A",
                "pdf_keywords": doc.pdf_keywords or "N/A",
                "pdf_creation_date": doc.pdf_creation_date.isoformat() if doc.pdf_creation_date else "N/A",
                "pdf_modification_date": doc.pdf_modification_date.isoformat() if doc.pdf_modification_date else "N/A",
                "pdf_version": doc.pdf_version or "N/A",
                "is_encrypted": bool(doc.is_encrypted),

                # Forensic Analysis
                "forensics": self._analyze_document_forensics(doc)
            }

        except Exception as e:
            logger.error(f"Get document metadata failed for doc {doc_id}: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        return result

    def _analyze_document_forensics(self, doc: Document) -> Dict:
        """
        Perform forensic analysis on document metadata.

        Args:
            doc: Document object

        Returns:
            Dictionary with forensic findings
        """
        findings = {
            "anomalies": [],
            "suspicious_indicators": [],
            "authenticity_score": 100,  # Start at 100, deduct for issues
            "risk_level": "LOW"
        }

        # Check for backdating
        if doc.pdf_creation_date and doc.pdf_modification_date:
            if doc.pdf_modification_date < doc.pdf_creation_date:
                findings["anomalies"].append({
                    "type": "BACKDATED",
                    "severity": "HIGH",
                    "description": f"Modification date ({doc.pdf_modification_date}) is before creation date ({doc.pdf_creation_date})",
                    "impact": -30
                })
                findings["authenticity_score"] -= 30

            # Same timestamps (suspicious)
            if doc.pdf_creation_date == doc.pdf_modification_date:
                findings["suspicious_indicators"].append({
                    "type": "IDENTICAL_TIMESTAMPS",
                    "severity": "MEDIUM",
                    "description": "Creation and modification dates are identical (may indicate metadata stripping/regeneration)",
                    "impact": -10
                })
                findings["authenticity_score"] -= 10

        # Check for future dates
        if doc.pdf_creation_date and doc.pdf_creation_date > datetime.utcnow():
            findings["anomalies"].append({
                "type": "FUTURE_DATE",
                "severity": "HIGH",
                "description": f"Creation date is in the future: {doc.pdf_creation_date}",
                "impact": -25
            })
            findings["authenticity_score"] -= 25

        # Check for very old documents uploaded recently
        if doc.pdf_creation_date and doc.created_at:
            age_at_upload = (doc.created_at - doc.pdf_creation_date).days / 365
            if age_at_upload > 10:
                findings["suspicious_indicators"].append({
                    "type": "OLD_DOCUMENT",
                    "severity": "LOW",
                    "description": f"Document claims to be {age_at_upload:.1f} years old at upload time",
                    "impact": -5
                })
                findings["authenticity_score"] -= 5

        # Check for missing critical metadata
        missing = []
        if not doc.pdf_author:
            missing.append("author")
        if not doc.pdf_creator:
            missing.append("creator")
        if not doc.pdf_producer:
            missing.append("producer")
        if not doc.pdf_creation_date:
            missing.append("creation_date")

        if len(missing) >= 3:
            findings["suspicious_indicators"].append({
                "type": "METADATA_STRIPPED",
                "severity": "MEDIUM",
                "description": f"Missing critical metadata fields: {', '.join(missing)} (may indicate intentional scrubbing)",
                "impact": -15
            })
            findings["authenticity_score"] -= 15

        # Check for suspicious software
        suspicious_producers = ["unknown", "none", "acrobat elements", "pdflib"]
        if doc.pdf_producer and any(kw in doc.pdf_producer.lower() for kw in suspicious_producers):
            findings["suspicious_indicators"].append({
                "type": "SUSPICIOUS_SOFTWARE",
                "severity": "LOW",
                "description": f"Generic or suspicious PDF producer: {doc.pdf_producer}",
                "impact": -5
            })
            findings["authenticity_score"] -= 5

        # Check encryption
        if doc.is_encrypted:
            findings["suspicious_indicators"].append({
                "type": "ENCRYPTED",
                "severity": "MEDIUM",
                "description": "Document was encrypted (may hide tampering or sensitive modifications)",
                "impact": -10
            })
            findings["authenticity_score"] -= 10

        # Determine risk level
        if findings["authenticity_score"] < 50:
            findings["risk_level"] = "CRITICAL"
        elif findings["authenticity_score"] < 70:
            findings["risk_level"] = "HIGH"
        elif findings["authenticity_score"] < 85:
            findings["risk_level"] = "MEDIUM"
        else:
            findings["risk_level"] = "LOW"

        return findings

    def get_software_distribution(self) -> Dict:
        """
        Analyze PDF software distribution across corpus.

        Returns:
            Dictionary with software usage statistics
        """
        session = self.Session()
        result = {
            "producers": [],
            "creators": [],
            "producer_timeline": [],
            "creator_timeline": []
        }

        try:
            # Get total document count for percentage calculation
            total_docs = session.query(func.count(Document.id)).filter(
                Document.status == "complete"
            ).scalar()

            # Producer distribution
            producer_counts = session.query(
                Document.pdf_producer,
                func.count(Document.id).label("count")
            ).filter(
                Document.pdf_producer.isnot(None),
                Document.status == "complete"
            ).group_by(Document.pdf_producer).order_by(
                func.count(Document.id).desc()
            ).limit(20).all()

            # Suspicious producer patterns
            suspicious_keywords = [
                "unknown", "custom", "modified", "hacked", "cracked",
                "piratedsoftware", "nulled", "generator"
            ]

            result["producers"] = []
            for prod, count in producer_counts:
                percentage = (count / total_docs * 100) if total_docs > 0 else 0

                # Analyze suspicion level
                suspicion = "NORMAL"
                prod_lower = prod.lower()

                if any(keyword in prod_lower for keyword in suspicious_keywords):
                    suspicion = "HIGH"
                elif "pdf" not in prod_lower and count == 1:
                    suspicion = "MEDIUM"  # Single-use custom tool

                result["producers"].append({
                    "name": prod,
                    "count": count,
                    "percentage": percentage,
                    "suspicion": suspicion
                })

            # Creator distribution
            creator_counts = session.query(
                Document.pdf_creator,
                func.count(Document.id).label("count")
            ).filter(
                Document.pdf_creator.isnot(None),
                Document.status == "complete"
            ).group_by(Document.pdf_creator).order_by(
                func.count(Document.id).desc()
            ).limit(20).all()

            result["creators"] = []
            for creator, count in creator_counts:
                percentage = (count / total_docs * 100) if total_docs > 0 else 0
                result["creators"].append({
                    "name": creator,
                    "count": count,
                    "percentage": percentage
                })

        except Exception as e:
            logger.error(f"Software distribution analysis failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        return result

    def get_temporal_distribution(self) -> Dict:
        """
        Analyze temporal distribution of document creation dates.

        Returns:
            Dictionary with timeline statistics
        """
        session = self.Session()
        result = {
            "by_year": [],
            "by_month": [],
            "recent_months": [],
            "recent_activity": []
        }

        try:
            # Get all creation dates
            docs = session.query(
                Document.pdf_creation_date,
                Document.title,
                Document.id
            ).filter(
                Document.pdf_creation_date.isnot(None),
                Document.status == "complete"
            ).all()

            # Group by year
            year_counter = Counter()
            month_counter = Counter()

            for creation_date, title, doc_id in docs:
                year = creation_date.year
                month_key = f"{creation_date.year}-{creation_date.month:02d}"

                year_counter[year] += 1
                month_counter[month_key] += 1

            # Format results with percentages
            total = len(docs)
            result["by_year"] = sorted([
                {
                    "year": year,
                    "count": count,
                    "percentage": (count / total * 100) if total > 0 else 0
                }
                for year, count in year_counter.items()
            ], key=lambda x: x["year"])

            result["by_month"] = sorted([
                {"month": month, "count": count}
                for month, count in month_counter.items()
            ], key=lambda x: x["month"])[-24:]  # Last 24 months

            # Recent months for timeline (modified + created counts)
            recent_cutoff = datetime.utcnow() - timedelta(days=180)  # Last 6 months
            recent_created = Counter()
            recent_modified = Counter()

            for creation_date, title, doc_id in docs:
                if creation_date >= recent_cutoff:
                    month_key = f"{creation_date.year}-{creation_date.month:02d}"
                    recent_created[month_key] += 1

            # Get modification dates
            mod_docs = session.query(
                Document.pdf_modification_date
            ).filter(
                Document.pdf_modification_date.isnot(None),
                Document.pdf_modification_date >= recent_cutoff,
                Document.status == "complete"
            ).all()

            for (mod_date,) in mod_docs:
                month_key = f"{mod_date.year}-{mod_date.month:02d}"
                recent_modified[month_key] += 1

            # Combine into recent_months
            all_months = set(recent_created.keys()) | set(recent_modified.keys())
            result["recent_months"] = sorted([
                {
                    "month": month,
                    "created": recent_created.get(month, 0),
                    "modified": recent_modified.get(month, 0)
                }
                for month in all_months
            ], key=lambda x: x["month"])

            # Recent activity (last 30 days)
            recent_cutoff = datetime.utcnow() - timedelta(days=30)
            recent_docs = [
                {"id": doc_id, "title": title, "date": creation_date.isoformat()}
                for creation_date, title, doc_id in docs
                if creation_date > recent_cutoff
            ]
            result["recent_activity"] = sorted(
                recent_docs,
                key=lambda x: x["date"],
                reverse=True
            )

        except Exception as e:
            logger.error(f"Temporal distribution analysis failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        return result

    def get_author_analysis(self) -> Dict:
        """
        Analyze document authors and their patterns.

        Returns:
            Dictionary with author statistics
        """
        session = self.Session()
        result = {
            "total_authors": 0,
            "top_authors": [],
            "single_document_authors": 0,
            "prolific_authors": 0,
            "anonymous_count": 0
        }

        try:
            # Get total document count
            total_docs = session.query(func.count(Document.id)).filter(
                Document.status == "complete"
            ).scalar()

            # Author distribution
            author_counts = session.query(
                Document.pdf_author,
                func.count(Document.id).label("count")
            ).filter(
                Document.status == "complete"
            ).group_by(Document.pdf_author).all()

            # Count unique authors (excluding null)
            authors_with_names = [(a, c) for a, c in author_counts if a]
            result["total_authors"] = len(authors_with_names)
            result["anonymous_count"] = sum(c for a, c in author_counts if not a)

            # Single-document authors
            result["single_document_authors"] = len([a for a, c in authors_with_names if c == 1])

            # Prolific authors (5+ documents)
            result["prolific_authors"] = len([a for a, c in authors_with_names if c >= 5])

            # Top authors with percentages
            top_authors = sorted(
                authors_with_names,
                key=lambda x: x[1],
                reverse=True
            )[:20]

            result["top_authors"] = [
                {
                    "name": author,
                    "count": count,
                    "percentage": (count / total_docs * 100) if total_docs > 0 else 0
                }
                for author, count in top_authors
            ]

        except Exception as e:
            logger.error(f"Author analysis failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        return result


# Singleton instance
_service_instance = None


def get_metadata_forensics_service() -> MetadataForensicsService:
    """Get singleton metadata forensics service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MetadataForensicsService()
    return _service_instance
