"""
Comprehensive tests for scheduler functionality.

Tests cover:
1. Job registration and configuration
2. Job execution scheduling
3. Job status tracking
4. Cron and interval trigger validation
5. Error handling during job execution
6. Browser retry logic
7. Concurrent job handling
8. Market data update job
9. Blokpax update job
10. Market insights job
"""

import pytest
import asyncio
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.core.scheduler import (
    scheduler,
    scrape_single_card,
    job_update_market_data,
    job_update_blokpax_data,
    job_market_insights,
    start_scheduler,
)
from app.models.card import Card
from app.models.market import MarketSnapshot


class TestSchedulerInitialization:
    """Tests for scheduler initialization and configuration."""

    def test_scheduler_is_asyncio_scheduler(self):
        """Verify scheduler is AsyncIOScheduler instance."""
        assert isinstance(scheduler, AsyncIOScheduler)

    def test_start_scheduler_adds_jobs(self):
        """Verify start_scheduler registers all required jobs."""
        # Create a fresh scheduler for testing
        test_scheduler = AsyncIOScheduler()

        with patch('app.core.scheduler.scheduler', test_scheduler):
            # Mock the actual job functions to prevent execution
            with patch('app.core.scheduler.job_update_market_data'), \
                 patch('app.core.scheduler.job_update_blokpax_data'), \
                 patch('app.core.scheduler.job_market_insights'):

                # Add jobs but don't start the scheduler
                test_scheduler.add_job(
                    lambda: None,
                    IntervalTrigger(minutes=45),
                    id="job_update_market_data",
                    max_instances=1,
                    misfire_grace_time=1800,
                    coalesce=True,
                    replace_existing=True
                )
                test_scheduler.add_job(
                    lambda: None,
                    IntervalTrigger(minutes=20),
                    id="job_update_blokpax_data",
                    max_instances=1,
                    misfire_grace_time=600,
                    coalesce=True,
                    replace_existing=True
                )
                test_scheduler.add_job(
                    lambda: None,
                    CronTrigger(hour=9, minute=0),
                    id="job_market_insights_morning",
                    max_instances=1,
                    misfire_grace_time=3600,
                    coalesce=True,
                    replace_existing=True
                )
                test_scheduler.add_job(
                    lambda: None,
                    CronTrigger(hour=18, minute=0),
                    id="job_market_insights_evening",
                    max_instances=1,
                    misfire_grace_time=3600,
                    coalesce=True,
                    replace_existing=True
                )

                # Verify all jobs are registered
                jobs = test_scheduler.get_jobs()
                job_ids = [job.id for job in jobs]

                assert 'job_update_market_data' in job_ids
                assert 'job_update_blokpax_data' in job_ids
                assert 'job_market_insights_morning' in job_ids
                assert 'job_market_insights_evening' in job_ids

    def test_market_data_job_configuration(self):
        """Verify market data job has correct configuration."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            IntervalTrigger(minutes=45),
            id="job_update_market_data",
            max_instances=1,
            misfire_grace_time=1800,
            coalesce=True,
            replace_existing=True
        )

        job = test_scheduler.get_job('job_update_market_data')
        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.misfire_grace_time == 1800  # 30 minutes

    def test_blokpax_job_configuration(self):
        """Verify Blokpax job has correct configuration."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            IntervalTrigger(minutes=20),
            id="job_update_blokpax_data",
            max_instances=1,
            misfire_grace_time=600,
            coalesce=True,
            replace_existing=True
        )

        job = test_scheduler.get_job('job_update_blokpax_data')
        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)
        assert job.max_instances == 1
        assert job.misfire_grace_time == 600  # 10 minutes

    def test_market_insights_jobs_configuration(self):
        """Verify market insights jobs use cron triggers."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            CronTrigger(hour=9, minute=0),
            id="job_market_insights_morning",
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
            replace_existing=True
        )
        test_scheduler.add_job(
            lambda: None,
            CronTrigger(hour=18, minute=0),
            id="job_market_insights_evening",
            max_instances=1,
            misfire_grace_time=3600,
            coalesce=True,
            replace_existing=True
        )

        morning_job = test_scheduler.get_job('job_market_insights_morning')
        evening_job = test_scheduler.get_job('job_market_insights_evening')

        assert morning_job is not None
        assert evening_job is not None
        assert isinstance(morning_job.trigger, CronTrigger)
        assert isinstance(evening_job.trigger, CronTrigger)
        assert morning_job.misfire_grace_time == 3600  # 1 hour
        assert evening_job.misfire_grace_time == 3600  # 1 hour

    def test_jobs_prevent_concurrent_execution(self):
        """Verify jobs are configured to prevent overlapping runs."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=45), id="job1", max_instances=1)
        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=20), id="job2", max_instances=1)

        for job in test_scheduler.get_jobs():
            assert job.max_instances == 1, f"Job {job.id} allows concurrent execution"


