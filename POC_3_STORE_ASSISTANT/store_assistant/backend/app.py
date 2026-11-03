import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from .agents import root_agent
from ..config import settings

APP_NAME = "store_assistant"
sessions = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=sessions)
app = FastAPI(title="Store Assistant POC")


class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str | None = None


@app.post("/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    if not await sessions.get_session(app_name=APP_NAME, user_id=req.user_id, session_id=sid):
        await sessions.create_session(app_name=APP_NAME, user_id=req.user_id, session_id=sid,
                                      state={"user_id": req.user_id})
    msg = types.Content(role="user", parts=[types.Part(text=req.message)])
    reply = ""
    async for ev in runner.run_async(user_id=req.user_id, session_id=sid, new_message=msg):
        if ev.is_final_response() and ev.content and ev.content.parts:
            reply = ev.content.parts[0].text or reply
    return {"reply": reply, "session_id": sid}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(settings.UI_DIR / "index.html")
