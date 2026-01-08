"""
Tests for scraper metrics tracking.

Tests cover:
- MetricsStore initialization
- Recording job start and completion
- Metrics retrieval
- Summary calculations
"""

from datetime import datetime, timezone

from app.core.metrics import MetricsStore, ScrapeMetrics, scraper_metrics


class TestScrapeMetrics:
    """Tests for ScrapeMetrics dataclass."""

    def test_scrape_metrics_defaults(self):
        """Test that ScrapeMetrics has correct defaults."""
        metrics = ScrapeMetrics(
            job_name="test_job",
            started_at=datetime.now(timezone.utc),
        )

        assert metrics.job_name == "test_job"
        assert metrics.completed_at is None
        assert metrics.cards_processed == 0
        assert metrics.successful == 0
        assert metrics.failed == 0
        assert metrics.db_errors == 0
        assert metrics.duration_seconds == 0.0


class TestMetricsStoreRecordStart:
    """Tests for recording job starts."""

    def test_record_start_creates_metrics(self):
        """Test that record_start creates metrics entry."""
        store = MetricsStore()

        store.record_start("test_job")

        metrics = store.get_last_run("test_job")
        assert metrics is not None
        assert metrics.job_name == "test_job"
        assert metrics.started_at is not None

    def test_record_start_replaces_previous(self):
        """Test that record_start replaces previous entry."""
        store = MetricsStore()

        # First start
        store.record_start("test_job")
        first_metrics = store.get_last_run("test_job")
        assert first_metrics is not None
        first_start = first_metrics.started_at

        # Second start (simulating a new run)
        store.record_start("test_job")
        second_metrics = store.get_last_run("test_job")
        assert second_metrics is not None
        second_start = second_metrics.started_at

        # Should have been replaced
        assert second_start >= first_start


class TestMetricsStoreRecordComplete:
    """Tests for recording job completions."""

    def test_record_complete_with_start(self):
        """Test recording completion after a start."""
        store = MetricsStore()

        store.record_start("test_job")
        store.record_complete(
            "test_job",
            cards_processed=100,
            successful=95,
            failed=5,
            db_errors=2,
        )

        metrics = store.get_last_run("test_job")
        assert metrics is not None
        assert metrics.completed_at is not None
        assert metrics.cards_processed == 100
        assert metrics.successful == 95
        assert metrics.failed == 5
        assert metrics.db_errors == 2
        assert metrics.duration_seconds >= 0

    def test_record_complete_without_start(self):
        """Test recording completion without a prior start."""
        store = MetricsStore()

        store.record_complete(
            "test_job",
            cards_processed=50,
            successful=50,
            failed=0,
        )

        metrics = store.get_last_run("test_job")
        assert metrics is not None
        assert metrics.cards_processed == 50
        assert metrics.successful == 50

    def test_record_complete_updates_totals(self):
        """Test that completion updates total counts."""
        store = MetricsStore()

        store.record_complete("test_job", 10, 10, 0)
        store.record_complete("test_job", 10, 10, 0)
        store.record_complete("test_job", 10, 10, 0)

        all_metrics = store.get_all_metrics()
        assert all_metrics["test_job"]["total_runs"] == 3
        assert all_metrics["test_job"]["total_failures"] == 0

    def test_record_complete_tracks_failures(self):
        """Test that mostly-failed runs are counted as failures."""
        store = MetricsStore()

        # Run where failed > successful counts as a failure
        store.record_complete("test_job", 10, 3, 7)

        all_metrics = store.get_all_metrics()
        assert all_metrics["test_job"]["total_failures"] == 1


class TestMetricsStoreGetLastRun:
    """Tests for retrieving last run metrics."""

    def test_get_last_run_returns_none_for_unknown(self):
        """Test that get_last_run returns None for unknown job."""
        store = MetricsStore()

        result = store.get_last_run("unknown_job")

        assert result is None

    def test_get_last_run_returns_most_recent(self):
        """Test that get_last_run returns most recent metrics."""
        store = MetricsStore()

        store.record_start("test_job")
        store.record_complete("test_job", 100, 100, 0)

        metrics = store.get_last_run("test_job")
        assert metrics is not None
        assert metrics.cards_processed == 100


