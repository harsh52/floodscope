"""Central configuration for FloodScope.

All tunable constants and environment wiring live here so the agent, baseline,
and eval harness share one source of truth (auditability + reproducibility).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # loads .env if present; no-op otherwise

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEN1FLOODS11_DIR = DATA / "sen1floods11"
NEPAL_DIR = DATA / "nepal"
REPORTS_DIR = ROOT / "reports"
TRAJECTORIES_DIR = ROOT / "trajectories"

# --- Planetary Computer / STAC ----------------------------------------------
STAC_ENDPOINT = "https://planetarycomputer.microsoft.com/api/stac/v1"
S1_COLLECTION = "sentinel-1-grd"  # anonymous, no key required
S1_RTC_COLLECTION = "sentinel-1-rtc"  # better terrain correction, needs free PC key
PC_SUBSCRIPTION_KEY = os.getenv("PC_SDK_SUBSCRIPTION_KEY") or None

# --- LLM ---------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AGENT_MODEL = os.getenv("FLOODSCOPE_AGENT_MODEL", "claude-opus-4-8")
BASELINE_MODEL = os.getenv("FLOODSCOPE_BASELINE_MODEL", "claude-opus-4-8")

# --- SAR flood-mapping constants --------------------------------------------
# Sen1Floods11 label encoding (from the dataset README).
LABEL_NODATA = -1
LABEL_LAND = 0
LABEL_WATER = 1

# Backscatter band used for water detection. VH is preferred for open water.
WATER_BAND = "vh"
# Fallback fixed threshold (dB) used when the histogram is not bimodal.
FALLBACK_DB_THRESHOLD = -18.0
# Slopes steeper than this (degrees) are masked to suppress radar shadow/layover.
MAX_SLOPE_DEG = 5.0
# JRC permanent-water occurrence (%) at/above which a pixel is treated as permanent.
PERMANENT_WATER_OCCURRENCE = 50


def require_anthropic_key() -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ANTHROPIC_API_KEY
