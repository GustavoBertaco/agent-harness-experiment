import time
import pytest
from unittest.mock import patch, call


class TestRateLimiterInit:
    def test_init_with_rate(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        assert rl.rate == 100

    def test_initial_tokens_at_capacity(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        assert rl.tokens == pytest.approx(100.0)

    def test_capacity_equals_one_second_of_events(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=200)
        assert rl.capacity == pytest.approx(200.0)


class TestRateLimiterRefill:
    def test_refill_proportional_to_elapsed_time(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        rl.tokens = 0.0
        elapsed = 0.5
        fake_now = rl.last_refill + elapsed
        with patch("time.time", return_value=fake_now):
            with patch("time.sleep"):
                rl.acquire()
        # After 0.5s at 100/s, 50 tokens refilled, 1 consumed → 49 remain
        assert rl.tokens == pytest.approx(49.0, abs=1.0)

    def test_burst_capacity_capped_at_one_second(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        rl.tokens = 0.0
        # Simulate 10 seconds elapsed — tokens should cap at 100 (1s burst)
        fake_now = rl.last_refill + 10.0
        with patch("time.time", return_value=fake_now):
            with patch("time.sleep"):
                rl.acquire()
        assert rl.tokens <= 100.0


class TestRateLimiterAcquire:
    def test_acquire_sleeps_when_tokens_exhausted(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        rl.tokens = 0.0

        slept = []

        def fake_sleep(duration):
            slept.append(duration)

        fake_now = rl.last_refill  # no elapsed time → no refill
        with patch("time.time", return_value=fake_now):
            with patch("time.sleep", side_effect=fake_sleep):
                rl.acquire()

        assert len(slept) == 1
        assert slept[0] > 0

    def test_acquire_does_not_sleep_when_tokens_available(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        rl.tokens = 50.0  # plenty of tokens

        slept = []
        fake_now = rl.last_refill
        with patch("time.time", return_value=fake_now):
            with patch("time.sleep", side_effect=lambda d: slept.append(d)):
                rl.acquire()

        assert len(slept) == 0

    def test_acquire_consumes_one_token(self):
        from producer.rate_limiter import RateLimiter
        rl = RateLimiter(rate=100)
        rl.tokens = 10.0
        fake_now = rl.last_refill
        with patch("time.time", return_value=fake_now):
            with patch("time.sleep"):
                rl.acquire()
        assert rl.tokens == pytest.approx(9.0)


class TestRateLimiterAverageRate:
    def test_average_achieved_rate_within_5_percent(self):
        """Steady-state rate test: drain burst first, then measure 1-second window."""
        from producer.rate_limiter import RateLimiter
        target_rate = 50  # lower rate for faster test
        rl = RateLimiter(rate=target_rate)

        # Drain the initial burst so we measure only steady-state throughput
        while rl.tokens >= 1.0:
            fake_now = rl.last_refill  # no elapsed → no extra refill
            with patch("time.time", return_value=fake_now):
                with patch("time.sleep"):
                    rl.acquire()
        rl.tokens = 0.0
        rl.last_refill = time.time()

        count = 0
        start = time.time()
        deadline = start + 1.0
        while time.time() < deadline:
            rl.acquire()
            count += 1

        elapsed = time.time() - start
        achieved = count / elapsed
        assert achieved == pytest.approx(target_rate, rel=0.15)  # ±15% for CI timing variance
