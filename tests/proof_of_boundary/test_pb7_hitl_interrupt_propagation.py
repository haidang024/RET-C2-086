"""PB-7: HITL interrupt propagation (conditional for RET-C2-086)."""

from __future__ import annotations

import pathlib
import warnings

import pytest


_CONFIG_PATH = pathlib.Path(__file__).parents[2] / "config" / "config.yaml"


def _hitl_enabled() -> bool:
    if not _CONFIG_PATH.exists():
        warnings.warn(
            f"{_CONFIG_PATH} not found — PB-7 skipped without verifying hitl.enabled.",
            stacklevel=2,
        )
        return False
    try:
        import yaml

        data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.warn(
            f"{_CONFIG_PATH} could not be read as YAML ({exc}) — PB-7 skipped without verifying hitl.enabled.",
            stacklevel=2,
        )
        return False
    hitl = (data or {}).get("hitl", {}) if isinstance(data, dict) else None
    if not isinstance(hitl, dict):
        warnings.warn(
            f"{_CONFIG_PATH} does not have the expected 'hitl:' mapping shape.",
            stacklevel=2,
        )
        return False
    return bool(hitl.get("enabled", False))


pytestmark = pytest.mark.skipif(
    not _hitl_enabled(),
    reason="config/config.yaml does not set hitl.enabled: true — PB-7 not applicable",
)


def test_pb7_hitl_interrupt_propagates() -> None:
    pytest.skip("Implement against the node that calls interrupt() if framework HITL is enabled.")


def test_pb7_hitl_allowed_false_skips_interrupt() -> None:
    pytest.skip("Implement the hitl_allowed=False assertion if framework HITL is enabled.")
