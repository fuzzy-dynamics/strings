#!/usr/bin/env python3
"""Canonical Witsoc/Lovasz claim-status vocabulary.

Single source of truth for status labels shared across the validators, the
scorer, and the status lattice. Both the coarse labels (``VERIFIED``,
``CHECKED``) used by the JSON schemas and the granular labels
(``VERIFIED_WIT``/``VERIFIED_LEAN``/``VERIFIED_EXTERNAL``,
``CHECKED_BOUNDED``/``CHECKED_SYMBOLIC``) used by the lattice and the lovasz
docs are first-class here. Importing the sets below guarantees a granular label
can never slip past a gate that was written against the coarse set (the bug that
previously let ``VERIFIED_LEAN`` nodes pass the run validators with no evidence).
"""

from __future__ import annotations

from typing import Any

# Statuses that carry no validated result; freely proposable by a research step.
STRUCTURAL_STATUSES = {
    "DRAFT",
    "OPEN",
    "UNVERIFIED",
    "CONJECTURE",
    "FAILED_ATTEMPT",
    "REJECTED",
    "DEMOTED",
    "GAP",
    "PLANNED",
    "SELECTED",
    "READY",
}

# Result-asserting statuses, coarse + granular. Each carries (some level of) a
# validated claim and therefore must be backed by evidence / receipt / skeptic.
VERIFIED_STATUSES = {"VERIFIED", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL"}
CHECKED_STATUSES = {"CHECKED", "CHECKED_BOUNDED", "CHECKED_SYMBOLIC"}
SKETCH_STATUSES = {"PROVED_SKETCH"}
PRODUCT_STATUSES = {"PARTIAL", "CONDITIONAL"}

ACCEPTED_STATUSES = VERIFIED_STATUSES | CHECKED_STATUSES | SKETCH_STATUSES | PRODUCT_STATUSES

# Verified/checked/sketch are the "strong" claims (full or partial proof), as
# opposed to the PARTIAL/CONDITIONAL products which have their own closure gates.
STRONG_STATUSES = VERIFIED_STATUSES | CHECKED_STATUSES | SKETCH_STATUSES

ALL_STATUSES = STRUCTURAL_STATUSES | ACCEPTED_STATUSES

# Coarse -> granular collapse, used only for transition-lattice lookups so that a
# schema-style coarse label can be matched against the granular transition graph.
LEGACY_ALIASES = {"CHECKED": "CHECKED_SYMBOLIC", "VERIFIED": "VERIFIED_LEAN"}


def normalize(status: Any) -> str:
    """Upper-case and strip a status; non-strings become ``""``."""
    return str(status or "").strip().upper()


def alias(status: Any) -> str:
    """Normalize and collapse coarse labels onto their granular equivalents."""
    text = normalize(status)
    return LEGACY_ALIASES.get(text, text)


def is_accepted(status: Any) -> bool:
    """True for any result-asserting status (coarse or granular)."""
    return normalize(status) in ACCEPTED_STATUSES


def is_verified(status: Any) -> bool:
    """True for any VERIFIED* status (coarse or granular)."""
    return normalize(status) in VERIFIED_STATUSES
