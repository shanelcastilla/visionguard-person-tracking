from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.camera_service import camera_service


router = APIRouter(prefix="/camera", tags=["Camera"])


@router.get("/status")
def read_camera_status():
    return camera_service.get_status()


@router.post("/start")
def start_camera():
    try:
        camera_service.start()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo iniciar la cámara: {exc}",
        ) from exc

    return {
        "message": "Solicitud de inicio enviada.",
        "status": camera_service.get_status(),
    }


@router.post("/stop")
def stop_camera():
    try:
        camera_service.stop()
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "message": "La cámara se finalizó correctamente.",
        "status": camera_service.get_status(),
    }


@router.get("/stream.mjpg")
def stream_camera():
    return StreamingResponse(
        camera_service.stream_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