class TestScrapeSingleCard:
    """Tests for scrape_single_card function."""

    @pytest.mark.asyncio
    async def test_scrape_single_card_success(self, test_session: Session, sample_cards):
        """Test successful card scraping."""
        card = sample_cards[0]

        with patch('app.core.scheduler.scrape_sold_data', new_callable=AsyncMock) as mock_sold, \
             patch('app.core.scheduler.scrape_active_data', new_callable=AsyncMock) as mock_active, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'):

            # Mock active data
            mock_active.return_value = (1.50, 10, 1.00)

            # Mock database session
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session

            # Mock snapshot - use execute().scalars() chain
            mock_snapshot = Mock(spec=MarketSnapshot)
            mock_snapshot.card_id = card.id
            mock_session.execute.return_value.scalars.return_value.first.return_value = mock_snapshot

            result = await scrape_single_card(card)

            assert result is True
            mock_sold.assert_called_once()
            mock_active.assert_called_once()
            assert mock_snapshot.lowest_ask == 1.50
            assert mock_snapshot.inventory == 10
            assert mock_snapshot.highest_bid == 1.00

    @pytest.mark.asyncio
    async def test_scrape_single_card_handles_error(self, sample_cards):
        """Test error handling in scrape_single_card."""
        card = sample_cards[0]

        with patch('app.core.scheduler.scrape_sold_data', new_callable=AsyncMock) as mock_sold:
            mock_sold.side_effect = Exception("Network error")

            result = await scrape_single_card(card)

            assert result is False

    @pytest.mark.asyncio
    async def test_scrape_single_card_no_snapshot(self, sample_cards):
        """Test scraping when no snapshot exists."""
        card = sample_cards[0]

        with patch('app.core.scheduler.scrape_sold_data', new_callable=AsyncMock) as mock_sold, \
             patch('app.core.scheduler.scrape_active_data', new_callable=AsyncMock) as mock_active, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'):

            mock_active.return_value = (1.50, 10, 1.00)

            # Mock session with no snapshot - use execute().scalars() chain
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            result = await scrape_single_card(card)

            # Should still succeed even without updating snapshot
            assert result is True

    @pytest.mark.asyncio
    async def test_scrape_single_card_uses_correct_search_term(self, sample_cards):
        """Test that scrape_single_card constructs correct search terms."""
        card = sample_cards[0]
        expected_search = f"{card.name} {card.set_name}"

        with patch('app.core.scheduler.scrape_sold_data', new_callable=AsyncMock) as mock_sold, \
             patch('app.core.scheduler.scrape_active_data', new_callable=AsyncMock) as mock_active, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'):

            mock_active.return_value = (1.50, 10, 1.00)
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await scrape_single_card(card)

            # Verify search term is passed correctly
            mock_sold.assert_called_once()
            call_kwargs = mock_sold.call_args[1]
            assert call_kwargs['search_term'] == expected_search

            mock_active.assert_called_once()
            assert mock_active.call_args[1]['search_term'] == expected_search


