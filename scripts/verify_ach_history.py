import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Setup path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.arkham.services.ach_service import get_ach_service
# from app.arkham.models.ach_models import ACHRatingEnum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_history():
    logger.info("Starting ACH History Verification...")

    service = get_ach_service()

    # 1. Create Analysis
    logger.info("Creating Test Analysis...")
    analysis = service.create_analysis(
        title="History Test Analysis",
        focus_question="Does the version history feature work?",
        description="Automated verification.",
    )
    a_id = analysis["id"]
    logger.info(f"Analysis created: ID {a_id}")

    # 2. Add Hypotheses
    logger.info("Adding Hypotheses...")
    h1 = service.add_hypothesis(a_id, "H1: It works perfectly")
    h2 = service.add_hypothesis(a_id, "H2: It has bugs")

    # 3. Add Evidence
    logger.info("Adding Evidence...")
    e1 = service.add_evidence(a_id, "E1: Unit test passed")
    e2 = service.add_evidence(a_id, "E2: Logs look clean")

    # 4. Rate (Calculations should happen)
    logger.info("Adding Ratings...")
    service.set_rating(a_id, e1["id"], h1["id"], "CC")  # Consistent
    service.set_rating(a_id, e1["id"], h2["id"], "II")  # Inconsistent
    # Recalculate scores
    service.calculate_scores(a_id)

    # 5. Create Snapshot 1
    logger.info("Creating Snapshot 1...")
    service.create_snapshot(a_id, "Snapshot 1", "Initial state")

    # Verify snapshot count
    snapshots = service.get_snapshots(a_id)
    logger.info(f"Snapshots found: {len(snapshots)}")
    assert len(snapshots) == 1

    # 6. Modify State
    logger.info("Modifying State...")
    # Add new hypothesis
    h3 = service.add_hypothesis(a_id, "H3: It works mysteriously")
    # Remove H2
    service.delete_hypothesis(h2["id"])
    # Add new evidence
    e3 = service.add_evidence(a_id, "E3: User is happy")
    # Change rating for H1 (make it worse)
    service.set_rating(a_id, e1["id"], h1["id"], "II")  # Now inconsistent
    service.calculate_scores(a_id)

    # 7. Create Snapshot 2
    logger.info("Creating Snapshot 2...")
    service.create_snapshot(a_id, "Snapshot 2", "Modified state")

    snapshots = service.get_snapshots(a_id)
    assert len(snapshots) == 2
    s1_id = snapshots[0][
        "id"
    ]  # Oldest first? or newest? get_snapshots sorts by created_at desc generally?
    # db/migrate_ach_history just has created_at default.
    # service.get_snapshots logic:
    # return [s.to_dict() for s in self.db.query(ACHAnalysisSnapshot)...order_by(desc(ACHAnalysisSnapshot.created_at)).all()]
    # So index 0 is NEWEST (Snapshot 2), index 1 is OLDEST (Snapshot 1).

    s_new_id = snapshots[0]["id"]
    s_old_id = snapshots[1]["id"]
    logger.info(f"Comparing New ({s_new_id}) vs Old ({s_old_id})")

    # 8. Compare
    diff = service.get_snapshot_diff(s_old_id, s_new_id)

    # 9. Validate Diff
    logger.info("Diff Results:")
    logger.info(str(diff))

    # H3 should be added
    assert "H3" in diff["hypotheses"]["added"]
    # H2 should be removed
    assert "H2" in diff["hypotheses"]["removed"]
    # E3 should be added
    assert "E3" in diff["evidence"]["added"]

    logger.info("✓ Verification Successful!")


if __name__ == "__main__":
    try:
        verify_history()
    except Exception as e:
        logger.error(f"Verification Failed: {e}")
        sys.exit(1)
