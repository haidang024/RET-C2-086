"""Unit tests for ReorderCalcNode."""

from __future__ import annotations

from framework.schemas.agent_status import AgentStatus

from src.nodes.reorder_calc_node import ReorderCalcNode


def test_reorder_calc_applies_pack_and_moq_rounding() -> None:
    node = ReorderCalcNode(config={})
    state = {
        "adjusted_forecast": {
            "items": [
                {
                    "store_id": "S1",
                    "sku_id": "SKU1",
                    "adjusted_forecast_qty": 12.0,
                    "confidence": 0.7,
                }
            ]
        },
        "inventory_snapshot": {"S1:SKU1": 5.0},
        "supplier_constraints": {"lead_time_days": 2, "safety_days": 1, "moq": 10, "pack_size": 5},
    }
    result = node.execute(state)
    assert result["status"] == AgentStatus.SUCCESS.value
    item = result["replenishment_quantities"]["items"][0]
    assert item["recommended_qty"] % 5 == 0
    assert item["recommended_qty"] >= 10
