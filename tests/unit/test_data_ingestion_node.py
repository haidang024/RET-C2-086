"""Unit tests for DataIngestionNode."""

from __future__ import annotations

from framework.schemas.agent_status import AgentStatus

from src.nodes.data_ingestion_node import DataIngestionNode


def test_data_ingestion_normalizes_rows() -> None:
    node = DataIngestionNode(config={})
    state = {
        "pos_records": [
            {"storeCode": "S1", "itemCode": "SKU1", "business_date": "2026-07-01", "quantity": 10},
            {"store_id": "S2", "sku_id": "SKU2", "date": "2026-07-01", "qty": 6},
        ],
        "inventory_snapshot": {"S1:SKU1": 3},
        "sku_master": {"SKU1": {"category": "grocery"}},
    }
    result = node.execute(state)
    assert result["status"] == AgentStatus.SUCCESS.value
    assert result["validation_report"]["normalized_rows"] == 2
    assert result["normalized_dataset"]["rows"][0]["store_id"] == "S1"


def test_data_ingestion_reports_invalid_rows() -> None:
    node = DataIngestionNode(config={})
    result = node.execute(
        {
            "pos_records": ["bad-row", {"store_id": "S1"}],
            "inventory_snapshot": {},
            "sku_master": {},
        }
    )
    assert result["validation_report"]["error_count"] == 2
