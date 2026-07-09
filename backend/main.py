"""
FitCoach AI — backend
A FastAPI server that:
  1. Serves the static frontend (frontend/index.html + assets)
  2. Exposes POST /api/chat which streams responses from Anthropic's
     Messages API back to the browser as Server-Sent Events (SSE)

Security: the Anthropic API key is read from the ANTHROPIC_API_KEY
environment variable and never touches the frontend or version control.
"""

import asyncio
import os
import random
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL_NAME = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

MOCK_MODE = os.environ.get("MOCK_MODE", "").lower() == "true" or not ANTHROPIC_API_KEY

_MOCK_RESPONSES = [
    "Great question! Let's break this down into a simple plan. Start with "
    "3 workouts a week, focusing on compound movements like squats, push-ups, "
    "and rows. Keep each session under 45 minutes so it's sustainable, and "
    "make sure to rest at least one day between sessions targeting the same "
    "muscle groups. Consistency beats intensity, showing up 3 times a week "
    "for a month beats one brutal session and burning out.",
    "Good form matters more than heavy weight, especially early on. Keep your "
    "core braced, move through a full range of motion, and slow down the "
    "lowering part of each rep, that's often where most of the benefit "
    "comes from. If something causes sharp pain rather than muscle fatigue, "
    "stop and check in with a physical therapist or doctor rather than "
    "pushing through it.",
    "Staying motivated is often more about systems than willpower. Try "
    "stacking your workout onto an existing habit, like right after your "
    "morning coffee, track your sessions somewhere visible, and set a small "
    "non-negotiable minimum for low-energy days so you never fully skip. "
    "Simple strength logs tend to keep people going longer than the scale "
    "does.",
]


def _mock_stream_text() -> str:
    return random.choice(_MOCK_RESPONSES)

SYSTEM_PROMPT = (
    "You are FitCoach AI, an upbeat, knowledgeable fitness coaching persona. "
    "You help users build workout plans, understand exercise form and technique, "
    "stay motivated, and build sustainable habits around movement and general "
    "wellness. You are not a doctor, physical therapist, or registered "
    "dietitian: for injuries, pain, medical conditions, or specific medical "
    "nutrition needs, clearly tell the user to consult a qualified "
    "professional rather than guessing. Keep responses practical, encouraging, "
    "safety-conscious, and appropriately concise for a chat interface."
)

if not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY is not set. /api/chat will return an error.")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

app = FastAPI(title="FitCoach AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "mock_mode": MOCK_MODE}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    if not MOCK_MODE and client is None:
        raise HTTPException(
            status_code=500,
            detail="Server is missing ANTHROPIC_API_KEY. Set it as an environment variable.",
        )

    anthropic_messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def mock_event_stream():
        text = _mock_stream_text()
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0.04)
        yield "event: done\ndata: [DONE]\n\n"

    def event_stream():
        try:
            with client.messages.stream(
                model=MODEL_NAME,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=anthropic_messages,
            ) as stream:
                for chunk in stream.text_stream:
                    safe_chunk = chunk.replace("\n", "\\n")
                    yield f"data: {safe_chunk}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {str(exc)}\n\n"

    stream_fn = mock_event_stream() if MOCK_MODE else event_stream()

    return StreamingResponse(
        stream_fn,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
