"""End-to-end outer graph integration coverage."""

from __future__ import annotations

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph


def test_pipeline_end_to_end_generates_po_draft() -> None:
    graph = Graph(
        config={
            "forecast_horizon_days": 7,
            "max_input_length": 10000,
            "low_confidence_threshold": 0.55,
            "planner_review_draft_enabled": True,
            "lead_time_days_default": 2,
            "safety_days_default": 1,
            "moq_default": 10,
            "pack_size_default": 5,
            "llm": None,
        }
    )
    payload = {
        "pos_records": [
            {"store_id": "S1", "sku_id": "SKU1", "date": "2026-07-01", "qty": 10},
            {"store_id": "S1", "sku_id": "SKU1", "date": "2026-07-02", "qty": 11},
            {"store_id": "S1", "sku_id": "SKU1", "date": "2026-07-03", "qty": 9},
        ],
        "inventory_snapshot": {"S1:SKU1": 5},
        "sku_master": {"SKU1": {"category": "snack"}},
        "supplier_constraints": {
            "lead_time_days": 2,
            "safety_days": 1,
            "moq": 10,
            "pack_size": 5,
        },
        "adjustment_signals": {
            "weather_factor": 1.0,
            "holiday_factor": 1.0,
            "promotion_factor": 1.1,
        },
    }
    raw = json.dumps(payload)
    ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)
    result = graph.invoke(raw, ctx=ctx, input_context={"raw": raw})

    assert result.get("status") == AgentStatus.SUCCESS.value
    assert result["po_draft"]["lines"]
    assert result["output"]
