"""
Scheduler Service - Cron-like scheduled task execution.

Provides scheduling capabilities for recurring tasks,
one-time jobs, and interval-based execution.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union
import uuid

logger = logging.getLogger(__name__)

# Try to import APScheduler for advanced scheduling
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed - using basic scheduler")


# ============================================
# Exceptions
# ============================================

class SchedulerError(Exception):
    """Base exception for scheduler errors."""
    pass


class JobNotFoundError(SchedulerError):
    """Scheduled job not found."""
    pass


class JobExecutionError(SchedulerError):
    """Error during job execution."""
    pass


class InvalidScheduleError(SchedulerError):
    """Invalid schedule configuration."""
    pass


# ============================================
# Enums and Types
# ============================================

class JobStatus(str, Enum):
    """Status of a scheduled job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class TriggerType(str, Enum):
    """Types of job triggers."""
    CRON = "cron"
    INTERVAL = "interval"
    DATE = "date"


@dataclass
class JobResult:
    """Result of a job execution."""
    job_id: str
    started_at: datetime
    finished_at: datetime
    status: JobStatus
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0


@dataclass
class ScheduledJob:
    """A scheduled job definition."""
    id: str
    name: str
    func_name: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================
# Basic Scheduler (No APScheduler)
# ============================================

class BasicScheduler:
    """
    Simple asyncio-based scheduler for basic use cases.

    Used when APScheduler is not available.
    """

    def __init__(self):
        self._jobs: Dict[str, Dict] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self):
        """Start the scheduler."""
        self._running = True
        logger.info("Basic scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("Basic scheduler stopped")

    def add_job(
        self,
        func: Callable,
        trigger: str,
        **kwargs,
    ) -> str:
        """Add a job to the scheduler."""
        job_id = str(uuid.uuid4())[:8]

        job_data = {
            "id": job_id,
            "func": func,
            "trigger": trigger,
            "kwargs": kwargs,
            "next_run": None,
        }

        if trigger == "interval":
            seconds = kwargs.get("seconds", 60)
            job_data["interval"] = seconds
            job_data["next_run"] = datetime.utcnow() + timedelta(seconds=seconds)

            # Create task
            task = asyncio.create_task(self._run_interval_job(job_id, func, seconds))
            self._tasks[job_id] = task

        elif trigger == "date":
            run_date = kwargs.get("run_date")
            if run_date:
                job_data["next_run"] = run_date
                delay = (run_date - datetime.utcnow()).total_seconds()
                if delay > 0:
                    task = asyncio.create_task(self._run_date_job(job_id, func, delay))
                    self._tasks[job_id] = task

        self._jobs[job_id] = job_data
        return job_id

    async def _run_interval_job(
        self,
        job_id: str,
        func: Callable,
        interval: float,
    ):
        """Run an interval-based job."""
        while self._running:
            await asyncio.sleep(interval)
            if not self._running:
                break
            try:
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    func()
                if job_id in self._jobs:
                    self._jobs[job_id]["next_run"] = datetime.utcnow() + timedelta(seconds=interval)
            except Exception as e:
                logger.error(f"Job {job_id} failed: {e}")

    async def _run_date_job(
        self,
        job_id: str,
        func: Callable,
        delay: float,
    ):
        """Run a date-triggered job."""
        await asyncio.sleep(delay)
        if not self._running:
            return
        try:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
        finally:
            if job_id in self._jobs:
                del self._jobs[job_id]
            if job_id in self._tasks:
                del self._tasks[job_id]

    def remove_job(self, job_id: str) -> bool:
        """Remove a job."""
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            del self._tasks[job_id]
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def get_jobs(self) -> List[Dict]:
        """Get all jobs."""
        return list(self._jobs.values())

    def pause_job(self, job_id: str):
        """Pause a job."""
        if job_id in self._tasks:
            self._tasks[job_id].cancel()

    def resume_job(self, job_id: str):
        """Resume a paused job."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            if job["trigger"] == "interval":
                task = asyncio.create_task(
                    self._run_interval_job(job_id, job["func"], job["interval"])
                )
                self._tasks[job_id] = task


# ============================================
# Scheduler Service
# ============================================

class SchedulerService:
    """
    Service for scheduling and executing periodic tasks.

    Provides:
    - Cron-style scheduling
    - Interval-based scheduling
    - One-time scheduled execution
    - Job management (pause, resume, cancel)
    - Execution history
    """

    def __init__(
        self,
        event_bus=None,
        max_history: int = 1000,
    ):
        """
        Initialize the scheduler service.

        Args:
            event_bus: Optional event bus for job events
            max_history: Maximum job results to keep in history
        """
        self._event_bus = event_bus
        self._max_history = max_history

        # Job registry
        self._jobs: Dict[str, ScheduledJob] = {}
        self._job_funcs: Dict[str, Callable] = {}
        self._history: List[JobResult] = []

        # Initialize scheduler
        if APSCHEDULER_AVAILABLE:
            self._scheduler = AsyncIOScheduler()
            logger.info("Using APScheduler")
        else:
            self._scheduler = BasicScheduler()
            logger.info("Using basic scheduler")

        self._started = False

    async def start(self) -> None:
        """Start the scheduler."""
        if self._started:
            return

        if APSCHEDULER_AVAILABLE:
            self._scheduler.start()
        else:
            await self._scheduler.start()

        self._started = True
        logger.info("SchedulerService started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._started:
            return

        if APSCHEDULER_AVAILABLE:
            self._scheduler.shutdown(wait=True)
        else:
            await self._scheduler.stop()

        self._started = False
        logger.info("SchedulerService stopped")

    def register_job(
        self,
        name: str,
        func: Callable[..., Coroutine],
    ) -> None:
        """
        Register a job function that can be scheduled.

        Args:
            name: Unique name for the job function
            func: Async function to execute
        """
        self._job_funcs[name] = func
        logger.debug(f"Registered job function: {name}")

    def schedule_cron(
        self,
        name: str,
        func_name: str,
        cron_expression: Optional[str] = None,
        year: Optional[str] = None,
        month: Optional[str] = None,
        day: Optional[str] = None,
        week: Optional[str] = None,
        day_of_week: Optional[str] = None,
        hour: Optional[str] = None,
        minute: Optional[str] = None,
        second: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledJob:
        """
        Schedule a job with cron-style timing.

        Args:
            name: Job name
            func_name: Registered function name
            cron_expression: Cron expression (alternative to individual fields)
            year: Year pattern
            month: Month pattern (1-12)
            day: Day of month pattern (1-31)
            week: Week of year pattern (1-53)
            day_of_week: Day of week pattern (0-6 or mon-sun)
            hour: Hour pattern (0-23)
            minute: Minute pattern (0-59)
            second: Second pattern (0-59)
            metadata: Additional job metadata

        Returns:
            ScheduledJob object
        """
        if func_name not in self._job_funcs:
            raise InvalidScheduleError(f"Function not registered: {func_name}")

        job_id = f"job-{len(self._jobs) + 1:04d}"

        trigger_config = {}
        if cron_expression:
            # Parse cron expression (basic support)
            parts = cron_expression.split()
            if len(parts) >= 5:
                trigger_config = {
                    "minute": parts[0],
                    "hour": parts[1],
                    "day": parts[2],
                    "month": parts[3],
                    "day_of_week": parts[4],
                }
        else:
            if year: trigger_config["year"] = year
            if month: trigger_config["month"] = month
            if day: trigger_config["day"] = day
            if week: trigger_config["week"] = week
            if day_of_week: trigger_config["day_of_week"] = day_of_week
            if hour: trigger_config["hour"] = hour
            if minute: trigger_config["minute"] = minute
            if second: trigger_config["second"] = second

        job = ScheduledJob(
            id=job_id,
            name=name,
            func_name=func_name,
            trigger_type=TriggerType.CRON,
            trigger_config=trigger_config,
            metadata=metadata or {},
        )

        # Add to scheduler
        func = self._job_funcs[func_name]
        wrapped_func = self._wrap_job(job_id, func)

        if APSCHEDULER_AVAILABLE:
            trigger = CronTrigger(**trigger_config)
            self._scheduler.add_job(
                wrapped_func,
                trigger,
                id=job_id,
                name=name,
            )
        else:
            # Basic scheduler doesn't support cron, use interval as fallback
            logger.warning("Cron triggers require APScheduler, using hourly interval instead")
            self._scheduler.add_job(func, "interval", seconds=3600)

        self._jobs[job_id] = job
        logger.info(f"Scheduled cron job: {name} ({job_id})")

        return job

    def schedule_interval(
        self,
        name: str,
        func_name: str,
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledJob:
        """
        Schedule a job to run at regular intervals.

        Args:
            name: Job name
            func_name: Registered function name
            weeks: Weeks between executions
            days: Days between executions
            hours: Hours between executions
            minutes: Minutes between executions
            seconds: Seconds between executions
            start_date: First execution time
            end_date: Last execution time
            metadata: Additional job metadata

        Returns:
            ScheduledJob object
        """
        if func_name not in self._job_funcs:
            raise InvalidScheduleError(f"Function not registered: {func_name}")

        # Calculate total seconds
        total_seconds = (
            weeks * 7 * 24 * 3600 +
            days * 24 * 3600 +
            hours * 3600 +
            minutes * 60 +
            seconds
        )

        if total_seconds <= 0:
            raise InvalidScheduleError("Interval must be positive")

        job_id = f"job-{len(self._jobs) + 1:04d}"

        trigger_config = {
            "weeks": weeks,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
        }
        if start_date:
            trigger_config["start_date"] = start_date.isoformat()
        if end_date:
            trigger_config["end_date"] = end_date.isoformat()

        job = ScheduledJob(
            id=job_id,
            name=name,
            func_name=func_name,
            trigger_type=TriggerType.INTERVAL,
            trigger_config=trigger_config,
            next_run=start_date or datetime.utcnow() + timedelta(seconds=total_seconds),
            metadata=metadata or {},
        )

        # Add to scheduler
        func = self._job_funcs[func_name]
        wrapped_func = self._wrap_job(job_id, func)

        if APSCHEDULER_AVAILABLE:
            trigger = IntervalTrigger(
                weeks=weeks,
                days=days,
                hours=hours,
                minutes=minutes,
                seconds=seconds,
                start_date=start_date,
                end_date=end_date,
            )
            self._scheduler.add_job(
                wrapped_func,
                trigger,
                id=job_id,
                name=name,
            )
        else:
            self._scheduler.add_job(func, "interval", seconds=total_seconds)

        self._jobs[job_id] = job
        logger.info(f"Scheduled interval job: {name} ({job_id}) every {total_seconds}s")

        return job

    def schedule_once(
        self,
        name: str,
        func_name: str,
        run_date: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledJob:
        """
        Schedule a one-time job execution.

        Args:
            name: Job name
            func_name: Registered function name
            run_date: When to execute the job
            metadata: Additional job metadata

        Returns:
            ScheduledJob object
        """
        if func_name not in self._job_funcs:
            raise InvalidScheduleError(f"Function not registered: {func_name}")

        if run_date <= datetime.utcnow():
            raise InvalidScheduleError("Run date must be in the future")

        job_id = f"job-{len(self._jobs) + 1:04d}"

        trigger_config = {
            "run_date": run_date.isoformat(),
        }

        job = ScheduledJob(
            id=job_id,
            name=name,
            func_name=func_name,
            trigger_type=TriggerType.DATE,
            trigger_config=trigger_config,
            next_run=run_date,
            metadata=metadata or {},
        )

        # Add to scheduler
        func = self._job_funcs[func_name]
        wrapped_func = self._wrap_job(job_id, func)

        if APSCHEDULER_AVAILABLE:
            trigger = DateTrigger(run_date=run_date)
            self._scheduler.add_job(
                wrapped_func,
                trigger,
                id=job_id,
                name=name,
            )
        else:
            self._scheduler.add_job(func, "date", run_date=run_date)

        self._jobs[job_id] = job
        logger.info(f"Scheduled one-time job: {name} ({job_id}) at {run_date}")

        return job

    def _wrap_job(
        self,
        job_id: str,
        func: Callable,
    ) -> Callable:
        """Wrap a job function with tracking and error handling."""
        async def wrapped():
            job = self._jobs.get(job_id)
            if not job:
                return

            started = datetime.utcnow()
            job.status = JobStatus.RUNNING
            job.last_run = started

            result = JobResult(
                job_id=job_id,
                started_at=started,
                finished_at=started,
                status=JobStatus.RUNNING,
            )

            try:
                if asyncio.iscoroutinefunction(func):
                    result.result = await func()
                else:
                    result.result = func()

                result.status = JobStatus.COMPLETED
                job.status = JobStatus.PENDING
                job.run_count += 1

            except Exception as e:
                result.status = JobStatus.FAILED
                result.error = str(e)
                job.status = JobStatus.FAILED
                job.error_count += 1
                logger.error(f"Job {job_id} failed: {e}")

            finally:
                result.finished_at = datetime.utcnow()
                result.execution_time_ms = (
                    result.finished_at - result.started_at
                ).total_seconds() * 1000

                # Add to history
                self._history.append(result)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

                # Emit event
                if self._event_bus:
                    await self._event_bus.publish(
                        "scheduler.job.completed",
                        {
                            "job_id": job_id,
                            "status": result.status.value,
                            "execution_time_ms": result.execution_time_ms,
                        }
                    )

        return wrapped

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[ScheduledJob]:
        """
        List all scheduled jobs.

        Args:
            status: Optional status filter

        Returns:
            List of ScheduledJob objects
        """
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        return sorted(jobs, key=lambda j: j.created_at)

    def pause_job(self, job_id: str) -> bool:
        """
        Pause a scheduled job.

        Args:
            job_id: Job ID

        Returns:
            True if paused, False if not found
        """
        job = self._jobs.get(job_id)
        if not job:
            return False

        if APSCHEDULER_AVAILABLE:
            self._scheduler.pause_job(job_id)
        else:
            self._scheduler.pause_job(job_id)

        job.status = JobStatus.PAUSED
        logger.info(f"Paused job: {job_id}")
        return True

    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.

        Args:
            job_id: Job ID

        Returns:
            True if resumed, False if not found
        """
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.PAUSED:
            return False

        if APSCHEDULER_AVAILABLE:
            self._scheduler.resume_job(job_id)
        else:
            self._scheduler.resume_job(job_id)

        job.status = JobStatus.PENDING
        logger.info(f"Resumed job: {job_id}")
        return True

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: Job ID

        Returns:
            True if removed, False if not found
        """
        if job_id not in self._jobs:
            return False

        if APSCHEDULER_AVAILABLE:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        else:
            self._scheduler.remove_job(job_id)

        job = self._jobs.pop(job_id)
        job.status = JobStatus.CANCELLED
        logger.info(f"Removed job: {job_id}")
        return True

    def get_history(
        self,
        job_id: Optional[str] = None,
        limit: int = 100,
        status: Optional[JobStatus] = None,
    ) -> List[JobResult]:
        """
        Get job execution history.

        Args:
            job_id: Filter by job ID
            limit: Maximum entries to return
            status: Filter by status

        Returns:
            List of JobResult objects
        """
        result = self._history

        if job_id:
            result = [r for r in result if r.job_id == job_id]

        if status:
            result = [r for r in result if r.status == status]

        return result[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        by_status = {}
        by_trigger = {}

        for job in self._jobs.values():
            by_status[job.status.value] = by_status.get(job.status.value, 0) + 1
            by_trigger[job.trigger_type.value] = by_trigger.get(job.trigger_type.value, 0) + 1

        total_runs = sum(j.run_count for j in self._jobs.values())
        total_errors = sum(j.error_count for j in self._jobs.values())

        return {
            "total_jobs": len(self._jobs),
            "by_status": by_status,
            "by_trigger": by_trigger,
            "total_runs": total_runs,
            "total_errors": total_errors,
            "history_size": len(self._history),
            "running": self._started,
        }
