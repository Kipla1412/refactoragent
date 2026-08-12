# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# voice-agent
- Split voice agent modules into separate files per responsibility: voiceagent.py for shared utilities (VoiceSession, translate_text, LANGUAGE_MAP), voiceintake.py for VoiceIntakeAgent, voiceconsult.py for VoiceConsultAgent. Confidence: 0.60

# architecture
See [architecture/taste.md](architecture/taste.md)
# testing
- Test files for agents live in `test/` with the naming convention `check{agentname}.py` (e.g., `checkmedical.py` for MedicalAgent). Confidence: 0.55
- Structure agent test files as: multiple `async def test_*()` functions (one per scenario), a shared `_print_event(event)` helper that switches on event type (`agent_start`/`agent_end`/`text_delta`/`text_complete`/`tool_call_start`/`tool_call_complete`), an `async def main()` orchestrator, and `asyncio.run(main())` at the bottom. Confidence: 0.65
- Prefers interactive conversation-based (REPL-style) testcases where the user types questions and sees live streaming tool calls and text deltas, over automated batch test functions — but both modes can coexist in different test files. Confidence: 0.75
- Include a "sanity check" that exercises tools directly (bypassing the agent) before running full agent integration tests — verifies tool registration and basic execution before diagnosing agent-level issues. Confidence: 0.60
- Interactive REPL tests create a fresh agent per query, call `agent.session.initialize()` before `agent.run(message)`, and stream events live — `tool_call_start` prints the tool name + arg preview, `tool_call_complete` prints the result preview, `text_delta` prints content inline. Confidence: 0.70

# workflow
- Prefer explore-plan-implement workflow for non-trivial feature additions: thoroughly explore the existing codebase to understand patterns, write a concrete implementation plan, then execute from the plan. Confidence: 0.65

# diarization
- Label diarized speakers with human-readable role names (e.g., Doctor, Patient) instead of numeric speaker IDs (SPEAKER_00, 0:, 1:). Confidence: 0.70

# tooling
See [tooling/taste.md](tooling/taste.md)
# project-hygiene
- Maintain a `.env.example` file with all environment variables the project reads, ready for new developers to copy and fill in. Confidence: 0.65
- Include `CONTRIBUTING.md` with prerequisites, quick-start steps, config reference, API endpoint table, project structure map, and dependency management commands. Confidence: 0.65
- `.gitignore` must cover `.venv/` (not just `venv/`), `vault/`, `dist/`, `build/`, `*.egg-info/`, and IDE files (`.vscode/`, `.idea/`, `*.swp`). Confidence: 0.70
