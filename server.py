"""
FastAPI Server - REST API + WebSocket for browser automation agent
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from agent import BrowserAgent
from browser_controller import BrowserController, DEFAULT_PROFILE_DIR
from dotenv import load_dotenv
import uvicorn
import asyncio
import json
import os
import uuid
import shutil
import logging
from pathlib import Path

load_dotenv()

# ============================================================================
# LLM Interaction Logging Setup
# ============================================================================

LLM_LOG_DIR = Path("llm_logs")
LLM_LOG_DIR.mkdir(exist_ok=True)

def setup_llm_logger(flow_id: str) -> logging.Logger:
    """Create a logger for a specific workflow to track LLM interactions"""
    logger = logging.getLogger(f"llm_interaction_{flow_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Clear any existing handlers
    
    # Create log file for this workflow
    log_file = LLM_LOG_DIR / f"{flow_id}.log"
    handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    handler.setLevel(logging.INFO)
    
    # Format: timestamp - level - message
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def log_llm_interaction(logger: logging.Logger, iteration: int, messages: List[Dict], response: Any, provider: str):
    """Log detailed LLM interaction for cost analysis"""
    logger.info(f"\n{'='*80}")
    logger.info(f"ITERATION {iteration} - Provider: {provider}")
    logger.info(f"{'='*80}\n")
    
    # Log input messages
    logger.info("INPUT MESSAGES:")
    for i, msg in enumerate(messages):
        logger.info(f"\n--- Message {i+1} ({msg.get('role', 'unknown')}) ---")
        if msg.get('content'):
            content = msg['content']
            if len(content) > 1000:
                logger.info(f"{content[:500]}...\n[TRUNCATED {len(content)} chars total]\n...{content[-500:]}")
            else:
                logger.info(content)
        if msg.get('tool_calls'):
            logger.info(f"Tool Calls: {json.dumps(msg['tool_calls'], indent=2)}")
    
    # Log response
    logger.info(f"\n{'='*40}")
    logger.info("LLM RESPONSE:")
    logger.info(f"{'='*40}\n")
    if hasattr(response, 'content') and response.content:
        logger.info(f"Content: {response.content}")
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info("\nTool Calls:")
        for tc in response.tool_calls:
            logger.info(f"  - {tc.function.name}: {tc.function.arguments}")
    
    # Log token usage if available
    if hasattr(response, 'usage') and response.usage:
        logger.info(f"\n{'='*40}")
        logger.info("TOKEN USAGE:")
        logger.info(f"{'='*40}")
        logger.info(f"Input tokens:  {response.usage.get('input_tokens', 0):,}")
        logger.info(f"Output tokens: {response.usage.get('output_tokens', 0):,}")
        logger.info(f"Total tokens:  {response.usage.get('total_tokens', 0):,}")
        
        # Calculate cost for this specific call
        input_tokens = response.usage.get('input_tokens', 0)
        output_tokens = response.usage.get('output_tokens', 0)
        # We'll calculate cost inline to avoid circular import
        pricing = {
            "openai": {"input": 10, "output": 30},
            "anthropic": {"input": 3, "output": 15},
            "gemini": {"input": 0.075, "output": 0.30}
        }
        p = pricing.get(provider, pricing["openai"])
        cost = (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]
        logger.info(f"\nCost for this call: ${cost:.6f}")
    
    logger.info(f"\n{'='*80}\n")

app = FastAPI(title="Browser Automation Agent API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Data Storage (File-based for simplicity)
# ============================================================================

FLOWS_FILE = "flows_history.json"

def load_flows() -> List[Dict[str, Any]]:
    """Load flows from file"""
    if os.path.exists(FLOWS_FILE):
        try:
            with open(FLOWS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_flows(flows: List[Dict[str, Any]]):
    """Save flows to file"""
    with open(FLOWS_FILE, 'w') as f:
        json.dump(flows, f, indent=2, default=str)

def save_flow(flow: Dict[str, Any]):
    """Add or update a flow"""
    flows = load_flows()
    existing_idx = next((i for i, f in enumerate(flows) if f['id'] == flow['id']), None)
    if existing_idx is not None:
        flows[existing_idx] = flow
    else:
        flows.insert(0, flow)
    flows = flows[:50]  # Keep only last 50 flows
    save_flows(flows)

# ============================================================================
# Models
# ============================================================================

class TaskRequest(BaseModel):
    instruction: str
    initial_url: Optional[str] = None
    provider: Optional[str] = None
    flow_id: Optional[str] = None

class TaskResponse(BaseModel):
    success: bool
    result: str
    flow_id: str
    error: Optional[str] = None

class FlowUpdate(BaseModel):
    instruction: str

# ============================================================================
# Global State
# ============================================================================

agent: Optional[BrowserAgent] = None
current_task: Optional[Dict[str, Any]] = None
task_lock = asyncio.Lock()
websocket_clients: List[WebSocket] = []

# Profile browser state (separate from automation agent)
profile_browser: Optional[BrowserController] = None

# ============================================================================
# WebSocket Management
# ============================================================================

async def broadcast_event(event: Dict[str, Any]):
    """Broadcast event to all connected WebSocket clients"""
    if not websocket_clients:
        return
    
    message = json.dumps(event, default=str)
    disconnected = []
    
    for ws in websocket_clients:
        try:
            await ws.send_text(message)
        except:
            disconnected.append(ws)
    
    for ws in disconnected:
        if ws in websocket_clients:
            websocket_clients.remove(ws)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    websocket_clients.append(websocket)
    
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {
                "running": agent is not None,
                "current_task": current_task
            }
        }))
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "keepalive"}))
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)

# ============================================================================
# Event Emitter for Agent
# ============================================================================

class EventEmitter:
    """Emits events during agent execution"""
    
    def __init__(self, flow_id: str):
        self.flow_id = flow_id
        self.actions: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
    
    async def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to all WebSocket clients"""
        event = {
            "type": event_type,
            "flow_id": self.flow_id,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        if event_type == "action":
            self.actions.append(data)
        
        await broadcast_event(event)
    
    def get_actions(self) -> List[Dict[str, Any]]:
        return self.actions

# ============================================================================
# Agent Execution (Async wrapper using thread pool for sync Playwright)
# ============================================================================

def _create_and_start_agent(provider: str, headless: bool, use_profile: bool = True) -> BrowserAgent:
    """Synchronous function to create and start agent (runs in thread pool)"""
    print(f"[Server] Creating agent with provider={provider}, headless={headless}, use_profile={use_profile}")
    agent = BrowserAgent(provider=provider, headless=headless, use_profile=use_profile)
    agent.start()
    print(f"[Server] Agent started successfully")
    return agent

def _run_agent_sync(agent: BrowserAgent, instruction: str, initial_url: Optional[str]) -> str:
    """Synchronous function to run the agent (runs in thread pool)"""
    return agent.run(user_instruction=instruction, initial_url=initial_url)

async def run_agent_task(
    instruction: str,
    initial_url: Optional[str],
    provider: str,
    flow_id: str,
    emitter: EventEmitter
):
    """Run agent task with event emission"""
    global agent, current_task
    
    result = ""
    error = None
    status = "completed"
    
    try:
        if not agent:
            await emitter.emit("status", {"message": "Starting browser...", "status": "initializing"})
            # Run sync Playwright code in thread pool
            agent = await asyncio.to_thread(_create_and_start_agent, provider, False)
        elif agent.provider != provider:
            # Provider changed, update the LLM client
            await emitter.emit("status", {"message": f"Switching to {provider}...", "status": "initializing"})
            await asyncio.to_thread(agent.set_provider, provider)
        
        await emitter.emit("status", {"message": "Task started", "status": "running"})
        
        # Setup LLM logger for this workflow
        llm_logger = setup_llm_logger(flow_id)
        llm_logger.info(f"Starting workflow: {instruction}")
        llm_logger.info(f"Provider: {provider}")
        llm_logger.info(f"Initial URL: {initial_url}\n")
        
        # Run the agent in a thread pool to avoid blocking the event loop
        result = await run_agent_with_events(agent, instruction, initial_url, emitter, llm_logger)
        
        await emitter.emit("status", {"message": "Task completed", "status": "completed"})
        
    except Exception as e:
        error = str(e)
        status = "failed"
        await emitter.emit("error", {"message": error})
        await emitter.emit("status", {"message": f"Task failed: {error}", "status": "failed"})
    
    finally:
        # Get token usage and calculate cost
        token_usage = agent.get_token_usage() if agent else {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        cost_data = calculate_cost(provider, token_usage['input_tokens'], token_usage['output_tokens'])
        
        # Log final workflow summary
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
            # Close logger handlers
            for handler in llm_logger.handlers:
                handler.close()
                llm_logger.removeHandler(handler)
        
        flow = {
            "id": flow_id,
            "instruction": instruction,
            "initial_url": initial_url,
            "provider": provider,
            "status": status,
            "result": result,
            "error": error,
            "actions": emitter.get_actions(),
            "created_at": emitter.start_time.isoformat(),
            "completed_at": datetime.now().isoformat(),
            # Add actual token usage and costs
            "input_tokens": token_usage['input_tokens'],
            "output_tokens": token_usage['output_tokens'],
            "total_tokens": token_usage['total_tokens'],
            "input_cost": cost_data['input_cost'],
            "output_cost": cost_data['output_cost'],
            "total_cost": cost_data['total_cost']
        }
        save_flow(flow)
        
        await emitter.emit("complete", {
            "flow_id": flow_id,
            "result": result,
            "status": status,
            "error": error
        })
        
        current_task = None
    
    return result, error

async def run_agent_with_events(
    agent: BrowserAgent,
    instruction: str,
    initial_url: Optional[str],
    emitter: EventEmitter,
    llm_logger: logging.Logger = None
) -> str:
    """Run agent with event emission for each action"""
    import json as json_module
    
    await emitter.emit("action", {
        "type": "start",
        "message": f"Starting task: {instruction}",
        "iteration": 0
    })
    
    if initial_url:
        await emitter.emit("action", {
            "type": "navigate",
            "message": f"Navigating to {initial_url}",
            "url": initial_url,
            "iteration": 0
        })
        # Run sync navigate in thread pool
        await asyncio.to_thread(agent.browser.navigate, initial_url)
    
    agent.conversation_history = [
        {'role': 'system', 'content': agent.llm.get_system_prompt()},
        {'role': 'user', 'content': instruction}
    ]
    
    # Reset token tracking for this workflow
    agent.reset_token_tracking()
    
    tools = agent.llm.get_tools_definition()
    
    for iteration in range(agent.max_iterations):
        await emitter.emit("iteration", {
            "current": iteration + 1,
            "max": agent.max_iterations
        })
        
        try:
            await emitter.emit("action", {
                "type": "thinking",
                "message": "Agent is thinking...",
                "iteration": iteration + 1
            })
            
            # LLM calls are I/O bound, run in thread pool
            response = await asyncio.to_thread(
                agent.llm.chat_completion,
                agent.conversation_history,
                tools,
                'auto'
            )
            
            # Track token usage from this response
            if hasattr(response, 'usage') and response.usage:
                agent.total_input_tokens += response.usage.get('input_tokens', 0)
                agent.total_output_tokens += response.usage.get('output_tokens', 0)
            
            # Log the LLM interaction for cost analysis
            if llm_logger:
                await asyncio.to_thread(
                    log_llm_interaction,
                    llm_logger,
                    iteration + 1,
                    agent.conversation_history,
                    response,
                    agent.provider
                )
                
        except Exception as e:
            await emitter.emit("error", {"message": f"LLM Error: {e}"})
            return f"Error: {e}"
        
        if response.content and not response.tool_calls:
            agent.conversation_history.append({
                'role': 'assistant',
                'content': response.content
            })
            
            await emitter.emit("action", {
                "type": "complete",
                "message": response.content,
                "iteration": iteration + 1
            })
            
            return response.content
        
        if response.tool_calls:
            tool_calls_data = []
            for tc in response.tool_calls:
                tool_calls_data.append({
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    }
                })
            
            agent.conversation_history.append({
                'role': 'assistant',
                'content': response.content,
                'tool_calls': tool_calls_data
            })
            
            for tool_call in response.tool_calls:
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
                    "iteration": iteration + 1
                })
                
                # Run sync tool execution in thread pool
                try:
                    print(f"[Server] Executing tool: {function_name} with args: {arguments}")
                    result = await asyncio.to_thread(agent.execute_tool, function_name, arguments)
                    print(f"[Server] Tool result: {result}")
                except Exception as tool_error:
                    print(f"[Server] Tool error: {tool_error}")
                    result = {'error': str(tool_error), 'success': False}
                
                # Check success - look at both 'error' field and 'success' field
                success = result.get('success', True) if not result.get('error') else False
                await emitter.emit("action", {
                    "type": "tool_result",
                    "tool": function_name,
                    "success": success,
                    "message": f"{function_name} {'succeeded' if success else 'failed'}" + (f": {result.get('url', '')}" if function_name == 'navigate' and success else ""),
                    "iteration": iteration + 1
                })
                
                agent.conversation_history.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': json_module.dumps(result, default=str)
                })
        
        await asyncio.sleep(0.1)
    
    return "Task incomplete - reached maximum iterations."

# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Browser Automation Agent API",
        "version": "2.0.0",
        "endpoints": {
            "POST /start": "Start browser agent",
            "POST /stop": "Stop browser agent",
            "POST /task": "Run automation task",
            "GET /status": "Get agent status",
            "GET /flows": "Get flow history",
            "GET /flows/{id}": "Get specific flow",
            "PUT /flows/{id}": "Update flow instruction",
            "DELETE /flows/{id}": "Delete flow",
            "POST /flows/{id}/rerun": "Re-run a flow",
            "WS /ws": "WebSocket for real-time updates"
        }
    }

@app.post("/start")
async def start_browser(provider: str = "openai", headless: bool = False):
    """Start the browser agent"""
    global agent
    
    try:
        if agent:
            return {"status": "already_running", "message": "Browser is already running"}
        
        # Run sync Playwright code in thread pool
        agent = await asyncio.to_thread(_create_and_start_agent, provider, headless)
        
        await broadcast_event({
            "type": "browser_started",
            "data": {"provider": provider, "headless": headless}
        })
        
        return {
            "status": "started",
            "provider": provider,
            "headless": headless
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _close_agent(agent_instance: BrowserAgent):
    """Synchronous function to close agent (runs in thread pool)"""
    agent_instance.close()

@app.post("/stop")
async def stop_browser():
    """Stop the browser agent"""
    global agent, current_task
    
    try:
        if not agent:
            return {"status": "not_running", "message": "Browser is not running"}
        
        if current_task:
            return {"status": "busy", "message": "Cannot stop while task is running"}
        
        # Run sync close in thread pool
        await asyncio.to_thread(_close_agent, agent)
        agent = None
        
        await broadcast_event({
            "type": "browser_stopped",
            "data": {}
        })
        
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Profile Browser Management
# ============================================================================

def _start_profile_browser() -> BrowserController:
    """Synchronous function to start profile browser (runs in thread pool)"""
    browser = BrowserController(headless=False, use_profile=True)
    browser.start()
    return browser

def _close_profile_browser(browser: BrowserController):
    """Synchronous function to close profile browser (runs in thread pool)"""
    browser.close()

@app.post("/profile/start")
async def start_profile_browser(url: str = None):
    """
    Launch a browser for setting up profiles (logging into websites).
    The browser uses a persistent profile that saves cookies, localStorage,
    and credentials. Users can navigate to websites, log in, and their
    sessions will be preserved for future automation tasks.
    """
    global profile_browser, agent
    
    try:
        # Don't start if automation agent is running
        if agent:
            return {
                "status": "error",
                "message": "Please stop the automation browser first before setting up profiles"
            }
        
        if profile_browser:
            return {
                "status": "already_running",
                "message": "Profile browser is already running. Use it to set up your credentials."
            }
        
        # Start profile browser in thread pool
        profile_browser = await asyncio.to_thread(_start_profile_browser)
        
        # Navigate to URL if provided
        if url:
            await asyncio.to_thread(profile_browser.navigate, url)
        
        await broadcast_event({
            "type": "profile_browser_started",
            "data": {"url": url}
        })
        
        return {
            "status": "started",
            "message": "Profile browser launched. Navigate to websites and log in to save your credentials.",
            "profile_dir": DEFAULT_PROFILE_DIR
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/profile/stop")
async def stop_profile_browser():
    """
    Close the profile browser. All credentials and sessions are automatically
    saved to the profile directory.
    """
    global profile_browser
    
    try:
        if not profile_browser:
            return {"status": "not_running", "message": "Profile browser is not running"}
        
        # Close profile browser
        await asyncio.to_thread(_close_profile_browser, profile_browser)
        profile_browser = None
        
        await broadcast_event({
            "type": "profile_browser_stopped",
            "data": {}
        })
        
        return {
            "status": "stopped",
            "message": "Profile browser closed. Your credentials have been saved."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile/status")
async def get_profile_status():
    """Get the status of the profile browser and saved profile"""
    global profile_browser
    
    profile_exists = os.path.exists(DEFAULT_PROFILE_DIR)
    profile_size = 0
    
    if profile_exists:
        # Calculate profile directory size
        for dirpath, dirnames, filenames in os.walk(DEFAULT_PROFILE_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                profile_size += os.path.getsize(fp)
    
    return {
        "profile_browser_running": profile_browser is not None,
        "profile_exists": profile_exists,
        "profile_dir": DEFAULT_PROFILE_DIR,
        "profile_size_mb": round(profile_size / (1024 * 1024), 2) if profile_size > 0 else 0
    }

@app.delete("/profile/clear")
async def clear_profile():
    """
    Clear all saved credentials and browser data.
    This will delete all cookies, localStorage, and saved logins.
    """
    global profile_browser
    
    try:
        if profile_browser:
            return {
                "status": "error",
                "message": "Please close the profile browser first"
            }
        
        if os.path.exists(DEFAULT_PROFILE_DIR):
            shutil.rmtree(DEFAULT_PROFILE_DIR)
            
            await broadcast_event({
                "type": "profile_cleared",
                "data": {}
            })
            
            return {
                "status": "cleared",
                "message": "Profile data has been cleared. You will need to log in to websites again."
            }
        else:
            return {
                "status": "not_found",
                "message": "No profile data found"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/task", response_model=TaskResponse)
async def run_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Run a task with the agent"""
    global current_task
    
    async with task_lock:
        if current_task:
            raise HTTPException(
                status_code=409,
                detail="A task is already running. Please wait or stop it first."
            )
        
        flow_id = request.flow_id or str(uuid.uuid4())
        provider = request.provider or os.getenv("DEFAULT_PROVIDER", "openai")
        
        current_task = {
            "flow_id": flow_id,
            "instruction": request.instruction,
            "initial_url": request.initial_url,
            "started_at": datetime.now().isoformat()
        }
    
    emitter = EventEmitter(flow_id)
    
    result, error = await run_agent_task(
        instruction=request.instruction,
        initial_url=request.initial_url,
        provider=provider,
        flow_id=flow_id,
        emitter=emitter
    )
    
    return TaskResponse(
        success=error is None,
        result=result or "",
        flow_id=flow_id,
        error=error
    )

@app.get("/status")
async def get_status():
    """Get agent status"""
    global agent, current_task
    
    return {
        "browser_running": agent is not None,
        "task_running": current_task is not None,
        "current_task": current_task,
        "connected_clients": len(websocket_clients)
    }

# ============================================================================
# Flow History Endpoints
# ============================================================================

@app.get("/flows")
async def get_flows(limit: int = 20, offset: int = 0):
    """Get flow history"""
    flows = load_flows()
    total = len(flows)
    flows = flows[offset:offset + limit]
    
    summaries = []
    for flow in flows:
        summaries.append({
            "id": flow["id"],
            "instruction": flow["instruction"],
            "initial_url": flow.get("initial_url"),
            "status": flow["status"],
            "created_at": flow["created_at"],
            "completed_at": flow.get("completed_at"),
            "action_count": len(flow.get("actions", []))
        })
    
    return {
        "flows": summaries,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/flows/{flow_id}")
async def get_flow(flow_id: str):
    """Get specific flow with full details"""
    flows = load_flows()
    flow = next((f for f in flows if f["id"] == flow_id), None)
    
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    return flow

@app.put("/flows/{flow_id}")
async def update_flow(flow_id: str, update: FlowUpdate):
    """Update flow instruction (for re-running with modifications)"""
    flows = load_flows()
    flow_idx = next((i for i, f in enumerate(flows) if f["id"] == flow_id), None)
    
    if flow_idx is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    flows[flow_idx]["instruction"] = update.instruction
    flows[flow_idx]["modified_at"] = datetime.now().isoformat()
    save_flows(flows)
    
    return flows[flow_idx]

@app.delete("/flows/{flow_id}")
async def delete_flow(flow_id: str):
    """Delete a flow from history"""
    flows = load_flows()
    flows = [f for f in flows if f["id"] != flow_id]
    save_flows(flows)
    
    return {"status": "deleted", "flow_id": flow_id}

@app.post("/flows/{flow_id}/rerun")
async def rerun_flow(flow_id: str, background_tasks: BackgroundTasks):
    """Re-run a previous flow"""
    flows = load_flows()
    flow = next((f for f in flows if f["id"] == flow_id), None)
    
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    request = TaskRequest(
        instruction=flow["instruction"],
        initial_url=flow.get("initial_url"),
        provider=flow.get("provider"),
        flow_id=str(uuid.uuid4())
    )
    
    return await run_task(request, background_tasks)

@app.delete("/flows")
async def clear_flows():
    """Clear all flow history"""
    save_flows([])
    return {"status": "cleared"}

# ============================================================================
# Cost Analytics Endpoints
# ============================================================================

# Pricing per 1M tokens (as of Dec 2024)
PRICING = {
    "openai": {
        "input": 10.00,   # $10 per 1M input tokens
        "output": 30.00,  # $30 per 1M output tokens
    },
    "anthropic": {
        "input": 3.00,    # $3 per 1M input tokens
        "output": 15.00,  # $15 per 1M output tokens
    },
    "gemini": {
        "input": 0.3,   # $0.075 per 1M input tokens
        "output": 2.5,   # $0.30 per 1M output tokens
    }
}

def calculate_cost(provider: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
    """Calculate cost based on provider and token counts"""
    pricing = PRICING.get(provider, PRICING["openai"])
    
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost
    }

def estimate_tokens(text: str) -> int:
    """Rough estimation: ~4 characters per token"""
    return len(text) // 4

@app.get("/costs")
async def get_costs(time_range: str = "all"):
    """Get cost analytics"""
    from datetime import datetime, timedelta
    
    flows = load_flows()
    
    # Filter by time range
    now = datetime.now()
    if time_range == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        flows = [f for f in flows if datetime.fromisoformat(f["created_at"]) >= cutoff]
    elif time_range == "week":
        cutoff = now - timedelta(days=7)
        flows = [f for f in flows if datetime.fromisoformat(f["created_at"]) >= cutoff]
    elif time_range == "month":
        cutoff = now - timedelta(days=30)
        flows = [f for f in flows if datetime.fromisoformat(f["created_at"]) >= cutoff]
    
    # Calculate costs per flow
    total_cost = 0
    total_tokens = 0
    by_provider = {}
    workflow_costs = []
    
    for flow in flows:
        provider = flow.get("provider", "openai")
        
        # Check if flow has saved token/cost data (new flows will have this)
        if "total_tokens" in flow and "total_cost" in flow:
            # Use saved actual data
            input_tokens = flow.get("input_tokens", 0)
            output_tokens = flow.get("output_tokens", 0)
            total_flow_tokens = flow.get("total_tokens", 0)
            input_cost = flow.get("input_cost", 0)
            output_cost = flow.get("output_cost", 0)
            total_flow_cost = flow.get("total_cost", 0)
        else:
            # Fallback to estimation for old flows without saved data
            instruction = flow.get("instruction", "")
            result = flow.get("result", "")
            actions = flow.get("actions", [])
            
            input_tokens = estimate_tokens(instruction) + sum(estimate_tokens(str(a)) for a in actions) * 2
            output_tokens = estimate_tokens(result) + len(actions) * 50
            total_flow_tokens = input_tokens + output_tokens
            
            costs = calculate_cost(provider, input_tokens, output_tokens)
            input_cost = costs["input_cost"]
            output_cost = costs["output_cost"]
            total_flow_cost = costs["total_cost"]
        
        # Add to workflow data
        workflow_costs.append({
            "id": flow["id"],
            "instruction": flow["instruction"],
            "provider": provider,
            "created_at": flow["created_at"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_flow_tokens,
            "cost": total_flow_cost
        })
        
        # Aggregate totals
        total_cost += total_flow_cost
        total_tokens += total_flow_tokens
        
        # By provider
        if provider not in by_provider:
            by_provider[provider] = {
                "workflows": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "input_cost": 0,
                "output_cost": 0,
                "cost": 0
            }
        
        by_provider[provider]["workflows"] += 1
        by_provider[provider]["input_tokens"] += input_tokens
        by_provider[provider]["output_tokens"] += output_tokens
        by_provider[provider]["input_cost"] += input_cost
        by_provider[provider]["output_cost"] += output_cost
        by_provider[provider]["cost"] += total_flow_cost
    
    return {
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "total_workflows": len(flows),
        "avg_cost_per_workflow": total_cost / len(flows) if flows else 0,
        "by_provider": by_provider,
        "recent_workflows": sorted(workflow_costs, key=lambda x: x["created_at"], reverse=True)[:20],
        "trend": {
            "cost": 0,  # Could calculate week-over-week growth
        }
    }

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║        Browser Automation Agent API Server v2.0           ║
    ╚════════════════════════════════════════════════════════════╝
    
    🌐 Server running at: http://{host}:{port}
    📚 API docs: http://{host}:{port}/docs
    🔌 WebSocket: ws://{host}:{port}/ws
    
    Ready to accept requests!
    """)
    
    uvicorn.run(app, host=host, port=port)
