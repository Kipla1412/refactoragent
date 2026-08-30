import pytest

from utils.pdf_ocr import PDFOCR


class _FakeStreamEvent:
    def __init__(self, text):
        self.type = "message_complete"
        self.text_delta = type("TextDelta", (), {"content": text})()


class _FakeClient:
    def __init__(self, texts):
        self._texts = list(texts)

    async def chat_completion(self, messages, stream=False, **kwargs):
        for text in self._texts:
            yield _FakeStreamEvent(text)
        return


@pytest.mark.asyncio
async def test_ocr_extracts_text():
    client = _FakeClient(["Fever"])
    ocr = PDFOCR(client)
    result = await ocr.extract_text([b"fake-image-bytes"])
    assert result == "Fever"


@pytest.mark.asyncio
async def test_ocr_empty_images_raises():
    ocr = PDFOCR(_FakeClient([]))
    with pytest.raises(ValueError):
        await ocr.extract_text([])
