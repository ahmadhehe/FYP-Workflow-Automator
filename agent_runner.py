"""
Core agent execution logic shared by the browser and flows routers.
Extracted from server.py to avoid circular imports.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import WebSocket

import app_state
from utils.flows_store import save_flow
from utils.llm_logging import setup_llm_logger, log_llm_interaction, calculate_cost
from agent import BrowserAgent, prune_history_for_llm

logger = logging.getLogger(__name__)


def _failure_key(fn_name: str, args: dict) -> tuple:
    """Compute a stable key for tracking consecutive failures of the same call."""
    for k in ('nodeId', 'url', 'text', 'key', 'tabIndex'):
        if k in args:
            return (fn_name, str(args[k]))
    return (fn_name, '')


async def broadcast_event(event: Dict[str, Any]):
    """Broadcast a JSON event to all connected WebSocket clients (deduplicated by id)."""
    if not app_state.websocket_clients:
        return
    message = json.dumps(event, default=str)
    disconnected = []
    seen = set()
    for ws in app_state.websocket_clients:
        ws_id = id(ws)
        if ws_id in seen:
            disconnected.append(ws)
            continue
        seen.add(ws_id)
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in app_state.websocket_clients:
            app_state.websocket_clients.remove(ws)


class EventEmitter:
    """Collects actions and broadcasts events during agent execution."""

    def __init__(self, flow_id: str):
        self.flow_id = flow_id
        self.actions: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

    async def emit(self, event_type: str, data: Dict[str, Any]):
        event = {
            "type": event_type,
            "flow_id": self.flow_id,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        if event_type == "action":
            self.actions.append(data)
        await broadcast_event(event)

    def get_actions(self) -> List[Dict[str, Any]]:
        return self.actions


def _create_and_start_agent(provider: str, headless: bool, use_profile: bool = True) -> BrowserAgent:
    """Sync — runs in the Playwright thread pool."""
    print(f"[Server] Creating agent with provider={provider}, headless={headless}, use_profile={use_profile}")
    new_agent = BrowserAgent(
        provider=provider,
        headless=headless,
        use_profile=use_profile,
        google_sheets_client=app_state.google_sheets_client,
    )
    new_agent.start()
    print("[Server] Agent started successfully")
    return new_agent


def _run_agent_sync(agent: BrowserAgent, instruction: str, initial_url: Optional[str], file_context: Optional[str] = None) -> str:
    return agent.run(user_instruction=instruction, initial_url=initial_url, file_context=file_context)


def _collect_page_text_fallback(agent: BrowserAgent) -> Dict[str, Any]:
    """Runs in the Playwright thread. Returns truncated page text + URL/title."""
    page = agent.browser.page
    try:
        text = page.evaluate(
            "() => (document.body && document.body.innerText || '').slice(0, 4000)"
        )
    except Exception:
        text = ''
    url = ''
    title = ''
    try:
        url = page.url
    except Exception:
        pass
    try:
        title = page.title()
    except Exception:
        pass
    return {'url': url, 'title': title, 'pageText': text}


async def run_agent_task(
    instruction: str,
    initial_url: Optional[str],
    provider: str,
    flow_id: str,
    emitter: EventEmitter,
    file_context: Optional[str] = None,
    file_name: Optional[str] = None,
    files: Optional[List[Dict[str, str]]] = None,
    original_instruction: Optional[str] = None,
):
    """
    Run the agent for a single task, emit events, persist the flow.

    `instruction` is the enriched prompt (may include LMS context prefix).
    `original_instruction` is what gets stored in history (no credentials).
    If original_instruction is None, instruction is stored as-is.
    """
    result = ""
    error = None
    status = "completed"
    stored_instruction = original_instruction if original_instruction is not None else instruction

    # Capture the running asyncio loop so the Playwright executor thread can
    # schedule WS broadcasts back onto it (e.g. for requestUserAction).
    try:
        app_state._event_loop = asyncio.get_running_loop()
    except RuntimeError:
        app_state._event_loop = asyncio.get_event_loop()

    try:
        if not app_state.agent:
            await emitter.emit("status", {"message": "Starting browser...", "status": "initializing"})
            loop = asyncio.get_event_loop()
            app_state.agent = await loop.run_in_executor(
                app_state.playwright_executor, _create_and_start_agent, provider, False, True
            )
        elif app_state.agent.provider != provider:
            await emitter.emit("status", {"message": f"Switching to {provider}...", "status": "initializing"})
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(app_state.playwright_executor, app_state.agent.set_provider, provider)

        await emitter.emit("status", {"message": "Task started", "status": "running"})

        llm_logger = setup_llm_logger(flow_id)
        llm_logger.info(f"Starting workflow: {stored_instruction}")
        llm_logger.info(f"Provider: {provider}")
        llm_logger.info(f"Initial URL: {initial_url}")
        if files:
            for f in files:
                llm_logger.info(f"File attached: {f.get('name')} ({len(f.get('content', ''))} chars)")
            llm_logger.info("")
        elif file_context:
            llm_logger.info(f"File attached: {file_name}")
            llm_logger.info(f"File content length: {len(file_context)} characters\n")
        else:
            llm_logger.info("")

        # Merge course files (keyed by original filename) + manually attached files
        course_file_paths = getattr(app_state, '_course_file_paths', {}) or {}
        manual_file_paths = {f['name']: f['path'] for f in (files or []) if f.get('path')}
        app_state.agent.uploaded_file_paths = {**course_file_paths, **manual_file_paths}

        result = await run_agent_with_events(
            app_state.agent, instruction, initial_url, emitter, llm_logger, file_context, file_name, files
        )

        if app_state.stop_requested:
            status = "stopped"
            await emitter.emit("status", {"message": "Task stopped", "status": "stopped"})
        else:
            await emitter.emit("status", {"message": "Task completed", "status": "completed"})

    except Exception as e:
        error = str(e)
        status = "failed"
        await emitter.emit("error", {"message": error})
        await emitter.emit("status", {"message": f"Task failed: {error}", "status": "failed"})

    finally:
        app_state.stop_requested = False
        # Clear any lingering intervention state and unblock the Playwright
        # thread if it was waiting (e.g. after a stop or unhandled error).
        if app_state.intervention_pending:
            app_state.intervention_pending = False
            app_state.intervention_response = ''
            app_state.intervention_event.set()
        app_state.intervention_message = None
        app_state.intervention_reason = None
        token_usage = app_state.agent.get_token_usage() if app_state.agent else {
            'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0
        }
        cost_data = calculate_cost(provider, token_usage['input_tokens'], token_usage['output_tokens'])

        if 'llm_logger' in locals():
            llm_logger.info(f"\n{'='*80}")
            llm_logger.info("WORKFLOW COMPLETE")
            llm_logger.info(f"{'='*80}")
            llm_logger.info(f"Status: {status}")
            llm_logger.info(f"Total Input Tokens: {token_usage['input_tokens']:,}")
            llm_logger.info(f"Total Output Tokens: {token_usage['output_tokens']:,}")
            llm_logger.info(f"Total Tokens: {token_usage['total_tokens']:,}")
            llm_logger.info(f"Total Cost: ${cost_data['total_cost']:.6f}")
            if error:
                llm_logger.error(f"Error: {error}")
            for handler in llm_logger.handlers:
                handler.close()
                llm_logger.removeHandler(handler)

        flow = {
            "id": flow_id,
            "instruction": stored_instruction,
            "initial_url": initial_url,
            "provider": provider,
            "status": status,
            "result": result,
            "error": error,
            "actions": emitter.get_actions(),
            "created_at": emitter.start_time.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "input_tokens": token_usage['input_tokens'],
            "output_tokens": token_usage['output_tokens'],
            "total_tokens": token_usage['total_tokens'],
            "input_cost": cost_data['input_cost'],
            "output_cost": cost_data['output_cost'],
            "total_cost": cost_data['total_cost'],
        }
        save_flow(flow)

        await emitter.emit("complete", {
            "flow_id": flow_id,
            "result": result,
            "status": status,
            "error": error,
        })

        app_state.current_task = None

    return result, error


async def run_agent_with_events(
    agent: BrowserAgent,
    instruction: str,
    initial_url: Optional[str],
    emitter: EventEmitter,
    llm_logger: logging.Logger = None,
    file_context: Optional[str] = None,
    file_name: Optional[str] = None,
    files: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Drive the agent loop, emitting WebSocket events for each action."""
    import json as json_module

    await emitter.emit("action", {
        "type": "start",
        "message": f"Starting task: {instruction}",
        "iteration": 0,
    })

    if initial_url:
        await emitter.emit("action", {
            "type": "navigate",
            "message": f"Navigating to {initial_url}",
            "url": initial_url,
            "iteration": 0,
        })
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(app_state.playwright_executor, agent.browser.navigate, initial_url)

    # Build user message with optional file context
    user_message = instruction
    if files:
        parts = [f"[File {i+1}: {f['name']}]\n{f.get('content', '')}" for i, f in enumerate(files)]
        user_message = f"{instruction}\n\n[Attached Files]\n" + "\n\n".join(parts)
        for f in files:
            await emitter.emit("action", {
                "type": "file_attached",
                "message": f"File attached: {f['name']}",
                "file_name": f['name'],
                "iteration": 0,
            })
    elif file_context:
        user_message = f"{instruction}\n\n[File Context Provided by User ({file_name})]:\n{file_context}"
        await emitter.emit("action", {
            "type": "file_attached",
            "message": f"File attached: {file_name}",
            "file_name": file_name,
            "iteration": 0,
        })

    agent.conversation_history = [
        {'role': 'system', 'content': agent.llm.get_system_prompt()},
        {'role': 'user', 'content': user_message},
    ]
    agent.reset_token_tracking()
    tools = agent.llm.get_tools_definition()

    # Reset cancellation flag for this run
    app_state.stop_requested = False

    # Circuit breaker: track consecutive snapshot failures. If getInteractiveSnapshot
    # fails twice in a row, on the next call we substitute a page-text fallback so
    # the LLM can keep progressing instead of burning tokens looping.
    snapshot_failure_streak = 0
    SNAPSHOT_FAILURE_THRESHOLD = 2

    # Adaptive recovery: track consecutive failures per (tool, key_arg) pair.
    # key: (function_name, primary_arg_value)  value: int count
    tool_failure_streaks: Dict[tuple, int] = {}

    # Loop detection: track recent tool calls to catch infinite loops
    recent_tools: List[str] = []

    for iteration in range(agent.max_iterations):
        if app_state.stop_requested:
            await emitter.emit("action", {
                "type": "stopped",
                "message": "Task stopped by user",
                "iteration": iteration + 1,
            })
            return "Task stopped by user."

        await emitter.emit("iteration", {"current": iteration + 1, "max": agent.max_iterations})

        try:
            await emitter.emit("action", {
                "type": "thinking",
                "message": "Agent is thinking...",
                "iteration": iteration + 1,
            })

            response = await asyncio.to_thread(
                agent.llm.chat_completion,
                prune_history_for_llm(agent.conversation_history),
                tools,
                'auto',
            )

            if hasattr(response, 'usage') and response.usage:
                agent.total_input_tokens += response.usage.get('input_tokens', 0)
                agent.total_output_tokens += response.usage.get('output_tokens', 0)

            if llm_logger:
                await asyncio.to_thread(
                    log_llm_interaction, llm_logger, iteration + 1,
                    agent.conversation_history, response, agent.provider
                )

        except Exception as e:
            await emitter.emit("error", {"message": f"LLM Error: {e}"})
            return f"Error: {e}"

        if response.content and not response.tool_calls:
            agent.conversation_history.append({'role': 'assistant', 'content': response.content})
            await emitter.emit("action", {
                "type": "complete",
                "message": response.content,
                "iteration": iteration + 1,
            })
            return response.content

        if response.tool_calls:
            tool_calls_data = []
            for tc in response.tool_calls:
                entry = {
                    'id': tc.id,
                    'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                }
                sig = getattr(tc, 'thought_signature', None)
                if sig:
                    entry['thought_signature'] = sig
                tool_calls_data.append(entry)
            history_entry = {
                'role': 'assistant',
                'content': response.content,
                'tool_calls': tool_calls_data,
            }
            gemini_content = getattr(response, '_gemini_content', None)
            if gemini_content is not None:
                history_entry['_gemini_content'] = gemini_content
            agent.conversation_history.append(history_entry)

            for tool_call in response.tool_calls:
                if app_state.stop_requested:
                    await emitter.emit("action", {
                        "type": "stopped",
                        "message": "Task stopped by user",
                        "iteration": iteration + 1,
                    })
                    return "Task stopped by user."

                function_name = tool_call.function.name
                try:
                    arguments = json_module.loads(tool_call.function.arguments)
                except json_module.JSONDecodeError:
                    arguments = {}

                await emitter.emit("action", {
                    "type": "tool_call",
                    "tool": function_name,
                    "arguments": arguments,
                    "message": f"Executing: {function_name}",
                    "iteration": iteration + 1,
                })

                try:
                    logger.debug("Executing tool: %s with args: %s", function_name, arguments)
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        app_state.playwright_executor, agent.execute_tool, function_name, arguments
                    )
                    logger.debug("Tool result: %s", result)
                except Exception as tool_error:
                    logger.error("Tool error: %s", tool_error)
                    result = {'error': str(tool_error), 'success': False}

                success = result.get('success', True) if not result.get('error') else False

                # Adaptive recovery: enrich failure results with structured context
                key = _failure_key(function_name, arguments)
                if not success:
                    tool_failure_streaks[key] = tool_failure_streaks.get(key, 0) + 1
                    streak = tool_failure_streaks[key]
                    result['_recovery'] = {
                        'attempt': streak,
                        'tool': function_name,
                        'strategies_exhausted': streak >= 2,
                    }
                    if streak >= 2:
                        agent.conversation_history.append({
                            'role': 'user',
                            'content': (
                                f"RECOVERY NEEDED: {function_name}({arguments}) has failed {streak} times in a row. "
                                f"Do NOT repeat it with the same arguments. "
                                f"Diagnose from the error above and try a fundamentally different approach."
                            )
                        })
                else:
                    tool_failure_streaks.pop(key, None)

                # Snapshot circuit breaker — replace third+ consecutive failure with a
                # page-text fallback so the agent can keep moving.
                if function_name == 'getInteractiveSnapshot':
                    if not success:
                        snapshot_failure_streak += 1
                        if snapshot_failure_streak > SNAPSHOT_FAILURE_THRESHOLD:
                            try:
                                fallback = await loop.run_in_executor(
                                    app_state.playwright_executor,
                                    _collect_page_text_fallback,
                                    agent,
                                )
                                result = {
                                    'success': False,
                                    'error': 'Interactive snapshot unavailable; using page-text fallback.',
                                    'hint': (
                                        'Structured snapshot failed repeatedly. Work from this page text: '
                                        'navigate by URL, or use clickByText with any visible label below. '
                                        'Do NOT call getInteractiveSnapshot again until you navigate or scroll.'
                                    ),
                                    'fallback': True,
                                    'url': fallback.get('url'),
                                    'title': fallback.get('title'),
                                    'pageText': fallback.get('pageText'),
                                    'elements': [],
                                }
                            except Exception as fb_err:
                                logger.warning("Page-text fallback failed: %s", fb_err)
                    else:
                        snapshot_failure_streak = 0

                await emitter.emit("action", {
                    "type": "tool_result",
                    "tool": function_name,
                    "success": success,
                    "message": (
                        f"{function_name} {'succeeded' if success else 'failed'}"
                        + (f": {result.get('url', '')}" if function_name == 'navigate' and success else "")
                    ),
                    "iteration": iteration + 1,
                })

                agent.conversation_history.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': json_module.dumps(result, default=str),
                })

                # Loop detection: catch when the same tool is called 3+ times in a row
                recent_tools.append(function_name)
                if len(recent_tools) > 6:
                    recent_tools.pop(0)
                if len(recent_tools) >= 3 and len(set(recent_tools[-3:])) == 1:
                    repeated = recent_tools[-1]
                    if repeated == 'getInteractiveSnapshot':
                        hint = "LOOP: Stop calling getInteractiveSnapshot. Read _snapshot.elements from the last successful action and act directly."
                    else:
                        hint = f"LOOP: {repeated} called 3+ times in a row. Switch to a different tool or approach entirely."
                    agent.conversation_history.append({'role': 'user', 'content': hint})

        await asyncio.sleep(0.1)

    return "Task incomplete - reached maximum iterations."
