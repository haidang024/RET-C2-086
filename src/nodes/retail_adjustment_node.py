"""RetailAdjustmentNode for RET-C2-086 forecast adjustment factors."""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class RetailAdjustmentNode(FunctionNode):
    """Step 3: adjust baseline forecast using retail context signals."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        forecast = state.get("demand_forecast", {})
        signals = state.get("adjustment_signals", {}) if isinstance(state.get("adjustment_signals", {}), dict) else {}

        weather_factor = float(signals.get("weather_factor", 1.0))
        holiday_factor = float(signals.get("holiday_factor", 1.0))
        promotion_factor = float(signals.get("promotion_factor", 1.0))
        local_event_factor = float(signals.get("local_event_factor", 1.0))
        shelf_life_penalty = float(signals.get("shelf_life_penalty", 0.0))

        adjusted_items: list[dict[str, Any]] = []
        factor_map: dict[str, dict[str, Any]] = {}
        for item in forecast.get("items", []):
            base_qty = float(item.get("forecast_qty", 0.0))
            adjusted_multiplier = weather_factor * holiday_factor * promotion_factor * local_event_factor
            adjusted_qty = max(0.0, base_qty * adjusted_multiplier * (1.0 - shelf_life_penalty))

            store_id = str(item.get("store_id", ""))
            sku_id = str(item.get("sku_id", ""))
            key = f"{store_id}:{sku_id}"

            adjusted_items.append(
                {
                    **item,
                    "adjusted_forecast_qty": round(adjusted_qty, 2),
                }
            )
            factor_map[key] = {
                "weather_factor": weather_factor,
                "holiday_factor": holiday_factor,
                "promotion_factor": promotion_factor,
                "local_event_factor": local_event_factor,
                "shelf_life_penalty": shelf_life_penalty,
                "net_multiplier": round(adjusted_multiplier * (1.0 - shelf_life_penalty), 4),
            }

        emit_trace_event(
            "RetailAdjustmentNode_forecast_adjusted",
            {
                "items": len(adjusted_items),
                "weather_factor": weather_factor,
                "promotion_factor": promotion_factor,
            },
            state,
        )
        return {
            "adjusted_forecast": {"items": adjusted_items},
            "adjustment_factors": factor_map,
            "status": AgentStatus.SUCCESS.value,
        }
