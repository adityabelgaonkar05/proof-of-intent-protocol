"""Unit tests for proof_of_intent helper functions. No network, no env vars required."""
import time

import pytest

from proof_of_intent import (
    usdc, from_usdc,
    weth, from_weth,
    token, from_token,
    in_minutes, in_hours,
)


class TestUsdc:
    def test_integer(self):
        assert usdc(500) == 500_000_000

    def test_fractional(self):
        assert usdc(0.5) == 500_000

    def test_small(self):
        assert usdc(1) == 1_000_000

    def test_zero(self):
        assert usdc(0) == 0

    def test_round_trip(self):
        assert from_usdc(usdc(123.45)) == pytest.approx(123.45, rel=1e-5)


class TestWeth:
    def test_one(self):
        assert weth(1) == 1_000_000_000_000_000_000

    def test_decimal(self):
        assert weth(0.15) == 150_000_000_000_000_000

    def test_zero(self):
        assert weth(0) == 0

    def test_round_trip(self):
        assert from_weth(weth(0.25)) == pytest.approx(0.25, rel=1e-9)


class TestToken:
    def test_six_decimals(self):
        assert token(100, 6) == 100_000_000

    def test_eighteen_decimals(self):
        assert token(1, 18) == 1_000_000_000_000_000_000

    def test_round_trip(self):
        assert from_token(token(50, 8), 8) == pytest.approx(50.0)


class TestDeadlines:
    def test_in_minutes_is_future(self):
        now = int(time.time())
        ts = in_minutes(10)
        assert ts > now
        assert ts <= now + 10 * 60 + 2

    def test_in_hours_is_future(self):
        now = int(time.time())
        ts = in_hours(1)
        assert ts > now
        assert ts <= now + 3600 + 2

    def test_in_hours_matches_in_minutes(self):
        assert abs(in_hours(1) - in_minutes(60)) <= 1

    def test_in_hours_two(self):
        assert abs(in_hours(2) - in_minutes(120)) <= 1
