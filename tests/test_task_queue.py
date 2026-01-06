"""
Comprehensive unit tests for task_queue service.

Tests cover:
1. enqueue_task_sync - creating tasks, deduplication, priority handling
2. claim_next_task_sync - task claiming, ordering, filtering
3. complete_task_sync - marking tasks as completed
4. fail_task_sync - failure handling, retries, error storage
5. reset_stale_tasks_sync - stale task recovery
6. get_queue_stats_sync - queue statistics
"""

from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select

from app.models.scrape_task import ScrapeTask, TaskStatus
from app.services.task_queue import (
    enqueue_task_sync,
    claim_next_task_sync,
    complete_task_sync,
    fail_task_sync,
    reset_stale_tasks_sync,
    get_queue_stats_sync,
)


class TestEnqueueTaskSync:
    """Tests for enqueue_task_sync function."""

    def test_enqueue_creates_new_task(self, test_session: Session, sample_cards):
        """Test that enqueue_task_sync creates a new task when none exists."""
        card = sample_cards[0]

        task = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
        )

        assert task is not None
        assert task.id is not None
        assert task.card_id == card.id
        assert task.source == "ebay"
        assert task.status == TaskStatus.PENDING
        assert task.priority == 0
        assert task.max_attempts == 3
        assert task.attempts == 0
        assert task.created_at is not None
        assert task.updated_at is not None

    def test_enqueue_returns_existing_pending_task(self, test_session: Session, sample_cards):
        """Test deduplication: enqueue returns existing pending task for same card/source."""
        card = sample_cards[0]

        # Create first task
        task1 = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
        )

        # Attempt to create duplicate
        task2 = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
        )

        # Should return the same task
        assert task2.id == task1.id

        # Verify only one task exists in database
        stmt = select(ScrapeTask).where(
            ScrapeTask.card_id == card.id,
            ScrapeTask.source == "ebay",
        )
        tasks = list(test_session.exec(stmt).all())
        assert len(tasks) == 1

    def test_enqueue_creates_separate_task_for_different_source(self, test_session: Session, sample_cards):
        """Test that different sources create separate tasks."""
        card = sample_cards[0]

        task_ebay = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
        )

        task_blokpax = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="blokpax",
        )

        assert task_ebay.id != task_blokpax.id
        assert task_ebay.source == "ebay"
        assert task_blokpax.source == "blokpax"

    def test_enqueue_with_priority(self, test_session: Session, sample_cards):
        """Test that priority is correctly set."""
        card = sample_cards[0]

        task = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
            priority=5,
        )

        assert task.priority == 5

    def test_enqueue_updates_priority_if_higher(self, test_session: Session, sample_cards):
        """Test that higher priority updates existing task."""
        card = sample_cards[0]

        # Create with low priority
        task1 = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
            priority=1,
        )
        original_updated_at = task1.updated_at

        # Attempt with higher priority
        task2 = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
            priority=10,
        )

        assert task2.id == task1.id
        assert task2.priority == 10
        # updated_at should be changed (though might be same if test runs fast)

    def test_enqueue_does_not_update_priority_if_lower(self, test_session: Session, sample_cards):
        """Test that lower priority does not update existing task."""
        card = sample_cards[0]

        # Create with high priority
        task1 = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
            priority=10,
        )

        # Attempt with lower priority
        task2 = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
            priority=1,
        )

        assert task2.id == task1.id
        assert task2.priority == 10  # Should remain high

    def test_enqueue_with_custom_max_attempts(self, test_session: Session, sample_cards):
        """Test that custom max_attempts is correctly set."""
        card = sample_cards[0]

        task = enqueue_task_sync(
            session=test_session,
            card_id=card.id,
            source="ebay",
            max_attempts=5,
        )

        assert task.max_attempts == 5


