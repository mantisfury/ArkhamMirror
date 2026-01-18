"""
Perceptual hash computation for image similarity detection.
Computes pHash, dHash, and aHash.
"""

from typing import Dict, List
from pathlib import Path
import hashlib

from PIL import Image
import numpy as np

import structlog

logger = structlog.get_logger()


class PerceptualHashService:
    """Compute perceptual hashes for images."""

    def __init__(self, frame):
        self.frame = frame

    async def compute_all_hashes(self, file_path: Path) -> Dict[str, str]:
        """Compute all available hashes for an image file."""
        result = {
            "sha256": await self._compute_sha256(file_path),
            "md5": await self._compute_md5(file_path),
        }

        # Perceptual hashes
        try:
            result["phash"] = await self._compute_phash(file_path)
            result["ahash"] = await self._compute_ahash(file_path)
            result["dhash"] = await self._compute_dhash(file_path)
        except Exception as e:
            logger.warning("Perceptual hash computation failed", error=str(e))

        return result

    async def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA-256 hash."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _compute_md5(self, file_path: Path) -> str:
        """Compute MD5 hash."""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    async def _compute_phash(self, file_path: Path) -> str:
        """
        Compute perceptual hash (pHash).
        Resistant to minor modifications like resizing, compression.
        """
        from scipy.fftpack import dct

        with Image.open(file_path) as img:
            # Convert to grayscale and resize to 32x32
            img = img.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
            pixels = np.array(img, dtype=np.float64)

            # Compute 2D DCT
            dct_result = dct(dct(pixels.T, norm="ortho").T, norm="ortho")

            # Use top-left 8x8 (excluding DC component)
            dct_low = dct_result[:8, :8]

            # Compute median (excluding DC)
            med = np.median(dct_low.flatten()[1:])

            # Generate hash
            diff = dct_low > med
            return self._bool_array_to_hex(diff.flatten())

    async def _compute_ahash(self, file_path: Path) -> str:
        """
        Compute average hash (aHash).
        Fast but less robust than pHash.
        """
        with Image.open(file_path) as img:
            img = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
            pixels = np.array(img)
            avg = pixels.mean()
            diff = pixels > avg
            return self._bool_array_to_hex(diff.flatten())

    async def _compute_dhash(self, file_path: Path) -> str:
        """
        Compute difference hash (dHash).
        Good for detecting subtle modifications.
        """
        with Image.open(file_path) as img:
            img = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = np.array(img)
            # Compare adjacent pixels
            diff = pixels[:, :-1] > pixels[:, 1:]
            return self._bool_array_to_hex(diff.flatten())

    def _bool_array_to_hex(self, arr: np.ndarray) -> str:
        """Convert boolean array to hex string."""
        bits = "".join(["1" if b else "0" for b in arr])
        return hex(int(bits, 2))[2:].zfill(len(arr) // 4)

    def compute_hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        Compute Hamming distance between two perceptual hashes.
        Lower = more similar. 0 = identical. >10 typically different images.
        """
        if len(hash1) != len(hash2):
            raise ValueError("Hashes must be same length")

        # Convert hex to binary
        bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
        bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)

        return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))

    def similarity_score(self, hash1: str, hash2: str) -> float:
        """
        Compute similarity score (0.0 to 1.0) between two hashes.
        1.0 = identical, 0.0 = completely different.
        """
        distance = self.compute_hamming_distance(hash1, hash2)
        max_distance = len(hash1) * 4  # Each hex char = 4 bits
        return 1.0 - (distance / max_distance)

    async def find_similar(
        self, target_hash: str, hash_type: str = "phash", threshold: int = 10
    ) -> List[Dict]:
        """
        Find images with similar hashes in the database.

        Args:
            target_hash: Hash to compare against
            hash_type: Type of hash (phash, dhash, ahash)
            threshold: Maximum Hamming distance to consider similar

        Returns:
            List of dicts with analysis_id, hash, hamming_distance, similarity_score
        """
        db = self.frame.database if self.frame else None
        if not db:
            logger.warning("Database not available for similarity search")
            return []

        # Get all hashes from database
        try:
            rows = await db.fetch_all(
                f"SELECT id, {hash_type} FROM arkham_media_analyses WHERE {hash_type} IS NOT NULL"
            )
        except Exception as e:
            logger.warning("Failed to query hashes from database", error=str(e))
            return []

        similar = []
        for row in rows:
            hash_value = row.get(hash_type) or row.get(hash_type.upper())
            if hash_value:
                try:
                    distance = self.compute_hamming_distance(target_hash, hash_value)
                    if distance <= threshold:
                        similar.append({
                            "analysis_id": row.get("id"),
                            "hash": hash_value,
                            "hamming_distance": distance,
                            "similarity_score": self.similarity_score(target_hash, hash_value),
                        })
                except Exception:
                    continue

        # Sort by distance (most similar first)
        similar.sort(key=lambda x: x["hamming_distance"])
        return similar
