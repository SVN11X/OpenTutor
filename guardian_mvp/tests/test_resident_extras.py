from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

from guardian_mvp import autostart, integrations
from guardian_mvp.session_state import INACTIVE, SessionState, SessionStore, parse_schedule

NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


class PendingAndScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SessionStore(Path(self.tmp.name) / "session.json")

    def test_pending_survives_inactive_and_expired_session(self):
        self.store.save(SessionState(False, pending=True))
        self.assertTrue(self.store.load(NOW).pending)
        self.store.save(SessionState(True, NOW - timedelta(minutes=1), pending=True, windows=(("09:00", "12:00"),)))
        kept = self.store.load(NOW)
        self.assertFalse(kept.active)
        self.assertTrue(kept.pending)
        self.assertEqual(kept.windows, (("09:00", "12:00"),))

    def test_nothing_to_keep_removes_file(self):
        self.store.save(SessionState(True, NOW + timedelta(hours=1)))
        self.store.save(SessionState(False))
        self.assertFalse(self.store.path.exists())
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_bad_windows_rejected_on_load(self):
        self.store.path.write_text(
            '{"schema_version":1,"active":false,"until":null,"paused_until":null,'
            '"topic":"x","source":"y","pending":true,"windows":[["25:00","26:00"]]}', encoding="utf-8")
        self.assertEqual(self.store.load(NOW), INACTIVE)

    def test_parse_schedule(self):
        self.assertEqual(parse_schedule(""), ())
        self.assertEqual(parse_schedule("09:00-12:00, 14:30-17:00"), (("09:00", "12:00"), ("14:30", "17:00")))
        for bad in ("9-12", "09:00", "09:00-25:00"):
            with self.assertRaises(ValueError):
                parse_schedule(bad)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        code = {"/ok": 200, "/missing": 404, "/boom": 500}[self.path]
        self.send_response(code)
        self.end_headers()

    def log_message(self, *_):
        pass


class IntegrationProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_states(self):
        self.assertEqual(integrations.probe_http("x", self.base + "/ok").state, "ok")
        self.assertEqual(integrations.probe_http("x", self.base + "/missing").state, "incompatible")
        self.assertEqual(integrations.probe_http("x", self.base + "/boom").state, "degraded")
        self.assertEqual(integrations.probe_http("x", "http://127.0.0.1:1/", timeout=0.5).state, "disconnected")

    def test_focolocal_never_claims_connection(self):
        states = {h.name: h.state for h in integrations.check_all(bank_ok=True)}
        self.assertEqual(states["FocoLocal"], "unavailable")

    def test_label_has_icon_and_text(self):
        self.assertIn("desconectado", integrations.Health("Ollama", "disconnected").text())


@unittest.skipUnless(sys.platform == "win32", "Windows registry only")
class AutostartTests(unittest.TestCase):
    def test_enable_disable_uses_isolated_key_and_is_reversible(self):
        key = r"Software\OpenTutorGuardianTest" + uuid.uuid4().hex
        try:
            self.assertFalse(autostart.is_enabled(key))
            autostart.enable(Path("C:/repo"), key)
            self.assertTrue(autostart.is_enabled(key))
            autostart.disable(key)
            self.assertFalse(autostart.is_enabled(key))
            autostart.disable(key)  # idempotent
        finally:
            import winreg
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except OSError:
                pass

    def test_command_is_hidden_and_user_level(self):
        cmd = autostart.build_command(Path("C:/repo"), sys.executable)
        self.assertIn("--hidden", cmd)
        self.assertIn("guardian_mvp.desktop", cmd)


if __name__ == "__main__":
    unittest.main()
