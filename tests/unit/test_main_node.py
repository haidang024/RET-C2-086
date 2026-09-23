"""Unit tests for RET-C2-086 pre/post process nodes."""

from __future__ import annotations

import json

from framework.schemas.agent_status import AgentStatus

from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode


def _valid_payload() -> dict:
    return {
        "pos_records": [{"store_id": "S1", "sku_id": "SKU1", "date": "2026-07-01", "qty": 12}],
        "inventory_snapshot": {"S1:SKU1": 4},
        "sku_master": {"SKU1": {"category": "snack"}},
        "supplier_constraints": {"lead_time_days": 2, "moq": 10, "pack_size": 5},
        "adjustment_signals": {"weather_factor": 1.05, "promotion_factor": 1.1},
    }


def test_pre_process_valid_payload_success() -> None:
    node = PreProcessNode(config={"max_input_length": 10000})
    result = node.execute({"user_input": _valid_payload()})
    assert result["status"] == AgentStatus.SUCCESS.value
    parsed = json.loads(result["validated_input"])
    assert parsed["pos_records"][0]["sku_id"] == "SKU1"


def test_pre_process_missing_required_keys_returns_guidance() -> None:
    node = PreProcessNode(config={"max_input_length": 10000})
    result = node.execute({"user_input": {"pos_records": []}})
    assert result["status"] == AgentStatus.SUCCESS.value
    assert "Missing required fields" in result["input_error_message"]
    assert result["input_error_guidance"]


def test_post_process_formats_json_output() -> None:
    node = PostProcessNode(config={})
    state = {
        "po_draft": {"lines": [{"sku_id": "SKU1", "quantity": 10}]},
        "exception_report": "# Exception Report\n- none",
        "replenishment_quantities": {"items": [{"sku_id": "SKU1", "recommended_qty": 10}]},
        "status": AgentStatus.SUCCESS.value,
    }
    result = node.execute(state)
    assert result["status"] == AgentStatus.SUCCESS.value
    assert '"po_draft"' in result["formatted_output"]
