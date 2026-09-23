"""Unit tests for RetailAdjustmentNode."""

from __future__ import annotations

from framework.schemas.agent_status import AgentStatus

from src.nodes.retail_adjustment_node import RetailAdjustmentNode


def test_adjustment_applies_factors() -> None:
    node = RetailAdjustmentNode(config={})
    state = {
        "demand_forecast": {"items": [{"store_id": "S1", "sku_id": "SKU1", "forecast_qty": 10.0, "confidence": 0.8}]},
        "adjustment_signals": {
            "weather_factor": 1.1,
            "holiday_factor": 1.0,
            "promotion_factor": 1.2,
            "local_event_factor": 1.0,
            "shelf_life_penalty": 0.1,
        },
    }
    result = node.execute(state)
    assert result["status"] == AgentStatus.SUCCESS.value
    qty = result["adjusted_forecast"]["items"][0]["adjusted_forecast_qty"]
    assert qty > 10.0
    assert "S1:SKU1" in result["adjustment_factors"]
