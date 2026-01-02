"""Deprecated compatibility module.

The repository standardizes on Superset for BI automation.

This module remains only to avoid breaking older imports; it intentionally
exports the Superset router.
"""

from __future__ import annotations

from app.api.superset import router
