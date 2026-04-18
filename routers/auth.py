"""
Google OAuth, voice transcription, and file upload endpoints.
"""
import io
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse

import app_state

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


# ── File upload ───────────────────────────────────────────────────────────────

@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse a file (supports PDF and text files)."""
    try:
        content = await file.read()

        saved_name = f"{uuid.uuid4()}_{file.filename}"
        saved_path = UPLOAD_DIR / saved_name
        saved_path.write_bytes(content)

        file_content = ""

        if file.filename.lower().endswith('.pdf'):
            if PdfReader is None:
                raise HTTPException(
                    status_code=400,
                    detail="PDF support not installed. Run: pip install PyPDF2"
                )
            try:
                pdf_file = io.BytesIO(content)
                pdf_reader = PdfReader(pdf_file)
                text_parts = []
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                file_content = "\n\n".join(text_parts)
                if not file_content.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="Could not extract text from PDF. It may be scanned or image-based."
                    )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error parsing PDF: {str(e)}")
        else:
            try:
                file_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    file_content = content.decode('latin-1')
                except Exception:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not decode file. Please ensure it's a text-based file."
                    )

        MAX_CHARS = 50000
        if len(file_content) > MAX_CHARS:
            file_content = file_content[:MAX_CHARS] + '\n\n[... Content truncated due to length ...]'

        return {
            "success": True,
            "file_name": file.filename,
            "file_content": file_content,
            "file_path": str(saved_path.resolve()),
            "content_length": len(file_content),
            "is_pdf": file.filename.lower().endswith('.pdf'),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Course file download (signed URL → local disk path for agent) ─────────────

@router.post("/course-file/download")
async def download_course_file(payload: dict):
    """
    Download a course file from a Supabase signed URL and save it locally
    so the agent can use uploadFileToBrowser with a real disk path.
    """
    import httpx
    signed_url = payload.get("signed_url", "")
    file_name = payload.get("file_name", "file")
    if not signed_url:
        raise HTTPException(status_code=400, detail="signed_url is required")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(signed_url)
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to download file: HTTP {response.status_code}")
        safe_name = f"{uuid.uuid4()}_{Path(file_name).name}"
        dest = UPLOAD_DIR / safe_name
        dest.write_bytes(response.content)
        return {"success": True, "file_path": str(dest.resolve()), "file_name": file_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Voice transcription ───────────────────────────────────────────────────────

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio using Google Cloud Speech-to-Text API."""
    import base64
    import httpx

    api_key = os.getenv("GOOGLE_CLOUD_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Google Cloud API key not configured. Add GOOGLE_CLOUD_API_KEY to your .env file."
        )

    try:
        audio_bytes = await file.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        content_type = file.content_type or ""
        if "webm" in content_type or (file.filename and "webm" in file.filename):
            encoding = "WEBM_OPUS"
        elif "ogg" in content_type:
            encoding = "OGG_OPUS"
        elif "wav" in content_type:
            encoding = "LINEAR16"
        else:
            encoding = "WEBM_OPUS"

        request_body = {
            "config": {
                "encoding": encoding,
                "sampleRateHertz": 48000,
                "languageCode": "en-US",
                "model": "latest_long",
                "enableAutomaticPunctuation": True,
            },
            "audio": {"content": audio_b64},
        }

        stt_url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(stt_url, json=request_body)

        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", response.text)
            raise HTTPException(status_code=response.status_code, detail=f"Google STT API error: {error_detail}")

        result = response.json()
        results = result.get("results", [])
        if not results:
            return {"success": True, "transcript": "", "message": "No speech detected"}

        transcript = " ".join(
            alt["transcript"]
            for r in results
            for alt in r.get("alternatives", [])[:1]
        )
        return {"success": True, "transcript": transcript.strip()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/auth/google")
async def google_auth_url():
    try:
        if not app_state.google_sheets_client.credentials_file_exists():
            raise HTTPException(
                status_code=400,
                detail="Google OAuth credentials not configured. Place client_secret.json in the project root."
            )
        auth_url = app_state.google_sheets_client.get_auth_url()
        return {"auth_url": auth_url}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/google/callback")
async def google_auth_callback(code: str = None, error: str = None):
    if error:
        html = f"""
        <html><body>
            <h2>Authentication Failed</h2><p>{error}</p>
            <p>You can close this window.</p>
            <script>setTimeout(() => window.close(), 3000);</script>
        </body></html>
        """
        return HTMLResponse(content=html)

    if not code:
        return HTMLResponse(content="<html><body><h2>No authorization code received</h2></body></html>")

    try:
        result = app_state.google_sheets_client.handle_callback(code)
        email = result.get('email', 'Unknown')
        html = f"""
        <html>
        <head><title>Google Account Connected</title></head>
        <body style="font-family: system-ui, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f9fafb;">
            <div style="text-align: center; padding: 2rem; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="font-size: 48px; margin-bottom: 16px;">&#10003;</div>
                <h2 style="color: #166534; margin-bottom: 8px;">Google Account Connected!</h2>
                <p style="color: #6b7280;">Signed in as <strong>{email}</strong></p>
                <p style="color: #9ca3af; font-size: 14px; margin-top: 16px;">This window will close automatically...</p>
            </div>
            <script>setTimeout(() => window.close(), 2500);</script>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except Exception as e:
        html = f"""
        <html><body style="font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh;">
            <div style="text-align: center;">
                <h2 style="color: #dc2626;">Authentication Failed</h2>
                <p>{str(e)}</p>
                <script>setTimeout(() => window.close(), 5000);</script>
            </div>
        </body></html>
        """
        return HTMLResponse(content=html)


@router.get("/auth/google/status")
async def google_auth_status():
    return app_state.google_sheets_client.get_status()


@router.post("/auth/google/disconnect")
async def google_auth_disconnect():
    try:
        result = app_state.google_sheets_client.disconnect()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
