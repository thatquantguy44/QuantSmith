"""MCP adapter contract + knowledge resources server — spec 0052.

Public surface::

    from quantsmith.adapters.mcp_servers.contract import (
        PUBLIC, INTERNAL, RESTRICTED,
        ACCESS_RANK, clearance_allows,
        KnowledgeUri, ResourceMeta, ResourceContent,
        McpRequest, McpResponse, McpError,
    )
    from quantsmith.adapters.mcp_servers.knowledge_resources import dispatch

See ``adapters/mcp_servers/adapter_contract.md`` for the full contract and
``specs/0052-mcp-adapter-contract/`` for requirements and acceptance criteria.
"""
