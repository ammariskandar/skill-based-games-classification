"""
Frozen calculation constants — SBGC-65.

Every normative number here is transcribed verbatim from
``docs/statistical_model.md`` (`STATISTICAL_MODEL_V1.0.0`).  Changing any of
them requires a deliberate calculation-version change, never a silent edit.
"""

from __future__ import annotations

import math
from decimal import Decimal

# ---------------------------------------------------------------------------
# Calculation versions
# ---------------------------------------------------------------------------

MASTER_VERSION = "STATISTICAL_MODEL_V1.0.0"
METHODS_VERSION = "METHODS_V2.0.0"
BHPCM_VERSION = "BHPCM_V1"
CONFIDENCE_BASE_VERSION = "CONFIDENCE_BASE_V1"
CONFIDENCE_RESILIENCE_VERSION = "CONFIDENCE_RESILIENCE_V1"
PROVISIONAL_CONFIDENCE_VERSION = "PROVISIONAL_CONFIDENCE_V1"
BOUNDARY_CONTINUITY_VERSION = "BOUNDARY_CONTINUITY_V1"
CONFIDENCE_FINAL_VERSION = "CONFIDENCE_V2"

CALCULATION_VERSIONS = {
    "master": MASTER_VERSION,
    "methods": METHODS_VERSION,
    "bhpcm": BHPCM_VERSION,
    "confidence_base": CONFIDENCE_BASE_VERSION,
    "confidence_resilience": CONFIDENCE_RESILIENCE_VERSION,
    "provisional_confidence": PROVISIONAL_CONFIDENCE_VERSION,
    "boundary_continuity": BOUNDARY_CONTINUITY_VERSION,
    "confidence_final": CONFIDENCE_FINAL_VERSION,
}

# ---------------------------------------------------------------------------
# Component ordering
# ---------------------------------------------------------------------------

# Canonical serialization/display order (section 0.6).
PROFILE_DISPLAY_ORDER = ("micro", "macro", "mystiko")

# Six marginal analysis dimensions (section 2.3): C_mu, C_y, C_a, R_mu, R_y, R_a.
PROFILE_ANALYSIS_ORDER = (
    ("challenge", "micro"),
    ("challenge", "mystiko"),
    ("challenge", "macro"),
    ("reward", "micro"),
    ("reward", "mystiko"),
    ("reward", "macro"),
)

# Human-facing deterministic tie priority (section 0.6 / 11.5).
TIE_PRIORITY = ("micro", "macro", "mystiko")

# ---------------------------------------------------------------------------
# Role hierarchy and fixed base weights (section 6 / B.3.4 / C.5)
# ---------------------------------------------------------------------------

ROLE_SUPERUSER = "superuser"
ROLE_MODERATOR = "moderator"
ROLE_COMMUNITY_LEADER = "community_leader"
ROLE_COMMUNITY = "community"

ROLE_BASE_WEIGHTS: dict[str, Decimal] = {
    ROLE_SUPERUSER: Decimal("1.00"),
    ROLE_MODERATOR: Decimal("0.95"),
    ROLE_COMMUNITY_LEADER: Decimal("0.65"),
    ROLE_COMMUNITY: Decimal("0.20"),
}

AUTHORITATIVE_ROLES = (
    ROLE_COMMUNITY_LEADER,
    ROLE_MODERATOR,
    ROLE_SUPERUSER,
)

# ---------------------------------------------------------------------------
# Method 1 (Part V-XIV)
# ---------------------------------------------------------------------------

METHOD1_MIN_N = 9  # N_1,min — detectors active from N=9
METHOD1_DELTA = 5.0  # practical deviation floor
METHOD1_K_A_LOW = 2.5  # 9 <= N <= 50
METHOD1_K_A_HIGH = 3.0  # N >= 51
METHOD1_K_A_HIGH_THRESHOLD = 51
METHOD1_K_B = 3.5
METHOD1_SN_FACTOR = 1.1926

METHOD1_HIGH_N_ANCHOR = 401  # protected -> evidence-weighted anchor boundary
METHOD1_ANCHOR_W_BOTH = 1.0
METHOD1_ANCHOR_W_ONE = 0.5
METHOD1_ANCHOR_W_NEITHER = 0.1

METHOD1_COMMUNITY_FALLBACK_MIN_N = 50
METHOD1_COMMUNITY_FALLBACK_CAP = Decimal("0.30")
METHOD1_COMMUNITY_FALLBACK_CAP_HIGH = Decimal("0.95")

