# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# voice-agent
- Split voice agent modules into separate files per responsibility: voiceagent.py for shared utilities (VoiceSession, translate_text, LANGUAGE_MAP), voiceintake.py for VoiceIntakeAgent, voiceconsult.py for VoiceConsultAgent. Confidence: 0.60
- Voice agents should greet the user on session start with a per-agent-type greeting (intake vs consult differ) and emit a status event protocol over the WebSocket (greeting → ready → thinking → ready) so the frontend can render a visible listening/processing indicator — explicitly asked to "add the initial greeting message and when the agent is ready to answer it, i want to show". Confidence: 0.7

# architecture
See [architecture/taste.md](architecture/taste.md)
# testing
See [testing/taste.md](testing/taste.md)
# workflow
See [workflow/taste.md](workflow/taste.md)
# communication
See [communication/taste.md](communication/taste.md)
# diarization
- Label diarized speakers with human-readable role names (e.g., Doctor, Patient) instead of numeric speaker IDs (SPEAKER_00, 0:, 1:). Confidence: 0.70
- When assigning roles to diarized speakers, prefer content-aware LLM reasoning (who asks diagnostic questions / reports symptoms) over a simple "most words = Doctor" heuristic — explicitly chose the accurate option ("labels become accurate. best one") even though it adds one LLM call per session, while keeping the heuristic as a fallback so a failed or malformed LLM response never breaks the transcript. Confidence: 0.70

# tooling
See [tooling/taste.md](tooling/taste.md)
# project-hygiene
See [project-hygiene/taste.md](project-hygiene/taste.md)
