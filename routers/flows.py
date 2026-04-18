"""
Flow history CRUD endpoints.
"""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks

from models import FlowUpdate, TaskRequest
from utils.flows_store import load_flows, save_flows, save_flow

router = APIRouter()


@router.get("/flows")
async def get_flows(limit: int = 20, offset: int = 0):
    flows = load_flows()
    total = len(flows)
    flows = flows[offset:offset + limit]
    summaries = [
        {
            "id": f["id"],
            "instruction": f["instruction"],
            "initial_url": f.get("initial_url"),
            "status": f["status"],
            "created_at": f["created_at"],
            "completed_at": f.get("completed_at"),
            "action_count": len(f.get("actions", [])),
        }
        for f in flows
    ]
    return {"flows": summaries, "total": total, "limit": limit, "offset": offset}


@router.get("/flows/{flow_id}")
async def get_flow(flow_id: str):
    flows = load_flows()
    flow = next((f for f in flows if f["id"] == flow_id), None)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.put("/flows/{flow_id}")
async def update_flow(flow_id: str, update: FlowUpdate):
    flows = load_flows()
    flow_idx = next((i for i, f in enumerate(flows) if f["id"] == flow_id), None)
    if flow_idx is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    flows[flow_idx]["instruction"] = update.instruction
    flows[flow_idx]["modified_at"] = datetime.now().isoformat()
    save_flows(flows)
    return flows[flow_idx]


@router.delete("/flows/{flow_id}")
async def delete_flow(flow_id: str):
    flows = load_flows()
    flows = [f for f in flows if f["id"] != flow_id]
    save_flows(flows)
    return {"status": "deleted", "flow_id": flow_id}


@router.post("/flows/{flow_id}/rerun")
async def rerun_flow(flow_id: str, background_tasks: BackgroundTasks):
    flows = load_flows()
    flow = next((f for f in flows if f["id"] == flow_id), None)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Import run_task here to avoid circular imports
    from routers.browser import run_task
    request = TaskRequest(
        instruction=flow["instruction"],
        initial_url=flow.get("initial_url"),
        provider=flow.get("provider"),
        flow_id=str(uuid.uuid4()),
    )
    return await run_task(request, background_tasks)


@router.delete("/flows")
async def clear_flows():
    save_flows([])
    return {"status": "cleared"}
