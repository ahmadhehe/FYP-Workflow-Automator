"""
FastAPI application entry point.
All business logic lives in routers/ and shared utilities.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import os
import logging

from routers import browser, flows, auth, lms
from utils.flows_store import load_flows
from utils.llm_logging import calculate_cost, estimate_tokens

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Browser Automation Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(browser.router)
app.include_router(flows.router)
app.include_router(auth.router)
app.include_router(lms.router)


@app.get("/")
async def root():
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
            "WS /ws": "WebSocket for real-time updates",
            "GET /onboarding/status": "Check onboarding completion",
            "GET /profile/lms": "Get LMS teacher profile",
            "POST /profile/lms": "Save LMS teacher profile",
        }
    }


@app.get("/costs")
async def get_costs(time_range: str = "all"):
    """Get cost analytics across all recorded flows."""
    from datetime import datetime, timedelta

    flows = load_flows()

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

    total_cost = 0
    total_tokens = 0
    by_provider = {}
    workflow_costs = []

    for flow in flows:
        provider = flow.get("provider", "openai")

        if "total_tokens" in flow and "total_cost" in flow:
            input_tokens = flow.get("input_tokens", 0)
            output_tokens = flow.get("output_tokens", 0)
            total_flow_tokens = flow.get("total_tokens", 0)
            input_cost = flow.get("input_cost", 0)
            output_cost = flow.get("output_cost", 0)
            total_flow_cost = flow.get("total_cost", 0)
        else:
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

        workflow_costs.append({
            "id": flow["id"],
            "instruction": flow["instruction"],
            "provider": provider,
            "created_at": flow["created_at"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_flow_tokens,
            "cost": total_flow_cost,
        })

        total_cost += total_flow_cost
        total_tokens += total_flow_tokens

        if provider not in by_provider:
            by_provider[provider] = {
                "workflows": 0, "input_tokens": 0, "output_tokens": 0,
                "input_cost": 0, "output_cost": 0, "cost": 0,
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
        "trend": {"cost": 0},
    }


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║        Browser Automation Agent API Server v2.0           ║
    ╚════════════════════════════════════════════════════════════╝

    Server running at: http://{host}:{port}
    API docs: http://{host}:{port}/docs
    WebSocket: ws://{host}:{port}/ws

    Ready to accept requests!
    """)
    uvicorn.run(app, host=host, port=port)