class TestMetricsStoreGetAllMetrics:
    """Tests for retrieving all metrics."""

    def test_get_all_metrics_empty(self):
        """Test get_all_metrics returns empty dict when no jobs."""
        store = MetricsStore()

        result = store.get_all_metrics()

        assert result == {}

    def test_get_all_metrics_structure(self):
        """Test get_all_metrics returns correct structure."""
        store = MetricsStore()

        store.record_start("test_job")
        store.record_complete("test_job", 100, 90, 10)

        result = store.get_all_metrics()

        assert "test_job" in result
        job_metrics = result["test_job"]
        assert "last_run" in job_metrics
        assert "total_runs" in job_metrics
        assert "total_failures" in job_metrics

        last_run = job_metrics["last_run"]
        assert "started_at" in last_run
        assert "completed_at" in last_run
        assert "cards_processed" in last_run
        assert "successful" in last_run
        assert "failed" in last_run
        assert "db_errors" in last_run
        assert "duration_seconds" in last_run
        assert "success_rate" in last_run

    def test_get_all_metrics_success_rate_calculation(self):
        """Test that success rate is calculated correctly."""
        store = MetricsStore()

        store.record_start("test_job")
        store.record_complete("test_job", 100, 80, 20)

        result = store.get_all_metrics()
        success_rate = result["test_job"]["last_run"]["success_rate"]

        assert success_rate == 80.0

    def test_get_all_metrics_zero_cards_success_rate(self):
        """Test success rate is 0 when no cards processed."""
        store = MetricsStore()

        store.record_start("test_job")
        store.record_complete("test_job", 0, 0, 0)

        result = store.get_all_metrics()
        success_rate = result["test_job"]["last_run"]["success_rate"]

        assert success_rate == 0


class TestMetricsStoreGetSummary:
    """Tests for metrics summary."""

    def test_get_summary_empty(self):
        """Test get_summary returns correct structure when empty."""
        store = MetricsStore()

        result = store.get_summary()

        assert result["total_jobs"] == 0
        assert result["healthy_jobs"] == 0
        assert result["degraded_jobs"] == 0
        assert result["unhealthy_jobs"] == 0

    def test_get_summary_healthy_jobs(self):
        """Test that jobs with 90%+ success rate are healthy."""
        store = MetricsStore()

        # 95% success rate = healthy
        store.record_complete("healthy_job", 100, 95, 5)

        result = store.get_summary()

        assert result["total_jobs"] == 1
        assert result["healthy_jobs"] == 1
        assert result["degraded_jobs"] == 0
        assert result["unhealthy_jobs"] == 0

    def test_get_summary_degraded_jobs(self):
        """Test that jobs with 50-89% success rate are degraded."""
        store = MetricsStore()

        # 70% success rate = degraded
        store.record_complete("degraded_job", 100, 70, 30)

        result = store.get_summary()

        assert result["total_jobs"] == 1
        assert result["healthy_jobs"] == 0
        assert result["degraded_jobs"] == 1
        assert result["unhealthy_jobs"] == 0

    def test_get_summary_unhealthy_jobs(self):
        """Test that jobs with <50% success rate are unhealthy."""
        store = MetricsStore()

        # 30% success rate = unhealthy
        store.record_complete("unhealthy_job", 100, 30, 70)

        result = store.get_summary()

        assert result["total_jobs"] == 1
        assert result["healthy_jobs"] == 0
        assert result["degraded_jobs"] == 0
        assert result["unhealthy_jobs"] == 1

    def test_get_summary_mixed_jobs(self):
        """Test summary with mixed job health states."""
        store = MetricsStore()

        store.record_complete("healthy", 100, 95, 5)
        store.record_complete("degraded", 100, 60, 40)
        store.record_complete("unhealthy", 100, 20, 80)

        result = store.get_summary()

        assert result["total_jobs"] == 3
        assert result["healthy_jobs"] == 1
        assert result["degraded_jobs"] == 1
        assert result["unhealthy_jobs"] == 1

    def test_get_summary_zero_cards_not_counted(self):
        """Test that jobs with zero cards aren't counted as healthy."""
        store = MetricsStore()

        store.record_complete("empty_job", 0, 0, 0)

        result = store.get_summary()

        assert result["total_jobs"] == 1
        # Not healthy or degraded (no cards processed)
        assert result["healthy_jobs"] == 0
        assert result["degraded_jobs"] == 0
        assert result["unhealthy_jobs"] == 1


class TestGlobalMetricsStore:
    """Tests for the global metrics store instance."""

    def test_global_metrics_store_exists(self):
        """Test that global scraper_metrics exists."""
        assert scraper_metrics is not None
        assert isinstance(scraper_metrics, MetricsStore)
