import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.repositories.detection_event_repository import close_event, create_event


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIRECTORY = PROJECT_ROOT / "events"
MODEL_PATH = PROJECT_ROOT / "yolo11n.pt"


class CameraService:
    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._frame_condition = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_jpeg: bytes | None = None
        self._frame_version = 0
        self._last_publish_at: float | None = None
        self._status: dict[str, Any] = {
            "online": False,
            "state": "stopped",
            "message": "La cámara todavía no se ha iniciado.",
            "people_detected": 0,
            "last_frame_at": None,
            "fps": 0.0,
            "storage_warning": None,
        }

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._set_status(
                online=False,
                state="starting",
                message="Iniciando el detector y la cámara.",
                fps=0.0,
                last_frame_at=None,
                storage_warning=None,
            )
            self._thread = threading.Thread(
                target=self._run,
                name="camera-detector",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_event.set()
            self._set_status(
                online=False,
                state="stopping",
                message="Finalizando la cámara y cerrando detecciones activas.",
                fps=0.0,
            )
            with self._frame_condition:
                self._frame_condition.notify_all()

            thread = self._thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=5)
                if thread.is_alive():
                    raise TimeoutError(
                        "La cámara no se pudo detener en 5 segundos. "
                        "El detector todavía está finalizando el fotograma actual."
                    )
            elif thread is None:
                self._set_status(
                    state="stopped",
                    message="El servicio de cámara está detenido.",
                    people_detected=0,
                    fps=0.0,
                )

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return self._status.copy()

    def stream_frames(self):
        last_frame_version = 0
        while not self._stop_event.is_set():
            with self._frame_condition:
                self._frame_condition.wait_for(
                    lambda: (
                        self._stop_event.is_set()
                        or self._frame_version != last_frame_version
                    ),
                    timeout=1,
                )
                if self._stop_event.is_set():
                    return

                frame = self._latest_jpeg
                last_frame_version = self._frame_version

            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
            else:
                time.sleep(0.1)

    def _set_status(self, **updates: Any) -> None:
        with self._lock:
            self._status.update(updates)

    def _run(self) -> None:
        camera = None
        active_tracks: dict[int, dict[str, Any]] = {}
        storage_warning_logged = False

        try:
            import cv2
            import torch
            from ultralytics import YOLO

            EVIDENCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
            if not MODEL_PATH.is_file():
                raise FileNotFoundError(f"No se encontró el modelo: {MODEL_PATH}")

            torch.set_num_threads(1)
            self._set_status(
                state="connecting",
                message="Conectando con la cámara.",
            )
            camera = cv2.VideoCapture(self.camera_index)
            if not camera.isOpened():
                self._set_status(
                    online=False,
                    state="offline",
                    message="No se pudo abrir la cámara. Revisa permisos y conexión.",
                )
                logger.error("No se pudo abrir la cámara con índice %s", self.camera_index)
                return

            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            detector = YOLO(str(MODEL_PATH))
            self._set_status(
                online=True,
                state="online",
                message="Cámara conectada y detector activo.",
            )

            while not self._stop_event.is_set():
                success, frame = camera.read()
                if not success:
                    raise RuntimeError("La cámara dejó de entregar fotogramas.")

                result = detector.track(
                    frame,
                    persist=True,
                    conf=0.35,
                    imgsz=416,
                    verbose=False,
                )[0]
                current_person_ids: set[int] = set()

                if result.boxes.id is not None:
                    track_ids = result.boxes.id.int().cpu().tolist()
                    class_ids = result.boxes.cls.int().cpu().tolist()
                    confidences = result.boxes.conf.cpu().tolist()

                    for track_id, class_id, confidence in zip(
                        track_ids,
                        class_ids,
                        confidences,
                    ):
                        if class_id != 0:
                            continue

                        current_person_ids.add(track_id)
                        track = active_tracks.get(track_id)

                        if track is None:
                            entry_time = datetime.now(timezone.utc)
                            image_name = (
                                f"person_{track_id}_"
                                f"{entry_time.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                            )
                            image_path = EVIDENCE_DIRECTORY / image_name

                            if not cv2.imwrite(str(image_path), frame):
                                raise OSError(f"No se pudo guardar la evidencia: {image_path}")

                            try:
                                event_id = create_event(
                                    track_id=track_id,
                                    entry_time=entry_time,
                                    confidence=confidence,
                                    image_path=str(image_path),
                                )
                            except Exception:
                                if not storage_warning_logged:
                                    logger.exception(
                                        "No se pudo guardar un evento en la base de datos; "
                                        "el video seguirá activo.",
                                    )
                                    storage_warning_logged = True
                                event_id = None
                                self._set_status(
                                    storage_warning=(
                                        "No se pudo guardar un evento en la base de datos."
                                    ),
                                    message=(
                                        "Video activo; no se pudo guardar un evento "
                                        "en la base de datos."
                                    ),
                                )
                            else:
                                self._set_status(storage_warning=None)
                            active_tracks[track_id] = {
                                "entry_time": entry_time,
                                "missed_frames": 0,
                                "event_id": event_id,
                            }
                        else:
                            track["missed_frames"] = 0

                ids_to_close = []
                for track_id, track in active_tracks.items():
                    if track_id in current_person_ids:
                        continue

                    track["missed_frames"] += 1
                    if track["missed_frames"] >= 20:
                        if track["event_id"] is not None:
                            exit_time = datetime.now(timezone.utc)
                            duration = exit_time - track["entry_time"]
                            try:
                                close_event(
                                    event_id=track["event_id"],
                                    exit_time=exit_time,
                                    duration_seconds=int(duration.total_seconds()),
                                )
                            except Exception:
                                if not storage_warning_logged:
                                    logger.exception(
                                        "No se pudo actualizar un evento en la base de datos; "
                                        "el video seguirá activo.",
                                    )
                                    storage_warning_logged = True
                                self._set_status(
                                    storage_warning=(
                                        "No se pudo actualizar un evento en la base de datos."
                                    ),
                                    message=(
                                        "Video activo; no se pudo actualizar un evento "
                                        "en la base de datos."
                                    ),
                                )
                        ids_to_close.append(track_id)

                for track_id in ids_to_close:
                    del active_tracks[track_id]

                annotated_frame = result.plot()
                encoded, buffer = cv2.imencode(".jpg", annotated_frame)
                if not encoded:
                    raise RuntimeError("No se pudo codificar el fotograma de la cámara.")

                published_at = time.monotonic()
                with self._frame_condition:
                    if self._last_publish_at is None:
                        fps = 0.0
                    else:
                        elapsed = published_at - self._last_publish_at
                        instantaneous_fps = 1 / elapsed if elapsed > 0 else 0.0
                        previous_fps = self._status["fps"]
                        fps = (
                            instantaneous_fps
                            if previous_fps == 0
                            else previous_fps * 0.75 + instantaneous_fps * 0.25
                        )

                    self._latest_jpeg = buffer.tobytes()
                    self._frame_version += 1
                    self._last_publish_at = published_at
                    self._status.update(
                        online=True,
                        state="online",
                        message="Cámara conectada y detector activo.",
                        people_detected=len(current_person_ids),
                        last_frame_at=datetime.now(timezone.utc).isoformat(),
                        fps=round(fps, 1),
                    )
                    self._frame_condition.notify_all()

        except Exception as exc:
            logger.exception("El servicio de cámara se detuvo por un error.")
            self._set_status(
                online=False,
                state="error",
                message=str(exc),
            )
        finally:
            if camera is not None:
                camera.release()

            exit_time = datetime.now(timezone.utc)
            for track in active_tracks.values():
                if track["event_id"] is None:
                    continue
                duration = exit_time - track["entry_time"]
                try:
                    close_event(
                        event_id=track["event_id"],
                        exit_time=exit_time,
                        duration_seconds=int(duration.total_seconds()),
                    )
                except Exception:
                    logger.exception(
                        "No se pudo cerrar el evento %s al detener la cámara.",
                        track["event_id"],
                    )

            with self._lock:
                self._latest_jpeg = None
                self._last_publish_at = None
                if self._status["state"] not in {"offline", "error"}:
                    self._status.update(
                        online=False,
                        state="stopped",
                        message="El servicio de cámara está detenido.",
                        people_detected=0,
                        fps=0.0,
                    )
            with self._frame_condition:
                self._frame_condition.notify_all()


camera_service = CameraService()
