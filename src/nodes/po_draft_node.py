"""PODraftNode for RET-C2-086 PO draft and exception report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class PODraftNode(FunctionNode):
    """Step 5: build PO draft and markdown exception report."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3: block supplier secret leakage in generated output."""
        out_text = str(result)
        for marker in ["supplier_api_key", "erp_token", "password", "secret"]:
            if marker in out_text.lower():
                raise SecurityViolationError(f"Sensitive marker detected in output: {marker}")
        return result

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        replenishments = state.get("replenishment_quantities", {}).get("items", [])
        flags = state.get("reorder_flags", {}).get("items", [])
        adjusted_items = state.get("adjusted_forecast", {}).get("items", [])

        lines: list[dict[str, Any]] = []
        low_confidence: list[dict[str, Any]] = []
        threshold = float(self._config.get("low_confidence_threshold", 0.55))

        for item in replenishments:
            qty = int(item.get("recommended_qty", 0))
            if qty > 0:
                lines.append(
                    {
                        "store_id": item.get("store_id"),
                        "sku_id": item.get("sku_id"),
                        "quantity": qty,
                        "uom": "EA",
                    }
                )

        for item in adjusted_items:
            if float(item.get("confidence", 1.0)) < threshold:
                low_confidence.append(
                    {
                        "store_id": item.get("store_id"),
                        "sku_id": item.get("sku_id"),
                        "confidence": item.get("confidence"),
                    }
                )

        po_draft = {
            "po_id": f"PO-DRAFT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "DRAFT",
            "lines": lines,
        }

        report_lines = [
            "# Exception Report",
            "",
            f"- low_confidence_items: {len(low_confidence)}",
            f"- constraint_flags: {len(flags)}",
            "",
            "## Low Confidence Forecast Items",
        ]
        if low_confidence:
            for item in low_confidence:
                report_lines.append(
                    f"- store={item.get('store_id')} sku={item.get('sku_id')} confidence={item.get('confidence')}"
                )
        else:
            report_lines.append("- none")

        report_lines.append("")
        report_lines.append("## Reorder Constraint Flags")
        if flags:
            for item in flags:
                report_lines.append(
                    f"- store={item.get('store_id')} sku={item.get('sku_id')} "
                    f"stockout_risk={item.get('stockout_risk')} constraint_flag={item.get('constraint_flag')}"
                )
        else:
            report_lines.append("- none")

        exception_report = "\n".join(report_lines)

        result = {
            "po_draft": po_draft,
            "exception_report": exception_report,
            "status": AgentStatus.SUCCESS.value,
        }

        output: dict[str, Any] = dict(result)
        review_draft_enabled = bool(
            self._config.get(
                "planner_review_draft_enabled",
                self._config.get("hitl_enabled", False),
            )
        )
        if review_draft_enabled and low_confidence:
            output["hitl_draft"] = {
                "reason": "low-confidence forecast",
                "review_required": True,
                "items": low_confidence,
            }

        emit_trace_event(
            "PODraftNode_po_draft_generated",
            {
                "po_lines": len(lines),
                "low_confidence_items": len(low_confidence),
                "constraint_flags": len(flags),
            },
            state,
        )
        return output
