"""
FastAPI Server - REST API for browser automation agent
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from agent import BrowserAgent
from dotenv import load_dotenv
import uvicorn
import os

load_dotenv()

app = FastAPI(title="Browser Automation Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent: Optional[BrowserAgent] = None


class TaskRequest(BaseModel):
    instruction: str
    initial_url: Optional[str] = None
    provider: Optional[str] = None


class TaskResponse(BaseModel):
    success: bool
    result: str
    error: Optional[str] = None


@app.post("/start")
async def start_browser(provider: str = "openai", headless: bool = False):
    """Start the browser agent"""
    global agent
    
    try:
        if agent:
            return {"status": "already_running"}
        
        agent = BrowserAgent(provider=provider, headless=headless)
        agent.start()
        
        return {
            "status": "started",
            "provider": provider,
            "headless": headless
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stop")
async def stop_browser():
    """Stop the browser agent"""
    global agent
    
    try:
        if not agent:
            return {"status": "not_running"}
        
        agent.close()
        agent = None
        
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/task", response_model=TaskResponse)
async def run_task(request: TaskRequest):
    """Run a task with the agent"""
    global agent
    
    try:
        # Create agent if not running
        if not agent:
            provider = request.provider or os.getenv("DEFAULT_PROVIDER", "openai")
            agent = BrowserAgent(provider=provider, headless=False)
            agent.start()
        
        # Run task
        result = agent.run(
            user_instruction=request.instruction,
            initial_url=request.initial_url
        )
        
        return TaskResponse(
            success=True,
            result=result
        )
        
    except Exception as e:
        return TaskResponse(
            success=False,
            result="",
            error=str(e)
        )


@app.get("/status")
async def get_status():
    """Get agent status"""
    global agent
    
    return {
        "running": agent is not None,
        "browser_active": agent.browser.page is not None if agent else False
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Browser Automation Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /start": "Start browser agent",
            "POST /stop": "Stop browser agent",
            "POST /task": "Run automation task",
            "GET /status": "Get agent status"
        }
    }


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    print(f"""
    ╔════════════════════════════════════════════════════════╗
    ║     Browser Automation Agent API Server               ║
    ╚════════════════════════════════════════════════════════╝
    
    🌐 Server running at: http://{host}:{port}
    📚 API docs: http://{host}:{port}/docs
    
    Ready to accept requests!
    """)
    
    uvicorn.run(app, host=host, port=port)
