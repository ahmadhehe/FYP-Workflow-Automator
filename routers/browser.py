"""
Browser control endpoints: start/stop, task execution, WebSocket, profile browser.
"""
import asyncio
import json
import os
import shutil
import uuid
import logging
from datetime import datetime
from typing import Optional
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Header

import app_state
from agent_runner import EventEmitter, broadcast_event, _create_and_start_agent, run_agent_task
from browser_controller import BrowserController, DEFAULT_PROFILE_DIR
from models import TaskRequest, TaskResponse

logger = logging.getLogger(__name__)
router = APIRouter()


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if websocket not in app_state.websocket_clients:
        app_state.websocket_clients.append(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {
                "running": app_state.agent is not None,
                "current_task": app_state.current_task,
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
        if websocket in app_state.websocket_clients:
            app_state.websocket_clients.remove(websocket)


# ── Browser start/stop/status ─────────────────────────────────────────────────

@router.post("/start")
async def start_browser(provider: str = "openai", headless: bool = False):
    if app_state.agent:
        return {"status": "already_running", "message": "Browser is already running"}
    try:
        loop = asyncio.get_event_loop()
        app_state.agent = await loop.run_in_executor(
            app_state.playwright_executor, _create_and_start_agent, provider, headless, True
        )
        await broadcast_event({"type": "browser_started", "data": {"provider": provider, "headless": headless}})
        return {"status": "started", "provider": provider, "headless": headless}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _close_agent(agent_instance):
    agent_instance.close()


@router.post("/stop")
async def stop_browser():
    if not app_state.agent:
        return {"status": "not_running", "message": "Browser is not running"}
    if app_state.current_task:
        return {"status": "busy", "message": "Cannot stop while task is running"}
    try:
        await asyncio.to_thread(_close_agent, app_state.agent)
        app_state.agent = None
        await broadcast_event({"type": "browser_stopped", "data": {}})
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    return {
        "browser_running": app_state.agent is not None,
        "task_running": app_state.current_task is not None,
        "current_task": app_state.current_task,
        "connected_clients": len(app_state.websocket_clients),
    }


# ── Task execution ────────────────────────────────────────────────────────────

@router.post("/task", response_model=TaskResponse)
async def run_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
):
    async with app_state.task_lock:
        if app_state.current_task:
            raise HTTPException(
                status_code=409,
                detail="A task is already running. Please wait or stop it first."
            )
        flow_id = request.flow_id or str(uuid.uuid4())
        provider = request.provider or os.getenv("DEFAULT_PROVIDER", "openai")
        app_state.current_task = {
            "flow_id": flow_id,
            "instruction": request.instruction,
            "initial_url": request.initial_url,
            "started_at": datetime.now().isoformat(),
        }

    # Enrich instruction with LMS context (Sakai credentials + course list)
    enriched_instruction = request.instruction
    try:
        from supabase_client import get_teacher_profile, get_courses, get_all_course_files, build_lms_context_prefix, get_authed_supabase
        user_jwt = authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else None

        # Resolve user_id from JWT to scope the profile lookup
        user_id = None
        if user_jwt:
            try:
                client = get_authed_supabase(user_jwt)
                res = client.auth.get_user(user_jwt)
                user_id = res.user.id if res.user else None
            except Exception:
                pass

        profile = get_teacher_profile(user_id=user_id)
        if profile and profile.get("onboarding_done"):
            courses = get_courses(user_jwt) if user_jwt else []
            all_files = get_all_course_files(user_jwt, courses) if user_jwt and courses else []
            prefix = build_lms_context_prefix(profile, courses, user_jwt=user_jwt)
            enriched_instruction = prefix + request.instruction
            # Register downloaded files so uploadFileToBrowser can find them by original filename
            if all_files:
                if not hasattr(app_state, '_course_file_paths'):
                    app_state._course_file_paths = {}
                for f in all_files:
                    if f.get("local_path"):
                        app_state._course_file_paths[f["file_name"]] = f["local_path"]
    except Exception as ctx_err:
        logger.warning("Could not build LMS context: %s", ctx_err)

    emitter = EventEmitter(flow_id)
    result, error = await run_agent_task(
        instruction=enriched_instruction,
        initial_url=request.initial_url,
        provider=provider,
        flow_id=flow_id,
        emitter=emitter,
        file_context=request.file_content,
        file_name=request.file_name,
        files=request.files,
        original_instruction=request.instruction,
    )

    return TaskResponse(success=error is None, result=result or "", flow_id=flow_id, error=error)


# ── Profile browser ───────────────────────────────────────────────────────────

def _start_profile_browser() -> BrowserController:
    browser = BrowserController(headless=False, use_profile=True)
    browser.start()
    return browser


def _close_profile_browser(browser: BrowserController):
    browser.close()


@router.post("/profile/start")
async def start_profile_browser(url: str = None):
    if app_state.agent:
        return {"status": "error", "message": "Please stop the automation browser first before setting up profiles"}
    if app_state.profile_browser:
        return {"status": "already_running", "message": "Profile browser is already running."}
    try:
        loop = asyncio.get_event_loop()
        app_state.profile_browser = await loop.run_in_executor(
            app_state.playwright_executor, _start_profile_browser
        )
        if url:
            await loop.run_in_executor(app_state.playwright_executor, app_state.profile_browser.navigate, url)
        await broadcast_event({"type": "profile_browser_started", "data": {"url": url}})
        return {
            "status": "started",
            "message": "Profile browser launched. Navigate to websites and log in to save your credentials.",
            "profile_dir": DEFAULT_PROFILE_DIR,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/stop")
async def stop_profile_browser():
    if not app_state.profile_browser:
        return {"status": "not_running", "message": "Profile browser is not running"}
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            app_state.playwright_executor, _close_profile_browser, app_state.profile_browser
        )
        app_state.profile_browser = None
        await broadcast_event({"type": "profile_browser_stopped", "data": {}})
        return {"status": "stopped", "message": "Profile browser closed. Your credentials have been saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/status")
async def get_profile_status():
    profile_exists = os.path.exists(DEFAULT_PROFILE_DIR)
    profile_size = 0
    if profile_exists:
        for dirpath, dirnames, filenames in os.walk(DEFAULT_PROFILE_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                profile_size += os.path.getsize(fp)
    return {
        "profile_browser_running": app_state.profile_browser is not None,
        "profile_exists": profile_exists,
        "profile_dir": DEFAULT_PROFILE_DIR,
        "profile_size_mb": round(profile_size / (1024 * 1024), 2) if profile_size > 0 else 0,
    }


@router.delete("/profile/clear")
async def clear_profile():
    if app_state.profile_browser:
        return {"status": "error", "message": "Please close the profile browser first"}
    try:
        if os.path.exists(DEFAULT_PROFILE_DIR):
            shutil.rmtree(DEFAULT_PROFILE_DIR)
            await broadcast_event({"type": "profile_cleared", "data": {}})
            return {"status": "cleared", "message": "Profile data has been cleared."}
        return {"status": "not_found", "message": "No profile data found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
