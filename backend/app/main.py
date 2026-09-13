"""Local API. Session state is bounded, ephemeral, and isolated per sample patient."""
import os
from pathlib import Path
from threading import RLock
from time import monotonic
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import ReceptionEngine
from .models import ChatRequest, ConfirmationRequest, SessionView
from .providers import create_interpreter

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def create_app(engine: ReceptionEngine | None = None) -> FastAPI:
    if engine is None:
        mode = os.getenv("AI_PROVIDER", "gemini").strip().lower()
        interpreter = create_interpreter(mode)
        engine = ReceptionEngine(interpreter, mode=mode, model=getattr(interpreter, "model", None))
    app = FastAPI(title="CliniKit reception", version="0.1.0")
    sessions = {}
    registry_lock = RLock()
    app.state.sessions = sessions
    app.state.engine = engine
    allowed_origins = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"}
    for variable in ("PUBLIC_ORIGIN", "RENDER_EXTERNAL_URL"):
        value = os.getenv(variable, "").strip()
        if not value:
            continue
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise RuntimeError(f"{variable} must be an http(s) origin, such as https://your-app.onrender.com")
        allowed_origins.add(f"{parsed.scheme}://{parsed.netloc}")

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and origin not in allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "This demo does not accept requests from that origin."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_session(session_id):
        with registry_lock:
            session = sessions.get(session_id)
            if session is None or monotonic() - session.touched > 7200:
                raise HTTPException(404, "This sample session has expired. Start a new conversation.")
            session.touched = monotonic()
            return session

    def deduplicate(s, request_id, fingerprint):
        previous = s.requests.get(request_id)
        if previous is not None:
            if previous != fingerprint:
                raise HTTPException(409, "This request id was already used for a different action.")
            return True
        if len(s.requests) >= 256:
            raise HTTPException(429, "This demo conversation has reached its limit. Start a new conversation.")
        return False

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": engine.mode, "model": engine.model, "timezone": "Asia/Beirut"}

    @app.post("/api/sessions", response_model=SessionView)
    def new_session():
        with registry_lock:
            expired = [key for key, s in sessions.items() if monotonic() - s.touched > 7200]
            for key in expired:
                del sessions[key]
            if len(sessions) >= 200:
                raise HTTPException(429, "The local demo has reached its session limit. Restart the server to reset it.")
            session = engine.create_session()
            sessions[session.id] = session
        return engine.view(session)

    @app.get("/api/sessions/{session_id}", response_model=SessionView)
    def read_session(session_id: str):
        session = get_session(session_id)
        with session.lock:
            return engine.view(session)

    @app.post("/api/sessions/{session_id}/messages", response_model=SessionView)
    def message(session_id: str, body: ChatRequest):
        session = get_session(session_id)
        with session.lock:
            fingerprint = "message:" + body.message
            if not deduplicate(session, body.request_id, fingerprint):
                engine.chat(session, body.message)
                session.requests[body.request_id] = fingerprint
            return engine.view(session)

    def apply_confirmation(session_id, body, dismiss):
        session = get_session(session_id)
        with session.lock:
            fingerprint = f"{'dismiss' if dismiss else 'confirm'}:{body.proposal_id}"
            if not deduplicate(session, body.request_id, fingerprint):
                try:
                    engine.confirm(session, body.proposal_id, dismiss)
                except ValueError as error:
                    raise HTTPException(409, str(error)) from error
                session.requests[body.request_id] = fingerprint
            return engine.view(session)

    @app.post("/api/sessions/{session_id}/confirm", response_model=SessionView)
    def confirm(session_id: str, body: ConfirmationRequest):
        return apply_confirmation(session_id, body, False)

    @app.post("/api/sessions/{session_id}/dismiss", response_model=SessionView)
    def dismiss(session_id: str, body: ConfirmationRequest):
        return apply_confirmation(session_id, body, True)

    built_ui = ROOT / "frontend" / "dist"
    if built_ui.is_dir():
        app.mount("/", StaticFiles(directory=built_ui, html=True), name="frontend")
    return app


app = create_app()
