import pytest


@pytest.mark.asyncio
async def test_mcp_register_tools_clears_stale_registrations(config):
    """Re-registering MCP tools must not leave prior tools in the registry."""
    from tools.mcp.mcp_manager import MCPManager
    from tools.mcp.client import MCPServerStatus
    from tools.registry import ToolRegistry

    manager = MCPManager(config)

    # Simulate one connected client exposing a tool.
    class _FakeClient:
        name = "fhir"
        status = MCPServerStatus.CONNECTED
        tools = []

    # Simulate a single registered MCP tool directly through the registry API.
    registry = ToolRegistry(config)
    manager.register_tools(registry)
    assert registry._mcp_tools == {}

    # Now inject a connected client and confirm tools land in the MCP bucket.
    from tools.mcp.client import MCPToolInfo

    client = _FakeClient()
    client.tools = [MCPToolInfo(name="search", description="search")]
    manager._clients["fhir"] = client

    manager.register_tools(registry)
    assert "fhir__search" in registry._mcp_tools
    assert "fhir__search" not in registry._tools
