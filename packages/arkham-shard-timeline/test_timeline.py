"""Quick verification test for Timeline Shard functionality."""

import sys
from datetime import datetime

from arkham_shard_timeline.extraction import DateExtractor
from arkham_shard_timeline.merging import TimelineMerger
from arkham_shard_timeline.conflicts import ConflictDetector
from arkham_shard_timeline.models import (
    ExtractionContext,
    MergeStrategy,
    ConflictType,
)


def test_date_extraction():
    """Test date extraction with various formats."""
    print("\n=== Date Extraction Test ===")

    extractor = DateExtractor()

    test_texts = [
        "The meeting occurred on January 15, 2024.",
        "The contract was signed 3 days ago.",
        "The project started in Q3 2023.",
        "Around 2020, the company was founded.",
        "Last Tuesday we had a discussion.",
        "The deadline is 2024-12-31.",
        "In mid-2024, we will launch.",
        "The 1990s were significant.",
    ]

    context = ExtractionContext(reference_date=datetime(2024, 12, 15))

    for text in test_texts:
        events = extractor.extract_events(text, "test-doc", context)
        print(f"\nText: {text}")
        for event in events:
            print(f"  -> {event.date_start.date()} ({event.precision.value}, confidence: {event.confidence:.2f})")

    return True


def test_date_normalization():
    """Test date normalization."""
    print("\n=== Date Normalization Test ===")

    extractor = DateExtractor()

    dates_to_normalize = [
        "January 15, 2024",
        "15/01/2024",
        "2024-01-15",
        "mid-2024",
        "Q3 2024",
        "yesterday",
        "around 2020",
    ]

    context = ExtractionContext(reference_date=datetime(2024, 12, 15))

    for date_str in dates_to_normalize:
        normalized = extractor.normalize_date(date_str, context)
        if normalized:
            print(f"{date_str:20s} -> {normalized.normalized.date()} ({normalized.precision.value})")
        else:
            print(f"{date_str:20s} -> FAILED TO PARSE")

    return True


def test_timeline_merging():
    """Test timeline merging."""
    print("\n=== Timeline Merging Test ===")

    from arkham_shard_timeline.models import TimelineEvent, EventType, DatePrecision
    import uuid

    # Create some test events
    events = [
        TimelineEvent(
            id=str(uuid.uuid4()),
            document_id="doc1",
            text="Meeting on Jan 15",
            date_start=datetime(2024, 1, 15),
            precision=DatePrecision.DAY,
            confidence=0.95,
            event_type=EventType.OCCURRENCE,
        ),
        TimelineEvent(
            id=str(uuid.uuid4()),
            document_id="doc2",
            text="Meeting on January 15",
            date_start=datetime(2024, 1, 15),
            precision=DatePrecision.DAY,
            confidence=0.90,
            event_type=EventType.OCCURRENCE,
        ),
        TimelineEvent(
            id=str(uuid.uuid4()),
            document_id="doc1",
            text="Follow-up on Jan 20",
            date_start=datetime(2024, 1, 20),
            precision=DatePrecision.DAY,
            confidence=0.85,
            event_type=EventType.OCCURRENCE,
        ),
    ]

    merger = TimelineMerger()

    # Test chronological merge
    result = merger.merge(events, strategy=MergeStrategy.CHRONOLOGICAL)
    print(f"\nChronological merge: {result.count} events")

    # Test deduplicated merge
    result = merger.merge(events, strategy=MergeStrategy.DEDUPLICATED)
    print(f"Deduplicated merge: {result.count} events (removed {result.duplicates_removed} duplicates)")

    return True


def test_conflict_detection():
    """Test conflict detection."""
    print("\n=== Conflict Detection Test ===")

    from arkham_shard_timeline.models import TimelineEvent, EventType, DatePrecision
    import uuid

    # Create events with conflicts
    events = [
        TimelineEvent(
            id=str(uuid.uuid4()),
            document_id="doc1",
            text="Meeting on Jan 15",
            date_start=datetime(2024, 1, 15),
            precision=DatePrecision.DAY,
            confidence=0.95,
            event_type=EventType.OCCURRENCE,
            entities=["person1"],
        ),
        TimelineEvent(
            id=str(uuid.uuid4()),
            document_id="doc2",
            text="Meeting on Jan 17",
            date_start=datetime(2024, 1, 17),
            precision=DatePrecision.DAY,
            confidence=0.90,
            event_type=EventType.OCCURRENCE,
            entities=["person1"],
        ),
    ]

    detector = ConflictDetector(tolerance_days=0)

    conflicts = detector.detect_conflicts(events, conflict_types=[ConflictType.CONTRADICTION])

    print(f"\nDetected {len(conflicts)} conflicts")
    for conflict in conflicts:
        print(f"  - {conflict.type.value} ({conflict.severity.value}): {conflict.description}")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Timeline Shard Verification Tests")
    print("=" * 60)

    tests = [
        ("Date Extraction", test_date_extraction),
        ("Date Normalization", test_date_normalization),
        ("Timeline Merging", test_timeline_merging),
        ("Conflict Detection", test_conflict_detection),
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
            print(f"\n[OK] {name}")
        except Exception as e:
            results.append((name, False))
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
