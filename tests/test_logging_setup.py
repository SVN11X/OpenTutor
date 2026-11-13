import logging
import tempfile
import unittest
from pathlib import Path

from guardian.logging_setup import LOG_NAME, setup_logging


class LoggingSetupTests(unittest.TestCase):
    def test_writes_to_app_data_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = logging.getLogger("guardian")
            before = list(logger.handlers)
            try:
                path = setup_logging(Path(tmp))
                setup_logging(Path(tmp))
                self.assertEqual(path.name, LOG_NAME)
                self.assertEqual(len(logger.handlers), len(before) + 1)
                logging.getLogger("guardian.test").warning("hello")
                for handler in logger.handlers:
                    handler.flush()
                self.assertIn("hello", path.read_text(encoding="utf-8"))
            finally:
                for handler in list(logger.handlers):
                    if handler not in before:
                        handler.close()
                        logger.removeHandler(handler)


if __name__ == "__main__":
    unittest.main()
