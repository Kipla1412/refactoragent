from __future__ import annotations

import base64
from typing import Any

from client.response import StreamEventType

_OCR_PROMPT = (
    "Extract all text from this document page image. "
    "Return only the extracted text, preserving paragraphs and tables "
    "as faithfully as possible. Do not add commentary."
)


class PDFOCR:
    """OCR page images using the existing vision-capable LLM client.

    This class is isolated from PDF parsing/rendering so the extractor and
    agent remain independent of the OCR implementation.
    """

    def __init__(self, client: Any, model: str | None = None):
        self._client = client
        self._model = model

    async def extract_text(self, images: list[bytes]) -> str:
        if not images:
            raise ValueError("No images provided for OCR.")

        texts: list[str] = []
        for image in images:
            encoded = base64.b64encode(image).decode("utf-8")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded}",
                            },
                        },
                    ],
                }
            ]

            kwargs: dict[str, Any] = {}
            if self._model:
                kwargs["model"] = self._model

            async for event in self._client.chat_completion(
                messages,
                stream=False,
                **kwargs,
            ):
                if event.type == StreamEventType.MESSAGE_COMPLETE and event.text_delta:
                    texts.append(event.text_delta.content.strip())

        result = "\n\n".join(t for t in texts if t).strip()
        if not result:
            raise ValueError("OCR could not extract any text from the PDF.")

        return result
