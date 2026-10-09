import cv2
from datetime import datetime, timezone
from pathlib import Path
from ultralytics import YOLO

from app.repositories.detection_event_repository import (
    close_event,
    create_event,
)


def main():

    camera = cv2.VideoCapture(0)
    active_tracks = {}

    try:

        if not camera.isOpened():
            raise RuntimeError(
                "No se pudo abrir la cámara. "
                "Revisa los permisos o prueba otro índice."
            )

        detector = YOLO("yolo11n.pt")

        # Carpeta para guardar evidencias
        events_folder = Path("events")
        events_folder.mkdir(exist_ok=True)

        # Cuántos frames permitimos que una persona desaparezca
        # antes de considerar que salió
        max_missed_frames = 20

        while True:

            success, frame = camera.read()

            if not success:
                print("No se pudo leer un fotograma.")
                break

            result = detector.track(
                frame,
                persist=True,
                conf=0.35,
                verbose=False
            )[0]

            # IDs de personas detectadas EN ESTE FRAME
            current_person_ids = set()

            if result.boxes.id is not None:

                track_ids = result.boxes.id.int().cpu().tolist()
                class_ids = result.boxes.cls.int().cpu().tolist()
                confidences = result.boxes.conf.cpu().tolist()

                for track_id, class_id, confidence in zip(
                    track_ids,
                    class_ids,
                    confidences
                ):

                    # Clase 0 = persona
                    if class_id != 0:
                        continue

                    current_person_ids.add(track_id)

                    print(
                        f"Persona ID={track_id} "
                        f"Confianza={confidence:.2%}"
                    )

                    # --------------------------------
                    # PERSONA NUEVA
                    # --------------------------------

                    if track_id not in active_tracks:

                        timestamp = datetime.now(timezone.utc)

                        image_name = (
                            f"person_{track_id}_"
                            f"{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                        )

                        image_path = events_folder / image_name

                        cv2.imwrite(
                            str(image_path),
                            frame
                        )

                        event_id = create_event(
                            track_id=track_id,
                            entry_time=timestamp,
                            confidence=confidence,
                            image_path=str(image_path),
                        )

                        active_tracks[track_id] = {
                            "entry_time": timestamp,
                            "missed_frames": 0,
                            "event_id": event_id,
                        }

                        print(
                            f"🟢 ENTRADA | "
                            f"ID={track_id} | "
                            f"Evento={event_id} | "
                            f"Evidencia={image_path}"
                        )

                    # --------------------------------
                    # PERSONA QUE YA ESTABA
                    # --------------------------------

                    else:

                        active_tracks[track_id]["missed_frames"] = 0

            # --------------------------------
            # BUSCAR PERSONAS QUE DESAPARECIERON
            # --------------------------------

            ids_to_remove = []

            for track_id in active_tracks:

                if track_id not in current_person_ids:

                    active_tracks[track_id]["missed_frames"] += 1

                    missed = active_tracks[track_id]["missed_frames"]

                    # Si desapareció demasiado tiempo
                    if missed >= max_missed_frames:

                        entry_time = active_tracks[track_id]["entry_time"]
                        exit_time = datetime.now(timezone.utc)

                        duration = exit_time - entry_time
                        event_id = active_tracks[track_id]["event_id"]

                        close_event(
                            event_id=event_id,
                            exit_time=exit_time,
                            duration_seconds=int(duration.total_seconds()),
                        )

                        print(
                            f"🔴 SALIDA | "
                            f"ID={track_id} | "
                            f"Evento={event_id} | "
                            f"Duración={duration} | "
                            "Registro actualizado en PostgreSQL"
                        )

                        ids_to_remove.append(track_id)

            # --------------------------------
            # ELIMINAR PERSONAS QUE YA SALIERON
            # --------------------------------

            for track_id in ids_to_remove:

                del active_tracks[track_id]

            # Mostrar cámara
            annotated_frame = result.plot()

            cv2.imshow(
                "Sistema de seguridad",
                annotated_frame
            )

            # Presionar Q para salir
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:

        try:
            exit_time = datetime.now(timezone.utc)
            for track_id, track in active_tracks.items():
                duration = exit_time - track["entry_time"]
                close_event(
                    event_id=track["event_id"],
                    exit_time=exit_time,
                    duration_seconds=int(duration.total_seconds()),
                )
                print(
                    f"Evento={track['event_id']} | "
                    f"ID={track_id} | "
                    "Registro cerrado en PostgreSQL al detener la app."
                )
        finally:
            camera.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()