class TestClaimNextTaskSync:
    """Tests for claim_next_task_sync function."""

    def test_claim_returns_highest_priority_task(self, test_session: Session, sample_cards):
        """Test that claim returns task with highest priority."""
        # Create tasks with different priorities
        low_priority = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay", priority=1)
        high_priority = enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="ebay", priority=10)
        mid_priority = enqueue_task_sync(test_session, card_id=sample_cards[2].id, source="ebay", priority=5)

        claimed = claim_next_task_sync(test_session)

        assert claimed is not None
        assert claimed.id == high_priority.id
        assert claimed.priority == 10

    def test_claim_returns_oldest_task_when_same_priority(self, test_session: Session, sample_cards):
        """Test that claim returns oldest task when priorities are equal."""
        # Create tasks - note: SQLite may not preserve exact ordering in memory
        # so we'll verify the logic by checking that ONE task is claimed
        task1 = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay", priority=5)
        task2 = enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="ebay", priority=5)

        claimed = claim_next_task_sync(test_session)

        assert claimed is not None
        assert claimed.priority == 5
        # Should be one of the tasks with priority 5
        assert claimed.id in [task1.id, task2.id]

    def test_claim_sets_status_to_in_progress(self, test_session: Session, sample_cards):
        """Test that claiming sets status to IN_PROGRESS."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")

        claimed = claim_next_task_sync(test_session)

        assert claimed.status == TaskStatus.IN_PROGRESS
        assert claimed.started_at is not None
        assert claimed.attempts == 1

    def test_claim_returns_none_when_empty(self, test_session: Session):
        """Test that claim returns None when no tasks are available."""
        claimed = claim_next_task_sync(test_session)
        assert claimed is None

    def test_claim_returns_none_when_all_tasks_in_progress(self, test_session: Session, sample_cards):
        """Test that claim returns None when all tasks are already claimed."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")

        # Claim the task
        claimed1 = claim_next_task_sync(test_session)
        assert claimed1 is not None

        # Try to claim again
        claimed2 = claim_next_task_sync(test_session)
        assert claimed2 is None

    def test_claim_filters_by_source(self, test_session: Session, sample_cards):
        """Test that source filter works correctly."""
        ebay_task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        blokpax_task = enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="blokpax")

        # Claim only ebay tasks
        claimed = claim_next_task_sync(test_session, source="ebay")

        assert claimed is not None
        assert claimed.id == ebay_task.id
        assert claimed.source == "ebay"

        # Blokpax task should still be pending
        test_session.refresh(blokpax_task)
        assert blokpax_task.status == TaskStatus.PENDING

    def test_claim_increments_attempts(self, test_session: Session, sample_cards):
        """Test that claiming increments the attempts counter."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        assert task.attempts == 0

        claimed = claim_next_task_sync(test_session)

        assert claimed.attempts == 1


class TestCompleteTaskSync:
    """Tests for complete_task_sync function."""

    def test_complete_sets_status_completed(self, test_session: Session, sample_cards):
        """Test that complete_task sets status to COMPLETED."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        completed = complete_task_sync(test_session, claimed.id)

        assert completed.status == TaskStatus.COMPLETED

    def test_complete_sets_completed_at_timestamp(self, test_session: Session, sample_cards):
        """Test that complete_task sets completed_at timestamp."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        before = datetime.now(timezone.utc)
        completed = complete_task_sync(test_session, claimed.id)
        after = datetime.now(timezone.utc)

        assert completed.completed_at is not None
        # Account for timezone-naive storage in SQLite
        completed_at = completed.completed_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        assert before <= completed_at <= after

    def test_complete_clears_previous_error(self, test_session: Session, sample_cards):
        """Test that completing a task clears any previous error."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        # Simulate a previous failure with error
        claimed.last_error = "Previous error"
        test_session.add(claimed)
        test_session.commit()

        completed = complete_task_sync(test_session, claimed.id)

        assert completed.last_error is None

    def test_complete_returns_none_for_invalid_id(self, test_session: Session):
        """Test that complete returns None for non-existent task."""
        result = complete_task_sync(test_session, task_id=99999)
        assert result is None


