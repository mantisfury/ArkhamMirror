import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL
from app.arkham.services.db.models import Document, TimelineEvent

# Database setup from central config
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_day_of_week_hour_heatmap(project_id: int = None) -> Dict[str, Any]:
    """
    Generate heatmap data showing activity by day of week and hour of day.

    Args:
        project_id: Optional project ID to filter by (0 or None means all projects)

    Returns structure for Plotly heatmap:
    {
        "x": [0, 1, 2, ... 23],  # Hours
        "y": ["Monday", "Tuesday", ...],  # Days of week
        "z": [[count, count, ...], ...],  # Activity counts
        "total_events": int
    }
    """
    with SessionLocal() as session:
        # Get all events with valid dates
        query = session.query(TimelineEvent).filter(
            TimelineEvent.event_date.isnot(None)
        )

        # Filter by project if specified (0 means "All Projects")
        # Also include unassigned documents (project_id=None) to show legacy data
        if project_id and project_id > 0:
            from sqlalchemy import or_

            query = query.join(Document, TimelineEvent.doc_id == Document.id).filter(
                or_(Document.project_id == project_id, Document.project_id.is_(None))
            )

        events = query.all()

        if not events:
            return {
                "x": list(range(24)),
                "y": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
                "z": [[0] * 24 for _ in range(7)],
                "total_events": 0,
            }

        # Initialize 7x24 grid (7 days, 24 hours)
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        activity_grid = [[0 for _ in range(24)] for _ in range(7)]

        # Aggregate events
        for event in events:
            if event.event_date:
                # Get day of week (0=Monday, 6=Sunday) and hour
                day_of_week = event.event_date.weekday()
                hour = event.event_date.hour

                activity_grid[day_of_week][hour] += 1

        return {
            "x": list(range(24)),  # Hours 0-23
            "y": day_names,
            "z": activity_grid,
            "total_events": len(events),
        }


def get_weekly_activity_heatmap(
    project_id: int = None, weeks: int = 52
) -> Dict[str, Any]:
    """
    Generate heatmap showing activity over weeks.

    Args:
        project_id: Optional project ID to filter by (0 or None means all projects)
        weeks: Number of weeks to display

    Returns structure for Plotly heatmap:
    {
        "x": ["Week 1", "Week 2", ...],  # Week labels
        "y": ["Monday", "Tuesday", ...],  # Days of week
        "z": [[count, count, ...], ...],  # Activity counts per day/week
        "date_range": {"start": "2023-01-01", "end": "2023-12-31"}
    }
    """
    with SessionLocal() as session:
        # Get all events with valid dates
        query = session.query(TimelineEvent).filter(
            TimelineEvent.event_date.isnot(None)
        )

        # Filter by project if specified (0 means "All Projects")
        # Also include unassigned documents (project_id=None) to show legacy data
        if project_id and project_id > 0:
            from sqlalchemy import or_

            query = query.join(Document, TimelineEvent.doc_id == Document.id).filter(
                or_(Document.project_id == project_id, Document.project_id.is_(None))
            )

        events = query.all()

        if not events:
            return {
                "x": [f"W{i + 1}" for i in range(weeks)],
                "y": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "z": [[0] * weeks for _ in range(7)],
                "date_range": {"start": None, "end": None},
            }

        # Find date range
        dates = [e.event_date for e in events if e.event_date]
        if not dates:
            return {
                "x": [],
                "y": [],
                "z": [],
                "date_range": {"start": None, "end": None},
            }

        min_date = min(dates)
        max_date = max(dates)

        # Initialize grid: 7 days x number of weeks
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        week_activity = defaultdict(lambda: [0] * 7)

        # Aggregate by week and day
        for event in events:
            if event.event_date:
                year, week, day_of_week = event.event_date.isocalendar()
                week_key = f"{year}-W{week:02d}"
                week_activity[week_key][day_of_week - 1] += 1  # ISO weekday is 1-7

        # Sort weeks chronologically
        sorted_weeks = sorted(week_activity.keys())

        # Limit to requested number of weeks
        sorted_weeks = (
            sorted_weeks[-weeks:] if len(sorted_weeks) > weeks else sorted_weeks
        )

        # Build z matrix (transpose for proper display)
        z_matrix = []
        for day_idx in range(7):
            row = [week_activity[week][day_idx] for week in sorted_weeks]
            z_matrix.append(row)

        # Create readable week labels
        week_labels = [f"W{w.split('-W')[1]}" for w in sorted_weeks]

        return {
            "x": week_labels,
            "y": day_names,
            "z": z_matrix,
            "date_range": {
                "start": min_date.strftime("%Y-%m-%d"),
                "end": max_date.strftime("%Y-%m-%d"),
            },
        }


