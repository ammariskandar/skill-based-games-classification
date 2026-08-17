"""
Compositional geometry — SBGC-65 (B.5 / C.7).

Isometric log-ratio transformation on the fixed orthonormal basis, the
multiplicative zero-replacement rule, and Aitchison distance.
"""

from __future__ import annotations

import math

from classifications.calculations.constants import BHPCM_ZERO_DELTA
from classifications.calculations.profiles import Profile

_SQRT2 = math.sqrt(2.0)
_SQRT6 = math.sqrt(6.0)


def zero_replaced_fractions(profile: Profile) -> tuple[float, float, float]:
    """Unit-sum fractions with multiplicative zero replacement (B.5.3 / C.7.3).

    Zero components are replaced with ``delta = 1e-6`` and the nonzero
    components are rescaled proportionally so the composition sums to one.
    """
    fractions = (
        profile.micro / 100.0,
        profile.macro / 100.0,
        profile.mystiko / 100.0,
    )
    zero_indices = [j for j, value in enumerate(fractions) if value == 0.0]
    if not zero_indices:
        return fractions

    nonzero_sum = sum(
        value for j, value in enumerate(fractions) if j not in zero_indices
    )
    adjusted = []
    for j, value in enumerate(fractions):
        if j in zero_indices:
            adjusted.append(BHPCM_ZERO_DELTA)
        else:
            adjusted.append(
                value * (1.0 - len(zero_indices) * BHPCM_ZERO_DELTA) / nonzero_sum
            )
    return (adjusted[0], adjusted[1], adjusted[2])


def ilr(profile: Profile) -> tuple[float, float]:
    """Isometric log-ratio coordinates of a percent-unit profile (B.5.4)."""
    mu, macro, mystiko = zero_replaced_fractions(profile)
    z1 = (1.0 / _SQRT2) * math.log(mu / macro)
    z2 = (1.0 / _SQRT6) * math.log((mu * macro) / (mystiko * mystiko))
    return (z1, z2)


def ilr_inv(z: tuple[float, float]) -> Profile:
    """Inverse ilr transform, producing positive components summing to 100."""
    z1, z2 = z
    ell1 = z1 / _SQRT2 + z2 / _SQRT6
    ell2 = -z1 / _SQRT2 + z2 / _SQRT6
    ell3 = -2.0 * z2 / _SQRT6
    q = (math.exp(ell1), math.exp(ell2), math.exp(ell3))
    total = sum(q)
    return Profile(
        micro=100.0 * q[0] / total,
        macro=100.0 * q[1] / total,
        mystiko=100.0 * q[2] / total,
    )


def aitchison_distance(a: Profile, b: Profile) -> float:
    """Aitchison distance between two compositions (B.5.6)."""
    az = ilr(a)
    bz = ilr(b)
    return math.hypot(az[0] - bz[0], az[1] - bz[1])


def joint_ilr(challenge: Profile, reward: Profile) -> tuple[float, float, float, float]:
    """Four-dimensional joint Challenge/Reward representation (B.6 / C.8)."""
    cz = ilr(challenge)
    rz = ilr(reward)
    return (cz[0], cz[1], rz[0], rz[1])


__all__ = [
    "aitchison_distance",
    "ilr",
    "ilr_inv",
    "joint_ilr",
    "zero_replaced_fractions",
]
