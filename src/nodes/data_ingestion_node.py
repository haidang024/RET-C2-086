"""DataIngestionNode for RET-C2-086 data validation and normalization."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class DataIngestionNode(FunctionNode):
    """Step 1: normalize POS and inventory inputs to a common schema."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config: dict[str, Any] = config or {}

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2: check PII markers in incoming POS records payload."""
        domain = (state.get("input_context") or {}).get("domain", {})
        if not isinstance(domain, dict):
            domain = {}
        records = state.get("pos_records") or domain.get("pos_records", [])
        text = json.dumps(records, ensure_ascii=False)
        for marker in ["email", "phone", "customer_name", "address"]:
            if marker in text.lower():
                raise SecurityViolationError(f"PII marker detected in pos_records: {marker}")
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        domain = (state.get("input_context") or {}).get("domain", {})
        if not isinstance(domain, dict):
            domain = {}
        pos_records = state.get("pos_records") or domain.get("pos_records", [])
        inventory_snapshot = state.get("inventory_snapshot") or domain.get("inventory_snapshot", {})
        sku_master = state.get("sku_master") or domain.get("sku_master", {})
        supplier_constraints = state.get("supplier_constraints") or domain.get("supplier_constraints", {})
        adjustment_signals = state.get("adjustment_signals") or domain.get("adjustment_signals", {})

        normalized_rows: list[dict[str, Any]] = []
        errors: list[str] = []
        for idx, row in enumerate(pos_records):
            if not isinstance(row, dict):
                errors.append(f"row[{idx}] is not a dict")
                continue
            store_id = row.get("store_id") or row.get("storeCode")
            sku_id = row.get("sku_id") or row.get("itemCode")
            qty = row.get("qty") if row.get("qty") is not None else row.get("quantity")
            date = row.get("date") or row.get("business_date")
            if not store_id or not sku_id or qty is None or not date:
                errors.append(f"row[{idx}] missing required fields")
                continue
            normalized_rows.append(
                {
                    "store_id": str(store_id),
                    "sku_id": str(sku_id),
                    "date": str(date),
                    "qty": float(qty),
                    "price": float(row.get("price", 0.0)),
                }
            )

        normalized_dataset = {
            "rows": normalized_rows,
            "inventory_snapshot": inventory_snapshot if isinstance(inventory_snapshot, dict) else {},
            "sku_master": sku_master if isinstance(sku_master, dict) else {},
        }
        validation_report = {
            "input_rows": len(pos_records),
            "normalized_rows": len(normalized_rows),
            "error_count": len(errors),
            "errors": errors,
        }

        emit_trace_event(
            "DataIngestionNode_pos_data_ingested",
            {
                "input_rows": len(pos_records),
                "normalized_rows": len(normalized_rows),
                "error_count": len(errors),
            },
            state,
        )
        return {
            "pos_records": pos_records,
            "inventory_snapshot": inventory_snapshot,
            "sku_master": sku_master,
            "supplier_constraints": supplier_constraints,
            "adjustment_signals": adjustment_signals,
            "normalized_dataset": normalized_dataset,
            "validation_report": validation_report,
            "status": AgentStatus.SUCCESS.value,
        }
