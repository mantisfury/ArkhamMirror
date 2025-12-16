"""
Fingerprint Duplicate Detector Service

Fuzzy matching for near-duplicate documents:
- MinHash/SimHash for fast similarity detection
- Identify plagiarism, template reuse, copy-paste patterns
- Cluster similar documents by content fingerprint
"""

import os
import logging
import hashlib
import re
from typing import Dict, Any, List, Set
from datetime import datetime
from collections import defaultdict
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import Document, Chunk
from app.arkham.services.utils.security_utils import get_display_filename

load_dotenv()
logger = logging.getLogger(__name__)




class FingerprintService:
    """Service for detecting near-duplicate documents using fingerprinting."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        self.num_perm = 128  # Number of permutations for MinHash
        self.shingle_size = 5  # Words per shingle

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        words = text.split()
        return [w for w in words if len(w) > 2]

    def _create_shingles(self, text: str) -> Set[str]:
        """Create word-based shingles from text."""
        words = self._tokenize(text)
        if len(words) < self.shingle_size:
            return {" ".join(words)} if words else set()

        shingles = set()
        for i in range(len(words) - self.shingle_size + 1):
            shingle = " ".join(words[i : i + self.shingle_size])
            shingles.add(shingle)
        return shingles

    def _simhash(self, text: str) -> int:
        """Compute SimHash fingerprint for text."""
        shingles = self._create_shingles(text)
        if not shingles:
            return 0

        v = [0] * 64
        for shingle in shingles:
            h = int(hashlib.md5(shingle.encode()).hexdigest(), 16)
            for i in range(64):
                bit = (h >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1

        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= 1 << i
        return fingerprint

    def _hamming_distance(self, hash1: int, hash2: int) -> int:
        """Compute Hamming distance between two hashes."""
        xor = hash1 ^ hash2
        count = 0
        while xor:
            count += xor & 1
            xor >>= 1
        return count

    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Compute Jaccard similarity between two sets."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def compute_document_fingerprint(self, doc_id: int) -> Dict[str, Any]:
        """Compute fingerprint for a single document."""
        session = self.Session()
        try:
            doc = session.query(Document).filter_by(id=doc_id).first()
            if not doc:
                return {"error": "Document not found"}

            chunks = session.query(Chunk).filter_by(doc_id=doc_id).all()
            full_text = " ".join([c.text for c in chunks])

            simhash = self._simhash(full_text)
            shingles = self._create_shingles(full_text)
            word_count = len(self._tokenize(full_text))

            return {
                "document_id": doc_id,
                "filename": get_display_filename(doc),
                "simhash": simhash,
                "shingle_count": len(shingles),
                "word_count": word_count,
                "shingles": shingles,  # Keep for detailed comparison
            }
        finally:
            session.close()

    def find_similar_documents(self, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Find all pairs of similar documents in the corpus."""
        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(100)
                .all()
            )

            # Compute fingerprints for all documents
            fingerprints = []
            for doc in documents:
                chunks = session.query(Chunk).filter_by(doc_id=doc.id).all()
                full_text = " ".join([c.text for c in chunks])

                if len(full_text) < 50:  # Skip very short documents
                    continue

                simhash = self._simhash(full_text)
                shingles = self._create_shingles(full_text)

                fingerprints.append(
                    {
                        "document_id": doc.id,
                        "filename": get_display_filename(doc),
                        "simhash": simhash,
                        "shingles": shingles,
                        "word_count": len(self._tokenize(full_text)),
                    }
                )

            # Find similar pairs
            similar_pairs = []
            for i in range(len(fingerprints)):
                for j in range(i + 1, len(fingerprints)):
                    fp1 = fingerprints[i]
                    fp2 = fingerprints[j]

                    # Quick check with SimHash (Hamming distance)
                    hamming = self._hamming_distance(fp1["simhash"], fp2["simhash"])
                    if hamming > 20:  # Too different based on SimHash
                        continue

                    # Detailed check with Jaccard similarity
                    jaccard = self._jaccard_similarity(fp1["shingles"], fp2["shingles"])

                    if jaccard >= threshold:
                        similar_pairs.append(
                            {
                                "doc1_id": fp1["document_id"],
                                "doc1_filename": fp1["filename"],
                                "doc2_id": fp2["document_id"],
                                "doc2_filename": fp2["filename"],
                                "similarity": round(jaccard * 100, 1),
                                "hamming_distance": hamming,
                                "match_type": self._classify_match(jaccard),
                            }
                        )

            # Sort by similarity
            similar_pairs.sort(key=lambda x: x["similarity"], reverse=True)
            return similar_pairs

        finally:
            session.close()

    def _classify_match(self, similarity: float) -> str:
        """Classify the type of match based on similarity score."""
        if similarity >= 0.95:
            return "exact_duplicate"
        elif similarity >= 0.85:
            return "near_duplicate"
        elif similarity >= 0.7:
            return "similar_content"
        elif similarity >= 0.5:
            return "partial_overlap"
        else:
            return "low_similarity"

    def find_copy_paste_patterns(self, min_length: int = 50) -> List[Dict[str, Any]]:
        """Find shared text segments across documents (copy-paste detection)."""
        session = self.Session()
        try:
            documents = session.query(Document).limit(50).all()

            # Extract paragraphs/segments from each document
            doc_segments = {}
            segment_to_docs = defaultdict(list)

            for doc in documents:
                chunks = session.query(Chunk).filter_by(doc_id=doc.id).all()

                for chunk in chunks:
                    # Split into paragraphs
                    paragraphs = [
                        p.strip()
                        for p in chunk.text.split("\n\n")
                        if len(p.strip()) >= min_length
                    ]

                    for para in paragraphs:
                        # Normalize for comparison
                        normalized = " ".join(para.lower().split())
                        segment_hash = hashlib.md5(normalized.encode()).hexdigest()

                        if doc.id not in doc_segments:
                            doc_segments[doc.id] = {
                                "filename": get_display_filename(doc),
                                "segments": set(),
                            }
                        doc_segments[doc.id]["segments"].add(segment_hash)

                        segment_to_docs[segment_hash].append(
                            {
                                "doc_id": doc.id,
                                "filename": get_display_filename(doc),
                                "original_text": para[:200] + "..."
                                if len(para) > 200
                                else para,
                            }
                        )

            # Find segments that appear in multiple documents
            shared_patterns = []
            for segment_hash, occurrences in segment_to_docs.items():
                if len(occurrences) > 1:
                    # Deduplicate by doc_id
                    unique_docs = {}
                    for occ in occurrences:
                        if occ["doc_id"] not in unique_docs:
                            unique_docs[occ["doc_id"]] = occ

                    if len(unique_docs) > 1:
                        shared_patterns.append(
                            {
                                "pattern_hash": segment_hash[:8],
                                "occurrences": len(unique_docs),
                                "documents": list(unique_docs.values()),
                                "sample_text": occurrences[0]["original_text"],
                            }
                        )

            # Sort by number of occurrences
            shared_patterns.sort(key=lambda x: x["occurrences"], reverse=True)
            return shared_patterns[:50]

        finally:
            session.close()

    def cluster_similar_documents(self, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """Cluster documents by content similarity."""
        similar_pairs = self.find_similar_documents(threshold)

        if not similar_pairs:
            return []

        # Build adjacency list
        graph = defaultdict(set)
        doc_info = {}

        for pair in similar_pairs:
            graph[pair["doc1_id"]].add(pair["doc2_id"])
            graph[pair["doc2_id"]].add(pair["doc1_id"])
            doc_info[pair["doc1_id"]] = pair["doc1_filename"]
            doc_info[pair["doc2_id"]] = pair["doc2_filename"]

        # Find connected components (clusters)
        visited = set()
        clusters = []

        for doc_id in graph:
            if doc_id in visited:
                continue

            # BFS to find cluster
            cluster = []
            queue = [doc_id]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster.append(
                    {"id": current, "filename": doc_info.get(current, "Unknown")}
                )

                for neighbor in graph[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(cluster) > 1:
                clusters.append(
                    {
                        "cluster_id": len(clusters) + 1,
                        "size": len(cluster),
                        "documents": cluster,
                    }
                )

        # Sort by cluster size
        clusters.sort(key=lambda x: x["size"], reverse=True)
        return clusters

    def get_duplicate_summary(self) -> Dict[str, Any]:
        """Get summary statistics about duplicates in the corpus."""
        similar_pairs = self.find_similar_documents(threshold=0.5)
        clusters = self.cluster_similar_documents(threshold=0.6)
        copy_patterns = self.find_copy_paste_patterns()

        # Count by match type
        match_types = defaultdict(int)
        for pair in similar_pairs:
            match_types[pair["match_type"]] += 1

        return {
            "total_similar_pairs": len(similar_pairs),
            "exact_duplicates": match_types.get("exact_duplicate", 0),
            "near_duplicates": match_types.get("near_duplicate", 0),
            "similar_content": match_types.get("similar_content", 0),
            "partial_overlap": match_types.get("partial_overlap", 0),
            "total_clusters": len(clusters),
            "shared_patterns": len(copy_patterns),
            "analyzed_at": datetime.now().isoformat(),
        }

    # ========== STYLOMETRY / AUTHORSHIP ANALYSIS ==========

    # Common function words (highly author-specific usage patterns)
    FUNCTION_WORDS = [
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "then",
        "because",
        "as",
        "of",
        "in",
        "to",
        "for",
        "with",
        "on",
        "at",
        "by",
        "from",
        "about",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "their",
        "them",
        "he",
        "she",
        "him",
        "her",
        "his",
        "we",
        "us",
        "our",
        "you",
        "your",
        "who",
        "which",
        "what",
        "when",
        "where",
        "how",
        "why",
        "not",
        "no",
        "yes",
        "all",
        "some",
        "any",
        "each",
        "every",
        "both",
        "more",
        "most",
        "other",
        "such",
        "only",
        "just",
        "also",
        "very",
        "even",
    ]

    def _get_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting on period, exclamation, question mark
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

    def _get_words_with_punctuation(self, text: str) -> List[str]:
        """Get words preserving some structure for analysis."""
        return text.lower().split()

    def compute_style_profile(self, doc_id: int) -> Dict[str, Any]:
        """Compute stylometric profile for a document."""
        session = self.Session()
        try:
            doc = session.query(Document).filter_by(id=doc_id).first()
            if not doc:
                return {"error": "Document not found"}

            chunks = session.query(Chunk).filter_by(doc_id=doc_id).all()
            full_text = " ".join([c.text for c in chunks])

            if len(full_text) < 100:
                return {"error": "Document too short for analysis"}

            words = self._tokenize(full_text)
            sentences = self._get_sentences(full_text)

            if not words or not sentences:
                return {"error": "Unable to parse document"}

            # Lexical features
            word_count = len(words)
            unique_words = set(words)
            vocabulary_richness = (
                len(unique_words) / word_count if word_count > 0 else 0
            )
            avg_word_length = (
                sum(len(w) for w in words) / word_count if word_count > 0 else 0
            )

            # Hapax legomena (words used only once) - author signature
            word_freq = defaultdict(int)
            for w in words:
                word_freq[w] += 1
            hapax_count = sum(1 for w, c in word_freq.items() if c == 1)
            hapax_ratio = hapax_count / word_count if word_count > 0 else 0

            # Sentence features
            sentence_lengths = [len(self._tokenize(s)) for s in sentences]
            avg_sentence_length = (
                sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
            )
            sentence_length_variance = (
                sum((length - avg_sentence_length) ** 2 for length in sentence_lengths)
                / len(sentence_lengths)
                if len(sentence_lengths) > 1
                else 0
            )

            # Function word usage (highly author-specific)
            function_word_counts = {}
            for fw in self.FUNCTION_WORDS:
                count = sum(1 for w in words if w == fw)
                if count > 0:
                    function_word_counts[fw] = count / word_count

            # Top function words
            top_function_words = sorted(
                function_word_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # Punctuation patterns
            comma_count = full_text.count(",")
            semicolon_count = full_text.count(";")
            colon_count = full_text.count(":")
            exclamation_count = full_text.count("!")
            question_count = full_text.count("?")

            punctuation_per_sentence = (
                (comma_count + semicolon_count + colon_count) / len(sentences)
                if sentences
                else 0
            )

            # Word length distribution
            word_length_dist = defaultdict(int)
            for w in words:
                length_bucket = min(len(w), 12)  # Bucket 12+ together
                word_length_dist[length_bucket] += 1

            # Normalize distribution
            word_length_dist = {k: v / word_count for k, v in word_length_dist.items()}

            return {
                "document_id": doc_id,
                "filename": get_display_filename(doc),
                "word_count": word_count,
                "sentence_count": len(sentences),
                # Lexical metrics
                "avg_word_length": round(avg_word_length, 2),
                "vocabulary_richness": round(vocabulary_richness, 3),
                "hapax_ratio": round(hapax_ratio, 3),
                # Sentence metrics
                "avg_sentence_length": round(avg_sentence_length, 1),
                "sentence_variance": round(sentence_length_variance, 1),
                # Function words (author fingerprint)
                "top_function_words": top_function_words,
                "function_word_vector": function_word_counts,
                # Punctuation style
                "punctuation_per_sentence": round(punctuation_per_sentence, 2),
                "exclamation_ratio": round(exclamation_count / len(sentences), 3)
                if sentences
                else 0,
                "question_ratio": round(question_count / len(sentences), 3)
                if sentences
                else 0,
                # Word length distribution
                "word_length_distribution": dict(word_length_dist),
            }
        finally:
            session.close()

    def _style_similarity(self, profile1: Dict, profile2: Dict) -> float:
        """Compute similarity between two style profiles (0-100)."""
        if "error" in profile1 or "error" in profile2:
            return 0.0

        # Weight different features
        similarity_scores = []

        # Lexical similarity (25%)
        awl_diff = abs(profile1["avg_word_length"] - profile2["avg_word_length"])
        awl_sim = max(0, 1 - awl_diff / 3)  # 3-char diff = 0 similarity
        similarity_scores.append(awl_sim * 0.10)

        vr_diff = abs(profile1["vocabulary_richness"] - profile2["vocabulary_richness"])
        vr_sim = max(0, 1 - vr_diff / 0.2)
        similarity_scores.append(vr_sim * 0.10)

        hr_diff = abs(profile1["hapax_ratio"] - profile2["hapax_ratio"])
        hr_sim = max(0, 1 - hr_diff / 0.15)
        similarity_scores.append(hr_sim * 0.05)

        # Sentence similarity (25%)
        asl_diff = abs(
            profile1["avg_sentence_length"] - profile2["avg_sentence_length"]
        )
        asl_sim = max(0, 1 - asl_diff / 10)  # 10-word diff = 0 similarity
        similarity_scores.append(asl_sim * 0.15)

        sv_diff = abs(profile1["sentence_variance"] - profile2["sentence_variance"])
        sv_sim = max(0, 1 - sv_diff / 50)
        similarity_scores.append(sv_sim * 0.10)

        # Function word similarity (35%) - most author-specific
        fw1 = profile1.get("function_word_vector", {})
        fw2 = profile2.get("function_word_vector", {})
        all_fw = set(fw1.keys()) | set(fw2.keys())
        if all_fw:
            fw_diffs = []
            for fw in all_fw:
                v1 = fw1.get(fw, 0)
                v2 = fw2.get(fw, 0)
                fw_diffs.append(abs(v1 - v2))
            avg_fw_diff = sum(fw_diffs) / len(fw_diffs)
            fw_sim = max(0, 1 - avg_fw_diff / 0.02)
            similarity_scores.append(fw_sim * 0.35)

        # Punctuation style (15%)
        pps_diff = abs(
            profile1["punctuation_per_sentence"] - profile2["punctuation_per_sentence"]
        )
        pps_sim = max(0, 1 - pps_diff / 3)
        similarity_scores.append(pps_sim * 0.15)

        return round(sum(similarity_scores) * 100, 1)

    def find_style_matches(self, threshold: float = 60.0) -> List[Dict[str, Any]]:
        """Find documents with similar writing styles."""
        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(50)
                .all()
            )

            # Compute profiles for all documents
            profiles = []
            for doc in documents:
                profile = self.compute_style_profile(doc.id)
                if "error" not in profile:
                    profiles.append(profile)

            # Find similar pairs
            style_matches = []
            for i in range(len(profiles)):
                for j in range(i + 1, len(profiles)):
                    similarity = self._style_similarity(profiles[i], profiles[j])
                    if similarity >= threshold:
                        style_matches.append(
                            {
                                "doc1_id": profiles[i]["document_id"],
                                "doc1_filename": profiles[i]["filename"],
                                "doc2_id": profiles[j]["document_id"],
                                "doc2_filename": profiles[j]["filename"],
                                "style_similarity": similarity,
                                "key_similarities": self._get_style_comparison(
                                    profiles[i], profiles[j]
                                ),
                            }
                        )

            style_matches.sort(key=lambda x: x["style_similarity"], reverse=True)
            return style_matches

        finally:
            session.close()

    def _get_style_comparison(self, p1: Dict, p2: Dict) -> List[str]:
        """Get human-readable comparison of style features."""
        comparisons = []

        # Sentence length
        if abs(p1["avg_sentence_length"] - p2["avg_sentence_length"]) < 3:
            comparisons.append(
                f"Similar sentence length (~{round((p1['avg_sentence_length'] + p2['avg_sentence_length']) / 2)} words)"
            )

        # Vocabulary
        if abs(p1["vocabulary_richness"] - p2["vocabulary_richness"]) < 0.05:
            richness = (p1["vocabulary_richness"] + p2["vocabulary_richness"]) / 2
            label = (
                "rich"
                if richness > 0.4
                else "moderate"
                if richness > 0.25
                else "simple"
            )
            comparisons.append(f"Similar vocabulary ({label})")

        # Word length
        if abs(p1["avg_word_length"] - p2["avg_word_length"]) < 0.5:
            comparisons.append("Similar word complexity")

        # Punctuation
        if abs(p1["punctuation_per_sentence"] - p2["punctuation_per_sentence"]) < 1:
            comparisons.append("Similar punctuation style")

        # Top function words overlap
        top1 = set(fw for fw, _ in p1.get("top_function_words", [])[:5])
        top2 = set(fw for fw, _ in p2.get("top_function_words", [])[:5])
        overlap = len(top1 & top2)
        if overlap >= 3:
            comparisons.append("Similar function word patterns")

        return comparisons[:4]  # Return top 4 comparisons

    def cluster_by_authorship(self, threshold: float = 55.0) -> List[Dict[str, Any]]:
        """Cluster documents by writing style (potential same author)."""
        style_matches = self.find_style_matches(threshold)

        if not style_matches:
            return []

        # Build graph and find connected components (same as content clustering)
        graph = defaultdict(set)
        doc_info = {}

        for match in style_matches:
            graph[match["doc1_id"]].add(match["doc2_id"])
            graph[match["doc2_id"]].add(match["doc1_id"])
            doc_info[match["doc1_id"]] = match["doc1_filename"]
            doc_info[match["doc2_id"]] = match["doc2_filename"]

        visited = set()
        clusters = []

        for doc_id in graph:
            if doc_id in visited:
                continue

            cluster_docs = []
            queue = [doc_id]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster_docs.append(
                    {
                        "id": current,
                        "filename": doc_info.get(current, "Unknown"),
                    }
                )

                for neighbor in graph[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(cluster_docs) > 1:
                clusters.append(
                    {
                        "cluster_id": len(clusters) + 1,
                        "size": len(cluster_docs),
                        "documents": cluster_docs,
                        "label": f"Author Group {len(clusters) + 1}",
                    }
                )

        clusters.sort(key=lambda x: x["size"], reverse=True)
        return clusters

    def get_all_style_profiles(self) -> List[Dict[str, Any]]:
        """Get style profiles for all recent documents."""
        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(50)
                .all()
            )

            profiles = []
            for doc in documents:
                profile = self.compute_style_profile(doc.id)
                if "error" not in profile:
                    profiles.append(profile)

            return profiles
        finally:
            session.close()

    # ========== UNMASK AUTHOR / AUTHORSHIP ATTRIBUTION ==========

    def compute_aggregate_style_profile(self, doc_ids: List[int]) -> Dict[str, Any]:
        """Compute an aggregate style profile from multiple documents (known author corpus)."""
        if not doc_ids:
            return {"error": "No documents provided"}

        profiles = []
        for doc_id in doc_ids:
            profile = self.compute_style_profile(doc_id)
            if "error" not in profile:
                profiles.append(profile)

        if not profiles:
            return {"error": "No valid profiles computed"}

        # Aggregate numeric features by averaging
        aggregate = {
            "document_count": len(profiles),
            "document_ids": doc_ids,
            "total_words": sum(p["word_count"] for p in profiles),
            "avg_word_length": sum(p["avg_word_length"] for p in profiles)
            / len(profiles),
            "vocabulary_richness": sum(p["vocabulary_richness"] for p in profiles)
            / len(profiles),
            "hapax_ratio": sum(p["hapax_ratio"] for p in profiles) / len(profiles),
            "avg_sentence_length": sum(p["avg_sentence_length"] for p in profiles)
            / len(profiles),
            "sentence_variance": sum(p["sentence_variance"] for p in profiles)
            / len(profiles),
            "punctuation_per_sentence": sum(
                p["punctuation_per_sentence"] for p in profiles
            )
            / len(profiles),
        }

        # Aggregate function word vectors by averaging
        all_fw = set()
        for p in profiles:
            all_fw.update(p.get("function_word_vector", {}).keys())

        aggregated_fw = {}
        for fw in all_fw:
            values = [p.get("function_word_vector", {}).get(fw, 0) for p in profiles]
            aggregated_fw[fw] = sum(values) / len(profiles)

        aggregate["function_word_vector"] = aggregated_fw

        # Top function words from aggregate
        aggregate["top_function_words"] = sorted(
            aggregated_fw.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return aggregate

    def unmask_author(
        self, known_doc_ids: List[int], unknown_doc_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Unmask Author: Compare unknown documents against a known author's profile.

        Args:
            known_doc_ids: Document IDs known to be by the suspected author
            unknown_doc_ids: Document IDs to check for authorship match

        Returns:
            {
                "reference_profile": {...},  # Aggregate profile of known docs
                "results": [  # Sorted by probability (highest first)
                    {
                        "document_id": int,
                        "filename": str,
                        "probability": float,  # 0-100
                        "verdict": str,  # "likely_match", "possible_match", "unlikely_match"
                        "key_matches": [str],  # What features matched
                        "key_differences": [str],  # What features differed
                    }
                ],
                "pseudonym_groups": [  # Unknowns grouped by similar style
                    {
                        "group_id": int,
                        "match_to_reference": float,  # Average probability to reference
                        "documents": [{"id": int, "filename": str, "probability": float}]
                    }
                ]
            }
        """
        if not known_doc_ids:
            return {"error": "No known documents selected"}
        if not unknown_doc_ids:
            return {"error": "No unknown documents selected"}

        # Build reference profile from known documents
        reference = self.compute_aggregate_style_profile(known_doc_ids)
        if "error" in reference:
            return reference

        # Analyze each unknown document
        results = []
        unknown_profiles = []

        for doc_id in unknown_doc_ids:
            profile = self.compute_style_profile(doc_id)
            if "error" in profile:
                continue

            unknown_profiles.append(profile)

            # Compute similarity to reference
            similarity = self._style_similarity(reference, profile)

            # Determine verdict
            if similarity >= 75:
                verdict = "likely_match"
            elif similarity >= 55:
                verdict = "possible_match"
            else:
                verdict = "unlikely_match"

            # Get key matches and differences
            key_matches, key_differences = self._get_detailed_comparison(
                reference, profile
            )

            results.append(
                {
                    "document_id": doc_id,
                    "filename": profile["filename"],
                    "probability": similarity,
                    "verdict": verdict,
                    "key_matches": key_matches,
                    "key_differences": key_differences,
                }
            )

        # Sort by probability (highest first)
        results.sort(key=lambda x: x["probability"], reverse=True)

        # Group unknowns by their style similarity (find pseudonym clusters)
        pseudonym_groups = self._group_by_pseudonym(unknown_profiles, results)

        return {
            "reference_profile": {
                "document_count": reference["document_count"],
                "avg_word_length": round(reference["avg_word_length"], 2),
                "vocabulary_richness": round(reference["vocabulary_richness"], 3),
                "avg_sentence_length": round(reference["avg_sentence_length"], 1),
            },
            "results": results,
            "pseudonym_groups": pseudonym_groups,
            "summary": {
                "likely_matches": sum(
                    1 for r in results if r["verdict"] == "likely_match"
                ),
                "possible_matches": sum(
                    1 for r in results if r["verdict"] == "possible_match"
                ),
                "unlikely_matches": sum(
                    1 for r in results if r["verdict"] == "unlikely_match"
                ),
            },
        }

    def _get_detailed_comparison(self, ref: Dict, profile: Dict) -> tuple:
        """Get detailed comparison between reference and candidate profile."""
        matches = []
        differences = []

        # Word length
        awl_diff = abs(ref["avg_word_length"] - profile["avg_word_length"])
        if awl_diff < 0.3:
            matches.append("Word complexity")
        elif awl_diff > 1.0:
            differences.append("Word complexity")

        # Vocabulary richness
        vr_diff = abs(ref["vocabulary_richness"] - profile["vocabulary_richness"])
        if vr_diff < 0.05:
            matches.append("Vocabulary richness")
        elif vr_diff > 0.15:
            differences.append("Vocabulary richness")

        # Sentence length
        asl_diff = abs(ref["avg_sentence_length"] - profile["avg_sentence_length"])
        if asl_diff < 3:
            matches.append("Sentence length")
        elif asl_diff > 8:
            differences.append("Sentence length")

        # Punctuation
        pps_diff = abs(
            ref["punctuation_per_sentence"] - profile["punctuation_per_sentence"]
        )
        if pps_diff < 0.5:
            matches.append("Punctuation style")
        elif pps_diff > 2:
            differences.append("Punctuation style")

        # Function words
        ref_fw = set(fw for fw, _ in ref.get("top_function_words", [])[:5])
        prof_fw = set(fw for fw, _ in profile.get("top_function_words", [])[:5])
        overlap = len(ref_fw & prof_fw)
        if overlap >= 4:
            matches.append("Function word patterns")
        elif overlap <= 1:
            differences.append("Function word patterns")

        return matches[:4], differences[:3]

    def _group_by_pseudonym(
        self, profiles: List[Dict], results: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Group unknown documents by similar writing style (pseudonym detection)."""
        if len(profiles) < 2:
            return []

        # Build similarity matrix between unknowns
        n = len(profiles)
        similarity_matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                sim = self._style_similarity(profiles[i], profiles[j])
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim

        # Simple clustering: group documents with similarity > 60%
        visited = set()
        groups = []
        threshold = 60.0

        for i in range(n):
            if i in visited:
                continue

            # Start a new group
            group_members = [i]
            visited.add(i)

            # Find all documents similar to this one
            for j in range(n):
                if j not in visited and similarity_matrix[i][j] >= threshold:
                    group_members.append(j)
                    visited.add(j)

            if len(group_members) > 1:
                # Calculate average match to reference
                avg_prob = sum(results[m]["probability"] for m in group_members) / len(
                    group_members
                )

                groups.append(
                    {
                        "group_id": len(groups) + 1,
                        "match_to_reference": round(avg_prob, 1),
                        "size": len(group_members),
                        "documents": [
                            {
                                "id": results[m]["document_id"],
                                "filename": results[m]["filename"],
                                "probability": results[m]["probability"],
                            }
                            for m in group_members
                        ],
                    }
                )

        # Sort by match to reference
        groups.sort(key=lambda x: x["match_to_reference"], reverse=True)
        return groups

    def get_all_documents_for_selection(self) -> List[Dict[str, Any]]:
        """Get all documents for the unmask author selection UI."""
        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(100)
                .all()
            )

            return [
                {
                    "id": doc.id,
                    "filename": get_display_filename(doc),
                    "file_type": doc.doc_type or "unknown",
                }
                for doc in documents
            ]
        finally:
            session.close()


# Singleton
_service_instance = None


def get_fingerprint_service() -> FingerprintService:
    global _service_instance
    if _service_instance is None:
        _service_instance = FingerprintService()
    return _service_instance


# Alias for backwards compatibility
get_duplicates_service = get_fingerprint_service
