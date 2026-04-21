from __future__ import annotations
from typing import AsyncGenerator, Awaitable, Callable
from agent.events import AgentEvent, AgentEventType
from agent.session import Session
from client.response import StreamEventType, TokenUsage, ToolCall, ToolResultMessage, parse_tool_call_arguments
from config.config import Config
from prompts.system import create_loop_breaker_prompt
from tools.base import ToolConfirmation
import json
import time
from datetime import datetime
import asyncio

class Agent:
    def __init__(
        self,
        config: Config,
        confirmation_callback: Callable[[ToolConfirmation], bool] | None = None,
    ):
        self.config = config
        self.session: Session | None = Session(self.config)
        
        if confirmation_callback is not None:
            self.session.approval_manager.confirmation_callback = confirmation_callback

    async def run(self, message: str):

        self.session.start_mlflow_run(message)
        
        await self.session.hook_system.trigger_before_agent(message)

        yield AgentEvent.agent_start(message)
        
        self.session.context_manager.add_user_message(message)

        final_response: str | None = None

        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")

        await self.session.hook_system.trigger_after_agent(message, final_response)

        # Extract tools used and token usage from the session
        tools_used = []  # You can populate this from the session context
        token_usage = None  # You can extract this from the LLM client response
        
        yield AgentEvent.agent_end(final_response)

        self.session.end_mlflow_run()

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        max_turns = self.config.max_turns

        for turn_num in range(max_turns):
            self.session.increment_turn()
            
            while not self.session.event_queue.empty():

                event = await self.session.event_queue.get()

                data = event["data"]
                
                print("DEBUG: agent emitting approval event", data)

                yield AgentEvent.approval_request(
                    approval_id=data["approval_id"],
                    tool_name=data["tool_name"],
                    description=data["description"],
                    params=data.get("params")
                )
            
            response_text = ""

            # check for context overflow
            if self.session.context_manager.needs_compression():
                summary, usage = await self.session.chat_compactor.compress(
                    self.session.context_manager
                )

                if summary:
                    self.session.context_manager.replace_with_summary(summary)
                    self.session.context_manager.set_latest_usage(usage)
                    self.session.context_manager.add_usage(usage)

            tool_schemas = self.session.tool_registry.get_schemas()

            tool_calls: list[ToolCall] = []
            usage: TokenUsage | None = None

            async for event in self.session.client.chat_completion(
                self.session.context_manager.get_messages(),
                tools=tool_schemas if tool_schemas else None,
            ):
                if event.type == StreamEventType.TEXT_DELTA:
                    if event.text_delta:
                        content = event.text_delta.content
                        response_text += content
                        yield AgentEvent.text_delta(content)
                elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                    if event.tool_call:
                        tool_calls.append(event.tool_call)
                elif event.type == StreamEventType.ERROR:
                    yield AgentEvent.agent_error(
                        event.error or "Unknown error occurred.",
                    )
                elif event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage

                    if usage:
                        self.session.mlflow_tracker.log_metrics({
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                            "total_tokens": usage.total_tokens
                        })

            self.session.context_manager.add_assistant_message(
                response_text or "",
                (
                    [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in tool_calls
                    ]
                    if tool_calls
                    else None
                ),
            )
            
            if response_text:
                yield AgentEvent.text_complete(response_text)
                self.session.loop_detector.record_action(
                    "response",
                    text=response_text,
                )

            if not tool_calls:
                if usage:
                    self.session.context_manager.set_latest_usage(usage)
                    self.session.context_manager.add_usage(usage)

                self.session.context_manager.prune_tool_outputs()
                return

            tool_call_results: list[ToolResultMessage] = []

            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(
                    tool_call.call_id,
                    tool_call.name,
                    tool_call.arguments,
                )

                self.session.loop_detector.record_action(
                    "tool_call",
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                )
                # parsed_args = parse_tool_call_arguments(tool_call.arguments)
                
                print(f"DEBUG: Tool {tool_call.name} called with args: {tool_call.arguments}")
                
                with self.session.mlflow_tracker.start_span(
                    name=tool_call.name,
                    attributes={
                        "span_type": "tool",
                        "tool.name": tool_call.name,
                        "tool.args": json.dumps(tool_call.arguments)[:500],
                    },
                ):
                    # result = await self.session.tool_registry.invoke(
                    #     tool_call.name,
                    #     tool_call.arguments,
                    #     self.config.cwd,
                    #     self.session.hook_system,
                    #     self.session.approval_manager,
                    # )

                    # Wrap the tool invocation in a task so it runs in the background
                    invocation_task = asyncio.create_task(
                        self.session.tool_registry.invoke(
                            tool_call.name,
                            tool_call.arguments,
                            self.config.cwd,
                            self.session.hook_system,
                            self.session.approval_manager,
                        )
                    )

                    # While the tool is running (it might be paused waiting for approval!)
                    # We "drain" the event queue and yield requests to the frontend
                    result = None
                    while not invocation_task.done():
                        try:
                            # Check queue every 0.1s. If an approval is added, yield it immediately.
                            event_data = await asyncio.wait_for(self.session.event_queue.get(), timeout=0.1)
                            data = event_data["data"]
                            yield AgentEvent.approval_request(
                                approval_id=data["approval_id"],
                                tool_name=data["tool_name"],
                                description=data["description"],
                                params=data.get("params")
                            )
                        except asyncio.TimeoutError:
                            continue 
                    
                    result = await invocation_task
                    

                    yield AgentEvent.tool_call_complete(
                        tool_call.call_id,
                        tool_call.name,
                        result,
                    )

                    tool_call_results.append(
                        ToolResultMessage(
                            tool_call_id=tool_call.call_id,
                            content=result.to_model_output(),
                            is_error=not result.success,
                        )
                    )

            for tool_result in tool_call_results:
                self.session.context_manager.add_tool_result(
                    tool_result.tool_call_id,
                    tool_result.content,
                )

            loop_detection_error = self.session.loop_detector.check_for_loop()
            if loop_detection_error:
                loop_prompt = create_loop_breaker_prompt(loop_detection_error)
                self.session.context_manager.add_user_message(loop_prompt)

            if usage:
                self.session.context_manager.set_latest_usage(usage)
                self.session.context_manager.add_usage(usage)

            self.session.context_manager.prune_tool_outputs()
        yield AgentEvent.agent_error(f"Maximum turns ({max_turns}) reached")

    async def recommend_questions(self, conversation: list[str]):

        # 1. Clear old context (IMPORTANT)
        self.session.context_manager.clear()

        # 2. Add simple system prompt
        self.session.context_manager.add_user_message("""

    You are a clinical decision support assistant for doctors.

    Your task is to analyze the given patient conversation and generate the most relevant follow-up questions that a doctor should ask next.

    Focus on identifying missing critical clinical information.

    ---

    ## Instructions

    - Generate EXACTLY 3 follow-up questions
    - Questions must be short, clear, and clinically relevant
    - Do NOT ask multiple questions in one sentence
    - Do NOT repeat information already present in the conversation
    - Do NOT repeat previously asked questions (if provided)
    - Do NOT provide diagnosis, treatment, or explanations
    - Do NOT include greetings or extra text
    - Avoid vague questions like "Can you explain more?"

    ---

    ## Clinical Thinking Strategy

    When generating questions, prioritize missing information in this order:

    1. Location of symptoms  
    2. Duration and progression  
    3. Severity or intensity  
    4. Associated symptoms  
    5. Triggers or relieving factors  
    6. Relevant medical history (only if needed)

    Always ask:
    "What is the most important missing information right now?"

    ---

    ## Context Awareness

    Use the full conversation to:
    - Avoid repetition
    - Build logically on previous answers
    - Ask deeper, more specific questions

    ---

    ## Output Format (STRICT)

    Return ONLY valid JSON. No extra text.

    {
    "questions": [
        "question 1",
        "question 2",
        "question 3"
    ]
    }
    """)

        # 3. Add conversation messages
        for msg in conversation:
            self.session.context_manager.add_user_message(msg)

        # 4. Call LLM (NO agent loop, NO streaming)
        response_text = ""
        async for event in self.session.client.chat_completion(
            self.session.context_manager.get_messages(),
            stream=False
        ):
            if hasattr(event, 'text_delta') and event.text_delta:
                response_text += event.text_delta.content
            elif hasattr(event, 'type') and event.type == 'MESSAGE_COMPLETE':
                break

        # 5. Convert to JSON safely
        try:
            return json.loads(response_text)
        except:
            return {"questions": [response_text]}

    async def generate_report(self, conversation: list[str]):

        import json

        self.session.context_manager.clear()

        self.session.context_manager.add_user_message(""" 

    You are a clinical documentation assistant for doctors.

    Your task is to analyze the full patient conversation and generate structured medical notes in a professional clinical format.

    ---

    ## Instructions

    - Use only the information present in the conversation
    - Do NOT assume missing details
    - Do NOT provide a definitive diagnosis
    - Do NOT suggest medications
    - Keep the tone clinical and professional
    - Be concise but medically meaningful
    - Use proper medical terminology
    - If information is missing, write "Not specified"

    ---

    ## Clinical Format (STRICT)

    Return ONLY valid JSON.

    {
    "subjective": {
        "chief_complaint": "",
        "history_of_present_illness": "",
        "associated_symptoms": []
    },
    "objective": {
        "observations": []
    },
    "assessment": {
        "possible_conditions": [],
        "clinical_reasoning": ""
    },
    "plan": {
        "next_steps": [],
        "when_to_seek_care": ""
    },
    "summary": ""
    }
    """)

        for msg in conversation:
            self.session.context_manager.add_user_message(msg)

        response_text = ""

        async for event in self.session.client.chat_completion(
            self.session.context_manager.get_messages(),
            tools=None
        ):
            if hasattr(event, "text_delta") and event.text_delta:
                response_text += event.text_delta.content

        try:
            return json.loads(response_text)
        except:
            return {"raw": response_text}

    async def __aenter__(self) -> Agent:
        
        await self.session.initialize()
        # for tool in self.session.tool_registry.get_tools():
        #     # Check if the tool class has a 'session' attribute
        #     if hasattr(tool, 'session'):
        #         tool.session = self.session
        #         print(f"DEBUG: Linked Session to Tool: {tool.name}")
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_val,
        exc_tb,  
    ) -> None:
        if self.session and self.session.client:
            await self.session.client.close()
            # Cleanup MLflow run
            self.session.cleanup()
            self.session = None
