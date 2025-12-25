"""
Integration tests for Output Services (Phase 4).

Tests for:
- ExportService: Multi-format export (JSON, CSV, Markdown, HTML, Text)
- TemplateService: Jinja2 template management and rendering
- NotificationService: Multi-channel notifications (log, email, webhook)
- SchedulerService: Job scheduling (cron, interval, date)

Run with:
    cd packages/arkham-frame
    pytest tests/test_output_services.py -v -s
"""

import asyncio
import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile


# =============================================================================
# Test 1: ExportService
# =============================================================================

class TestExportService:
    """Test ExportService multi-format export capabilities."""

    @pytest.fixture
    def export_service(self):
        """Create ExportService instance for testing."""
        from arkham_frame.services.export import ExportService
        return ExportService()

    @pytest.fixture
    def sample_data(self):
        """Sample data for export tests."""
        return {
            "id": "doc-001",
            "title": "Test Document",
            "content": "This is test content",
            "created_at": "2025-01-15",
            "tags": ["test", "sample"]
        }

    @pytest.fixture
    def sample_tabular_data(self):
        """Sample tabular data for CSV export tests."""
        return [
            {"name": "Alice", "age": 30, "city": "NYC"},
            {"name": "Bob", "age": 25, "city": "SF"},
            {"name": "Charlie", "age": 35, "city": "LA"}
        ]

    def test_json_export_with_metadata(self, export_service, sample_data):
        """Test JSON export with metadata included."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(
            format=ExportFormat.JSON,
            include_metadata=True,
            title="Test Export",
            author="Test User"
        )

        result = export_service.export(sample_data, ExportFormat.JSON, options)

        assert result.format == ExportFormat.JSON
        assert result.content_type == "application/json"
        assert ".json" in result.filename
        assert result.size_bytes > 0

        # Parse and verify content
        content = json.loads(result.content)
        assert "data" in content
        assert "metadata" in content
        assert content["data"] == sample_data
        assert content["metadata"]["title"] == "Test Export"
        assert content["metadata"]["author"] == "Test User"

    def test_json_export_without_metadata(self, export_service, sample_data):
        """Test JSON export without metadata."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(
            format=ExportFormat.JSON,
            include_metadata=False
        )

        result = export_service.export(sample_data, ExportFormat.JSON, options)
        content = json.loads(result.content)

        # Should be plain data without metadata wrapper
        assert "metadata" not in content
        assert content == sample_data

    def test_json_export_pretty_print(self, export_service, sample_data):
        """Test JSON export with pretty printing."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        # With pretty print
        options_pretty = ExportOptions(format=ExportFormat.JSON, pretty_print=True, include_metadata=False)
        result_pretty = export_service.export(sample_data, ExportFormat.JSON, options_pretty)

        # Without pretty print
        options_compact = ExportOptions(format=ExportFormat.JSON, pretty_print=False, include_metadata=False)
        result_compact = export_service.export(sample_data, ExportFormat.JSON, options_compact)

        # Pretty print should be larger (has whitespace)
        assert result_pretty.size_bytes > result_compact.size_bytes
        assert "\n" in result_pretty.content
        assert "\n" not in result_compact.content

    def test_csv_export_list_of_dicts(self, export_service, sample_tabular_data):
        """Test CSV export with list of dictionaries."""
        from arkham_frame.services.export import ExportFormat

        result = export_service.export(sample_tabular_data, ExportFormat.CSV)

        assert result.format == ExportFormat.CSV
        assert result.content_type == "text/csv"
        assert ".csv" in result.filename

        # Verify CSV content
        lines = result.content.strip().split("\n")
        assert len(lines) == 4  # Header + 3 rows
        assert "name,age,city" in lines[0]
        assert "Alice" in result.content
        assert "Bob" in result.content
        assert "Charlie" in result.content

    def test_csv_export_single_dict(self, export_service, sample_data):
        """Test CSV export with single dictionary (key-value pairs)."""
        from arkham_frame.services.export import ExportFormat

        result = export_service.export(sample_data, ExportFormat.CSV)

        # Should export as key-value pairs
        assert "key,value" in result.content
        assert "id,doc-001" in result.content
        assert "title,Test Document" in result.content

    def test_markdown_export(self, export_service, sample_data):
        """Test Markdown export."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(
            format=ExportFormat.MARKDOWN,
            title="Test Report",
            author="Test User",
            include_metadata=True
        )

        result = export_service.export(sample_data, ExportFormat.MARKDOWN, options)

        assert result.format == ExportFormat.MARKDOWN
        assert result.content_type == "text/markdown"
        assert ".md" in result.filename

        # Verify markdown content
        assert "# Test Report" in result.content
        assert "**Author:** Test User" in result.content
        assert "**Date:**" in result.content
        assert "**id:** doc-001" in result.content

    def test_markdown_export_table(self, export_service, sample_tabular_data):
        """Test Markdown export with table data."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(format=ExportFormat.MARKDOWN, include_metadata=False)
        result = export_service.export(sample_tabular_data, ExportFormat.MARKDOWN, options)

        # Should create a markdown table
        assert "| name | age | city |" in result.content
        assert "| --- | --- | --- |" in result.content
        assert "| Alice | 30 | NYC |" in result.content

    def test_html_export(self, export_service, sample_data):
        """Test HTML export."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(
            format=ExportFormat.HTML,
            title="Test Report",
            author="Test User",
            include_metadata=True
        )

        result = export_service.export(sample_data, ExportFormat.HTML, options)

        assert result.format == ExportFormat.HTML
        assert result.content_type == "text/html"
        assert ".html" in result.filename

        # Verify HTML structure
        assert "<!DOCTYPE html>" in result.content
        assert "<html>" in result.content
        assert "<title>Test Report</title>" in result.content
        assert "<h1>Test Report</h1>" in result.content
        assert "Test User" in result.content

    def test_html_export_table(self, export_service, sample_tabular_data):
        """Test HTML export with table data."""
        from arkham_frame.services.export import ExportFormat

        result = export_service.export(sample_tabular_data, ExportFormat.HTML)

        # Should create HTML table
        assert "<table>" in result.content
        assert "<thead>" in result.content
        assert "<tbody>" in result.content
        assert "<th>name</th>" in result.content
        assert "<td>Alice</td>" in result.content

    def test_text_export(self, export_service, sample_data):
        """Test plain text export."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(
            format=ExportFormat.TEXT,
            title="Test Report",
            author="Test User",
            include_metadata=True
        )

        result = export_service.export(sample_data, ExportFormat.TEXT, options)

        assert result.format == ExportFormat.TEXT
        assert result.content_type == "text/plain"
        assert ".txt" in result.filename

        # Verify text content
        assert "Test Report" in result.content
        assert "=" in result.content  # Title underline
        assert "Author: Test User" in result.content
        assert "id: doc-001" in result.content

    def test_batch_export(self, export_service, sample_data):
        """Test batch export to multiple formats."""
        from arkham_frame.services.export import ExportFormat

        formats = [ExportFormat.JSON, ExportFormat.CSV, ExportFormat.MARKDOWN]
        results = export_service.batch_export(sample_data, formats)

        assert len(results) == 3
        assert ExportFormat.JSON in results
        assert ExportFormat.CSV in results
        assert ExportFormat.MARKDOWN in results

        # Each format should have valid result
        for format, result in results.items():
            assert result.format == format
            assert result.size_bytes > 0

    def test_export_history(self, export_service, sample_data):
        """Test export history tracking."""
        from arkham_frame.services.export import ExportFormat

        # Initial history should be empty
        export_service.clear_history()
        history = export_service.get_history()
        initial_count = len(history)

        # Perform exports
        export_service.export(sample_data, ExportFormat.JSON)
        export_service.export(sample_data, ExportFormat.CSV)

        # History should have 2 new entries
        history = export_service.get_history()
        assert len(history) == initial_count + 2

        # History entries should have correct format
        assert history[-2]["format"] == "json"
        assert history[-1]["format"] == "csv"
        assert "filename" in history[-1]
        assert "size_bytes" in history[-1]

    def test_invalid_format_handling(self, export_service, sample_data):
        """Test handling of invalid export format."""
        from arkham_frame.services.export import ExportFormatError

        with pytest.raises(ExportFormatError):
            export_service.export(sample_data, "invalid_format")

    def test_export_options_title_and_author(self, export_service, sample_data):
        """Test that title and author options are applied correctly."""
        from arkham_frame.services.export import ExportFormat, ExportOptions

        options = ExportOptions(
            format=ExportFormat.JSON,
            title="Custom Title",
            author="Custom Author",
            include_metadata=True
        )

        result = export_service.export(sample_data, ExportFormat.JSON, options)
        content = json.loads(result.content)

        assert content["metadata"]["title"] == "Custom Title"
        assert content["metadata"]["author"] == "Custom Author"
        assert "Custom Title" in result.filename


# =============================================================================
# Test 2: TemplateService
# =============================================================================

class TestTemplateService:
    """Test TemplateService template management and rendering."""

    @pytest.fixture
    def template_service(self):
        """Create TemplateService instance for testing."""
        from arkham_frame.services.templates import TemplateService
        return TemplateService()

    def test_register_template(self, template_service):
        """Test template registration."""
        template = template_service.register(
            name="test_template",
            content="Hello {{ name }}!",
            description="Test template",
            category="test"
        )

        assert template.name == "test_template"
        assert template.content == "Hello {{ name }}!"
        assert template.category == "test"

    def test_get_template(self, template_service):
        """Test retrieving a template."""
        template_service.register(
            name="test_get",
            content="Content here",
            category="test"
        )

        template = template_service.get("test_get")
        assert template is not None
        assert template.name == "test_get"

        # Non-existent template
        missing = template_service.get("nonexistent")
        assert missing is None

    def test_list_templates(self, template_service):
        """Test listing templates."""
        template_service.register("test1", "Content 1", category="cat1")
        template_service.register("test2", "Content 2", category="cat2")
        template_service.register("test3", "Content 3", category="cat1")

        # List all
        all_templates = template_service.list()
        test_templates = [t for t in all_templates if t.name.startswith("test")]
        assert len(test_templates) == 3

        # List by category
        cat1_templates = template_service.list(category="cat1")
        cat1_test = [t for t in cat1_templates if t.name.startswith("test")]
        assert len(cat1_test) == 2

    def test_delete_template(self, template_service):
        """Test template deletion."""
        template_service.register("test_delete", "Content")

        # Delete existing
        result = template_service.delete("test_delete")
        assert result is True

        # Verify deleted
        template = template_service.get("test_delete")
        assert template is None

        # Delete non-existent
        result = template_service.delete("nonexistent")
        assert result is False

    def test_render_template(self, template_service):
        """Test template rendering with variables."""
        template_service.register(
            "greeting",
            "Hello {{ name }}, welcome to {{ place }}!"
        )

        result = template_service.render(
            "greeting",
            {"name": "Alice", "place": "Wonderland"}
        )

        assert result.content == "Hello Alice, welcome to Wonderland!"
        assert result.template_name == "greeting"
        assert "name" in result.variables_used
        assert "place" in result.variables_used

    def test_render_template_with_kwargs(self, template_service):
        """Test template rendering with kwargs."""
        template_service.register("test", "{{ foo }} and {{ bar }}")

        result = template_service.render("test", foo="A", bar="B")

        assert result.content == "A and B"

    def test_render_missing_template(self, template_service):
        """Test rendering non-existent template raises error."""
        from arkham_frame.services.templates import TemplateNotFoundError

        with pytest.raises(TemplateNotFoundError):
            template_service.render("missing", {})

    def test_variable_extraction(self, template_service):
        """Test automatic variable extraction from template content."""
        template = template_service.register(
            "complex",
            "{{ user.name }} is {{ age }} years old. Lives in {{ city }}."
        )

        # Should extract root variable names
        assert "user" in template.variables
        assert "age" in template.variables
        assert "city" in template.variables

    def test_default_templates(self, template_service):
        """Test that default templates are registered."""
        # Check default templates exist
        report = template_service.get("report_basic")
        assert report is not None

        doc_summary = template_service.get("document_summary")
        assert doc_summary is not None

        entity = template_service.get("entity_report")
        assert entity is not None

        analysis = template_service.get("analysis_report")
        assert analysis is not None

        email = template_service.get("email_notification")
        assert email is not None

    def test_default_report_basic_rendering(self, template_service):
        """Test rendering the default report_basic template."""
        result = template_service.render(
            "report_basic",
            {
                "title": "Test Report",
                "author": "Test User",
                "content": "This is the report content."
            }
        )

        assert "Test Report" in result.content
        assert "Test User" in result.content
        assert "This is the report content." in result.content

    def test_template_validation(self, template_service):
        """Test template syntax validation."""
        # Valid template
        errors = template_service.validate("{{ name }} is valid")
        assert len(errors) == 0

        # Invalid template (unmatched braces)
        errors = template_service.validate("{{ name is invalid")
        assert len(errors) > 0

    def test_get_categories(self, template_service):
        """Test getting list of template categories."""
        template_service.register("t1", "c1", category="reports")
        template_service.register("t2", "c2", category="emails")
        template_service.register("t3", "c3", category="reports")

        categories = template_service.get_categories()
        assert "reports" in categories
        assert "emails" in categories
        assert "default" in categories  # From default templates

    def test_render_string(self, template_service):
        """Test rendering a template string directly without registration."""
        content = "Hello {{ name }}, you are {{ age }} years old."
        result = template_service.render_string(content, {"name": "Bob", "age": 30})

        assert result == "Hello Bob, you are 30 years old."

    def test_load_from_directory(self):
        """Test loading templates from a directory."""
        from arkham_frame.services.templates import TemplateService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test template files
            template_dir = Path(tmpdir)
            (template_dir / "test1.j2").write_text("Template 1: {{ var }}")
            (template_dir / "test2.html").write_text("<html>{{ content }}</html>")
            (template_dir / "test3.md").write_text("# {{ title }}")

            # Load templates
            service = TemplateService(template_dir=template_dir)
            count = service.load_from_directory(template_dir)

            assert count == 3
            assert service.get("test1") is not None
            assert service.get("test2") is not None
            assert service.get("test3") is not None


# =============================================================================
# Test 3: NotificationService
# =============================================================================

class TestNotificationService:
    """Test NotificationService multi-channel notification capabilities."""

    @pytest_asyncio.fixture
    async def notification_service(self):
        """Create NotificationService instance for testing."""
        from arkham_frame.services.notifications import NotificationService
        service = NotificationService()
        yield service
        service.clear_history()

    @pytest.mark.asyncio
    async def test_default_log_channel(self, notification_service):
        """Test that log channel is available by default."""
        channels = notification_service.list_channels()
        assert "log" in channels

    @pytest.mark.asyncio
    async def test_send_info_notification(self, notification_service):
        """Test sending INFO notification to log channel."""
        from arkham_frame.services.notifications import NotificationType

        notification = await notification_service.send(
            title="Test Info",
            message="This is a test info message",
            recipient="system",
            channel="log",
            type=NotificationType.INFO
        )

        assert notification.type == NotificationType.INFO
        assert notification.title == "Test Info"
        assert notification.message == "This is a test info message"
        assert notification.status.value == "sent"

    @pytest.mark.asyncio
    async def test_send_notification_all_types(self, notification_service):
        """Test sending notifications of all types."""
        from arkham_frame.services.notifications import NotificationType

        types = [
            NotificationType.INFO,
            NotificationType.SUCCESS,
            NotificationType.WARNING,
            NotificationType.ERROR,
            NotificationType.ALERT
        ]

        for notif_type in types:
            notification = await notification_service.send(
                title=f"Test {notif_type.value}",
                message=f"Testing {notif_type.value} notification",
                recipient="system",
                channel="log",
                type=notif_type
            )

            assert notification.type == notif_type
            assert notification.status.value == "sent"

    @pytest.mark.asyncio
    async def test_configure_webhook_channel(self, notification_service):
        """Test configuring a webhook channel."""
        notification_service.configure_webhook(
            name="test_webhook",
            url="https://example.com/webhook",
            method="POST",
            headers={"X-Custom": "header"}
        )

        channels = notification_service.list_channels()
        assert "test_webhook" in channels

    @pytest.mark.asyncio
    async def test_send_webhook_notification_mock(self, notification_service):
        """Test sending webhook notification with mocked HTTP client."""
        from arkham_frame.services.notifications import NotificationType

        # Configure webhook
        notification_service.configure_webhook(
            name="mock_webhook",
            url="https://example.com/webhook"
        )

        # Mock aiohttp to avoid real HTTP calls
        with patch('arkham_frame.services.notifications.aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="OK")

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_response
            mock_context.__aexit__.return_value = None

            mock_post = MagicMock(return_value=mock_context)
            mock_session.return_value.__aenter__.return_value.post = mock_post
            mock_session.return_value.__aexit__.return_value = None

            notification = await notification_service.send(
                title="Test Webhook",
                message="Test message",
                recipient="webhook-receiver",
                channel="mock_webhook",
                type=NotificationType.INFO
            )

            assert notification.status.value == "sent"

    @pytest.mark.asyncio
    async def test_notification_history(self, notification_service):
        """Test notification history tracking."""
        from arkham_frame.services.notifications import NotificationType

        # Clear history first
        notification_service.clear_history()

        # Send some notifications
        await notification_service.send("Test 1", "Message 1", "user1", "log")
        await notification_service.send("Test 2", "Message 2", "user2", "log")
        await notification_service.send("Test 3", "Message 3", "user3", "log")

        # Get history
        history = notification_service.get_history()
        assert len(history) >= 3

        # Recent ones should be at the end
        assert history[-1].title == "Test 3"
        assert history[-2].title == "Test 2"

    @pytest.mark.asyncio
    async def test_notification_history_filter_by_type(self, notification_service):
        """Test filtering notification history by type."""
        from arkham_frame.services.notifications import NotificationType

        notification_service.clear_history()

        # Send different types
        await notification_service.send("Info", "msg", "user", "log", NotificationType.INFO)
        await notification_service.send("Error", "msg", "user", "log", NotificationType.ERROR)
        await notification_service.send("Warning", "msg", "user", "log", NotificationType.WARNING)

        # Filter by ERROR
        errors = notification_service.get_history(type=NotificationType.ERROR)
        assert len(errors) == 1
        assert errors[0].type == NotificationType.ERROR

    @pytest.mark.asyncio
    async def test_notification_statistics(self, notification_service):
        """Test notification statistics."""
        from arkham_frame.services.notifications import NotificationType

        notification_service.clear_history()

        # Send various notifications
        await notification_service.send("Info1", "msg", "user", "log", NotificationType.INFO)
        await notification_service.send("Info2", "msg", "user", "log", NotificationType.INFO)
        await notification_service.send("Error", "msg", "user", "log", NotificationType.ERROR)

        stats = notification_service.get_stats()

        assert stats["total"] == 3
        assert stats["by_type"]["info"] == 2
        assert stats["by_type"]["error"] == 1
        assert stats["by_status"]["sent"] == 3
        assert stats["channels_configured"] >= 1

    @pytest.mark.asyncio
    async def test_channel_not_found_error(self, notification_service):
        """Test error when sending to non-existent channel."""
        from arkham_frame.services.notifications import ChannelNotFoundError

        with pytest.raises(ChannelNotFoundError):
            await notification_service.send(
                "Test",
                "Message",
                "user",
                channel="nonexistent_channel"
            )

    @pytest.mark.asyncio
    async def test_remove_channel(self, notification_service):
        """Test removing a notification channel."""
        # Configure a channel
        notification_service.configure_webhook(
            name="removable",
            url="https://example.com/hook"
        )

        assert "removable" in notification_service.list_channels()

        # Remove it
        result = notification_service.remove_channel("removable")
        assert result is True

        # Verify removed
        assert "removable" not in notification_service.list_channels()

        # Try to remove again
        result = notification_service.remove_channel("removable")
        assert result is False

    @pytest.mark.asyncio
    async def test_cannot_remove_log_channel(self, notification_service):
        """Test that default log channel cannot be removed."""
        result = notification_service.remove_channel("log")
        assert result is False
        assert "log" in notification_service.list_channels()


# =============================================================================
# Test 4: SchedulerService
# =============================================================================

class TestSchedulerService:
    """Test SchedulerService job scheduling capabilities."""

    @pytest_asyncio.fixture
    async def scheduler_service(self):
        """Create SchedulerService instance for testing."""
        from arkham_frame.services.scheduler import SchedulerService
        service = SchedulerService()
        await service.start()
        yield service
        await service.stop()

    @pytest.fixture
    def execution_tracker(self):
        """Create a tracker to count job executions."""
        class Tracker:
            def __init__(self):
                self.count = 0
                self.last_result = None

            async def increment(self):
                self.count += 1
                self.last_result = f"executed_{self.count}"
                return self.last_result

            def reset(self):
                self.count = 0
                self.last_result = None

        return Tracker()

    @pytest.mark.asyncio
    async def test_register_job_function(self, scheduler_service):
        """Test registering a job function."""
        async def test_func():
            return "test_result"

        scheduler_service.register_job("test_job", test_func)

        # Function should be registered
        assert "test_job" in scheduler_service._job_funcs

    @pytest.mark.asyncio
    async def test_schedule_interval_job(self, scheduler_service, execution_tracker):
        """Test scheduling an interval-based job."""
        scheduler_service.register_job("interval_job", execution_tracker.increment)

        job = scheduler_service.schedule_interval(
            name="Test Interval Job",
            func_name="interval_job",
            seconds=1  # Run every second
        )

        assert job.name == "Test Interval Job"
        assert job.trigger_type.value == "interval"
        assert job.status.value == "pending"

        # Wait for at least one execution
        await asyncio.sleep(2)

        # Job should have executed
        assert execution_tracker.count >= 1

    @pytest.mark.asyncio
    async def test_schedule_once_job(self, scheduler_service, execution_tracker):
        """Test scheduling a one-time job."""
        scheduler_service.register_job("once_job", execution_tracker.increment)

        run_date = datetime.utcnow() + timedelta(seconds=1)
        job = scheduler_service.schedule_once(
            name="One-Time Job",
            func_name="once_job",
            run_date=run_date
        )

        assert job.trigger_type.value == "date"
        assert execution_tracker.count == 0

        # Wait for execution
        await asyncio.sleep(2)

        # Should have executed exactly once
        assert execution_tracker.count == 1

    @pytest.mark.asyncio
    async def test_schedule_cron_job(self, scheduler_service):
        """Test scheduling a cron-style job."""
        async def cron_func():
            return "cron_executed"

        scheduler_service.register_job("cron_job", cron_func)

        # Schedule to run every minute (won't actually run in test)
        job = scheduler_service.schedule_cron(
            name="Cron Job",
            func_name="cron_job",
            minute="*",
            hour="*"
        )

        assert job.trigger_type.value == "cron"
        assert job.name == "Cron Job"

    @pytest.mark.asyncio
    async def test_list_jobs(self, scheduler_service):
        """Test listing scheduled jobs."""
        async def dummy():
            pass

        scheduler_service.register_job("dummy", dummy)

        # Schedule some jobs
        job1 = scheduler_service.schedule_interval("Job1", "dummy", seconds=60)
        job2 = scheduler_service.schedule_interval("Job2", "dummy", seconds=120)

        jobs = scheduler_service.list_jobs()

        # Should have our test jobs
        job_ids = [j.id for j in jobs]
        assert job1.id in job_ids
        assert job2.id in job_ids

    @pytest.mark.asyncio
    async def test_pause_resume_job(self, scheduler_service, execution_tracker):
        """Test pausing and resuming a job."""
        scheduler_service.register_job("pausable", execution_tracker.increment)

        job = scheduler_service.schedule_interval(
            name="Pausable Job",
            func_name="pausable",
            seconds=1
        )

        # Let it run once
        await asyncio.sleep(1.5)
        count_before_pause = execution_tracker.count
        assert count_before_pause >= 1

        # Pause the job
        result = scheduler_service.pause_job(job.id)
        assert result is True

        # Wait and verify it doesn't execute
        await asyncio.sleep(2)
        count_after_pause = execution_tracker.count
        # Count should not increase (or increase minimally due to timing)
        assert count_after_pause <= count_before_pause + 1

        # Resume the job
        result = scheduler_service.resume_job(job.id)
        assert result is True

        # Should start executing again
        await asyncio.sleep(1.5)
        final_count = execution_tracker.count
        assert final_count > count_after_pause

    @pytest.mark.asyncio
    async def test_remove_job(self, scheduler_service):
        """Test removing a scheduled job."""
        async def removable():
            pass

        scheduler_service.register_job("removable", removable)

        job = scheduler_service.schedule_interval("Removable", "removable", seconds=60)

        # Remove the job
        result = scheduler_service.remove_job(job.id)
        assert result is True

        # Job should not be in list
        jobs = scheduler_service.list_jobs()
        job_ids = [j.id for j in jobs]
        assert job.id not in job_ids

        # Try to remove again
        result = scheduler_service.remove_job(job.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_job(self, scheduler_service):
        """Test retrieving a specific job by ID."""
        async def test_func():
            pass

        scheduler_service.register_job("test", test_func)
        job = scheduler_service.schedule_interval("Test", "test", seconds=60)

        # Get the job
        retrieved = scheduler_service.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.name == "Test"

        # Non-existent job
        missing = scheduler_service.get_job("nonexistent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_execution_history(self, scheduler_service, execution_tracker):
        """Test job execution history tracking."""
        scheduler_service.register_job("tracked", execution_tracker.increment)

        job = scheduler_service.schedule_interval(
            name="Tracked Job",
            func_name="tracked",
            seconds=1
        )

        # Wait for some executions
        await asyncio.sleep(3)

        # Get history
        history = scheduler_service.get_history(job_id=job.id)
        assert len(history) >= 2

        # History entries should have execution details
        for entry in history:
            assert entry.job_id == job.id
            assert entry.started_at is not None
            assert entry.finished_at is not None
            assert entry.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_job_statistics(self, scheduler_service, execution_tracker):
        """Test scheduler statistics."""
        scheduler_service.register_job("stats_job", execution_tracker.increment)

        job = scheduler_service.schedule_interval(
            name="Stats Job",
            func_name="stats_job",
            seconds=1
        )

        # Wait for executions
        await asyncio.sleep(2.5)

        stats = scheduler_service.get_stats()

        assert stats["total_jobs"] >= 1
        assert stats["total_runs"] >= 2
        assert stats["running"] is True
        assert "by_status" in stats
        assert "by_trigger" in stats

    @pytest.mark.asyncio
    async def test_job_failure_tracking(self, scheduler_service):
        """Test that job failures are tracked properly."""
        async def failing_job():
            raise ValueError("Intentional failure")

        scheduler_service.register_job("failing", failing_job)

        job = scheduler_service.schedule_interval(
            name="Failing Job",
            func_name="failing",
            seconds=1
        )

        # Wait for failure
        await asyncio.sleep(2)

        # Job should show error count
        retrieved_job = scheduler_service.get_job(job.id)
        assert retrieved_job.error_count >= 1

        # History should show failed status
        history = scheduler_service.get_history(job_id=job.id)
        failed_runs = [h for h in history if h.status.value == "failed"]
        assert len(failed_runs) >= 1

        # Failed runs should have error message
        assert failed_runs[0].error is not None
        assert "Intentional failure" in failed_runs[0].error

    @pytest.mark.asyncio
    async def test_invalid_schedule_error(self, scheduler_service):
        """Test error when scheduling with invalid parameters."""
        from arkham_frame.services.scheduler import InvalidScheduleError

        async def test_func():
            pass

        scheduler_service.register_job("test", test_func)

        # Invalid: no time interval
        with pytest.raises(InvalidScheduleError):
            scheduler_service.schedule_interval("Bad Job", "test", seconds=0)

        # Invalid: function not registered
        with pytest.raises(InvalidScheduleError):
            scheduler_service.schedule_interval("Bad Job", "nonexistent_func", seconds=1)

        # Invalid: past run date
        past_date = datetime.utcnow() - timedelta(hours=1)
        with pytest.raises(InvalidScheduleError):
            scheduler_service.schedule_once("Bad Job", "test", run_date=past_date)


# =============================================================================
# Integration Test: Cross-Service Usage
# =============================================================================

class TestOutputServicesIntegration:
    """Test integration between multiple output services."""

    @pytest.mark.asyncio
    async def test_template_with_export(self):
        """Test using TemplateService to generate content for ExportService."""
        from arkham_frame.services.templates import TemplateService
        from arkham_frame.services.export import ExportService, ExportFormat

        # Create services
        templates = TemplateService()
        exports = ExportService()

        # Register a custom template
        templates.register(
            "report",
            "# {{ title }}\n\n{{ content }}\n\nGenerated at: {{ now }}"
        )

        # Render template
        rendered = templates.render("report", {
            "title": "Integration Test Report",
            "content": "This report was generated using templates."
        })

        # Export the rendered content
        result = exports.export(rendered.content, ExportFormat.MARKDOWN)

        assert "Integration Test Report" in result.content
        assert result.format == ExportFormat.MARKDOWN

    @pytest.mark.asyncio
    async def test_scheduler_with_notifications(self):
        """Test SchedulerService triggering NotificationService."""
        from arkham_frame.services.scheduler import SchedulerService
        from arkham_frame.services.notifications import NotificationService, NotificationType

        # Create services
        scheduler = SchedulerService()
        notifications = NotificationService()
        notifications.clear_history()

        await scheduler.start()

        # Define a job that sends a notification
        async def notification_job():
            await notifications.send(
                title="Scheduled Job Executed",
                message="This notification was sent by a scheduled job",
                recipient="system",
                channel="log",
                type=NotificationType.SUCCESS
            )

        # Register and schedule the job
        scheduler.register_job("notify_job", notification_job)
        scheduler.schedule_interval(
            name="Notification Job",
            func_name="notify_job",
            seconds=1
        )

        # Wait for execution
        await asyncio.sleep(2)

        # Check that notification was sent
        history = notifications.get_history()
        scheduled_notifications = [
            n for n in history
            if n.title == "Scheduled Job Executed"
        ]
        assert len(scheduled_notifications) >= 1

        await scheduler.stop()


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_output_services.py -v -s
    pytest.main([__file__, "-v", "-s"])
