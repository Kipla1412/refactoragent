from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import List
import json

from api.auth import require_permission
from agent.events import AgentType
from customagents.factory import AgentFactory
from customagents.sessionmanager import SessionManager

router = APIRouter(prefix="/agent")

# Global session manager
session_manager = SessionManager()

class ConversationRequest(BaseModel):
    conversation: List[str]


@router.post(
    "/doctoragent",
    summary="Doctor Assistant - Medical Question Recommendations",
    description="""
Generate intelligent medical question recommendations for doctors based on patient conversation.

This endpoint analyzes the conversation history and provides targeted follow-up questions
that help doctors gather essential patient information for better medical care.

**Features:**
- Medical question recommendations based on symptoms
- Targeted follow-up questions for clinical assessment
- Context-aware conversation analysis

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- conversation: List of conversation messages between doctor and patient

**Output:**
- Structured question recommendations for clinical use
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def recommend_questions_api(request: Request, data: ConversationRequest):

    if not data.conversation:
        return {"questions": [], "status": "empty_input"}
    
    user_id = request.state.user["sub"]
    config = request.app.state.config
    session = await session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.DOC, config, session)

    try:
        # await agent.session.initialize()

        result = await agent.recommend_questions(data.conversation)

        return result

    except Exception as e:
        return {
            "questions": [], 
            "error": "Failed to generate recommendations",
            "details": str(e)
        }


@router.post(
    "/soap",
    summary="SOAP Report Generation",
    description="""
Generate professional clinical notes in SOAP format from doctor-patient conversation.

This endpoint processes the complete conversation and creates structured clinical documentation
following the SOAP (Subjective, Objective, Assessment, Plan) format used in medical practice.

**Features:**
- Standard SOAP format documentation
- Professional medical note generation
- Conversation-to-clinical-notes conversion

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- conversation: List of conversation messages to be documented

**Output:**
- Structured SOAP report with all medical sections
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def generate_soap_api(request: Request, data: ConversationRequest):

    if not data.conversation:
        return {"error": "Conversation is empty"}
    
    user_id = request.state.user["sub"]
    config = request.app.state.config
    session = await session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.SOAP, config, session)

    try:
        # await agent.session.initialize()

        result = await agent.generate(data.conversation)

        return result

    except Exception as e:
        return {
            "error": "Failed to generate SOAP report",
            "details": str(e)
        }


# Assessment Plan
@router.post(
    "/assessment",
    summary="Medical Assessment and Plan Generation",
    description="""
Generate comprehensive medical assessment and treatment plan from patient conversation.

This endpoint analyzes the complete patient consultation and creates detailed clinical
documentation including differential diagnosis, assessment findings, and recommended
treatment plans for healthcare providers.

**Features:**
- Comprehensive medical assessment generation
- Differential diagnosis analysis
- Treatment plan recommendations
- Clinical decision support
- Evidence-based suggestions

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- conversation: List of conversation messages between doctor and patient

**Output:**
- Structured assessment with clinical findings
- Recommended treatment options
- Follow-up care suggestions
- Medical documentation in structured format
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def generate_assessment_api(request: Request, data: ConversationRequest):

    if not data.conversation:
        return {"error": "Conversation is empty"}
    
    user_id = request.state.user["sub"]
    config = request.app.state.config
    session = await session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.ASSESSMENT, config, session)

    try:
        # await agent.session.initialize()

        result = await agent.generate(data.conversation)

        return result

    except Exception as e:
        return {
            "error": "Failed to generate assessment",
            "details": str(e)
        }