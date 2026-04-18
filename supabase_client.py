"""
Supabase client wrapper for the browser automation backend.

Two clients:
  - Service-role client: used only for lms_teacher_profiles (bypasses RLS).
  - Authenticated client: built from a user JWT, used for courses/files so RLS
    correctly scopes data to the signed-in teacher.

SECURITY NOTE: Sakai passwords are stored as plaintext. Acceptable for a
local single-user tool only. Encrypt before any multi-user deployment.
"""
import os
import uuid
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_service_client = None


def get_supabase():
    """Service-role client — bypasses RLS. Use only for lms_teacher_profiles."""
    global _service_client
    if _service_client is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        _service_client = create_client(url, key)
    return _service_client


def get_authed_supabase(user_jwt: str):
    """Return a Supabase client authenticated as the teacher (respects RLS)."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
    client = create_client(url, anon_key)
    client.auth.set_session(user_jwt, "")   # set access token; refresh not needed here
    return client


# ── Teacher Profile (service_role) ────────────────────────────────────────────

def get_teacher_profile(user_id: Optional[str] = None) -> Optional[dict]:
    """Return the teacher's LMS profile, optionally filtered by user_id."""
    sb = get_supabase()
    q = sb.table("lms_teacher_profiles").select("*")
    if user_id:
        q = q.eq("user_id", user_id)
    res = q.limit(1).execute()
    return res.data[0] if res.data else None


