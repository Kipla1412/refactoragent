from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from pydantic import BaseModel, ValidationError
from sarvamai import AsyncSarvamAI

from client.llm_client import LLMClient
from client.response import StreamEventType
from speechtospeech.hybrid.audio_manager import AudioBufferManager
from speechtospeech.providers.stt.streamsarvam import SarvamStreamingSTTProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema for LLM structured-output role mapping
# ---------------------------------------------------------------------------

class ClinicRoles(BaseModel):
    doctor_speaker_id: str
    patient_speaker_id: str
    reasoning: str


# ---------------------------------------------------------------------------
# Few-shot system prompt for Indian clinical code-switching role mapping
# ---------------------------------------------------------------------------

_ROLE_MAP_SYSTEM_PROMPT = """\
You are an expert clinical conversation analyst. Your task is to map anonymous speaker
IDs from a diarized medical transcript to the roles "Doctor" and "Patient".

This is a clinical consultation in India. The conversation may mix English with
regional languages (Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi,
Gujarati, Punjabi) — a phenomenon known as code-switching.

IDENTIFICATION RULES
────────────────────
Doctor (healthcare provider):
- Asks diagnostic questions about symptoms, onset, duration, severity
- Gives treatment instructions and prescribes medications / dosages
- Uses medical terminology (diagnoses, anatomical terms, lab tests)
- Initiates the conversation with greetings and sets the clinical agenda
- Asks follow-up / clarifying questions
- Provides reassurance or medical advice

Patient:
- Reports symptoms and complaints using lay terms
- Answers the doctor's questions
- Describes pain location, intensity, duration in everyday language
- May use Hindi / regional words for body parts, symptoms, time references
- May hesitate, express worry, or ask non-clinical questions

INDIAN CODE-SWITCHING EXAMPLES
──────────────────────────────
SPEAKER_00: kab se fever hai? since when are you having this?               → Doctor
SPEAKER_01: kal raat se sir, and body pain bhi hai                          → Patient
SPEAKER_00: any vomiting or loose motions?                                  → Doctor
SPEAKER_01: nahi sir, but kamzori bahut hai                                 → Patient
SPEAKER_00: take tablet dolo 650 SOS for fever, plenty of fluids            → Doctor
SPEAKER_00: what about the abdominal pain you mentioned earlier?            → Doctor
SPEAKER_01: pet ke left side mein hai, khana khane ke baad badhta hai       → Patient
SPEAKER_01: kaan mein dard hai aur sunai bhi kam deta hai                   → Patient (first-visit symptom report)
SPEAKER_00: I'm prescribing an antibiotic course for five days, okay?       → Doctor
SPEAKER_00: aapko pehle kabhi yeh problem hui hai?                          → Doctor
SPEAKER_01: haan, pehle bhi, do mahine pehle                                → Patient

RESPONSE FORMAT
───────────────
Return a JSON object with exactly these fields:
- doctor_speaker_id: the speaker ID string for the doctor (e.g. "SPEAKER_00")
- patient_speaker_id: the speaker ID string for the patient
- reasoning: brief explanation (max 100 chars) of why you assigned each role

If the transcript contains more than 2 speaker IDs, merge or select the best 2.
If only one speaker is present, use "NONE" for the missing role."""


def _build_role_map_messages(transcript_snapshot: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": _ROLE_MAP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Map the speaker IDs to Doctor / Patient roles based on the "
                "following transcript excerpt from an Indian clinical consultation:\n\n"
                f"{transcript_snapshot}"
            ),
        },
    ]


# ---------------------------------------------------------------------------
# HybridSTTProvider
# ---------------------------------------------------------------------------