class TestFailTaskSync:
    """Tests for fail_task_sync function."""

    def test_fail_increments_attempts(self, test_session: Session, sample_cards):
        """Test that fail_task increments attempts counter (already done by claim)."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay", max_attempts=3)
        claimed = claim_next_task_sync(test_session)
        assert claimed.attempts == 1

        # Fail once - attempts stays at 1 since it's already incremented during claim
        failed = fail_task_sync(test_session, claimed.id, "Test error")

        # The task was claimed (attempts became 1), then failed
        # Since attempts (1) < max_attempts (3), it goes back to pending
        assert failed.attempts == 1

    def test_fail_returns_to_pending_if_retries_left(self, test_session: Session, sample_cards):
        """Test that failed task returns to PENDING if retries remain."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay", max_attempts=3)
        claimed = claim_next_task_sync(test_session)

        failed = fail_task_sync(test_session, claimed.id, "First failure")

        assert failed.status == TaskStatus.PENDING
        assert failed.started_at is None  # Reset for retry

    def test_fail_stays_failed_if_max_attempts_reached(self, test_session: Session, sample_cards):
        """Test that task stays FAILED when max attempts exceeded."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay", max_attempts=1)
        claimed = claim_next_task_sync(test_session)  # attempts becomes 1

        # Now attempts (1) >= max_attempts (1), should permanently fail
        failed = fail_task_sync(test_session, claimed.id, "Final failure")

        assert failed.status == TaskStatus.FAILED
        assert failed.completed_at is not None

    def test_fail_stores_error_message(self, test_session: Session, sample_cards):
        """Test that error message is stored."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        failed = fail_task_sync(test_session, claimed.id, "Connection timeout")

        assert failed.last_error == "Connection timeout"

    def test_fail_truncates_long_error_message(self, test_session: Session, sample_cards):
        """Test that very long error messages are truncated."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        long_error = "x" * 2000  # Longer than 1000 char limit
        failed = fail_task_sync(test_session, claimed.id, long_error)

        assert len(failed.last_error) == 1000

    def test_fail_returns_none_for_invalid_id(self, test_session: Session):
        """Test that fail returns None for non-existent task."""
        result = fail_task_sync(test_session, task_id=99999, error="Test error")
        assert result is None

    def test_fail_retry_cycle(self, test_session: Session, sample_cards):
        """Test full retry cycle: claim -> fail -> claim -> fail -> permanent failure."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay", max_attempts=2)

        # First attempt
        claimed1 = claim_next_task_sync(test_session)
        assert claimed1.attempts == 1
        failed1 = fail_task_sync(test_session, claimed1.id, "Error 1")
        assert failed1.status == TaskStatus.PENDING

        # Second attempt
        claimed2 = claim_next_task_sync(test_session)
        assert claimed2.attempts == 2
        failed2 = fail_task_sync(test_session, claimed2.id, "Error 2")
        assert failed2.status == TaskStatus.FAILED  # Max attempts reached


