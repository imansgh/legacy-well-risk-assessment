"""Integrity engine: scores the five barrier components and aggregates them."""

from lwra.integrity_engine.aggregator import assess_integrity, assess_integrity_traced
from lwra.integrity_engine.barrier_eval import (
    has_verified_secondary_barrier,
    primary_is_failed_or_unverified,
)

__all__ = [
    "assess_integrity",
    "assess_integrity_traced",
    "has_verified_secondary_barrier",
    "primary_is_failed_or_unverified",
]
