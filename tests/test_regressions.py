import io
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import cloud_notes
# Tests must never load real credentials or capture the user's webcam.
with patch.object(cloud_notes, "load_local_env"):
    import run
from board import SketchBoard
from notes_store import NotesStore
from camera import Camera


class BoardTests(unittest.TestCase):
    def stroke(self, points):
        return {"tool": "draw", "points": points, "color": (255,255,255), "width": 2}

    def test_erase_splits_sparse_segment(self):
        board = SketchBoard()
        board.strokes = [self.stroke([(0,100),(200,100)])]
        board._erase_near((100,100))
        self.assertEqual([s["points"] for s in board.strokes], [[(0,100),(60,100)],[(140,100),(200,100)]])

    def test_erase_dense_stroke_does_not_reconnect(self):
        board = SketchBoard()
        board.strokes = [self.stroke([(x,100) for x in range(0,201,10)])]
        board._erase_near((100,100))
        self.assertEqual(len(board.strokes), 2)
        self.assertLessEqual(board.strokes[0]["points"][-1][0],60)
        self.assertGreaterEqual(board.strokes[1]["points"][0][0],140)

    def test_tracking_loss_finishes_stroke_and_resets_hold(self):
        board = SketchBoard()
        board.active = self.stroke([(1,1),(2,2)])
        board.smooth, board.clear_since = (2,2), 10
        board.tracking_lost()
        self.assertIsNone(board.active)
        self.assertIsNone(board.smooth)
        self.assertIsNone(board.clear_since)
        self.assertEqual(len(board.strokes), 1)

    def test_clear_is_elapsed_time_and_undoable(self):
        board = SketchBoard()
        board.strokes = [self.stroke([(1,1),(2,2)])]
        hand = SimpleNamespace(landmark=[SimpleNamespace(x=.5,y=.5)]*21)
        with patch("board.time.monotonic", side_effect=[10,10.1,10.7]):
            board.apply("clear",hand,(480,640,3))
            board.apply("clear",hand,(480,640,3))
            self.assertEqual(len(board.strokes),1)
            board.apply("clear",hand,(480,640,3))
        self.assertEqual(board.strokes,[])
        board.undo_clear()
        self.assertEqual(len(board.strokes),1)


class NotesTests(unittest.TestCase):
    def test_order_retry_and_limit(self):
        notes = NotesStore()
        notes.add("second",1,"b")
        notes.add("first",0,"a")
        notes.add("first",0,"a")
        self.assertEqual(notes.text(),"first second")
        with self.assertRaises(ValueError): notes.add("different",0,"c")
        with self.assertRaises(ValueError): notes.add("x"*200001,2,"d")


