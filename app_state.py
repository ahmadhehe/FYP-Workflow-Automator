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

# Browser instances
agent: Optional[BrowserAgent] = None
profile_browser: Optional[BrowserController] = None

# Google Sheets (singleton)
google_sheets_client = GoogleSheetsClient()

# Dedicated single-threaded executor for Playwright (maintains thread affinity)
playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
playwright_thread_lock = threading.Lock()