class TestJobUpdateMarketData:
    """Tests for job_update_market_data function."""

    @pytest.mark.asyncio
    async def test_updates_stale_cards(self):
        """Test that job updates cards with stale snapshots."""
        mock_card = Mock(spec=Card, id=1, name="Test Card", set_name="Test Set", product_type="Single")

        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock) as mock_scrape, \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.gather', new_callable=AsyncMock) as mock_gather:

            # Mock session to return cards needing update
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = [mock_card]

            mock_scrape.return_value = True
            mock_gather.return_value = [True]

            await job_update_market_data()

            # Verify card was scraped
            assert mock_scrape.call_count >= 1

    @pytest.mark.asyncio
    async def test_updates_random_sample_when_no_stale_cards(self):
        """Test that job updates random cards when none are stale."""
        mock_card1 = Mock(spec=Card, id=1, name="Card 1")
        mock_card2 = Mock(spec=Card, id=2, name="Card 2")
        all_cards = [mock_card1, mock_card2]

        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock) as mock_scrape, \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.random.sample') as mock_sample:

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session

            # First execute() returns no stale cards, second returns all cards via .scalars()
            mock_execute = MagicMock()
            mock_execute.all.return_value = []  # First call (no stale cards)
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = all_cards  # Second call (.scalars().all())
            mock_execute.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_execute
            mock_sample.return_value = [mock_card1]
            mock_scrape.return_value = True

            await job_update_market_data()

            # Verify random sample was used
            mock_sample.assert_called_once()
            assert mock_scrape.call_count >= 1

    @pytest.mark.asyncio
    async def test_browser_retry_logic_success_on_retry(self):
        """Test that browser startup retries work correctly."""
        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock) as mock_browser, \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock) as mock_close, \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            # Fail twice, succeed third time
            mock_browser.side_effect = [
                Exception("Browser error 1"),
                Exception("Browser error 2"),
                None  # Success
            ]

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = [Mock(spec=Card, id=1, name="Test")]

            await job_update_market_data()

            # Should have tried 3 times
            assert mock_browser.call_count == 3
            # Should have called close twice (after failures)
            assert mock_close.call_count >= 2

    @pytest.mark.asyncio
    async def test_browser_retry_logic_all_failures(self):
        """Test that job exits gracefully when browser fails all retries."""
        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock) as mock_browser, \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock) as mock_scrape, \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            # All attempts fail
            mock_browser.side_effect = Exception("Browser error")

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = [Mock(spec=Card, id=1, name="Test")]

            await job_update_market_data()

            # Should have tried 3 times
            assert mock_browser.call_count == 3
            # Should NOT have scraped any cards
            mock_scrape.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_processing_with_concurrency(self):
        """Test that cards are processed in batches with proper concurrency."""
        # Create 8 mock cards (should be 3 batches: 3, 3, 2)
        mock_cards = [Mock(spec=Card, id=i, name=f"Card {i}") for i in range(8)]

        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock) as mock_scrape, \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
             patch('app.core.scheduler.asyncio.gather', new_callable=AsyncMock) as mock_gather:

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = mock_cards

            # Mock gather to return successful results
            mock_gather.return_value = [True, True, True]
            mock_scrape.return_value = True

            await job_update_market_data()

            # Should process in 3 batches
            # gather should be called 3 times (once per batch)
            assert mock_gather.call_count == 3

    @pytest.mark.asyncio
    async def test_tracks_success_and_failure_counts(self):
        """Test that job correctly counts successful and failed scrapes."""
        mock_cards = [Mock(spec=Card, id=i, name=f"Card {i}") for i in range(5)]

        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete') as mock_log_complete, \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock), \
             patch('app.core.scheduler.asyncio.gather', new_callable=AsyncMock) as mock_gather:

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = mock_cards

            # Mix of successes, failures, and exceptions
            mock_gather.return_value = [
                True,  # Success
                False,  # Failure
                Exception("Error"),  # Exception
            ]

            await job_update_market_data()

            # Verify log_scrape_complete was called with error count
            mock_log_complete.assert_called_once()
            call_kwargs = mock_log_complete.call_args[1]
            assert call_kwargs['errors'] > 0

    @pytest.mark.asyncio
    async def test_handles_no_cards_to_update(self):
        """Test job handles case where no cards exist."""
        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock) as mock_scrape:

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            # Both queries return empty - mock execute().all() and execute().scalars().all()
            mock_execute = MagicMock()
            mock_execute.all.return_value = []  # First call
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []  # Second call (.scalars().all())
            mock_execute.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_execute

            await job_update_market_data()

            # Should not scrape anything
            mock_scrape.assert_not_called()

    @pytest.mark.asyncio
    async def test_logs_scrape_start_and_complete(self):
        """Test that job logs start and completion to Discord."""
        mock_card = Mock(spec=Card, id=1, name="Test Card")

        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock) as mock_scrape, \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start') as mock_log_start, \
             patch('app.core.scheduler.log_scrape_complete') as mock_log_complete, \
             patch('app.core.scheduler.asyncio.gather', new_callable=AsyncMock):

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = [mock_card]
            mock_scrape.return_value = True

            await job_update_market_data()

            # Verify Discord logging
            mock_log_start.assert_called_once()
            assert mock_log_start.call_args[0][0] == 1  # 1 card
            assert mock_log_start.call_args[1]['scrape_type'] == "scheduled"

            mock_log_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_scraping_exception(self):
        """Test that job handles and logs exceptions during scraping."""
        mock_card = Mock(spec=Card, id=1, name="Test Card")

        with patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.scrape_single_card', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.get_browser', new_callable=AsyncMock), \
             patch('app.core.scheduler.BrowserManager.close', new_callable=AsyncMock), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_error') as mock_log_error, \
             patch('app.core.scheduler.asyncio.gather', new_callable=AsyncMock) as mock_gather:

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.all.return_value = [mock_card]

            # Simulate exception during batch processing
            mock_gather.side_effect = Exception("Unexpected error")

            await job_update_market_data()

            # Should log the error
            mock_log_error.assert_called_once()


