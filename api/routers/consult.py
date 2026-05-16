from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
import json
from api.auth import require_permission
from agent.events import AgentType, AgentEvent
from customagents.factory import AgentFactory
from customagents.sessionmanager import SessionManager
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
import uuid

router = APIRouter(prefix="/agent")

# global session manager
session_manager = SessionManager()

# Request Model
class ChatRequest(BaseModel):
    message: str


@router.post(
    "/consult",
    summary="Medical Consultation Assistant",
    description="""
Interactive medical consultation assistant for healthcare professionals.

This endpoint provides real-time conversational AI support for medical consultations,
offering clinical insights, medical information, and decision support tools.

**Features:**
- Real-time streaming responses
- Medical knowledge and clinical guidance
- Interactive consultation support
- Session-based conversation memory

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- message: Medical query or consultation request

**Output:**
- Streaming JSON events with AI responses
- Maintains conversation context across sessions
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def consult_api(request: Request, data: ChatRequest):

    # validation
    if not data.message:
        return {"error": "Message is empty"}

    user_id = request.state.user["sub"]
    config = request.app.state.config

    # get shared session (memory per user)
    session = await session_manager.get_session(user_id, config)

    # create agent with SAME session
    agent = AgentFactory.create(AgentType.CONSULT, config, session)

    async def event_stream():
        try:
            # Match the method name 'run' from your Agent class
            async for event in agent.run(data.message):
                # Ensure the event is a dict for json.dumps
                if hasattr(event, "model_dump"):
                    event_data = event.model_dump()
                elif hasattr(event, "to_dict"):
                    event_data = event.to_dict()
                else:
                    event_data = event
                
                yield json.dumps(jsonable_encoder(event)) + "\n"
        except Exception as e:
            # Catch streaming errors so the connection doesn't just hang
            yield json.dumps({"type": "error", "data": str(e)}) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson", # NDJSON is standard for streaming
        headers={
            "X-Session-ID": session.session_id
        }
    )


@router.post(
    "/intake",
    summary="Patient Intake Assistant",
    description="""
Automated patient information collection for pre-visit medical intake.

This endpoint guides patients through a structured conversation to collect
essential medical information before doctor visits, including demographics,
symptoms, medications, allergies, and medical history.

**Features:**
- Guided patient conversation flow
- Structured medical data collection
- Real-time streaming responses
- JSON-formatted intake summary

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- message: Patient response or intake initiation

**Output:**
- Streaming JSON events with intake questions
- Final structured patient data in JSON format
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def intake_stream(request: Request, data: ChatRequest):
    
    if not data.message:
        return {"error": "Message is empty"}
        
    user_id = request.state.user["sub"]
    config = request.app.state.config

    session = await session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.INTAKE, config, session)

    async def event_stream():
       
        try:
            # We use 'run' now to match your ConsultAgent pattern
            async for event in agent.run(data.message):
                # Standardize the event for the stream
                yield json.dumps(jsonable_encoder(event)) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "data": str(e)}) + "\n"

    return StreamingResponse(
        event_stream(), 
        media_type="application/x-ndjson",
        headers={
            "X-Session-ID": session.session_id
        }
    )