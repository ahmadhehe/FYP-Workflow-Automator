"""
All Pydantic request/response models for the FastAPI application.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict


class TaskRequest(BaseModel):
    instruction: str
    initial_url: Optional[str] = None
    provider: Optional[str] = None
    flow_id: Optional[str] = None
    file_content: Optional[str] = None   # legacy single-file support
    file_name: Optional[str] = None      # legacy single-file support
    files: Optional[List[Dict[str, str]]] = None  # [{name, content, path}]


class TaskResponse(BaseModel):
    success: bool
    result: str
    flow_id: str
    error: Optional[str] = None


class FlowUpdate(BaseModel):
    instruction: str


# ── LMS Models ────────────────────────────────────────────────────────────────

class LMSProfileRequest(BaseModel):
    sakai_url: str
    username: str
    password: str
    onboarding_done: Optional[bool] = False


class CourseRequest(BaseModel):
    name: str
    code: str
    semester: str
    sakai_site_id: Optional[str] = None


class TabPrefsRequest(BaseModel):
    course_id: str
    enabled_tabs: List[str]