class HybridSTTProvider:
    """Composes streaming STT with post-hoc batch speaker diarization.

    Dual-routes incoming audio bytes to both a live WebSocket transcription
    stream AND an on-disk audio cache.  When the session ends, uploads the
    cached WAV file to Sarvam's Batch STT endpoint with diarization enabled,
    maps the anonymous speaker IDs to "Doctor" / "Patient" via an LLM call,
    and returns the fully relabeled dialogue transcript.
    """

    def __init__(
        self,
        api_key: str,
        streaming_model: str = "saaras:v3",
        batch_model: str = "saarika:v2.5",
        language_code: str = "unknown",
        sample_rate: int = 16000,
        num_speakers: int = 2,
        llm_client: LLMClient | None = None,
        llm_model: str = "gpt-4.1",
        session_id: str | None = None,
    ):
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.num_speakers = num_speakers
        self.batch_model = batch_model
        self._llm_client = llm_client
        self._llm_model = llm_model

        # Composed streaming provider
        self._streaming = SarvamStreamingSTTProvider(
            api_key=api_key,
            language_code=language_code,
            model=streaming_model,
            sample_rate=sample_rate,
        )

        # Audio buffer for dual-routing
        self._buffer = AudioBufferManager(
            session_id=session_id,
            sample_rate=sample_rate,
            vault_dir="./vault",
        )

        # Separate client for batch API call (avoids WebSocket lifecycle coupling)
        self._batch_client = AsyncSarvamAI(api_subscription_key=api_key)

        # Accumulated streaming transcript for fallback
        self._streaming_transcript_lines: list[str] = []

    # ------------------------------------------------------------------
    # Delegated streaming interface (identical shape to existing provider)
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        await self._streaming.connect()

    async def send_audio(self, audio_bytes: bytes) -> None:
        if not audio_bytes:
            return

        # Route 1: Live streaming transcription
        send_task = asyncio.create_task(
            self._streaming.send_audio(audio_bytes)
        )

        # Route 2: Accumulate raw PCM for batch diarization
        await self._buffer.append_chunk(audio_bytes)

        # Await the send to catch errors without blocking the buffer
        try:
            await send_task
        except Exception:
            logger.exception("HybridSTTProvider: streaming send_audio failed")

    async def stream_transcripts(self) -> AsyncGenerator[dict[str, Any], None]:
        async for transcript in self._streaming.stream_transcripts():
            text = transcript.get("text", "")
            if transcript.get("is_final") and text.strip():
                self._streaming_transcript_lines.append(text.strip())
            yield transcript

    async def update_config(self, language_code: str) -> None:
        await self._streaming.update_config(language_code)

    async def flush(self) -> None:
        await self._streaming.flush()

    async def close(self) -> None:
        await self._streaming.close()
        await self._buffer.cleanup()

    # ------------------------------------------------------------------
    # Post-processing pipeline
    # ------------------------------------------------------------------

    async def finalize_with_diarization(self) -> str:
        """Execute the full batch diarization + role-mapping pipeline.

        Returns the final relabeled dialogue transcript with "Doctor:" and
        "Patient:" prefixes, or the raw streaming transcript if diarization
        is not possible.
        """
        wav_path = await self._buffer.get_wav_file()

        if wav_path is None:
            logger.warning(
                "HybridSTTProvider: no audio buffered, returning stream transcript"
            )
            return "\n".join(self._streaming_transcript_lines)

        segments = await self._run_batch_diarization(wav_path)

        if not segments:
            logger.warning(
                "HybridSTTProvider: batch diarization returned no segments, "
                "returning stream transcript"
            )
            return "\n".join(self._streaming_transcript_lines)

        # Build raw diarized transcript for the LLM snapshot
        raw_transcript = "\n".join(
            f"{seg['speaker_id']}: {seg['text']}" for seg in segments
        )

        roles = await self._map_speakers_to_roles(raw_transcript)
        final = self._relabel_transcript(segments, roles)

        await self._buffer.cleanup()
        return final

    async def _run_batch_diarization(self, wav_path: str) -> list[dict[str, Any]]:
        """Upload WAV to Sarvam's job-based STT API with diarization enabled.

        The simple ``transcribe()`` endpoint does not support diarization —
        we must use the job-based ``speech_to_text_job.create_job()`` flow
        which accepts ``with_diarization`` and ``num_speakers`` natively.

        Returns a list of segment dicts: {speaker_id, text, start, end}.
        """
        try:
            job = await self._batch_client.speech_to_text_job.create_job(
                model=self.batch_model,
                language_code=self.language_code,
                with_diarization=True,
                with_timestamps=True,
                num_speakers=self.num_speakers,
            )
            logger.info("Batch job created: %s", job.job_id)

            await job.upload_files(file_paths=[wav_path])
            logger.info("Batch job: file uploaded")

            await job.start()
            logger.info("Batch job: started, waiting for completion...")

            await job.wait_until_complete(poll_interval=3)
            logger.info("Batch job: completed")

            results = await job.get_file_results()
            logger.info("Batch job: got results type=%s keys=%s",
                        type(results).__name__,
                        list(results.keys()) if isinstance(results, dict) else "n/a")

            if results and isinstance(results, dict):
                successful = results.get("successful", [])
                logger.info("Batch result: successful=%d items", len(successful))
                for item in successful:
                    logger.info("Batch result item type=%s keys=%s repr=%s",
                                type(item).__name__,
                                list(item.keys()) if isinstance(item, dict) else "n/a",
                                repr(item)[:500])
                    if isinstance(item, dict):
                        segments = _parse_diarized_response(item)
                        if segments:
                            return segments

            # Try download_outputs as fallback — it downloads the raw JSON result files
            output_dir = f"./vault/job_output_{job.job_id}"
            downloaded = await job.download_outputs(output_dir=output_dir)
            logger.info("Batch job: download_outputs=%s dir=%s", downloaded, output_dir)
            if downloaded:
                import glob, json
                for jf in glob.glob(f"{output_dir}/**/*.json", recursive=True):
                    with open(jf) as fh:
                        data = json.load(fh)
                    logger.info("Downloaded JSON keys: %s", list(data.keys())[:20])
                    segments = _parse_diarized_response(data)
                    if segments:
                        return segments

            logger.warning("Batch job: no diarized segments in results")
            return []

        except Exception:
            logger.exception("HybridSTTProvider: batch diarization API call failed")
            return []

    async def _map_speakers_to_roles(self, transcript: str) -> ClinicRoles:
        """Use LLM structured output to identify Doctor vs Patient speaker IDs.

        Falls back to utterance-count heuristic if LLM is unavailable or fails.
        """
        if self._llm_client is None:
            logger.warning(
                "HybridSTTProvider: no LLM client — using heuristic role mapping"
            )
            return _heuristic_role_map(transcript)

        # Take first 8 lines as a behavioral snapshot
        lines = transcript.strip().split("\n")[:8]
        snapshot = "\n".join(lines)

        messages = _build_role_map_messages(snapshot)

        try:
            raw_content = ""
            async for event in self._llm_client.chat_completion(
                messages=messages,
                stream=False,
                response_format={"type": "json_object"},
                model=self._llm_model,
            ):
                if event.type == StreamEventType.TEXT_DELTA and event.text_delta:
                    raw_content += event.text_delta.content

            result = json.loads(raw_content)
            roles = ClinicRoles(**result)
            logger.info("HybridSTTProvider: LLM role map → %s", roles.reasoning)
            return roles

        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning(
                "HybridSTTProvider: LLM role map failed (%s) — using heuristic",
                exc,
            )
            return _heuristic_role_map(transcript)

    def _relabel_transcript(
        self,
        segments: list[dict[str, Any]],
        roles: ClinicRoles,
    ) -> str:
        """Swap numeric speaker IDs for explicit 'Doctor' / 'Patient' labels."""
        id_map = {
            roles.doctor_speaker_id: "Doctor",
            roles.patient_speaker_id: "Patient",
        }

        labeled: list[str] = []
        for seg in segments:
            speaker = id_map.get(seg["speaker_id"], "Unknown")
            labeled.append(f"{speaker}: {seg['text']}")

        return "\n".join(labeled)


