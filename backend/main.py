import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import documents, pipeline, sessions, websocket
from backend.api.session_store import get_session_store
from backend.api.ws_manager import set_main_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initializes the session-metadata SQLite database (backend/api/session_store.py)
    # on startup; the LangGraph checkpoint database is initialized lazily by
    # SqliteSaver itself the first time a session's pipeline actually runs.
    get_session_store()
    # Captures this (persistent, app-lifetime) loop so background pipeline
    # threads can safely schedule WebSocket broadcasts onto it later --
    # see ws_manager.set_main_loop's docstring for why this can't just be
    # captured from within whichever request handler starts a given run.
    set_main_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="ASDA", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(pipeline.router)
app.include_router(websocket.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
