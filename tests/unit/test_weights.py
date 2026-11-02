"""Unit tests for the poll weighting functions."""

from __future__ import annotations

import math

import pytest

from election_intelligence.aggregation.weights import (
    DEFAULT_QUALITY,
    MAX_EFFECTIVE_N,
    quality_weight,
    recency_weight,
    sample_size_weight,
)


@pytest.mark.unit
def test_sample_size_weight_is_sqrt() -> None:
    assert sample_size_weight(900) == pytest.approx(30.0)


@pytest.mark.unit
def test_sample_size_weight_is_capped() -> None:
    capped = sample_size_weight(1_000_000)
    assert capped == pytest.approx(math.sqrt(MAX_EFFECTIVE_N))


@pytest.mark.unit
def test_sample_size_weight_defaults_when_missing() -> None:
    assert sample_size_weight(None) == sample_size_weight(0) > 0


@pytest.mark.unit
def test_recency_weight_halves_each_half_life() -> None:
    assert recency_weight(0, half_life_days=14) == pytest.approx(1.0)
    assert recency_weight(14, half_life_days=14) == pytest.approx(0.5)
    assert recency_weight(28, half_life_days=14) == pytest.approx(0.25)


@pytest.mark.unit
def test_recency_weight_clamps_negative_age() -> None:
    assert recency_weight(-5, half_life_days=14) == pytest.approx(1.0)


@pytest.mark.unit
def test_quality_weight_mapping_and_default() -> None:
    assert quality_weight("A+") == pytest.approx(1.0)
    assert quality_weight("B+") == pytest.approx(0.8)
    assert quality_weight(None) == pytest.approx(DEFAULT_QUALITY)
    assert quality_weight("not-a-grade") == pytest.approx(DEFAULT_QUALITY)
