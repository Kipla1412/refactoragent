from fastapi import APIRouter, Request, Depends
from api.auth import get_current_user, require_permission
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import json
import uuid

from agent.agent import Agent

router = APIRouter(prefix="/agent")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post(
    "/doctoragent",
    summary="Doctor's Assistant - Medical Question Recommendations",
    description="""
Stream intelligent medical question recommendations from the AI doctor's assistant.

This endpoint processes user medical queries and provides targeted follow-up questions
that help doctors gather essential patient information for better medical care.

Features:
- Medical question recommendations based on symptoms
- Targeted follow-up questions for doctors to use
- Session-based conversation context
- Real-time streaming response
- Authenticated user isolation
- Focus on medical information gathering only

Authentication:
Requires a valid authenticated user session.

Permission Required:
`consultagent:chat`
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def chat(req: ChatRequest, request: Request):

    sessions = request.app.state.sessions
    config = request.app.state.config

    user = request.state.user
    # Generate session id if missing
    user_id = user.get("sub")
    session_id = req.session_id or str(uuid.uuid4())

    
    if user_id not in sessions:

        agent = Agent(config)
        await agent.__aenter__()

        sessions[user_id] = agent

    agent = sessions[user_id]

    async def event_stream():

        async for event in agent.run(req.message):

            yield json.dumps({
                "type": event.type.value if hasattr(event.type, "value") else str(event.type),
                "data": event.data
            }) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/json; charset=utf-8",
        headers={"X-Session-ID": session_id}
    )
