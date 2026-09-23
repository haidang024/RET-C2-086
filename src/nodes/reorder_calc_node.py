"""ReorderCalcNode for RET-C2-086 replenishment quantity calculation."""

from __future__ import annotations

from math import ceil
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class ReorderCalcNode(FunctionNode):
    """Step 4: compute reorder quantities with supplier constraints."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        adjusted = state.get("adjusted_forecast", {})
        inventory = state.get("inventory_snapshot", {}) if isinstance(state.get("inventory_snapshot", {}), dict) else {}
        supplier = (
            state.get("supplier_constraints", {}) if isinstance(state.get("supplier_constraints", {}), dict) else {}
        )

        lead_time_days = float(supplier.get("lead_time_days", self._config.get("lead_time_days_default", 2.0)))
        safety_days = float(supplier.get("safety_days", self._config.get("safety_days_default", 1.0)))
        moq = int(supplier.get("moq", 0))
        pack_size = max(1, int(supplier.get("pack_size", 1)))

        recommendations: list[dict[str, Any]] = []
        flags: list[dict[str, Any]] = []

        for item in adjusted.get("items", []):
            store_id = str(item.get("store_id", ""))
            sku_id = str(item.get("sku_id", ""))
            key = f"{store_id}:{sku_id}"

            adjusted_daily = float(item.get("adjusted_forecast_qty", 0.0))
            reorder_point = adjusted_daily * (lead_time_days + safety_days)
            current_stock = float(inventory.get(key, inventory.get(sku_id, 0.0)))

            required_qty = max(0.0, reorder_point - current_stock)
            rounded_qty = int(ceil(required_qty / pack_size) * pack_size) if required_qty > 0 else 0
            if moq > 0 and 0 < rounded_qty < moq:
                rounded_qty = moq

            stockout_risk = current_stock < adjusted_daily * lead_time_days
            constrained = required_qty > 0 and rounded_qty == 0

            recommendations.append(
                {
                    "store_id": store_id,
                    "sku_id": sku_id,
                    "current_stock": round(current_stock, 2),
                    "reorder_point": round(reorder_point, 2),
                    "recommended_qty": rounded_qty,
                    "pack_size": pack_size,
                    "moq": moq,
                    "confidence": item.get("confidence", 0.5),
                }
            )

            if stockout_risk or constrained:
                flags.append(
                    {
                        "store_id": store_id,
                        "sku_id": sku_id,
                        "stockout_risk": stockout_risk,
                        "constraint_flag": constrained,
                    }
                )

        emit_trace_event(
            "ReorderCalcNode_reorder_calculated",
            {
                "items": len(recommendations),
                "flags": len(flags),
            },
            state,
        )
        return {
            "replenishment_quantities": {"items": recommendations},
            "reorder_flags": {"items": flags},
            "status": AgentStatus.SUCCESS.value,
        }
