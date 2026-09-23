"""State schema for RET-C2-086 demand forecasting and replenishment."""

from __future__ import annotations

from typing import Any, Optional

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Flat, JSON-serializable state for the Cat 2 workflow."""

    validated_input: str

    pos_records: list[Any]
    inventory_snapshot: dict[str, Any]
    sku_master: dict[str, Any]
    supplier_constraints: dict[str, Any]
    adjustment_signals: dict[str, Any]

    normalized_dataset: dict[str, Any]
    validation_report: dict[str, Any]
    demand_forecast: dict[str, Any]
    adjusted_forecast: dict[str, Any]
    adjustment_factors: dict[str, Any]
    replenishment_quantities: dict[str, Any]
    reorder_flags: dict[str, Any]
    po_draft: dict[str, Any]
    exception_report: str

    # Declarative planner-review payload; framework HITL is disabled because no
    # node calls interrupt().
    hitl_draft: Optional[dict[str, Any]]
    hitl_feedback: Optional[str]

    formatted_output: str
    result: str
    error_message: Optional[str]
    input_error_message: str | None
    input_error_guidance: list[str]
    generation_mode: str | None
    provider_error_message: str | None
