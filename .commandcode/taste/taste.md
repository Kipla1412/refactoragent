# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# voice-agent
- Split voice agent modules into separate files per responsibility: voiceagent.py for shared utilities (VoiceSession, translate_text, LANGUAGE_MAP), voiceintake.py for VoiceIntakeAgent, voiceconsult.py for VoiceConsultAgent. Confidence: 0.60

# architecture
See [architecture/taste.md](architecture/taste.md)
# testing
See [testing/taste.md](testing/taste.md)
# workflow
See [workflow/taste.md](workflow/taste.md)
# communication
- After a multi-file fix, explicitly summarize exactly what was changed (files touched and behavioral changes) so the user can spot regressions — e.g., "what changes are u make in my code" signals they expected a clear change inventory. Confidence: 0.5
- When the assistant proposes an improvement, it should proactively justify the value and risk (e.g., "most valuable, low-risk improvement") before making the change, and hold off until the user gives a go-ahead. Confidence: 0.5
- The user reports problems by pasting raw logs/traces directly (NDJSON streaming-event dumps, backend stack traces like `opensearchpy` errors) and expects the agent to read and diagnose them directly rather than asking for more context. Confidence: 0.5
- Wants concrete, copy-pasteable answers (full `docker run` commands, `curl` commands, config snippets) rather than general explanations — asks "what i do da" / "how i check this da" and is satisfied by ready-to-run snippets. Also wants a specific value/name handed to them (e.g., "can u give me a model name please" → recommend one concrete model, not an open-ended menu). Confidence: 0.65


# diarization
- Label diarized speakers with human-readable role names (e.g., Doctor, Patient) instead of numeric speaker IDs (SPEAKER_00, 0:, 1:). Confidence: 0.70

# tooling
See [tooling/taste.md](tooling/taste.md)
# project-hygiene
- Maintain a `.env.example` file with all environment variables the project reads, ready for new developers to copy and fill in. Confidence: 0.65
- Include `CONTRIBUTING.md` with prerequisites, quick-start steps, config reference, API endpoint table, project structure map, and dependency management commands. Confidence: 0.65
- `.gitignore` must cover `.venv/` (not just `venv/`), `vault/`, `dist/`, `build/`, `*.egg-info/`, and IDE files (`.vscode/`, `.idea/`, `*.swp`). Confidence: 0.70
y management commands. Confidence: 0.65
- `.gitignore` must cover `.venv/` (not just `venv/`), `vault/`, `dist/`, `build/`, `*.egg-info/`, and IDE files (`.vscode/`, `.idea/`, `*.swp`). Confidence: 0.70
mmands. Confidence: 0.65
- `.gitignore` must cover `.venv/` (not just `venv/`), `vault/`, `dist/`, `build/`, `*.egg-info/`, and IDE files (`.vscode/`, `.idea/`, `*.swp`). Confidence: 0.70
