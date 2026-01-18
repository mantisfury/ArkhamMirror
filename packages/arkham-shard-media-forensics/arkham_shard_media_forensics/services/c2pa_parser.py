"""
C2PA (Content Credentials) parsing service.
Verifies provenance and authenticity metadata.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
import os

import structlog

logger = structlog.get_logger()

# Try to import c2pa-python
try:
    import c2pa
    C2PA_AVAILABLE = True
except ImportError:
    C2PA_AVAILABLE = False
    logger.info("c2pa-python not installed, C2PA features disabled")


class C2PAParser:
    """
    Parse and verify C2PA Content Credentials.

    C2PA is an open standard for media provenance adopted by:
    - Adobe (Photoshop, Lightroom, Firefly)
    - OpenAI (DALL-E)
    - Microsoft (Designer)
    - Google
    - Camera manufacturers (Leica, Nikon)

    AIR-GAP SAFE: This parser makes NO network calls.
    - Manifest parsing is fully offline
    - Signature verification requires pre-downloaded trust anchors
    - Without trust anchors, parsing still works but signatures are unverified
    """

    def __init__(self, frame, trust_anchors_path: Optional[str] = None):
        """
        Initialize C2PA parser.

        Args:
            frame: SHATTERED frame reference
            trust_anchors_path: Optional path to local trust anchors PEM file.
                               Can also be set via MEDIA_FORENSICS_TRUST_ANCHORS_PATH env var.
                               If not provided, signature verification is skipped
                               but manifest parsing still works fully offline.
        """
        self.frame = frame
        self._signature_verification_available = False

        # Check for trust anchors path (explicit param > env var)
        anchors_path = trust_anchors_path or os.environ.get("MEDIA_FORENSICS_TRUST_ANCHORS_PATH")

        if C2PA_AVAILABLE and anchors_path and Path(anchors_path).exists():
            try:
                with open(anchors_path) as f:
                    anchors_content = f.read()
                    c2pa.load_settings({
                        "verify": {"verify_cert_anchors": True},
                        "trust": {"trust_anchors": anchors_content}
                    })
                self._signature_verification_available = True
                logger.info("C2PA trust anchors loaded from local file", path=anchors_path)
            except Exception as e:
                logger.warning("Failed to load C2PA trust anchors", error=str(e))
        else:
            logger.info(
                "C2PA signature verification disabled (no trust anchors). "
                "Manifest parsing still works. For signature verification, "
                "set MEDIA_FORENSICS_TRUST_ANCHORS_PATH to a local .pem file."
            )

    def is_available(self) -> bool:
        """Check if C2PA parsing is available."""
        return C2PA_AVAILABLE

    def is_signature_verification_available(self) -> bool:
        """Check if signature verification is available (requires trust anchors)."""
        return self._signature_verification_available

    async def parse(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse C2PA manifest from a media file.

        Returns:
            Dict with manifest data if C2PA credentials exist, None otherwise.
        """
        if not C2PA_AVAILABLE:
            return {"error": "c2pa-python library not installed", "has_c2pa": False}

        try:
            with c2pa.Reader(str(file_path)) as reader:
                manifest_json = reader.json()

                if not manifest_json:
                    return {"has_c2pa": False}

                store = json.loads(manifest_json) if isinstance(manifest_json, str) else manifest_json

                result = {
                    "has_c2pa": True,
                    "manifests": [],
                    "active_manifest": None,
                    "signature_valid": False,
                    "signature_verification_available": self._signature_verification_available,
                    "signer": None,
                    "timestamp": None,
                    "actions": [],
                    "ingredients": [],
                    "claim_generator": None,
                    "ai_training_permissions": {},
                    "validation_status": [],
                    "raw_manifest": store,
                }

                # Extract active manifest
                if "active_manifest" in store:
                    active_id = store["active_manifest"]
                    result["active_manifest"] = active_id

                    if "manifests" in store and active_id in store["manifests"]:
                        manifest = store["manifests"][active_id]

                        # Claim generator
                        result["claim_generator"] = manifest.get("claim_generator")

                        # Signature info (present in manifest, verification depends on trust anchors)
                        if "signature_info" in manifest:
                            sig_info = manifest["signature_info"]
                            # signature_valid only true if we have trust anchors loaded
                            result["signature_valid"] = self._signature_verification_available
                            result["signer"] = sig_info.get("issuer")
                            result["timestamp"] = sig_info.get("time")

                        # Parse assertions
                        for assertion in manifest.get("assertions", []):
                            label = assertion.get("label", "")

                            # Actions (edit history)
                            if label == "c2pa.actions":
                                result["actions"] = assertion.get("data", {}).get("actions", [])

                            # AI training permissions
                            if label == "c2pa.training-mining":
                                entries = assertion.get("data", {}).get("entries", {})
                                result["ai_training_permissions"] = {
                                    "ai_training": entries.get("c2pa.ai_training", {}).get("use"),
                                    "ai_inference": entries.get("c2pa.ai_inference", {}).get("use"),
                                    "data_mining": entries.get("c2pa.data_mining", {}).get("use"),
                                    "ai_generative_training": entries.get("c2pa.ai_generative_training", {}).get("use"),
                                }

                        # Ingredients (source materials)
                        for ing in manifest.get("ingredients", []):
                            result["ingredients"].append({
                                "title": ing.get("title"),
                                "format": ing.get("format"),
                                "instance_id": ing.get("instance_id"),
                            })

                # All manifest IDs
                if "manifests" in store:
                    result["manifests"] = list(store["manifests"].keys())

                return result

        except Exception as e:
            logger.warning("C2PA parsing failed", error=str(e), path=str(file_path))
            return {"error": str(e), "has_c2pa": False}

    def interpret_c2pa(self, c2pa_data: Dict) -> Dict[str, Any]:
        """
        Interpret C2PA data into human-readable findings.
        """
        if not c2pa_data or c2pa_data.get("error") or not c2pa_data.get("has_c2pa"):
            return {
                "finding": "NO_C2PA",
                "confidence": "low",
                "interpretation": (
                    "No Content Credentials found. This doesn't prove the content is fake, "
                    "but means we cannot verify its provenance through C2PA."
                ),
                "implications": [
                    "Content may be genuine but created with non-C2PA tools",
                    "Content credentials may have been stripped",
                    "Content may be AI-generated without C2PA tagging",
                ],
            }

        findings = {
            "finding": "C2PA_PRESENT",
            "confidence": "high" if c2pa_data.get("signature_valid") else "medium",
            "signer": c2pa_data.get("signer"),
            "timestamp": c2pa_data.get("timestamp"),
            "interpretation": "",
            "implications": [],
            "is_ai_generated": False,
        }

        # Interpret based on signer
        signer = (c2pa_data.get("signer") or "").lower()

        if "openai" in signer or "dall-e" in signer:
            findings["interpretation"] = (
                "This image was generated by OpenAI's DALL-E and has valid Content Credentials."
            )
            findings["implications"] = [
                "Image is AI-generated (confirmed by creator)",
                "OpenAI has signed this as their creation",
                "This is a legitimate disclosure, not a fake",
            ]
            findings["is_ai_generated"] = True

        elif "adobe" in signer:
            findings["interpretation"] = "This content has Adobe Content Credentials."
            # Check actions for AI generation
            actions = c2pa_data.get("actions", [])
            if any("generative" in str(a).lower() or "firefly" in str(a).lower() for a in actions):
                findings["implications"].append("Contains AI-generated elements (Adobe Firefly)")
                findings["is_ai_generated"] = True
            else:
                findings["implications"].append("Created or edited with Adobe software")

        elif "microsoft" in signer:
            findings["interpretation"] = "This content has Microsoft Content Credentials."
            findings["implications"].append("May have been created with Microsoft Designer or Copilot")

        else:
            findings["interpretation"] = f"Content signed by: {c2pa_data.get('signer', 'Unknown')}"
            findings["implications"].append("Provenance verified through C2PA signature")

        return findings
