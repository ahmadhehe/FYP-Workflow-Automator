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
from dotenv import load_dotenv
import uvicorn
import asyncio
import json
import os
import uuid

load_dotenv()

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

def _create_and_start_agent(provider: str, headless: bool) -> BrowserAgent:
    """Synchronous function to create and start agent (runs in thread pool)"""
    print(f"[Server] Creating agent with provider={provider}, headless={headless}")
    agent = BrowserAgent(provider=provider, headless=headless)
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
        
        await emitter.emit("status", {"message": "Task started", "status": "running"})
        
        # Run the agent in a thread pool to avoid blocking the event loop
        result = await run_agent_with_events(agent, instruction, initial_url, emitter)
        
        await emitter.emit("status", {"message": "Task completed", "status": "completed"})
        
    except Exception as e:
        error = str(e)
        status = "failed"
        await emitter.emit("error", {"message": error})
        await emitter.emit("status", {"message": f"Task failed: {error}", "status": "failed"})
    
    finally:
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
            "completed_at": datetime.now().isoformat()
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
    emitter: EventEmitter
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
