# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# voice-agent
- Split voice agent modules into separate files per responsibility: voiceagent.py for shared utilities (VoiceSession, translate_text, LANGUAGE_MAP), voiceintake.py for VoiceIntakeAgent, voiceconsult.py for VoiceConsultAgent. Confidence: 0.60

# architecture
- Follow the 2-file convention for new agents: {agentname}.py (agent class extending Agent) + {agentname}prompt.py (system prompt string). Confidence: 0.75
- Register new WebSocket routers in api/main.py with appropriate prefix alongside existing routers. Confidence: 0.65

# diarization
- Label diarized speakers with human-readable role names (e.g., Doctor, Patient) instead of numeric speaker IDs (SPEAKER_00, 0:, 1:). Confidence: 0.70