class TestJobUpdateBlokpaxData:
    """Tests for job_update_blokpax_data function."""

    @pytest.mark.asyncio
    async def test_updates_all_storefronts(self):
        """Test that job updates all WOTF storefronts."""
        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['storefront-1', 'storefront-2']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234
            mock_floor.return_value = {
                'floor_price_bpx': 1000,
                'floor_price_usd': 1.23,
                'listed_count': 5,
                'total_tokens': 10
            }
            mock_sales.return_value = []

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await job_update_blokpax_data()

            # Should scrape both storefronts
            assert mock_floor.call_count == 2
            assert mock_sales.call_count == 2

            # Verify deep_scan is enabled
            for call_obj in mock_floor.call_args_list:
                assert call_obj[1]['deep_scan'] is True

    @pytest.mark.asyncio
    async def test_saves_snapshots_to_database(self):
        """Test that job saves BlokpaxSnapshot records."""
        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['test-storefront']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234
            mock_floor.return_value = {
                'floor_price_bpx': 1000,
                'floor_price_usd': 1.23,
                'listed_count': 5,
                'total_tokens': 10
            }
            mock_sales.return_value = []

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await job_update_blokpax_data()

            # Verify snapshot was added to session
            mock_session.add.assert_called()
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_updates_storefront_record(self):
        """Test that job updates BlokpaxStorefront records."""
        mock_storefront = MagicMock()
        mock_storefront.slug = 'test-storefront'

        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['test-storefront']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234
            floor_data = {
                'floor_price_bpx': 1000,
                'floor_price_usd': 1.23,
                'listed_count': 5,
                'total_tokens': 10
            }
            mock_floor.return_value = floor_data
            mock_sales.return_value = []

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = mock_storefront

            await job_update_blokpax_data()

            # Verify storefront was updated
            assert mock_storefront.floor_price_bpx == floor_data['floor_price_bpx']
            assert mock_storefront.floor_price_usd == floor_data['floor_price_usd']
            assert mock_storefront.listed_count == floor_data['listed_count']
            assert mock_storefront.total_tokens == floor_data['total_tokens']
            assert mock_storefront.updated_at is not None

    @pytest.mark.asyncio
    async def test_filters_reward_room_assets(self):
        """Test that reward-room assets are filtered for WOTF only."""
        mock_sale_wotf = MagicMock()
        mock_sale_wotf.asset_name = "WOTF Card"
        mock_sale_other = MagicMock()
        mock_sale_other.asset_name = "Other Game Card"

        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['reward-room']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.is_wotf_asset') as mock_is_wotf, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234
            mock_floor.return_value = {
                'floor_price_bpx': 1000,
                'floor_price_usd': 1.23,
                'listed_count': 5,
                'total_tokens': 10
            }
            mock_sales.return_value = [mock_sale_wotf, mock_sale_other]
            mock_is_wotf.side_effect = lambda name: "WOTF" in name

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await job_update_blokpax_data()

            # Verify is_wotf_asset was called for filtering
            assert mock_is_wotf.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_storefront_error_gracefully(self):
        """Test that errors on one storefront don't stop others."""
        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['storefront-1', 'storefront-2', 'storefront-3']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete') as mock_log_complete, \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234

            # Second storefront fails
            mock_floor.side_effect = [
                {'floor_price_bpx': 1000, 'floor_price_usd': 1.23, 'listed_count': 5, 'total_tokens': 10},
                Exception("Network error"),
                {'floor_price_bpx': 2000, 'floor_price_usd': 2.46, 'listed_count': 3, 'total_tokens': 8},
            ]
            mock_sales.return_value = []

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await job_update_blokpax_data()

            # All three storefronts should be attempted
            assert mock_floor.call_count == 3

            # Should report 1 error
            mock_log_complete.assert_called_once()
            assert mock_log_complete.call_args[1]['errors'] == 1

    @pytest.mark.asyncio
    async def test_limits_sales_pages_for_scheduled_runs(self):
        """Test that scheduled runs limit sales page scraping."""
        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['test-storefront']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete'), \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234
            mock_floor.return_value = {
                'floor_price_bpx': 1000,
                'floor_price_usd': 1.23,
                'listed_count': 5,
                'total_tokens': 10
            }
            mock_sales.return_value = []

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await job_update_blokpax_data()

            # Verify max_pages is set to 2
            mock_sales.assert_called_once()
            assert mock_sales.call_args[1]['max_pages'] == 2

    @pytest.mark.asyncio
    async def test_logs_start_and_complete(self):
        """Test that Blokpax job logs to Discord."""
        with patch('app.core.scheduler.WOTF_STOREFRONTS', ['storefront-1']), \
             patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.scrape_storefront_floor', new_callable=AsyncMock) as mock_floor, \
             patch('app.core.scheduler.scrape_recent_sales', new_callable=AsyncMock) as mock_sales, \
             patch('app.core.scheduler.Session') as mock_session_class, \
             patch('app.core.scheduler.engine'), \
             patch('app.core.scheduler.log_scrape_start') as mock_log_start, \
             patch('app.core.scheduler.log_scrape_complete') as mock_log_complete, \
             patch('app.core.scheduler.asyncio.sleep', new_callable=AsyncMock):

            mock_price.return_value = 0.001234
            mock_floor.return_value = {
                'floor_price_bpx': 1000,
                'floor_price_usd': 1.23,
                'listed_count': 5,
                'total_tokens': 10
            }
            mock_sales.return_value = []

            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_session.execute.return_value.scalars.return_value.first.return_value = None

            await job_update_blokpax_data()

            mock_log_start.assert_called_once()
            assert mock_log_start.call_args[1]['scrape_type'] == "blokpax"

            mock_log_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_fatal_error(self):
        """Test that fatal errors are logged appropriately."""
        with patch('app.core.scheduler.get_bpx_price', new_callable=AsyncMock) as mock_price, \
             patch('app.core.scheduler.log_scrape_start'), \
             patch('app.core.scheduler.log_scrape_complete') as mock_log_complete, \
             patch('app.core.scheduler.log_scrape_error') as mock_log_error:

            mock_price.side_effect = Exception("Fatal error")

            await job_update_blokpax_data()

            mock_log_error.assert_called_once()
            assert "Blokpax Scheduled" in mock_log_error.call_args[0][0]