def save_teacher_profile(
    sakai_url: str,
    username: str,
    password: str,
    onboarding_done: bool = False,
    profile_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    sb = get_supabase()
    payload = {
        "sakai_url": sakai_url,
        "username": username,
        "password": password,
        "onboarding_done": onboarding_done,
    }
    if user_id:
        payload["user_id"] = user_id
    if profile_id:
        res = sb.table("lms_teacher_profiles").update(payload).eq("id", profile_id).execute()
    else:
        res = sb.table("lms_teacher_profiles").insert(payload).execute()
    return res.data[0]


def mark_onboarding_complete(profile_id: str) -> None:
    get_supabase().table("lms_teacher_profiles").update(
        {"onboarding_done": True}
    ).eq("id", profile_id).execute()


# ── Courses (authenticated, existing `courses` table) ─────────────────────────

def get_courses(user_jwt: str) -> list:
    """
    Fetch the teacher's courses from the existing `courses` table.
    Uses an authenticated client so RLS scopes to the logged-in user.
    """
    sb = get_authed_supabase(user_jwt)
    res = (
        sb.table("courses")
        .select("id, name, code, semester, sakai_site_id")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def save_course(
    user_jwt: str,
    user_id: str,
    name: str,
    code: str,
    semester: str,
    sakai_site_id: Optional[str] = None,
) -> dict:
    sb = get_authed_supabase(user_jwt)
    res = sb.table("courses").insert({
        "name": name,
        "code": code,
        "semester": semester,
        "sakai_site_id": sakai_site_id,
        "created_by": user_id,
    }).execute()
    course = res.data[0]
    # Register teacher as owner in course_members
    sb.table("course_members").insert({
        "course_id": course["id"],
        "user_id": user_id,
        "role": "owner",
    }).execute()
    return course


def update_course(user_jwt: str, course_id: str, **fields) -> dict:
    sb = get_authed_supabase(user_jwt)
    res = sb.table("courses").update(fields).eq("id", course_id).execute()
    return res.data[0]


def delete_course(user_jwt: str, course_id: str) -> None:
    get_authed_supabase(user_jwt).table("courses").delete().eq("id", course_id).execute()


# ── Course Files (authenticated, existing `course_files` table) ───────────────

def get_course_files(user_jwt: str, course_id: str) -> list:
    sb = get_authed_supabase(user_jwt)
    res = sb.table("course_files").select("*").eq("course_id", course_id).execute()
    return res.data or []


def get_all_course_files(user_jwt: str, courses: list) -> list:
    """
    Return all files across all courses.
    Downloads each file from Supabase Storage to a local temp path so the
    agent can pass local_path directly to uploadFileToBrowser.
    """
    import urllib.request

    sb = get_authed_supabase(user_jwt)
    upload_dir = Path("uploads") / "course_files"
    upload_dir.mkdir(parents=True, exist_ok=True)

    all_files = []
    for course in courses:
        res = sb.table("course_files").select("*").eq("course_id", course["id"]).execute()
        for f in (res.data or []):
            original_name = f["file_name"]
            # Use a stable filename based on the file's DB id so we never re-download
            dest = upload_dir / f"{f['id']}{Path(original_name).suffix}"

            local_path = ""
            if dest.exists():
                # Already cached — skip download
                local_path = str(dest.resolve())
            else:
                try:
                    signed = sb.storage.from_("course-materials").create_signed_url(f["file_path"], 3600)
                    signed_url = signed.get("signedURL") or signed.get("signed_url") or ""
                    if signed_url:
                        urllib.request.urlretrieve(signed_url, dest)
                        local_path = str(dest.resolve())
                except Exception:
                    local_path = ""

            f["local_path"] = local_path
            f["course_name"] = course["name"]
            f["course_code"] = course.get("code", "")
            all_files.append(f)
    return all_files


def upload_file_to_storage(
    user_jwt: str,
    course_id: str,
    file_bytes: bytes,
    original_filename: str,
    file_type: str = "other",
) -> dict:
    """Upload to Supabase Storage (course-materials bucket) and record in course_files."""
    sb = get_authed_supabase(user_jwt)
    ext = Path(original_filename).suffix
    storage_path = f"{course_id}/{uuid.uuid4()}{ext}"
    sb.storage.from_("course-materials").upload(storage_path, file_bytes)
    res = sb.table("course_files").insert({
        "course_id": course_id,
        "file_name": original_filename,
        "file_path": storage_path,
        "file_type": file_type,
    }).execute()
    return res.data[0]


def delete_course_file(user_jwt: str, file_id: str, storage_path: str) -> None:
    sb = get_authed_supabase(user_jwt)
    sb.storage.from_("course-materials").remove([storage_path])
    sb.table("course_files").delete().eq("id", file_id).execute()


# ── Tab Preferences (lms_tab_preferences — new table, auth enforced by RLS) ───

SAKAI_TABS = [
    "Gradebook", "Resources", "Assignments", "Announcements",
    "Forums", "Calendar", "Syllabus", "Roster",
]


def save_tab_preferences(user_jwt: str, course_id: str, enabled_tabs: list) -> None:
    sb = get_authed_supabase(user_jwt)
    sb.table("lms_tab_preferences").delete().eq("course_id", course_id).execute()
    rows = [
        {"course_id": course_id, "tab_name": t, "is_enabled": t in enabled_tabs}
        for t in SAKAI_TABS
    ]
    sb.table("lms_tab_preferences").insert(rows).execute()


# ── Context Builder ───────────────────────────────────────────────────────────

def build_lms_context_prefix(profile: dict, courses: list, user_jwt: str = None) -> str:
    """
    Plaintext block prepended to every agent instruction.
    Contains Sakai credentials — passed to the agent only, never stored in flow history.
    """
    course_lines = []
    for c in courses:
        line = (
            f"  - {c['name']} ({c.get('code', '')}, {c.get('semester', '')})"
            + (f" [Sakai site ID: {c['sakai_site_id']}]" if c.get("sakai_site_id") else "")
        )
        course_lines.append(line)

    files_section = ""
    if user_jwt and courses:
        try:
            all_files = get_all_course_files(user_jwt, courses)
            if all_files:
                file_lines = "\n".join(
                    f"  - \"{f['file_name']}\" (course: {f['course_name']}, type: {f.get('file_type','other')}, local_path: {f['local_path']})"
                    for f in all_files
                )
                files_section = f"Uploaded course files (already downloaded to local disk — use the local_path with uploadFileToBrowser):\n{file_lines}\n"
        except Exception:
            pass

    return (
        f"[LMS CONTEXT]\n"
        f"Sakai URL: {profile['sakai_url']}\n"
        f"Username:  {profile['username']}\n"
        f"Password:  {profile['password']}\n"
        f"Courses you teach:\n{chr(10).join(course_lines) or '  (none configured)'}\n"
        f"{files_section}"
        f"[END LMS CONTEXT]\n\n"
    )
