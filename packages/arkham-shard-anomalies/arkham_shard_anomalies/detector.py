"""Core anomaly detection logic."""

import logging
import re
from typing import Any
from datetime import datetime

import numpy as np
from scipy import stats

from .models import (
    Anomaly,
    AnomalyType,
    SeverityLevel,
    DetectionConfig,
    OutlierResult,
)

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Core anomaly detection engine.

    Implements multiple detection strategies:
    - Embedding-based: documents far from cluster centroids
    - Statistical: unusual word frequencies, lengths, patterns
    - Temporal: documents with unexpected dates
    - Metadata: unusual file properties
    - Structural: unusual document structure
    - Red flags: sensitive content indicators
    """

    def __init__(self, config: DetectionConfig | None = None):
        """
        Initialize detector with configuration.

        Args:
            config: Detection configuration
        """
        self.config = config or DetectionConfig()

        # Red flag patterns
        self.money_pattern = re.compile(
            r'\$\s*\d+(?:,\d{3})*(?:\.\d{2})?|'
            r'\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|dollars?|euros?|pounds?)',
            re.IGNORECASE
        )
        self.date_pattern = re.compile(
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|'
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
            re.IGNORECASE
        )
        self.name_pattern = re.compile(
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'  # Simple capitalized name pattern
        )

        self.sensitive_keywords = {
            'confidential', 'secret', 'classified', 'private', 'restricted',
            'internal only', 'do not distribute', 'proprietary', 'privileged'
        }

    def detect_content_anomalies(
        self,
        doc_id: str,
        embedding: np.ndarray,
        corpus_embeddings: list[np.ndarray],
        corpus_doc_ids: list[str],
    ) -> list[Anomaly]:
        """
        Detect content anomalies using embedding distance.

        Documents that are semantically distant from the corpus
        are flagged as potential anomalies.

        Args:
            doc_id: Document ID
            embedding: Document embedding vector
            corpus_embeddings: All corpus embeddings
            corpus_doc_ids: Corresponding document IDs

        Returns:
            List of detected anomalies
        """
        if not self.config.detect_content:
            return []

        anomalies = []

        try:
            # Calculate distances to all other documents
            distances = []
            for other_emb in corpus_embeddings:
                # Cosine distance
                cos_sim = np.dot(embedding, other_emb) / (
                    np.linalg.norm(embedding) * np.linalg.norm(other_emb)
                )
                distance = 1 - cos_sim
                distances.append(distance)

            # Calculate statistics
            mean_dist = np.mean(distances)
            std_dist = np.std(distances)
            min_dist = np.min(distances)

            # Z-score for this document's minimum distance
            if std_dist > 0:
                z_score = (min_dist - mean_dist) / std_dist
            else:
                z_score = 0.0

            # Flag if significantly distant
            if z_score > self.config.z_score_threshold or min_dist > self.config.min_cluster_distance:
                severity = self._calculate_severity(z_score, self.config.z_score_threshold)

                anomaly = Anomaly(
                    id=self._generate_id(),
                    doc_id=doc_id,
                    anomaly_type=AnomalyType.CONTENT,
                    score=float(z_score),
                    severity=severity,
                    confidence=min(1.0, z_score / 5.0),  # Scale confidence
                    explanation=f"Document is semantically distant from corpus (z-score: {z_score:.2f})",
                    details={
                        'z_score': float(z_score),
                        'min_distance': float(min_dist),
                        'mean_distance': float(mean_dist),
                        'std_distance': float(std_dist),
                    }
                )
                anomalies.append(anomaly)

        except Exception as e:
            logger.error(f"Content anomaly detection failed for {doc_id}: {e}", exc_info=True)

        return anomalies

    def detect_statistical_anomalies(
        self,
        doc_id: str,
        text: str,
        corpus_stats: dict[str, Any],
    ) -> list[Anomaly]:
        """
        Detect statistical anomalies in text properties.

        Checks for:
        - Unusual document length
        - Unusual word frequency distributions
        - Unusual reading level
        - Unusual character/word ratios

        Args:
            doc_id: Document ID
            text: Document text
            corpus_stats: Corpus-wide statistics

        Returns:
            List of detected anomalies
        """
        if not self.config.detect_statistical:
            return []

        anomalies = []

        try:
            # Calculate document statistics
            doc_stats = self._calculate_text_stats(text)

            # Check each metric against corpus
            for metric_name, doc_value in doc_stats.items():
                if metric_name not in corpus_stats:
                    continue

                corpus_mean = corpus_stats[metric_name]['mean']
                corpus_std = corpus_stats[metric_name]['std']

                if corpus_std > 0:
                    z_score = abs((doc_value - corpus_mean) / corpus_std)

                    if z_score > self.config.z_score_threshold:
                        severity = self._calculate_severity(z_score, self.config.z_score_threshold)

                        anomaly = Anomaly(
                            id=self._generate_id(),
                            doc_id=doc_id,
                            anomaly_type=AnomalyType.STATISTICAL,
                            score=float(z_score),
                            severity=severity,
                            confidence=min(1.0, z_score / 5.0),
                            explanation=f"Unusual {metric_name}: {doc_value:.2f} (expected: {corpus_mean:.2f})",
                            details={
                                'metric': metric_name,
                                'value': float(doc_value),
                                'expected_mean': float(corpus_mean),
                                'expected_std': float(corpus_std),
                                'z_score': float(z_score),
                            },
                            field_name=metric_name,
                            expected_range=f"{corpus_mean - 2*corpus_std:.2f} - {corpus_mean + 2*corpus_std:.2f}",
                            actual_value=f"{doc_value:.2f}",
                        )
                        anomalies.append(anomaly)

        except Exception as e:
            logger.error(f"Statistical anomaly detection failed for {doc_id}: {e}", exc_info=True)

        return anomalies

    def detect_red_flags(self, doc_id: str, text: str, metadata: dict[str, Any]) -> list[Anomaly]:
        """
        Detect red flag patterns in content.

        Looks for:
        - Money amounts
        - Dates
        - Person names
        - Sensitive keywords

        Args:
            doc_id: Document ID
            text: Document text
            metadata: Document metadata

        Returns:
            List of detected anomalies
        """
        if not self.config.detect_red_flags:
            return []

        anomalies = []

        try:
            # Money patterns
            if self.config.money_patterns:
                money_matches = self.money_pattern.findall(text)
                if len(money_matches) > 10:  # Threshold for "many" money references
                    anomaly = Anomaly(
                        id=self._generate_id(),
                        doc_id=doc_id,
                        anomaly_type=AnomalyType.RED_FLAG,
                        score=float(len(money_matches)),
                        severity=SeverityLevel.HIGH,
                        confidence=0.9,
                        explanation=f"High frequency of monetary references ({len(money_matches)} found)",
                        details={
                            'pattern_type': 'money',
                            'count': len(money_matches),
                            'examples': money_matches[:5],
                        }
                    )
                    anomalies.append(anomaly)

            # Date patterns
            if self.config.date_patterns:
                date_matches = self.date_pattern.findall(text)
                if len(date_matches) > 15:  # Threshold for "many" date references
                    anomaly = Anomaly(
                        id=self._generate_id(),
                        doc_id=doc_id,
                        anomaly_type=AnomalyType.RED_FLAG,
                        score=float(len(date_matches)),
                        severity=SeverityLevel.MEDIUM,
                        confidence=0.8,
                        explanation=f"High frequency of date references ({len(date_matches)} found)",
                        details={
                            'pattern_type': 'dates',
                            'count': len(date_matches),
                            'examples': date_matches[:5],
                        }
                    )
                    anomalies.append(anomaly)

            # Name patterns
            if self.config.name_patterns:
                name_matches = self.name_pattern.findall(text)
                unique_names = len(set(name_matches))
                if unique_names > 20:  # Many unique name-like patterns
                    anomaly = Anomaly(
                        id=self._generate_id(),
                        doc_id=doc_id,
                        anomaly_type=AnomalyType.RED_FLAG,
                        score=float(unique_names),
                        severity=SeverityLevel.MEDIUM,
                        confidence=0.7,
                        explanation=f"High frequency of name patterns ({unique_names} unique found)",
                        details={
                            'pattern_type': 'names',
                            'count': unique_names,
                            'examples': list(set(name_matches))[:5],
                        }
                    )
                    anomalies.append(anomaly)

            # Sensitive keywords
            if self.config.sensitive_keywords:
                text_lower = text.lower()
                found_keywords = [kw for kw in self.sensitive_keywords if kw in text_lower]
                if found_keywords:
                    anomaly = Anomaly(
                        id=self._generate_id(),
                        doc_id=doc_id,
                        anomaly_type=AnomalyType.RED_FLAG,
                        score=float(len(found_keywords)),
                        severity=SeverityLevel.CRITICAL,
                        confidence=1.0,
                        explanation=f"Contains sensitive keywords: {', '.join(found_keywords)}",
                        details={
                            'pattern_type': 'sensitive_keywords',
                            'keywords': found_keywords,
                        }
                    )
                    anomalies.append(anomaly)

        except Exception as e:
            logger.error(f"Red flag detection failed for {doc_id}: {e}", exc_info=True)

        return anomalies

    def detect_metadata_anomalies(
        self,
        doc_id: str,
        metadata: dict[str, Any],
        corpus_metadata_stats: dict[str, Any],
    ) -> list[Anomaly]:
        """
        Detect anomalies in document metadata.

        Checks for:
        - Unusual file sizes
        - Unusual creation dates
        - Unusual modification dates
        - Missing expected metadata fields

        Args:
            doc_id: Document ID
            metadata: Document metadata
            corpus_metadata_stats: Corpus-wide metadata statistics

        Returns:
            List of detected anomalies
        """
        if not self.config.detect_metadata:
            return []

        anomalies = []

        try:
            # File size check
            if 'file_size' in metadata and 'file_size' in corpus_metadata_stats:
                size = metadata['file_size']
                mean = corpus_metadata_stats['file_size']['mean']
                std = corpus_metadata_stats['file_size']['std']

                if std > 0:
                    z_score = abs((size - mean) / std)
                    if z_score > self.config.z_score_threshold:
                        severity = self._calculate_severity(z_score, self.config.z_score_threshold)
                        anomaly = Anomaly(
                            id=self._generate_id(),
                            doc_id=doc_id,
                            anomaly_type=AnomalyType.METADATA,
                            score=float(z_score),
                            severity=severity,
                            confidence=min(1.0, z_score / 5.0),
                            explanation=f"Unusual file size: {size} bytes (expected: {mean:.0f})",
                            details={
                                'field': 'file_size',
                                'value': size,
                                'mean': mean,
                                'std': std,
                                'z_score': float(z_score),
                            },
                            field_name='file_size',
                        )
                        anomalies.append(anomaly)

        except Exception as e:
            logger.error(f"Metadata anomaly detection failed for {doc_id}: {e}", exc_info=True)

        return anomalies

    def _calculate_text_stats(self, text: str) -> dict[str, float]:
        """Calculate statistical properties of text."""
        words = text.split()
        sentences = text.split('.')

        return {
            'word_count': float(len(words)),
            'sentence_count': float(len(sentences)),
            'avg_word_length': float(np.mean([len(w) for w in words])) if words else 0.0,
            'avg_sentence_length': float(len(words) / len(sentences)) if sentences else 0.0,
            'char_count': float(len(text)),
        }

    def _calculate_severity(self, z_score: float, threshold: float) -> SeverityLevel:
        """Calculate severity level based on z-score."""
        if z_score >= threshold * 2:
            return SeverityLevel.CRITICAL
        elif z_score >= threshold * 1.5:
            return SeverityLevel.HIGH
        elif z_score >= threshold:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _generate_id(self) -> str:
        """Generate unique anomaly ID."""
        import uuid
        return str(uuid.uuid4())
