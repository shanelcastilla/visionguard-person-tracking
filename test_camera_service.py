import unittest
from queue import Empty, Queue
from threading import Thread
from time import sleep

from app.services.camera_service import CameraService


class CameraStreamTests(unittest.TestCase):
    def test_stream_sends_only_new_frames(self):
        service = CameraService()
        service._latest_jpeg = b"first-frame"
        service._frame_version = 1
        stream = service.stream_frames()
        first_frame = next(stream)

        received_frames: Queue[bytes] = Queue()
        reader = Thread(target=lambda: received_frames.put(next(stream)))
        reader.start()
        sleep(0.05)
        self.assertTrue(received_frames.empty())

        with service._frame_condition:
            service._latest_jpeg = b"second-frame"
            service._frame_version += 1
            service._frame_condition.notify_all()

        try:
            second_frame = received_frames.get(timeout=1)
        except Empty:
            self.fail("The stream did not deliver the new frame.")
        finally:
            reader.join(timeout=1)
            stream.close()

        self.assertIn(b"first-frame", first_frame)
        self.assertIn(b"second-frame", second_frame)