def get_monthly_activity_heatmap(project_id: int = None) -> Dict[str, Any]:
    """
    Generate heatmap showing activity by day of month across months.

    Args:
        project_id: Optional project ID to filter by (0 or None means all projects)

    Returns structure for Plotly heatmap:
    {
        "x": [1, 2, 3, ... 31],  # Days of month
        "y": ["2023-01", "2023-02", ...],  # Months
        "z": [[count, count, ...], ...],  # Activity counts
        "date_range": {"start": "2023-01-01", "end": "2023-12-31"}
    }
    """
    with SessionLocal() as session:
        # Get all events with valid dates
        query = session.query(TimelineEvent).filter(
            TimelineEvent.event_date.isnot(None)
        )

        # Filter by project if specified (0 means "All Projects")
        # Also include unassigned documents (project_id=None) to show legacy data
        if project_id and project_id > 0:
            from sqlalchemy import or_

            query = query.join(Document, TimelineEvent.doc_id == Document.id).filter(
                or_(Document.project_id == project_id, Document.project_id.is_(None))
            )

        events = query.all()

        if not events:
            return {
                "x": list(range(1, 32)),
                "y": [],
                "z": [],
                "date_range": {"start": None, "end": None},
            }

        # Find date range
        dates = [e.event_date for e in events if e.event_date]
        if not dates:
            return {
                "x": list(range(1, 32)),
                "y": [],
                "z": [],
                "date_range": {"start": None, "end": None},
            }

        min_date = min(dates)
        max_date = max(dates)

        # Generate list of months between min and max
        month_activity = defaultdict(lambda: [0] * 31)

        for event in events:
            if event.event_date:
                month_key = event.event_date.strftime("%Y-%m")
                day_of_month = event.event_date.day
                month_activity[month_key][day_of_month - 1] += 1  # 0-indexed

        # Sort months chronologically
        sorted_months = sorted(month_activity.keys())

        # Build z matrix
        z_matrix = [month_activity[month] for month in sorted_months]

        return {
            "x": list(range(1, 32)),  # Days 1-31
            "y": sorted_months,
            "z": z_matrix,
            "date_range": {
                "start": min_date.strftime("%Y-%m-%d"),
                "end": max_date.strftime("%Y-%m-%d"),
            },
        }


def get_heatmap_summary_stats(project_id: int = None) -> Dict[str, Any]:
    """
    Get summary statistics for heatmap visualization.

    Args:
        project_id: Optional project ID to filter by (0 or None means all projects)

    Returns:
    {
        "total_events": int,
        "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
        "busiest_day_of_week": str,
        "busiest_hour": int,
        "average_events_per_day": float
    }
    """
    with SessionLocal() as session:
        query = session.query(TimelineEvent).filter(
            TimelineEvent.event_date.isnot(None)
        )

        # Filter by project if specified (0 means "All Projects")
        # Also include unassigned documents (project_id=None) to show legacy data
        if project_id and project_id > 0:
            from sqlalchemy import or_

            query = query.join(Document, TimelineEvent.doc_id == Document.id).filter(
                or_(Document.project_id == project_id, Document.project_id.is_(None))
            )

        events = query.all()

        if not events:
            return {
                "total_events": 0,
                "date_range": {"start": None, "end": None},
                "busiest_day_of_week": None,
                "busiest_hour": None,
                "average_events_per_day": 0.0,
            }

        dates = [e.event_date for e in events if e.event_date]
        min_date = min(dates)
        max_date = max(dates)
        total_days = (max_date - min_date).days + 1

        # Count by day of week
        day_counts = defaultdict(int)
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        # Count by hour
        hour_counts = defaultdict(int)

        for event in events:
            if event.event_date:
                day_of_week = event.event_date.weekday()
                day_counts[day_of_week] += 1
                hour_counts[event.event_date.hour] += 1

        busiest_day = (
            max(day_counts.items(), key=lambda x: x[1])[0] if day_counts else 0
        )
        busiest_hour = (
            max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        )

        return {
            "total_events": len(events),
            "date_range": {
                "start": min_date.strftime("%Y-%m-%d"),
                "end": max_date.strftime("%Y-%m-%d"),
            },
            "busiest_day_of_week": day_names[busiest_day],
            "busiest_hour": busiest_hour,
            "average_events_per_day": round(len(events) / total_days, 2)
            if total_days > 0
            else 0.0,
        }