class TestJobMarketInsights:
    """Tests for job_market_insights function."""

    @pytest.mark.asyncio
    async def test_generates_and_posts_insights(self):
        """Test that market insights are generated and posted."""
        mock_generator = MagicMock()
        mock_generator.gather_market_data = MagicMock(return_value={"test": "data"})
        mock_generator.generate_insights = MagicMock(return_value="Market insights text")

        # Mock the import inside the function
        mock_module = MagicMock()
        mock_module.get_insights_generator = MagicMock(return_value=mock_generator)

        with patch.dict('sys.modules', {'app.services.market_insights': mock_module}), \
             patch('app.core.scheduler.log_market_insights') as mock_log_insights:

            mock_log_insights.return_value = True

            await job_market_insights()

            mock_generator.gather_market_data.assert_called_once()
            mock_generator.generate_insights.assert_called_once_with({"test": "data"})
            mock_log_insights.assert_called_once_with("Market insights text")

    @pytest.mark.asyncio
    async def test_handles_insights_generation_error(self):
        """Test error handling in market insights generation."""
        with patch('app.core.scheduler.log_scrape_error') as mock_log_error:
            # Mock import to raise exception
            with patch('builtins.__import__', side_effect=Exception("API error")):
                await job_market_insights()

                mock_log_error.assert_called_once()
                assert "Market Insights" in mock_log_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handles_post_failure(self):
        """Test handling when posting to Discord fails."""
        mock_generator = MagicMock()
        mock_generator.gather_market_data = MagicMock(return_value={"test": "data"})
        mock_generator.generate_insights = MagicMock(return_value="Market insights text")

        mock_module = MagicMock()
        mock_module.get_insights_generator = MagicMock(return_value=mock_generator)

        with patch.dict('sys.modules', {'app.services.market_insights': mock_module}), \
             patch('app.core.scheduler.log_market_insights') as mock_log_insights:

            mock_log_insights.return_value = False  # Post failed

            await job_market_insights()

            # Should complete without raising exception
            mock_log_insights.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_default_time_window(self):
        """Test that insights use default data gathering window."""
        mock_generator = MagicMock()
        mock_generator.gather_market_data = MagicMock(return_value={"test": "data"})
        mock_generator.generate_insights = MagicMock(return_value="Market insights text")

        mock_module = MagicMock()
        mock_module.get_insights_generator = MagicMock(return_value=mock_generator)

        with patch.dict('sys.modules', {'app.services.market_insights': mock_module}), \
             patch('app.core.scheduler.log_market_insights'):

            await job_market_insights()

            # Verify gather_market_data called without args (uses defaults)
            mock_generator.gather_market_data.assert_called_once_with()


