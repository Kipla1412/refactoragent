from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from agent.events import AgentType
from api.auth import require_permission
from customagents.factory import AgentFactory
from utils.pdf_extractor import PDFDocumentExtractor
from utils.pdf_ocr import PDFOCR

router = APIRouter(prefix="/agent")

logger = logging.getLogger(__name__)

_extractor = PDFDocumentExtractor()


@router.post(
    "/pdf-chat",
    summary="PDF Document Chat Assistant",
    description="""
Chat with an uploaded PDF document. The document text is extracted and
stored in the user's session, so follow-up questions can be asked without
re-uploading the file.

Authentication:
Requires valid user session with consultagent:chat permission.
""",
    dependencies=[Depends(require_permission("consultagent", "chat"))],
)
async def pdf_chat_api(
    request: Request,
    message: str = Form(...),
    file: UploadFile | None = File(None),
    session_id: str | None = Form(None),
):
    user_id = request.state.user["sub"]
    config = request.app.state.config

    # Pin a session id to isolate/resume a PDF conversation. Without one the
    # request uses the user's shared session so follow-up questions keep the
    # uploaded PDF context.
    session = await request.app.state.session_manager.get_session(
        user_id, config, session_id=session_id
    )
    logger.info(
        "[CHAT][pdf-chat] user=%s requested_session_id=%s resolved_session_id=%s uploaded=%s",
        user_id, session_id, session.session_id, bool(file and file.filename),
    )

    if not message or not message.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Message is empty"},
        )

    # If a file is uploaded, replace the stored PDF context.
    if file is not None and file.filename:
        pdf_bytes = await file.read()
        try:
            pdf_text = _extractor.extract_text(pdf_bytes)

            # Scanned/image PDFs have no meaningful text layer — fall back to OCR.
            if not pdf_text.strip():
                images = _extractor.render_pages(pdf_bytes)
                ocr = PDFOCR(session.client, model=config.vision_model_name)
                pdf_text = await ocr.extract_text(images)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
            )
        session.metadata["pdf_context"] = pdf_text
        session.metadata["pdf_filename"] = file.filename

    if not session.metadata.get("pdf_context"):
        return JSONResponse(
            status_code=400,
            content={"error": "No PDF context available. Upload a PDF file."},
        )

    agent = AgentFactory.create(AgentType.PDF_CHAT, config, session)

    async def event_stream():
        try:
            async for event in agent.run(message):
                yield json.dumps(jsonable_encoder(event)) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "data": str(exc)}) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"X-Session-ID": session.session_id},
    )
