"""Service utilities for RET-C2-086."""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any


class Service:
    """Domain service."""

    async def fetch(self, query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fetch domain data for the given query.

        Stub for future ERP/external data integration.
        Implement before wiring to a live data source.
        """
        raise NotImplementedError("Implement fetch() for Service")