# ---------------------------------------------------------------------------
# Helper: parse Sarvam batch diarization response
# ---------------------------------------------------------------------------

def _parse_diarized_response(response: Any) -> list[dict[str, Any]]:
    """Extract diarized segments from a Sarvam batch STT response.

    The SDK returns a ``SpeechToTextResponse`` with an optional
    ``diarized_transcript`` field of type ``DiarizedTranscript`` whose
    ``entries`` list contains ``DiarizedEntry`` objects.

    Returns a list of {speaker_id, text, start, end} dicts.
    """
    segments: list[dict[str, Any]] = []

    # Primary: SDK typed DiarizedTranscript on response.diarized_transcript
    dt = getattr(response, "diarized_transcript", None)
    if dt is not None:
        entries = getattr(dt, "entries", None) or dt
        for entry in entries:
            segments.append({
                "speaker_id": str(getattr(entry, "speaker_id", "0")),
                "text": getattr(entry, "transcript", ""),
                "start": getattr(entry, "start_time_seconds", 0.0),
                "end": getattr(entry, "end_time_seconds", 0.0),
            })
        return segments

    # Fallback: dict-style response
    if isinstance(response, dict):
        raw = response.get("diarized_transcript") or response.get("segments") or []
        if isinstance(raw, dict):
            raw = raw.get("entries", [])
        for seg in raw:
            segments.append({
                "speaker_id": str(seg.get("speaker_id", seg.get("speaker", "0"))),
                "text": seg.get("transcript", seg.get("text", "")),
                "start": seg.get("start_time_seconds", seg.get("start", 0.0)),
                "end": seg.get("end_time_seconds", seg.get("end", 0.0)),
            })
        return segments

    # Last resort: try iterating the response
    try:
        for seg in response:
            if hasattr(seg, "speaker_id"):
                segments.append({
                    "speaker_id": str(getattr(seg, "speaker_id", "")),
                    "text": getattr(seg, "transcript", getattr(seg, "text", "")),
                    "start": getattr(seg, "start_time_seconds", getattr(seg, "start", 0.0)),
                    "end": getattr(seg, "end_time_seconds", getattr(seg, "end", 0.0)),
                })
    except TypeError:
        pass

    return segments


