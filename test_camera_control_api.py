import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.camera import router


class CameraControlApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @patch("app.api.camera.camera_service.get_status", return_value={"state": "starting"})
    @patch("app.api.camera.camera_service.start")
    def test_start_camera_returns_status(self, start_camera, get_status):
        response = self.client.post("/camera/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], {"state": "starting"})
        start_camera.assert_called_once_with()
        get_status.assert_called_once_with()

    @patch("app.api.camera.camera_service.get_status", return_value={"state": "stopped"})
    @patch("app.api.camera.camera_service.stop")
    def test_stop_camera_returns_status(self, stop_camera, get_status):
        response = self.client.post("/camera/stop")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], {"state": "stopped"})
        stop_camera.assert_called_once_with()
        get_status.assert_called_once_with()

    @patch(
        "app.api.camera.camera_service.stop",
        side_effect=TimeoutError("El detector todavía está finalizando el fotograma actual."),
    )
    def test_stop_timeout_returns_service_unavailable(self, stop_camera):
        response = self.client.post("/camera/stop")

        self.assertEqual(response.status_code, 503)
        self.assertIn("finalizando", response.json()["detail"])
        stop_camera.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
