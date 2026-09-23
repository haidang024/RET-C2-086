"""PB-6: invoke lifecycle ordering and S-1 denial verification."""

import importlib
import inspect
import pkgutil
from typing import ClassVar

import pytest
from framework.nodes.base_node import BaseNode
from framework.schemas.trust_level import TrustLevel


class _PrivilegedTrustGateFixture(BaseNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _security_gate_input(self, state):
        return state

    def execute(self, state):
        return {"status": "success"}

    def _security_gate_output(self, result):
        return result


def _trust_predecessor(required: TrustLevel) -> TrustLevel:
    predecessors = {
        TrustLevel.VERIFIED_EXTERNAL: TrustLevel.ANONYMOUS,
        TrustLevel.INTERNAL: TrustLevel.VERIFIED_EXTERNAL,
    }
    try:
        return predecessors[required]
    except KeyError as exc:
        raise AssertionError(f"no lower trust level defined for {required!r}") from exc


def _discover_node_classes() -> list[type]:
    try:
        pkg = importlib.import_module("src.nodes")
    except ImportError as exc:
        pytest.fail(f"PB-6 cannot import src.nodes: {exc}")
    discovered = []
    for _, modname, _ in pkgutil.walk_packages(pkg.__path__, prefix="src.nodes."):
        module = importlib.import_module(modname)
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseNode)
                and attr is not BaseNode
                and attr.__module__ == modname
                and not inspect.isabstract(attr)
            ):
                discovered.append(attr)
    return discovered


def _valid_state(trust: TrustLevel) -> dict:
    payload = {
        "pos_records": [{"store_id": "S1", "sku_id": "SKU1", "date": "2026-07-01", "qty": 10}],
        "inventory_snapshot": {"S1:SKU1": 3},
        "sku_master": {"SKU1": {}},
        "supplier_constraints": {"lead_time_days": 2, "moq": 10, "pack_size": 5},
        "adjustment_signals": {"weather_factor": 1.0},
    }
    return {
        "caller_trust_level": trust.value,
        "correlation_id": "pb6-invoke-order-test",
        "user_input": payload,
        **payload,
        "normalized_dataset": {"rows": payload["pos_records"]},
        "demand_forecast": {"items": [{"store_id": "S1", "sku_id": "SKU1", "forecast_qty": 10, "confidence": 0.8}]},
        "adjusted_forecast": {
            "items": [
                {
                    "store_id": "S1",
                    "sku_id": "SKU1",
                    "adjusted_forecast_qty": 10,
                    "confidence": 0.8,
                }
            ]
        },
        "replenishment_quantities": {"items": [{"store_id": "S1", "sku_id": "SKU1", "recommended_qty": 10}]},
        "reorder_flags": {"items": []},
        "po_draft": {"lines": [{"sku_id": "SKU1", "quantity": 10}]},
        "exception_report": "# Exception Report\n- none",
        "status": "success",
    }


class TestInvokeOrder:
    def test_s1_denial_refuses_execution_before_execute(self, monkeypatch):
        import framework.nodes.base_node as base_node_module

        events: list[str] = []
        execute_calls: list[object] = []
        monkeypatch.setattr(
            base_node_module,
            "emit_trace_event",
            lambda event_type, _payload, _state: events.append(event_type),
        )
        original_execute = _PrivilegedTrustGateFixture.execute

        def spy_execute(self, state):
            execute_calls.append(state)
            return original_execute(self, state)

        monkeypatch.setattr(_PrivilegedTrustGateFixture, "execute", spy_execute)
        result = _PrivilegedTrustGateFixture()(
            {
                "caller_trust_level": _trust_predecessor(_PrivilegedTrustGateFixture.required_trust_level).value,
                "correlation_id": "tc08-s1-denial",
            }
        )
        assert result["status"] == "error"
        assert "S-1 trust gate denied" in result["error_log"][0]
        assert events == ["s1_denied"]
        assert not execute_calls

    def test_call_order_for_every_node(self, monkeypatch):
        node_classes = _discover_node_classes()
        if not node_classes:
            pytest.skip("no concrete BaseNode subclasses found under src/nodes/")
        import framework.nodes.base_node as base_node_module

        failures: list[str] = []
        for node_cls in node_classes:
            order: list[str] = []
            monkeypatch.setattr(
                base_node_module,
                "emit_trace_event",
                lambda event_type, _payload, _state, _o=order: _o.append(f"event:{event_type}"),
            )
            for method_name, label in (
                ("_security_gate_input", "security_gate_input"),
                ("execute", "execute"),
                ("_security_gate_output", "security_gate_output"),
            ):
                original = getattr(node_cls, method_name)

                def spy(self, arg, _o=order, _label=label, _orig=original):
                    _o.append(_label)
                    return _orig(self, arg)

                monkeypatch.setattr(node_cls, method_name, spy)
            node_cls()(_valid_state(node_cls.required_trust_level))
            expected = [
                "event:node_start",
                "security_gate_input",
                "execute",
                "security_gate_output",
                "event:node_complete",
            ]
            if order != expected:
                failures.append(f"{node_cls.__name__}: expected {expected}; actual {order}")
        assert not failures, "\n".join(failures)
