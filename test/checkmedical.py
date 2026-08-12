import asyncio
from config.config import Config
from customagents.medicalagent.medicalagent import MedicalAgent


async def main():
    config = Config()

    print("=" * 60)
    print("  MEDICAL AGENT — Interactive Console Test")
    print("=" * 60)
    print()
    print("Ask medical knowledge questions. The agent uses:")
    print("  • wiki_search  — patient records, diseases, medications")
    print("  • neo4j_query  — graph relationships")
    print()
    print("Try:")
    print('  "What medications is Elizabeth Williams taking?"')
    print('  "Who treats Rajesh Kumar?"')
    print('  "Summarize the diabetes information available"')
    print()
    print("Type 'exit' or 'quit' to stop.")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        if not user_input.strip():
            continue

        print()
        agent = MedicalAgent(config)
        await agent.session.initialize()

        async for event in agent.run(user_input):
            if event.type == "tool_call_start":
                name = event.data.get("name", "")
                args = event.data.get("arguments", {})
                print(f"\n🔧 Calling {name}({_brief(args)})")

            elif event.type == "tool_call_complete":
                success = event.data.get("success", False)
                output = event.data.get("output", "")[:200]
                status = "✓" if success else "✗"
                error = event.data.get("error", "")
                preview = error or output
                print(f"   {status} {preview[:150]}")

            elif event.type == "text_delta":
                content = event.data.get("content", "")
                print(content, end="", flush=True)

            elif event.type == "text_complete":
                pass

            elif event.type == "agent_error":
                error = event.data.get("error", "")
                print(f"\n❌ Error: {error[:200]}")

        print()


def _brief(d: dict) -> str:
    """Shorten dict for display."""
    s = str(d)
    return s if len(s) <= 100 else s[:97] + "..."


if __name__ == "__main__":
    asyncio.run(main())
