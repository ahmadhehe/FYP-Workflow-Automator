"""
Shared application state — imported by all routers to avoid circular dependencies.
All globals are module-level singletons initialized once at import time.
"""
from typing import Optional, List, Dict, Any
from fastapi import WebSocket
from agent import BrowserAgent
from browser_controller import BrowserController
from google_sheets_client import GoogleSheetsClient
from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading

# Task management
current_task: Optional[Dict[str, Any]] = None
task_lock = asyncio.Lock()
websocket_clients: List[WebSocket] = []

# Cooperative cancellation — set by /stop, checked between agent iterations.
stop_requested: bool = False

# Browser instances
agent: Optional[BrowserAgent] = None
profile_browser: Optional[BrowserController] = None

# Google Sheets (singleton)
google_sheets_client = GoogleSheetsClient()

# Dedicated single-threaded executor for Playwright (maintains thread affinity)
playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
playwright_thread_lock = threading.Lock()

# Human intervention bridge — used by requestUserAction to block the Playwright
# thread until the user responds via POST /intervention/respond. threading.Event
# (not asyncio.Event) is required: .wait() must block only the executor thread,
# while .set() must be callable safely from the asyncio loop.
intervention_pending: bool = False
intervention_event: threading.Event = threading.Event()
intervention_response: Optional[str] = None
intervention_message: Optional[str] = None
intervention_reason: Optional[str] = None

# Captured at task start so the Playwright thread can schedule WS broadcasts
# back onto the asyncio loop via run_coroutine_threadsafe.
_event_loop: Optional[asyncio.AbstractEventLoop] = None
