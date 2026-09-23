# Test Specification

## Test Strategy

- Coverage target: 85%+
- Test types: unit, integration, and proof-of-boundary
- Runtime target: published `agenticstar-agentcore[anthropic]==1.0.1` wheel

## Framework Compliance Tests

| TC-ID | Test | Expected Result |
|-------|------|-----------------|
| TC-01 | Flat state contract | No Pydantic/dataclass or credential fields |
| TC-02 | Oversized/unsafe input | S-2 rejects request |
| TC-03 | Credential scan | CI reports zero violations |
| TC-04 | Invocation context usage | Nodes use `InvocationContext.from_state()` only |
| TC-05 | Lifecycle event duplication | No manual `node_start/node_complete/node_error` events |
| TC-06 | Override `_security_gate_input()` | Framework raises `TypeError` at class definition |
| TC-07 | Override `_security_gate_output()` | Framework raises `TypeError` at class definition |
| TC-08 | Under-privileged caller | S-1 rejects before `execute()` |
| TC-09 | POS payload with PII markers | Domain S-2 rejects it |
| TC-10 | Credential-like output | Domain S-3 rejects it |
| TC-11 | Domain tracing | Every FunctionNode path emits an event |

## Proof-of-Boundary Tests

| PB-ID | Boundary | Test | Expected Result |
|-------|----------|------|-----------------|
| PB-1 | BaseNode → EventEmitter | Domain events fire | No silent path |
| PB-2 | State serialization | Inspect schema and representative output | JSON/msgpack-safe values only |
| PB-3 | Template → optional LLM | Construct server with and without key | Deterministic fallback; same client reaches forecasting node |
| PB-4 | Import isolation | AST scan `src/` | No Level-0 or mediator imports |
| PB-5 | Checkpoint safety (conditional) | Apply only when memory/HITL and ingress hooks are enabled | Auto-waived while checkpointing is disabled |
| PB-6 | Node lifecycle | S-1 → start → S-2 → execute → S-3 → complete | Exact order; denial before execute |
| PB-7 | HITL propagation (conditional) | Apply only when `config/config.yaml` enables framework HITL | Auto-waived; planner review is declarative |
| PB-8 | Standalone trust | Exercise external/internal/invalid bearer paths | No external elevation to INTERNAL |

## Business Logic Tests

| BL-ID | Scenario | Expected Result |
|-------|----------|-----------------|
| BL-01 | Mixed POS aliases | Rows normalize to store/SKU/date/quantity |
| BL-02 | Historical quantity series | Confidence interval fields are present |
| BL-03 | Promotion/weather/holiday factors | Adjusted forecast and factor map are emitted |
| BL-04 | MOQ and pack-size constraints | Quantity is correctly bounded and rounded |
| BL-05 | Low-confidence forecast | PO draft, exception report, and planner-review draft are emitted |
| BL-06 | LLM absent or failing | Deterministic forecast and PO result remain available |

## Execution Summary

- Date: 2026-08-18
- Static/scaffold gates: passed (integrity, design, imports, composition, invoke contract, credentials, trust, category, stub, and dependency-pin checks).
- Supporting gate regression suite: 192 passed, 3 skipped.
- Project checks available without the private runtime: Ruff lint/format, compileall, manifest schema, credentials, forbidden strings, generation-mode, OSS license, import-isolation, state-safety, and a complete manual domain-pipeline invocation passed.
- Full runtime tests and coverage: not executed because `agenticstar-agentcore[anthropic]==1.0.1` was unavailable from the configured package indexes. Re-run the command after setting `AGENTCORE_PYPI_INDEX` or `PIP_EXTRA_INDEX_URL` to the private AgentCore index.