class ApiTests(unittest.TestCase):
    def setUp(self):
        run.sessions.clear()
        run.app.logger.disabled = True
        self.client = run.app.test_client()
        response = self.call("/session", method="POST",headers={"X-AirSketch":"1"})
        self.token = response.json["token"]

    def call(self,path,**kwargs):
        headers = kwargs.pop("headers",{})
        if hasattr(self,"token"): headers.setdefault("X-Session-Token",self.token)
        return self.client.open(path,base_url="http://127.0.0.1:5000",headers=headers,**kwargs)

    def test_auth_origin_and_host(self):
        self.assertEqual(self.call("/frame.jpg",headers={"Origin":"https://untrusted.example"}).status_code,403)
        self.assertEqual(self.call("/frame.jpg",headers={"X-Session-Token":"bad"}).status_code,401)
        self.assertEqual(self.client.get("/frame.jpg",base_url="http://attacker.example:5000").status_code,403)
        self.assertEqual(self.call("/session",method="POST").status_code,403)

    def test_invalid_notes_return_400(self):
        for payload in [{"text":None},{"text":123},["text"],{"text":"x","sequence":True}]:
            self.assertEqual(self.call("/notes",method="POST",json=payload).status_code,400)

    def clip(self,data=b"audio",sequence=0):
        return self.call("/transcribe",method="POST",data={"sequence":str(sequence),"audio":(io.BytesIO(data),"lecture.webm","audio/webm")})

    def test_retry_deduplicates_and_sessions_are_isolated(self):
        with patch.object(run,"transcribe_audio",return_value="lecture one") as speech:
            self.assertEqual(self.clip().status_code,200)
            self.assertEqual(self.clip().status_code,200)
            self.assertEqual(speech.call_count,1)
            self.assertEqual(self.clip(b"different").status_code,409)
        old = self.token
        self.token = self.call("/session",method="POST",headers={"X-AirSketch":"1"}).json["token"]
        self.assertEqual(self.call("/summarize",method="POST").status_code,400)
        self.assertEqual(run.sessions[old].notes.text(),"lecture one")

    def test_upload_limit(self):
        self.assertEqual(self.clip(b"x"*(5*1024*1024)).status_code,413)

    def test_closed_lecture_rejects_late_transcription(self):
        lecture = run.sessions[self.token]
        def speech(_audio):
            lecture.closed = True
            return "late result"
        with patch.object(run,"transcribe_audio",side_effect=speech):
            self.assertEqual(self.clip().status_code,409)
        self.assertEqual(lecture.notes.text(),"")

    def test_busy_cloud_and_visible_fallback(self):
        lecture=run.sessions[self.token]
        lecture.cloud_lock.acquire()
        try: self.assertEqual(self.clip().status_code,429)
        finally: lecture.cloud_lock.release()
        lecture.notes.add("Plants use light for photosynthesis.",0)
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test"}), patch.object(run,"gemini_notes",side_effect=RuntimeError("private detail")):
            response=self.call("/summarize",method="POST")
        self.assertEqual(response.json["source"],"local")
        self.assertIn("warning",response.json)
        self.assertNotIn("private detail",json.dumps(response.json))


class CloudTests(unittest.TestCase):
    def test_grounded_response_and_blocked_output(self):
        result={"bullets":[{"text":"Plants use light.","evidence":"Plants use light"}],"questions":[]}
        response={"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(result)}]}}]}
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test"}),patch.object(cloud_notes,"_post_json",return_value=response):
            self.assertIn("Plants use light",cloud_notes.gemini_notes("Plants use light for photosynthesis."))
            with self.assertRaises(RuntimeError): cloud_notes.gemini_notes("An unrelated lecture.")
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test"}),patch.object(cloud_notes,"_post_json",return_value={"candidates":[]}):
            with self.assertRaises(RuntimeError): cloud_notes.gemini_notes("Lecture.")


class CameraTests(unittest.TestCase):
    def test_import_does_not_start_camera(self):
        self.assertIsNone(run.camera.thread)

    def test_stop_releases_device_and_resets_tracking(self):
        camera=Camera()
        capture=MagicMock()
        capture.read.return_value=(False,None)
        board=MagicMock()
        opened = threading.Event()
        def open_capture(_stop):
            opened.set()
            return capture
        with patch.object(camera,"_open",side_effect=open_capture),patch("camera.mp.solutions.hands.Hands"):
            camera.start("owner",board)
            self.assertTrue(opened.wait(2))
            camera.stop("owner")
        self.assertEqual(camera.snapshot("owner")[0]["state"],"off")
        self.assertFalse(camera.thread.is_alive())
        capture.release.assert_called()
        board.tracking_lost.assert_called()

    def test_expired_lease_stops_worker_without_opening_device(self):
        camera = Camera()
        camera.owner = "owner"
        camera.lease = 0
        board = MagicMock()
        with patch.object(camera,"_open") as open_camera,patch("camera.mp.solutions.hands.Hands"):
            camera._run(board, camera.stop_event)
        open_camera.assert_not_called()
        self.assertEqual(camera.state,"off")
        self.assertTrue(camera.stop_event.is_set())

    def test_other_session_cannot_read_frames(self):
        camera=Camera()
        camera.owner="owner"
        camera.jpeg=b"private"
        camera.state="on"
        self.assertIsNone(camera.snapshot("other")[1])


if __name__ == "__main__":
    unittest.main()
