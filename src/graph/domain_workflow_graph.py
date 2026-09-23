"""Inner DomainWorkflowGraph for RET-C2-086 5-step replenishment pipeline."""

from __future__ import annotations

from typing import Any

from framework.graph.base_graph import BaseGraph
from langgraph.graph import END, START

from src.nodes.data_ingestion_node import DataIngestionNode
from src.nodes.demand_forecasting_node import DemandForecastingNode
from src.nodes.po_draft_node import PODraftNode
from src.nodes.reorder_calc_node import ReorderCalcNode
from src.nodes.retail_adjustment_node import RetailAdjustmentNode
from src.schemas.state import State


class DomainWorkflowGraph(BaseGraph):
    """Inner demand forecasting and replenishment workflow graph."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = config or {}
        self._validate_config()
        super().__init__(config)

    @property
    def name(self) -> str:
        return "ret_c2_086_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        required = ["forecast_horizon_days", "max_input_length", "low_confidence_threshold"]
        for key in required:
            if self._config.get(key) is None:
                raise ValueError(f"DomainWorkflowGraph: missing required config key: {key}")

    def register_nodes(self) -> None:
        self._nodes["data_ingestion"] = DataIngestionNode(config=self._config)
        self._nodes["demand_forecasting"] = DemandForecastingNode(
            config=self._config,
            llm=self._config.get("llm"),
        )
        self._nodes["retail_adjustment"] = RetailAdjustmentNode(config=self._config)
        self._nodes["reorder_calc"] = ReorderCalcNode(config=self._config)
        self._nodes["po_draft"] = PODraftNode(config=self._config)

    def add_edges(self) -> None:
        self._sg.add_edge(START, "data_ingestion")
        self._sg.add_edge("data_ingestion", "demand_forecasting")
        self._sg.add_edge("demand_forecasting", "retail_adjustment")
        self._sg.add_edge("retail_adjustment", "reorder_calc")
        self._sg.add_edge("reorder_calc", "po_draft")
        self._sg.add_edge("po_draft", END)

    def route(self, state: dict[str, Any]) -> str:
        del state
        return "data_ingestion"

    def get_output(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "normalized_dataset": state.get("normalized_dataset", {}),
            "validation_report": state.get("validation_report", {}),
            "demand_forecast": state.get("demand_forecast", {}),
            "adjusted_forecast": state.get("adjusted_forecast", {}),
            "adjustment_factors": state.get("adjustment_factors", {}),
            "replenishment_quantities": state.get("replenishment_quantities", {}),
            "reorder_flags": state.get("reorder_flags", {}),
            "po_draft": state.get("po_draft", {}),
            "exception_report": state.get("exception_report", ""),
            "hitl_draft": state.get("hitl_draft"),
            "status": state.get("status", "unknown"),
            "output": state.get("po_draft", {}),
            "trace_id": state.get("trace_id", ""),
            "correlation_id": state.get("correlation_id", ""),
            "node_history": state.get("node_history", []),
        }