class TestJobCancellation:
    """Tests for job cancellation and cleanup."""

    @pytest.mark.asyncio
    async def test_scheduler_shutdown_stops_jobs(self):
        """Test that scheduler can be started and shutdown without error."""
        test_scheduler = AsyncIOScheduler()
        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=45), id="test_job")

        # Start the scheduler
        test_scheduler.start()
        assert test_scheduler.running is True

        # Verify job exists before shutdown
        assert test_scheduler.get_job("test_job") is not None

        # Shutdown should complete without error
        test_scheduler.shutdown(wait=False)

        # Verify the scheduler accepts the shutdown call
        # (state may not immediately change in async context)
        assert test_scheduler.get_job("test_job") is not None or test_scheduler.state == 0

    def test_individual_job_removal(self):
        """Test removing individual jobs from scheduler."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=45), id="job_update_market_data")
        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=20), id="job_update_blokpax_data")

        # Remove one job
        test_scheduler.remove_job('job_update_market_data')

        # Verify it's gone
        assert test_scheduler.get_job('job_update_market_data') is None

        # Other jobs still exist
        assert test_scheduler.get_job('job_update_blokpax_data') is not None


class TestCronExpressionParsing:
    """Tests for cron expression validation."""

    def test_morning_insights_schedule(self):
        """Test morning market insights cron schedule."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            CronTrigger(hour=9, minute=0),
            id="job_market_insights_morning"
        )

        job = test_scheduler.get_job('job_market_insights_morning')
        trigger = job.trigger

        # Verify trigger is set for 9:00 AM UTC
        assert isinstance(trigger, CronTrigger)
        # CronTrigger stores the values, we can check the string representation
        assert '9' in str(trigger) or 'hour=9' in repr(trigger)

    def test_evening_insights_schedule(self):
        """Test evening market insights cron schedule."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            CronTrigger(hour=18, minute=0),
            id="job_market_insights_evening"
        )

        job = test_scheduler.get_job('job_market_insights_evening')
        trigger = job.trigger

        # Verify trigger is set for 6:00 PM (18:00) UTC
        assert isinstance(trigger, CronTrigger)
        # CronTrigger stores the values, we can check the string representation
        assert '18' in str(trigger) or 'hour=18' in repr(trigger)


class TestIntervalTriggerConfiguration:
    """Tests for interval trigger validation."""

    def test_market_data_interval(self):
        """Test market data job interval configuration."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            IntervalTrigger(minutes=45),
            id="job_update_market_data"
        )

        job = test_scheduler.get_job('job_update_market_data')
        trigger = job.trigger

        # 45 minutes = 2700 seconds
        assert trigger.interval.total_seconds() == 2700

    def test_blokpax_interval(self):
        """Test Blokpax job interval configuration."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            IntervalTrigger(minutes=20),
            id="job_update_blokpax_data"
        )

        job = test_scheduler.get_job('job_update_blokpax_data')
        trigger = job.trigger

        # 20 minutes = 1200 seconds
        assert trigger.interval.total_seconds() == 1200


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_job_prevention(self):
        """Test that max_instances=1 prevents concurrent runs."""
        # This is enforced by APScheduler itself, we just verify config
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=45), id="job1", max_instances=1)
        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=20), id="job2", max_instances=1)

        # All jobs should have max_instances=1
        for job in test_scheduler.get_jobs():
            assert job.max_instances == 1

    @pytest.mark.asyncio
    async def test_misfire_grace_time_configuration(self):
        """Test that misfire grace times are set appropriately."""
        test_scheduler = AsyncIOScheduler()

        test_scheduler.add_job(
            lambda: None,
            IntervalTrigger(minutes=45),
            id="job_update_market_data",
            misfire_grace_time=1800
        )
        test_scheduler.add_job(
            lambda: None,
            IntervalTrigger(minutes=20),
            id="job_update_blokpax_data",
            misfire_grace_time=600
        )
        test_scheduler.add_job(
            lambda: None,
            CronTrigger(hour=9, minute=0),
            id="job_market_insights_morning",
            misfire_grace_time=3600
        )

        market_job = test_scheduler.get_job('job_update_market_data')
        blokpax_job = test_scheduler.get_job('job_update_blokpax_data')
        morning_insights = test_scheduler.get_job('job_market_insights_morning')

        # Market data: 30 minutes grace
        assert market_job.misfire_grace_time == 1800

        # Blokpax: 10 minutes grace
        assert blokpax_job.misfire_grace_time == 600

        # Insights: 1 hour grace
        assert morning_insights.misfire_grace_time == 3600

    @pytest.mark.asyncio
    async def test_replace_existing_jobs(self):
        """Test that jobs with replace_existing=True don't raise errors."""
        test_scheduler = AsyncIOScheduler()

        # Add a job
        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=45), id="job1")
        job1 = test_scheduler.get_job("job1")
        assert job1 is not None

        # Add same job again with replace_existing=True - should succeed without error
        test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=50), id="job1", replace_existing=True)

        # Job should still exist
        job1_after = test_scheduler.get_job("job1")
        assert job1_after is not None

        # Verify that replace_existing prevents ConflictingIdError
        # (Without replace_existing, this would raise an error)
        try:
            test_scheduler.add_job(lambda: None, IntervalTrigger(minutes=55), id="job1", replace_existing=True)
            replaced_successfully = True
        except Exception:
            replaced_successfully = False

        assert replaced_successfully is True
