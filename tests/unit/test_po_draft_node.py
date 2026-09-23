"""Unit tests for PODraftNode."""

from __future__ import annotations

from framework.schemas.agent_status import AgentStatus

from src.nodes.po_draft_node import PODraftNode


def test_po_draft_generates_exception_report_for_low_confidence() -> None:
    node = PODraftNode(
        config={
            "low_confidence_threshold": 0.6,
            "planner_review_draft_enabled": True,
        }
    )
    state = {
        "replenishment_quantities": {
            "items": [
                {
                    "store_id": "S1",
                    "sku_id": "SKU1",
                    "recommended_qty": 15,
                    "confidence": 0.52,
                }
            ]
        },
        "reorder_flags": {
            "items": [{"store_id": "S1", "sku_id": "SKU1", "stockout_risk": True, "constraint_flag": False}]
        },
        "adjusted_forecast": {"items": [{"store_id": "S1", "sku_id": "SKU1", "confidence": 0.52}]},
    }
    result = node.execute(state)
    assert result["status"] == AgentStatus.SUCCESS.value
    assert len(result["po_draft"]["lines"]) == 1
    assert "Low Confidence Forecast Items" in result["exception_report"]
    assert "hitl_draft" in result