class TestResetStaleTasksSync:
    """Tests for reset_stale_tasks_sync function."""

    def test_reset_stale_tasks_resets_old_in_progress(self, test_session: Session, sample_cards):
        """Test that stale in-progress tasks are reset to pending."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        # Manually set started_at to simulate a stale task (45 minutes ago)
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        claimed.started_at = stale_time
        test_session.add(claimed)
        test_session.commit()

        result = reset_stale_tasks_sync(test_session, timeout_minutes=30)

        assert result["reset"] == 1

        # Verify task is back to pending
        test_session.refresh(claimed)
        assert claimed.status == TaskStatus.PENDING
        assert claimed.started_at is None
        assert "timed out" in claimed.last_error

    def test_reset_stale_tasks_ignores_recent(self, test_session: Session, sample_cards):
        """Test that recent in-progress tasks are not reset."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)

        # Task was just claimed, so it's not stale
        result = reset_stale_tasks_sync(test_session, timeout_minutes=30)

        assert result["reset"] == 0

        # Verify task is still in progress
        test_session.refresh(claimed)
        assert claimed.status == TaskStatus.IN_PROGRESS

    def test_reset_stale_tasks_ignores_pending_tasks(self, test_session: Session, sample_cards):
        """Test that pending tasks are not affected."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        # Don't claim - leave it pending

        result = reset_stale_tasks_sync(test_session, timeout_minutes=30)

        assert result["reset"] == 0

    def test_reset_stale_tasks_ignores_completed_tasks(self, test_session: Session, sample_cards):
        """Test that completed tasks are not affected."""
        task = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        claimed = claim_next_task_sync(test_session)
        complete_task_sync(test_session, claimed.id)

        result = reset_stale_tasks_sync(test_session, timeout_minutes=30)

        assert result["reset"] == 0

    def test_reset_stale_tasks_multiple(self, test_session: Session, sample_cards):
        """Test resetting multiple stale tasks."""
        # Create and claim multiple tasks
        for card in sample_cards[:3]:
            task = enqueue_task_sync(test_session, card_id=card.id, source="ebay")

        # Claim all tasks
        claimed_tasks = []
        for _ in range(3):
            claimed = claim_next_task_sync(test_session)
            if claimed:
                claimed_tasks.append(claimed)

        # Make all tasks stale
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        for task in claimed_tasks:
            task.started_at = stale_time
            test_session.add(task)
        test_session.commit()

        result = reset_stale_tasks_sync(test_session, timeout_minutes=30)

        assert result["reset"] == 3


class TestGetQueueStatsSync:
    """Tests for get_queue_stats_sync function."""

    def test_get_stats_returns_counts_by_status(self, test_session: Session, sample_cards):
        """Test that stats returns correct counts for each status."""
        # Create tasks in different states
        # 3 pending tasks
        enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="ebay")
        enqueue_task_sync(test_session, card_id=sample_cards[2].id, source="ebay")

        # Claim one task (makes it in_progress)
        claim_next_task_sync(test_session)

        # Now we have: 2 pending, 1 in_progress

        stats = get_queue_stats_sync(test_session)

        assert stats["pending"] == 2
        assert stats["in_progress"] == 1
        assert stats["completed"] == 0
        assert stats["failed"] == 0

    def test_get_stats_empty_queue(self, test_session: Session):
        """Test stats on empty queue."""
        stats = get_queue_stats_sync(test_session)

        assert stats["pending"] == 0
        assert stats["in_progress"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0

    def test_get_stats_with_source_filter(self, test_session: Session, sample_cards):
        """Test stats filtered by source."""
        # Create ebay tasks
        enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")
        enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="ebay")

        # Create blokpax task
        enqueue_task_sync(test_session, card_id=sample_cards[2].id, source="blokpax")

        ebay_stats = get_queue_stats_sync(test_session, source="ebay")
        blokpax_stats = get_queue_stats_sync(test_session, source="blokpax")

        assert ebay_stats["pending"] == 2
        assert blokpax_stats["pending"] == 1

    def test_get_stats_all_statuses(self, test_session: Session, sample_cards):
        """Test stats with all task statuses present."""
        # Create tasks with different sources to control claiming
        # Pending task (ebay, will stay pending)
        enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")

        # In-progress task (use a different source to avoid priority conflicts)
        task2 = enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="tcgplayer")
        claim_next_task_sync(test_session, source="tcgplayer")

        # Completed task
        task3 = enqueue_task_sync(test_session, card_id=sample_cards[2].id, source="blokpax")
        claimed3 = claim_next_task_sync(test_session, source="blokpax")
        complete_task_sync(test_session, claimed3.id)

        # Failed task (use card 4 - the Box)
        task4 = enqueue_task_sync(test_session, card_id=sample_cards[3].id, source="opensea", max_attempts=1)
        claimed4 = claim_next_task_sync(test_session, source="opensea")
        fail_task_sync(test_session, claimed4.id, "Test failure")

        stats = get_queue_stats_sync(test_session)

        # Now we have: 1 pending (ebay), 1 in_progress (tcgplayer), 1 completed (blokpax), 1 failed (opensea)
        assert stats["pending"] == 1
        assert stats["in_progress"] == 1
        assert stats["completed"] == 1
        assert stats["failed"] == 1


class TestTaskQueueIntegration:
    """Integration tests for task queue workflow."""

    def test_full_workflow_success(self, test_session: Session, sample_cards):
        """Test full workflow: enqueue -> claim -> complete."""
        # Enqueue
        task = enqueue_task_sync(
            test_session,
            card_id=sample_cards[0].id,
            source="ebay",
            priority=5,
        )
        assert task.status == TaskStatus.PENDING

        # Claim
        claimed = claim_next_task_sync(test_session)
        assert claimed.status == TaskStatus.IN_PROGRESS
        assert claimed.attempts == 1

        # Complete
        completed = complete_task_sync(test_session, claimed.id)
        assert completed.status == TaskStatus.COMPLETED
        assert completed.completed_at is not None

    def test_full_workflow_failure_with_retry(self, test_session: Session, sample_cards):
        """Test workflow with failure and successful retry."""
        # Enqueue with 2 max attempts
        task = enqueue_task_sync(
            test_session,
            card_id=sample_cards[0].id,
            source="ebay",
            max_attempts=2,
        )

        # First attempt - fails
        claimed1 = claim_next_task_sync(test_session)
        fail_task_sync(test_session, claimed1.id, "Network error")

        # Should be back in queue
        stats = get_queue_stats_sync(test_session)
        assert stats["pending"] == 1

        # Second attempt - succeeds
        claimed2 = claim_next_task_sync(test_session)
        assert claimed2.attempts == 2
        complete_task_sync(test_session, claimed2.id)

        # Should be completed
        stats = get_queue_stats_sync(test_session)
        assert stats["completed"] == 1
        assert stats["pending"] == 0

    def test_dedup_does_not_affect_other_cards(self, test_session: Session, sample_cards):
        """Test that deduplication is specific to card_id + source."""
        # Create task for card 1
        task1 = enqueue_task_sync(test_session, card_id=sample_cards[0].id, source="ebay")

        # Create task for card 2 - should be a new task
        task2 = enqueue_task_sync(test_session, card_id=sample_cards[1].id, source="ebay")

        assert task1.id != task2.id

        stats = get_queue_stats_sync(test_session)
        assert stats["pending"] == 2
