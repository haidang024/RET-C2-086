# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `Graph` (registry name: `RetailDemandForecastingReplenishmentAgent`)
- **L1 Base**: `AgentBaseGraph`
- **Three-Layer Separation**:
  - State: flat `State(AgentState)` with JSON-serializable values only
  - Nodes: `FunctionNode` implementations plus a `GraphNode` composition wrapper
  - Graph: outer `AgentBaseGraph` and inner `BaseGraph`

## Architecture Overview

### Node Configuration

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Framework bootstrap | framework state | initialized state | default `InitializeNode` |
| pre_process | Validate and parse JSON replenishment request | `user_input`, `input_context` | normalized domain fields, `validated_input` | `PreProcessNode(FunctionNode)` / `execute` + S-2 hook |
| main | Invoke five-stage domain workflow | normalized retail fields | forecast, reorder, PO, exception fields | `DemandReplenishmentGraphNode(GraphNode)` / composition hooks |
| post_process | Render safe JSON response | PO and exception fields | `formatted_output`, `result` | `PostProcessNode(FunctionNode)` / `execute` + S-3 hook |
| finalize | Framework output envelope | final state | response | default `FinalizeNode` |

```text
START → initialize → pre_process → main/subgraph → post_process → finalize → END

main: data_ingestion → demand_forecasting → retail_adjustment → reorder_calc → po_draft
```

### State Definition

| Field | Type | Purpose |
|-------|------|---------|
| `validated_input` | `str` | Validated JSON envelope |
| `pos_records` | `list` | Store/SKU/date/quantity history |
| `inventory_snapshot` | `dict` | Current inventory by store/SKU |
| `sku_master` | `dict` | SKU metadata |
| `supplier_constraints` | `dict` | Lead time, safety days, MOQ, and pack size |
| `adjustment_signals` | `dict` | Weather, promotion, holiday, and event factors |
| `normalized_dataset` / `validation_report` | `dict` | Ingestion outputs |
| `demand_forecast` | `dict` | Deterministic forecast, confidence bounds, optional AI note |
| `adjusted_forecast` / `adjustment_factors` | `dict` | Context-adjusted demand and explanation |
| `replenishment_quantities` / `reorder_flags` | `dict` | Deterministic reorder result |
| `po_draft` / `exception_report` | `dict` / `str` | Draft order and planner exceptions |
| `hitl_draft` | `dict \| None` | Declarative review payload, not a framework interrupt |
| `formatted_output` / `result` | `str` | Final response payload |

State contains no secrets, SDK clients, Pydantic models, dataclasses, or
`InvocationContext`. The composite node calls `InvocationContext.from_state()`;
structured retail data crosses the inner boundary through non-persisted
`input_context` and is restored by `DataIngestionNode`.

## Runtime Configuration and LLM Injection

`config/agent.yaml` contains registry identity and the static generation
contract. `config/config.yaml` contains graph settings and domain defaults. The
forecast node resolves Azure OpenAI from invocation-scoped secrets and safely
omits commentary when the provider is unavailable.

`Graph.register_nodes()` injects the client into `main`; the wrapper passes it to
the inner graph, which injects it into `DemandForecastingNode`. Only aggregate
item count, horizon, and average confidence are sent to the model. Deterministic
forecast values, adjustments, reorder quantities, and PO lines are never model
outputs. Missing keys, provider failures, and unsupported responses omit the AI
note and preserve the deterministic result.

## HITL Semantics

`planner_review_draft_enabled: true` emits a review payload for low-confidence
forecasts. It does not call LangGraph `interrupt()`, so `hitl.enabled` is false,
no checkpointer is required, and PB-7 is auto-waived as non-HITL.

## Framework Utilization

- [x] `InvocationContext.from_state()` at the composite boundary
- [x] `SecurityViolationError`
- [x] S-2 via `_extra_security_gate_input()`
- [x] S-3 via `_extra_security_gate_output()`
- [x] S-4 domain events in every `FunctionNode.execute()`
- [x] No final framework security-gate overrides
- [x] No Level-0 or mediator imports from `src/`

## EU AI Act Art.13 Design-Time Evidence

Not applicable because the proposal declares the intended purpose outside Annex
III. Outputs still expose confidence, adjustment factors, constraint flags, and
planner-review status.

## Design Decision Record

| Decision | Options | Chosen | Rationale |
|----------|---------|--------|-----------|
| L1 base | AgentBaseGraph / AutonomousBaseGraph | AgentBaseGraph | Fixed, bounded Cat 2 workflow |
| Composition | flat chain / inner graph | GraphNode + BaseGraph | Isolates the five-step use case |
| AI authority | forecast quantities / commentary only | commentary only | Keeps calculations deterministic and auditable |
| Provider absence | fail boot / fallback | deterministic fallback | Core replenishment remains available |
| Human review | framework interrupt / declarative draft | declarative draft | Current code emits review data but has no interrupt/resume path |