# ---------------------------------------------------------------------------
# Heuristic fallback: speaker with more / longer utterances = Doctor
# ---------------------------------------------------------------------------

def _heuristic_role_map(transcript: str) -> ClinicRoles:
    """Assign roles based on utterance count and total character length.

    In clinical consultations the doctor typically speaks more and in longer
    turns than the patient.
    """
    speaker_utterances: dict[str, list[str]] = {}
    speaker_chars: dict[str, int] = {}

    for line in transcript.strip().split("\n"):
        if ":" not in line:
            continue
        sid, _, text = line.partition(":")
        sid = sid.strip()
        text = text.strip()
        if not text:
            continue
        speaker_utterances.setdefault(sid, []).append(text)
        speaker_chars[sid] = speaker_chars.get(sid, 0) + len(text)

    ids = list(speaker_utterances.keys())

    if len(ids) == 0:
        return ClinicRoles(
            doctor_speaker_id="NONE",
            patient_speaker_id="NONE",
            reasoning="No speakers detected",
        )
    if len(ids) == 1:
        return ClinicRoles(
            doctor_speaker_id=ids[0],
            patient_speaker_id="NONE",
            reasoning="Only one speaker detected — assigned as Doctor",
        )

    ids.sort(key=lambda sid: speaker_chars.get(sid, 0), reverse=True)
    return ClinicRoles(
        doctor_speaker_id=ids[0],
        patient_speaker_id=ids[1],
        reasoning="Heuristic: speaker with most total characters assigned as Doctor",
    )