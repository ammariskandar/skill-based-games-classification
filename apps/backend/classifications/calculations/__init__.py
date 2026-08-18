"""
Derived-classification calculation engine — SBGC-65.

Pure, deterministic implementations of the statistical methods governed by
``docs/statistical_model.md``.  Modules are import-order independent; the
package imports no Django models and performs no persistence.
"""

from __future__ import annotations

from classifications.calculations.constants import MASTER_VERSION

__all__ = ["MASTER_VERSION"]
