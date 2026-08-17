"""
Calculation errors — SBGC-65.

A ``CalculationInvariantError`` marks a mathematical invariant failure
(section 106 / Part G.10).  It is a calculation defect, never a signal to
invent repair logic.
"""

from __future__ import annotations


class CalculationInvariantError(Exception):
    """Raised when a frozen mathematical invariant is violated."""


__all__ = ["CalculationInvariantError"]
