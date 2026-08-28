from tools.registry import ToolRegistry, create_default_registry
from tools.base import Tool, ToolInvocation, ToolResult


class _FakeTool(Tool):
    name = "fake"
    description = "A fake tool for testing."
    schema = {"type": "object", "properties": {}}

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        return ToolResult.success_result("ok")


def test_mcp_tools_do_not_overwrite_builtin_tools(config):
    registry = create_default_registry(config)
    original_tool = registry.get("memory")
    assert original_tool is not None

    mcp_tool = _FakeTool(config)
    mcp_tool.name = "memory"
    registry.register_mcp(mcp_tool)

    # MCP registration is isolated from builtin/custom registration.
    assert registry.get("memory") is original_tool
    assert registry._mcp_tools["memory"] is mcp_tool


def test_get_tools_includes_mcp_tools(config):
    registry = create_default_registry(config)
    mcp_tool = _FakeTool(config)
    mcp_tool.name = "server__tool"
    registry.register_mcp(mcp_tool)

    names = {t.name for t in registry.get_tools()}
    assert "memory" in names
    assert "server__tool" in names


def test_clear_mcp_tools_removes_only_mcp_entries(config):
    registry = create_default_registry(config)
    registry.register_mcp(_FakeTool(config))

    registry.clear_mcp_tools()

    assert registry._mcp_tools == {}
    assert registry.get("memory") is not None


def test_unregister_mcp_tool(config):
    registry = create_default_registry(config)
    mcp_tool = _FakeTool(config)
    mcp_tool.name = "server__tool"
    registry.register_mcp(mcp_tool)

    assert registry.unregister("server__tool") is True
    assert registry.get("server__tool") is None
