from fastapi import APIRouter, Request, Depends
from api.auth import get_current_user, require_permission
from agent.agent import Agent
from config.config import Config
from pydantic import BaseModel
from typing import List


router = APIRouter(prefix="/agent")


class ConversationRequest(BaseModel):
    conversation: List[str]

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

Authentication:
Requires a valid authenticated user session.

Permission Required:
`consultagent:chat`
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def recommend_questions_api(data: ConversationRequest):

    if not data.conversation:
        return {"questions": []}

    conversation = data.conversation

    config = Config()

    try:
        async with Agent(config) as agent:
            result = await agent.recommend_questions(conversation)
        return result

    except Exception as e:
        return {"error": str(e)}

@router.post(
    "/doctor-report",
    summary="Generate Professional Doctor Report",
    description="""
Generate structured clinical notes (SOAP format) from full conversation.

- Used at end of consultation
- Returns professional medical documentation
- No diagnosis or medication included

Authentication:
Requires a valid authenticated user session.

Permission Required:
`consultagent:chat`
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def generate_report_api(data: ConversationRequest):

    # validation
    if not data.conversation:
        return {"error": "Conversation is empty"}

    config = Config()

    try:
        async with Agent(config) as agent:
            result = await agent.generate_report(data.conversation)

        return result

    except Exception as e:
        return {"error": str(e)}