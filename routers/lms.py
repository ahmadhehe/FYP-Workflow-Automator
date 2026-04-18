"""
LMS teacher onboarding endpoints.

- lms_teacher_profiles: service_role (no RLS needed, user_id FK scopes it)
- courses / course_files: authenticated client (existing tables, full RLS)
- lms_tab_preferences: authenticated client (new table, RLS = authenticated full access)

All mutating endpoints that touch RLS-protected tables require an
Authorization: Bearer <user_jwt> header from the frontend.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Header

from models import LMSProfileRequest, CourseRequest, TabPrefsRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _sb():
    import supabase_client
    return supabase_client


def _require_jwt(authorization: Optional[str]) -> str:
    """Extract and validate the Bearer token from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header with Bearer token required")
    return authorization.split(" ", 1)[1]


# ── Onboarding status ─────────────────────────────────────────────────────────

@router.get("/onboarding/status")
async def onboarding_status(authorization: Optional[str] = Header(default=None)):
    """Returns whether the teacher has completed onboarding."""
    try:
        sb = _sb()
        # Try to get user_id from JWT to scope the profile lookup
        user_id = None
        if authorization and authorization.startswith("Bearer "):
            jwt = authorization.split(" ", 1)[1]
            try:
                client = sb.get_authed_supabase(jwt)
                res = client.auth.get_user(jwt)
                user_id = res.user.id if res.user else None
            except Exception:
                pass
        profile = sb.get_teacher_profile(user_id=user_id)
        return {"completed": bool(profile and profile.get("onboarding_done"))}
    except Exception as e:
        logger.warning("Onboarding status check failed: %s", e)
        return {"completed": False}


# ── Teacher profile ───────────────────────────────────────────────────────────

@router.get("/profile/lms")
async def get_lms_profile(authorization: Optional[str] = Header(default=None)):
    """Return teacher's LMS profile. Courses are fetched from the shared `courses` table."""
    sb = _sb()
    user_id = None
    user_jwt = None

    if authorization and authorization.startswith("Bearer "):
        user_jwt = authorization.split(" ", 1)[1]
        try:
            client = sb.get_authed_supabase(user_jwt)
            res = client.auth.get_user(user_jwt)
            user_id = res.user.id if res.user else None
        except Exception:
            pass

    profile = sb.get_teacher_profile(user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="No LMS profile found")

    courses = sb.get_courses(user_jwt) if user_jwt else []
    return {"profile": profile, "courses": courses}


@router.post("/profile/lms")
async def save_lms_profile(
    request: LMSProfileRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Create or update the teacher's LMS profile (Sakai credentials)."""
    sb = _sb()
    user_id = None
    if authorization and authorization.startswith("Bearer "):
        jwt = authorization.split(" ", 1)[1]
        try:
            client = sb.get_authed_supabase(jwt)
            res = client.auth.get_user(jwt)
            user_id = res.user.id if res.user else None
        except Exception:
            pass

    existing = sb.get_teacher_profile(user_id=user_id)
    profile = sb.save_teacher_profile(
        sakai_url=request.sakai_url,
        username=request.username,
        password=request.password,
        onboarding_done=request.onboarding_done,
        profile_id=existing["id"] if existing else None,
        user_id=user_id,
    )
    return profile


@router.post("/profile/lms/complete-onboarding")
async def complete_onboarding(authorization: Optional[str] = Header(default=None)):
    """Mark onboarding as done."""
    sb = _sb()
    user_id = None
    if authorization and authorization.startswith("Bearer "):
        jwt = authorization.split(" ", 1)[1]
        try:
            client = sb.get_authed_supabase(jwt)
            res = client.auth.get_user(jwt)
            user_id = res.user.id if res.user else None
        except Exception:
            pass

    profile = sb.get_teacher_profile(user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="No profile exists yet")
    sb.mark_onboarding_complete(profile["id"])
    return {"success": True}


# ── Courses (proxy to existing `courses` table via authenticated client) ───────

@router.post("/profile/lms/courses")
async def add_course(request: CourseRequest, authorization: Optional[str] = Header(default=None)):
    jwt = _require_jwt(authorization)
    sb = _sb()
    client = sb.get_authed_supabase(jwt)
    res = client.auth.get_user(jwt)
    user_id = res.user.id if res.user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not identify user from token")
    return sb.save_course(jwt, user_id, request.name, request.code, request.semester, request.sakai_site_id)


@router.put("/profile/lms/courses/{course_id}")
async def edit_course(course_id: str, request: CourseRequest, authorization: Optional[str] = Header(default=None)):
    jwt = _require_jwt(authorization)
    return _sb().update_course(jwt, course_id, name=request.name, code=request.code,
                               semester=request.semester, sakai_site_id=request.sakai_site_id)


@router.delete("/profile/lms/courses/{course_id}")
async def remove_course(course_id: str, authorization: Optional[str] = Header(default=None)):
    jwt = _require_jwt(authorization)
    _sb().delete_course(jwt, course_id)
    return {"success": True}


# ── Course files (proxy to existing `course_files` table) ─────────────────────

@router.post("/profile/lms/courses/{course_id}/files")
async def upload_course_file(
    course_id: str,
    file: UploadFile = File(...),
    file_type: str = "other",
    authorization: Optional[str] = Header(default=None),
):
    jwt = _require_jwt(authorization)
    content = await file.read()
    return _sb().upload_file_to_storage(jwt, course_id, content, file.filename, file_type)


# ── Tab preferences ───────────────────────────────────────────────────────────

@router.post("/profile/lms/tab-preferences")
async def save_tab_prefs(request: TabPrefsRequest, authorization: Optional[str] = Header(default=None)):
    jwt = _require_jwt(authorization)
    _sb().save_tab_preferences(jwt, request.course_id, request.enabled_tabs)
    return {"success": True}