# ---------------------------------------------------------------------------
# Method 2 — Isolation Forest (Part XV)
# ---------------------------------------------------------------------------

IFOREST_MIN_N = 20
IFOREST_TREES = 512
IFOREST_SUBSAMPLE_MAX = 256
IFOREST_TAU = 0.60
IFOREST_SEED = 42

# ---------------------------------------------------------------------------
# Method 3 — LoOP (Part XVI-XVIII)
# ---------------------------------------------------------------------------

LOOP_MIN_N = 20
LOOP_K = 10
LOOP_LAMBDA = 3.0
LOOP_TAU = 0.75

# ---------------------------------------------------------------------------
# BHPCM_V1 (Part B)
# ---------------------------------------------------------------------------

BHPCM_ZERO_DELTA = 1e-6
BHPCM_BOOTSTRAP_REPLICATES = 10_000
BHPCM_GOVERNANCE_DRAWS = 20
BHPCM_LAMBDA_ALPHA = 10.0
BHPCM_LAMBDA_BETA = 10.0
BHPCM_LAMBDA_MIN = 0.35
BHPCM_LAMBDA_MAX = 0.65
BHPCM_OMEGA_MIN = 0.30
BHPCM_OMEGA_MAX = 0.50
BHPCM_DISAGREEMENT_HALF_LIFE = 0.25
BHPCM_KAPPA_E = 40.0
BHPCM_MAX_INVALID_BOOTSTRAP_RATE = 0.01
BHPCM_MIN_VALID_BOOTSTRAP = 9_000
BHPCM_CI_LEVEL = 0.90

# ---------------------------------------------------------------------------
# CONFIDENCE_BASE_V1 (Part C)
# ---------------------------------------------------------------------------

CONFIDENCE_N_REF = 500.0
CONFIDENCE_ALPHA = 0.60
CONFIDENCE_RHO = 0.25
CONFIDENCE_N_0 = 5.0
CONFIDENCE_GAMMA_D = 0.50
CONFIDENCE_D_0 = 0.25
CONFIDENCE_GAMMA_V = 0.50
CONFIDENCE_V_0 = 0.25
CONFIDENCE_N_V = 3.0

# ---------------------------------------------------------------------------
# CONFIDENCE_RESILIENCE_V1 (Part D1)
# ---------------------------------------------------------------------------

RESILIENCE_MAX = 25.0
RESILIENCE_N_SAT = 401
RESILIENCE_EXPONENT = 3.5
RESILIENCE_APPLY_THRESHOLD = 50.0

# ---------------------------------------------------------------------------
# PROVISIONAL_CONFIDENCE_V1 (Part D2)
# ---------------------------------------------------------------------------

PROVISIONAL_MAX = 49.0
PROVISIONAL_QN_FACTOR = 2.2191
PROVISIONAL_Q_HALF = 0.50
PROVISIONAL_S_MAX = 45.0
PROVISIONAL_S_EXPONENT = 8.0
PROVISIONAL_S_DENOMINATOR = 1.0 - math.exp(-19 / 8)
PROVISIONAL_ROLE_UPLIFT = Decimal("4") / Decimal("45")
PROVISIONAL_H_0 = 3.0

# Frozen finite-sample factors d_N for the Qn-style Aitchison dispersion.
PROVISIONAL_QN_FACTORS: dict[int, float] = {
    2: 0.3995,
    3: 0.9937,
    4: 0.5132,
    5: 0.8440,
    6: 0.6122,
    7: 0.8588,
    8: 0.6699,
    9: 0.8734,
    10: 0.7201,
    11: 0.8891,
    12: 0.7575,
    13: 0.9023,
    14: 0.7855,
    15: 0.9125,
    16: 0.8078,
    17: 0.9210,
    18: 0.8260,
    19: 0.9279,
}

# ---------------------------------------------------------------------------
# BOUNDARY_CONTINUITY_V1 (Part D3)
# ---------------------------------------------------------------------------

BOUNDARY_SUBSET_SIZE = 20
BOUNDARY_MIN_READY_LOO = 10
BOUNDARY_MAX_SUBSETS = 256
BOUNDARY_READY_FRACTION = 0.80
BOUNDARY_DECAY_TAU = 100.0
BOUNDARY_SAMPLER_VERSION = "BOUNDARY_SUBSAMPLE_V1"
BOUNDARY_SEED = 42

# ---------------------------------------------------------------------------
# Numerical tolerances (B.20 / C.16)
# ---------------------------------------------------------------------------

SUM_TOLERANCE = 1e-9
TIE_TOLERANCE = 1e-12
