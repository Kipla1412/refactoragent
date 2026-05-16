
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import json
import uuid

from api.auth import require_permission
from customagents.factory import AgentFactory
from customagents.sessionmanager import SessionManager
from agent.events import AgentType

router = APIRouter(prefix="/agent")

session_manager = SessionManager()


class MCPRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post(
    "/mcpagent",
    summary="FHIR MCP Assistant",
    description="""
FHIR-enabled healthcare assistant using MCP tools.

Features:
- Fetch patient information
- Retrieve medications
- Read observations
- View encounters
- Access FHIR resources securely

Requires:
- Valid JWT authentication
- MCP healthcare permissions

# Permission Required:
# `texttosqlagent:chat` - Healthcare data query access

"""
    # dependencies=[Depends(require_permission("texttosqlagent", "chat"))]
)
async def mcp_chat(req: MCPRequest, request: Request):

    config = request.app.state.config

    user = request.state.user
    user_id = user.get("sub")

    session_id = req.session_id or str(uuid.uuid4())

    # shared session
    session = await session_manager.get_session(
        user_id,
        config
    )

    # inject runtime token
    session.auth_token = request.state.token

    print("REQUEST TOKEN:", request.state.token)

    await session.initialize()

    # # reinitialize MCP with fresh token
    # session.mcp_manager._initialized = False

    # await session.mcp_manager.initialize(
    #     auth_token=session.auth_token
    # )

    # session.mcp_manager.register_tools(
    #     session.tool_registry
    # )

    # current_token = request.state.token

    # if (
    #     not getattr(session, "mcp_initialized", False)
    #     or session.auth_token != current_token
    # ):

    #     session.auth_token = current_token

    #     await session.mcp_manager.shutdown()

    #     await session.mcp_manager.initialize(
    #         auth_token=current_token
    #     )

    #     session.mcp_initialized = True

    # create MCP agent
    agent = AgentFactory.create(
        AgentType.EHR,
        config,
        session
    )

    async def event_stream():

        async for event in agent.run(req.message):

            event_type = (
                event.type.value
                if hasattr(event.type, "value")
                else str(event.type)
            )

            # TOOL START
            if event_type == "tool_call_start":

                yield json.dumps({
                    "type": "tool_start",
                    "tool": event.data.get("name"),
                    "arguments": event.data.get("arguments", {}),
                    "agent": "ehr"
                }) + "\n"

            # TOOL COMPLETE
            elif event_type == "tool_call_complete":

                yield json.dumps({
                    "type": "tool_result",
                    "tool": event.data.get("name"),
                    "success": event.data.get("success"),
                    "output": event.data.get("output"),
                    "agent": "ehr"
                }) + "\n"

            # TEXT DELTA
            elif event_type == "text_delta":

                yield json.dumps({
                    "type": "text_delta",
                    "message": event.data.get("content", ""),
                    "agent": "ehr"
                }) + "\n"

            # TEXT COMPLETE
            elif event_type == "text_complete":

                yield json.dumps({
                    "type": "text_complete",
                    "message": event.data.get("content", ""),
                    "agent": "ehr"
                }) + "\n"

            # ERROR
            elif event_type == "agent_error":

                yield json.dumps({
                    "type": "error",
                    "message": event.data.get("error", "Unknown error")
                }) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/json",
        headers={
            "X-Session-ID": session_id
        }
    )