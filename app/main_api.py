from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.camera import router as camera_router
from app.api.dashboard import router as dashboard_router
from app.api.event import router as events_router
from app.services.camera_service import camera_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    camera_service.start()
    yield
    camera_service.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(events_router)
app.include_router(camera_router)
app.include_router(dashboard_router)
project_root = Path(__file__).resolve().parent.parent
evidence_directory = project_root / "events"
evidence_directory.mkdir(exist_ok=True)
app.mount(
    "/evidence",
    StaticFiles(directory=evidence_directory),
    name="evidence",
)

@app.get("/")
def root():

    return {
        "message": "AI Security API funcionando"
    }


app = CORSMiddleware(
    app=app,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)