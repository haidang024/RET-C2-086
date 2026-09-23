"""PreProcessNode for RET-C2-086 input validation and sanitization."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

_INPUT_GUIDANCE = [
    "Send a JSON object with pos_records, inventory_snapshot, sku_master, supplier_constraints, and adjustment_signals.",
    "pos_records should contain dated store/SKU sales rows.",
    "Use JSON objects for inventory, SKU, supplier, and adjustment data.",
]


def _input_error(message: str) -> dict[str, Any]:
    return {
        "status": AgentStatus.SUCCESS.value,
        "validated_input": "",
        "input_error_message": message,
        "input_error_guidance": _INPUT_GUIDANCE,
        "error_message": None,
    }


class PreProcessNode(FunctionNode):
    """Validate replenishment payload and enforce S-2 input checks."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2: reject oversized payloads, path traversal hints, and obvious PII fields."""
        user_input = (state.get("input_context") or {}).get("raw", state.get("user_input", ""))
        if isinstance(user_input, dict):
            raw = json.dumps(user_input, ensure_ascii=False)
            payload = user_input
        else:
            raw = str(user_input)
            payload = {}

        max_input_length = int(self._config.get("max_input_length", 10000))
        if len(raw) > max_input_length:
            raise SecurityViolationError(f"Input exceeds max_input_length={max_input_length}")

        lowered = raw.lower()
        for blocked in ["<script", "javascript:", "../", "..\\"]:
            if blocked in lowered:
                raise SecurityViolationError(f"Injection pattern detected: {blocked}")

        # Domain-specific PII check for sales feeds.
        suspicious = ["email", "phone", "customer_name", "address"]
        for key in suspicious:
            if key in lowered:
                raise SecurityViolationError(f"PII-like field detected in payload: {key}")

        if isinstance(payload, dict) and payload.get("credentials"):
            raise SecurityViolationError("Credentials must not be passed in state payload")
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = (state.get("input_context") or {}).get("raw", state.get("user_input", {}))
        if isinstance(user_input, str):
            text = user_input.strip()
            if not text:
                emit_trace_event(
                    "PreProcessNode_execute_rejected",
                    {"reason": "empty_input"},
                    state,
                )
                return _input_error("Please provide the replenishment input as a JSON object.")
            try:
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    payload = {}
            except json.JSONDecodeError:
                payload = {}
        elif isinstance(user_input, dict):
            payload = user_input
        else:
            payload = {}

        required_keys = [
            "pos_records",
            "inventory_snapshot",
            "sku_master",
            "supplier_constraints",
            "adjustment_signals",
        ]
        missing = [key for key in required_keys if key not in payload]
        if missing:
            emit_trace_event(
                "PreProcessNode_execute_rejected",
                {"missing_keys": missing},
                state,
            )
            return _input_error(f"Missing required fields: {', '.join(missing)}.")

        validated_input = json.dumps(payload, ensure_ascii=False)
        emit_trace_event(
            "PreProcessNode_execute_complete",
            {
                "payload_size": len(validated_input),
                "pos_records": len(payload.get("pos_records", [])),
            },
            state,
        )
        return {
            "validated_input": validated_input,
            "pos_records": payload.get("pos_records", []),
            "inventory_snapshot": payload.get("inventory_snapshot", {}),
            "sku_master": payload.get("sku_master", {}),
            "supplier_constraints": payload.get("supplier_constraints", {}),
            "adjustment_signals": payload.get("adjustment_signals", {}),
            "status": AgentStatus.SUCCESS.value,
            "error_message": None,
        }
