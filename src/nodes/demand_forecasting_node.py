"""DemandForecastingNode for RET-C2-086 baseline demand prediction."""

from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.llm_runtime import complete_text


class DemandForecastingNode(FunctionNode):
    """Step 2: forecast demand with simple confidence bounds per store/SKU."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None, llm: Any = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}
        self._llm = llm if llm is not None else self._config.get("llm")

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # S-2: no domain extension needed — normalized_dataset is gated upstream in DataIngestionNode.
        dataset = state.get("normalized_dataset", {})
        rows = dataset.get("rows", []) if isinstance(dataset, dict) else []

        buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row in rows:
            key = (str(row.get("store_id", "")), str(row.get("sku_id", "")))
            buckets[key].append(float(row.get("qty", 0.0)))

        forecast_items: list[dict[str, Any]] = []
        for (store_id, sku_id), history in buckets.items():
            n = max(len(history), 1)
            mean = sum(history) / n
            variance = sum((x - mean) ** 2 for x in history) / n
            stddev = sqrt(max(variance, 0.0))
            ci = 1.96 * (stddev / sqrt(n)) if n > 1 else mean * 0.2
            confidence_score = min(0.99, max(0.2, 1.0 - (stddev / max(mean, 1.0)) * 0.4))

            forecast_items.append(
                {
                    "store_id": store_id,
                    "sku_id": sku_id,
                    "forecast_qty": round(mean, 2),
                    "lower_ci": round(max(0.0, mean - ci), 2),
                    "upper_ci": round(mean + ci, 2),
                    "confidence": round(confidence_score, 3),
                    "history_points": n,
                }
            )

        demand_forecast = {
            "horizon_days": int(self._config.get("forecast_horizon_days", 7)),
            "items": forecast_items,
        }
        ai_note = self._generate_forecast_note(state, demand_forecast)
        if ai_note:
            demand_forecast["ai_note"] = ai_note

        emit_trace_event(
            "DemandForecastingNode_forecast_executed",
            {"items": len(forecast_items), "llm_used": bool(ai_note)},
            state,
        )
        return {
            "demand_forecast": demand_forecast,
            "status": AgentStatus.SUCCESS.value,
        }

    def _generate_forecast_note(self, state: dict[str, Any], forecast: dict[str, Any]) -> str:
        """Generate optional commentary from aggregate metrics only."""
        items = forecast.get("items", [])
        confidences = [float(item.get("confidence", 0.0)) for item in items]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        messages = [
            {
                "role": "system",
                "content": (
                    "Write one concise Japanese note for a retail replenishment planner. "
                    "Do not change quantities, invent facts, or approve a purchase order."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"forecast_items={len(items)}; "
                    f"horizon_days={int(forecast.get('horizon_days', 0))}; "
                    f"average_confidence={average_confidence:.3f}"
                ),
            },
        ]
        try:
            return complete_text(
                state,
                messages,
                self._llm,
                max_tokens=256,
                timeout_s=float(self._config.get("timeout_s", 30.0)),
                max_retry=int(self._config.get("max_retry", 3)),
            )
        except Exception:
            return ""
