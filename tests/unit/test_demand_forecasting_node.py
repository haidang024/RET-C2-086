"""Unit tests for DemandForecastingNode."""

from __future__ import annotations

from framework.schemas.agent_status import AgentStatus

from src.nodes.demand_forecasting_node import DemandForecastingNode


def test_demand_forecast_contains_confidence_intervals() -> None:
    node = DemandForecastingNode(config={"forecast_horizon_days": 7})
    state = {
        "normalized_dataset": {
            "rows": [
                {"store_id": "S1", "sku_id": "SKU1", "qty": 10},
                {"store_id": "S1", "sku_id": "SKU1", "qty": 12},
                {"store_id": "S1", "sku_id": "SKU1", "qty": 8},
            ]
        }
    }
    result = node.execute(state)
    assert result["status"] == AgentStatus.SUCCESS.value
    item = result["demand_forecast"]["items"][0]
    assert "lower_ci" in item and "upper_ci" in item
    assert item["upper_ci"] >= item["lower_ci"]


def test_optional_llm_adds_commentary_without_changing_quantities() -> None:
    class _DummyLlm:
        def complete(self, messages):
            assert "pos_records" not in str(messages)
            return "信頼度を確認して発注案をレビューしてください。"

    state = {
        "normalized_dataset": {
            "rows": [
                {"store_id": "S1", "sku_id": "SKU1", "qty": 10},
                {"store_id": "S1", "sku_id": "SKU1", "qty": 12},
            ]
        }
    }
    deterministic = DemandForecastingNode(config={"forecast_horizon_days": 7}).execute(state)
    enriched = DemandForecastingNode(
        config={"forecast_horizon_days": 7},
        llm=_DummyLlm(),
    ).execute(state)

    assert enriched["demand_forecast"]["ai_note"]
    assert enriched["demand_forecast"]["items"] == deterministic["demand_forecast"]["items"]
