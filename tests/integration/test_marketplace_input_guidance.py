import json

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph


def test_invalid_marketplace_request_returns_readable_guidance():
    graph = Graph(config={})
    graph.compile()
    result = graph.invoke(
        "Hello, hi",
        ctx=InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL),
        input_context={"conversation_history": []},
    )

    assert result["status"] == "success"
    assert result["output"].startswith("Demand replenishment request could not be processed.")
    assert "Reason:" in result["output"]
    assert "How to continue:" in result["output"]


def test_success_output_is_readable_only_for_marketplace():
    graph = Graph(config={})
    canonical = json.dumps(
        {
            "po_draft": {
                "status": "draft",
                "po_number": "PO-123",
                "lines": [{"sku_id": "SKU-1", "quantity": 20}],
            },
            "exception_report": "No blocking exceptions.",
            "replenishment_quantities": {"SKU-1": 20},
        }
    )
    state = {"formatted_output": canonical, "result": canonical, "status": "success"}

    assert graph.get_output(state)["output"] == canonical

    marketplace = graph.get_output({**state, "input_context": {"conversation_history": []}})
    assert marketplace["output"].startswith("# Demand Replenishment Draft")
    assert "SKU-1: 20 unit(s)" in marketplace["output"]
    assert not marketplace["output"].lstrip().startswith("{")
