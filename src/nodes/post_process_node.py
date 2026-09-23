"""PostProcessNode for RET-C2-086 output formatting and safety checks."""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.llm_runtime import provider_metadata


class PostProcessNode(FunctionNode):
    """Finalize PO draft response with S-3 output checks."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3: enforce non-empty output and redact credential-like leak patterns."""
        output = str(result.get("formatted_output", "")) if isinstance(result, dict) else str(result)
        if not output.strip():
            raise SecurityViolationError("Output is empty - blocked by S-3 gate")
        if re.search(r"\b(api[_-]?key|password|token|secret)\b", output, flags=re.IGNORECASE):
            raise SecurityViolationError("Credential-like content detected in output")
        return result

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("input_error_message"):
            message = str(state["input_error_message"])
            return {
                "formatted_output": message,
                "result": message,
                "status": AgentStatus.SUCCESS.value,
                "input_error_message": message,
            }
        po_draft = state.get("po_draft", {})
        exception_report = state.get("exception_report", "")
        replenishments = state.get("replenishment_quantities", {})

        summary = {
            "po_draft": po_draft,
            "exception_report": exception_report,
            "replenishment_quantities": replenishments,
        }
        formatted_output = json.dumps(summary, ensure_ascii=False, indent=2)
        result = {
            "formatted_output": formatted_output,
            "result": formatted_output,
            "status": state.get("status", AgentStatus.SUCCESS.value),
            **provider_metadata(state),
        }
        emit_trace_event(
            "PostProcessNode_execute_complete",
            {
                "po_lines": len(po_draft.get("lines", [])) if isinstance(po_draft, dict) else 0,
                "exception_chars": len(exception_report),
            },
            state,
        )
        return result
