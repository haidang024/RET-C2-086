"""RET-C2-086 outer graph (Cat 2 nested architecture)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.utils.config_loader import load_config

from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import State


class DemandReplenishmentGraphNode(GraphNode):
    """GraphNode wrapper for the inner replenishment workflow."""

    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        llm: Any = None,
        **kwargs: Any,
    ) -> None:
        self._config = config or {}
        self._llm = llm if llm is not None else self._config.get("llm")
        super().__init__(**kwargs)

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import DomainWorkflowGraph

        return DomainWorkflowGraph(config=self._parent_config())

    def extract_input(self, state: AgentState) -> str:
        del state
        # Structured retail data travels through input_context so framework PII
        # masking of user_input cannot corrupt dates or the JSON envelope.
        return "Generate the retail demand forecast and replenishment draft."

    @staticmethod
    def _domain_context(state: AgentState) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        validated = state.get("validated_input", "")
        if isinstance(validated, str) and validated:
            try:
                parsed = json.loads(validated)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                payload = parsed
        return {
            "pos_records": state.get("pos_records", payload.get("pos_records", [])),
            "inventory_snapshot": state.get("inventory_snapshot", payload.get("inventory_snapshot", {})),
            "sku_master": state.get("sku_master", payload.get("sku_master", {})),
            "supplier_constraints": state.get("supplier_constraints", payload.get("supplier_constraints", {})),
            "adjustment_signals": state.get("adjustment_signals", payload.get("adjustment_signals", {})),
        }

    def execute(self, state: AgentState) -> dict[str, Any]:
        """Delegate without placing the structured domain envelope in user_input."""
        if state.get("input_error_message"):
            return {"status": AgentStatus.SUCCESS.value}
        ctx = replace(InvocationContext.from_state(state), hitl_allowed=False)
        subgraph = self.get_subgraph()
        try:
            sub_result = subgraph.invoke(
                self.extract_input(state),
                session_id=ctx.session_id,
                ctx=ctx,
                input_context={"domain": self._domain_context(state)},
            )
        except Exception as exc:
            return cast(dict[str, Any], self._handle_call_error(subgraph, exc, state))
        return self.merge_output(state, sub_result)

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        del state
        keys = (
            "normalized_dataset",
            "validation_report",
            "demand_forecast",
            "adjusted_forecast",
            "adjustment_factors",
            "replenishment_quantities",
            "reorder_flags",
            "po_draft",
            "exception_report",
            "hitl_draft",
            "status",
        )
        return {key: sub_result.get(key) for key in keys if key in sub_result}

    def _parent_config(self) -> dict[str, Any]:
        """Pass all runtime parameters and the in-memory LLM to the inner graph."""
        return {**self._config, "llm": self._llm}


class Graph(AgentBaseGraph):
    """RetailDemandForecastingReplenishmentAgent outer graph."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    # Harness J2/J4: the Marketplace runner constructs the agent with a bare
    # ``agent_cls()`` on agentcore 1.0.1 and ``agent_cls(config=...)`` on 1.0.3,
    # and it never reads ``config/config.yaml``. A template whose graph requires
    # a config key therefore fails at compile time on the container path, before
    # any node runs. Loading the file here makes both runner generations work;
    # ``**kwargs`` absorbs arguments added by later runner versions.
    def __init__(self, config: dict[str, Any] | None = None, **kwargs: Any) -> None:
        # Load config/config.yaml first, then overlay whatever the runner passed.
        # agentcore 1.0.1 calls agent_cls() (config=None) but 1.0.3 calls
        # agent_cls(config={...}) — often an EMPTY dict. Keying off `is None`
        # alone therefore skipped the file load on 1.0.3 and left required keys
        # missing, which surfaced as a bare
        # "Graph invocation did not succeed: status='error'".
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
        file_config = load_config(str(config_path)) if config_path.exists() else {}
        config = {**file_config, **dict(config or {})}
        super().__init__(config=dict(config), **kwargs)

    @property
    def name(self) -> str:
        return "RetailDemandForecastingReplenishmentAgent"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()
        self._nodes["pre_process"] = PreProcessNode(config=self.config)
        self._nodes["main"] = DemandReplenishmentGraphNode(
            config=self.config,
            llm=self.config.get("llm"),
        )
        self._nodes["post_process"] = PostProcessNode(config=self.config)

    def get_output(self, state: AgentState) -> dict[str, Any]:
        """Expose the framework envelope and structured replenishment result."""
        output = {
            "output": state.get("formatted_output") or state.get("result"),
            "po_draft": state.get("po_draft", {}),
            "exception_report": state.get("exception_report", ""),
            "replenishment_quantities": state.get("replenishment_quantities", {}),
            "hitl_draft": state.get("hitl_draft"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
            "generation_mode": state.get("generation_mode"),
            "provider_error_message": state.get("provider_error_message"),
        }
        context = state.get("input_context")
        is_marketplace = isinstance(context, dict) and "conversation_history" in context
        if not is_marketplace:
            return output
        if _set_marketplace_guidance(output, state, "Demand replenishment request"):
            return output
        payload = self._parse_payload(output.get("output", output.get("formatted_output")))
        if payload is not None:
            output["output"] = self._render_marketplace_draft(payload)
        return output

    @staticmethod
    def _parse_payload(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _render_marketplace_draft(payload: dict[str, Any]) -> str:
        po_draft = payload.get("po_draft")
        po_draft = po_draft if isinstance(po_draft, dict) else {}
        lines = [
            "# Demand Replenishment Draft",
            "",
            f"**Status:** {po_draft.get('status', 'Draft — planner review required')}",
        ]
        for key in ("po_number", "supplier_id", "supplier_name"):
            if po_draft.get(key):
                lines.append(f"**{key.replace('_', ' ').title()}:** {po_draft[key]}")

        po_lines = po_draft.get("lines")
        if isinstance(po_lines, list) and po_lines:
            lines.extend(["", "## Purchase-order lines", ""])
            for item in po_lines:
                if not isinstance(item, dict):
                    continue
                sku = item.get("sku_id", item.get("sku", "Unknown SKU"))
                quantity = item.get("quantity", item.get("recommended_qty", "unknown"))
                store = f" for store {item['store_id']}" if item.get("store_id") else ""
                lines.append(f"- {sku}: {quantity} unit(s){store}")

        replenishments = payload.get("replenishment_quantities")
        if isinstance(replenishments, dict):
            items = replenishments.get("items")
            if isinstance(items, list) and items:
                lines.extend(["", "## Replenishment recommendations", ""])
                for item in items:
                    if isinstance(item, dict):
                        sku = item.get("sku_id", item.get("sku", "Unknown SKU"))
                        quantity = item.get("recommended_qty", item.get("quantity", "unknown"))
                        lines.append(f"- {sku}: {quantity} unit(s)")
            elif replenishments:
                lines.extend(["", "## Replenishment quantities", ""])
                lines.extend(f"- {sku}: {quantity}" for sku, quantity in replenishments.items())

        exception_report = payload.get("exception_report")
        if exception_report:
            lines.extend(["", "## Exceptions", "", str(exception_report)])
        lines.extend(["", "> This is a draft. A planner must review it before a purchase order is issued."])
        return "\n".join(lines)


def _set_marketplace_guidance(output: dict[str, Any], state: AgentState, subject: str) -> bool:
    context = state.get("input_context")
    message = state.get("input_error_message")
    if not (isinstance(context, dict) and "conversation_history" in context and message):
        return False
    lines = [f"{subject} could not be processed.", "", f"Reason: {message}"]
    guidance = state.get("input_error_guidance")
    if isinstance(guidance, list) and guidance:
        lines.extend(["", "How to continue:"])
        lines.extend(f"- {item}" for item in guidance)
    output["output"] = "\n".join(lines)
    return True
