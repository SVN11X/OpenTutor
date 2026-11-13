import tempfile
import unittest
from pathlib import Path

from guardian.evidence.pptx_check import Check
from guardian.task_store import (
    FAILED,
    NEEDS_REVIEW,
    PENDING_DEFENSE,
    VALIDATED,
    TaskStore,
    clean_terms,
    defense_passed,
    final_status,
)


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TaskStore(Path(self.tmp.name) / "g.sqlite3")

    def test_add_list_and_archive_hides_without_deleting(self):
        first = self.store.add_task("BigQuery deck", 5, "partitioning, clustering, partitioning")
        self.store.add_task("Dataflow deck", 3)
        tasks = self.store.list_tasks()
        self.assertEqual([t.title for t in tasks], ["BigQuery deck", "Dataflow deck"])
        self.assertEqual(tasks[0].required_terms, ("partitioning", "clustering"))  # no duplicates
        sub = self.store.add_submission(
            first, "C:/secret/folder/deck.pptx", "passed", [Check("archive", True)]
        )
        self.store.archive_task(first)
        self.assertEqual([t.title for t in self.store.list_tasks()], ["Dataflow deck"])
        self.assertEqual(self.store.recent_submissions()[0].id, sub)  # evidence stays

    def test_validation_of_inputs(self):
        for title, slides in (("", 5), ("  ", 5), ("x" * 121, 5), ("ok", 0), ("ok", 101), ("ok", True)):
            with self.assertRaises(ValueError):
                self.store.add_task(title, slides)
        with self.assertRaises(ValueError):
            clean_terms(",".join(f"term{i}" for i in range(11)))
        with self.assertRaises(ValueError):
            clean_terms("x" * 41)

    def test_submission_keeps_only_the_file_name(self):
        task = self.store.add_task("T", 2)
        self.store.add_submission(
            task, "C:/Users/someone/private/deck.pptx", "needs_review", [Check("terms", False, "x")]
        )
        recent = self.store.recent_submissions()[0]
        self.assertEqual(recent.file_name, "deck.pptx")
        self.assertEqual(recent.checks, (("terms", False, "x"),))

    def test_defense_flow_and_statuses(self):
        task = self.store.add_task("T", 2)
        sub = self.store.add_submission(task, "d.pptx", "passed", [])
        self.assertEqual(self.store.recent_submissions()[0].final_status, PENDING_DEFENSE)
        self.assertEqual(self.store.record_defense(sub, 2, 3), VALIDATED)
        self.assertEqual(self.store.record_defense(sub, 1, 3), NEEDS_REVIEW)
        with self.assertRaises(ValueError):
            self.store.record_defense(999, 3, 3)

    def test_failed_rubric_cannot_be_validated_by_the_defense(self):
        task = self.store.add_task("T", 2)
        sub = self.store.add_submission(task, "d.pptx", "failed", [])
        self.assertEqual(self.store.record_defense(sub, 3, 3), FAILED)

    def test_final_status_rules(self):
        self.assertEqual(final_status("needs_review", 3, 3), NEEDS_REVIEW)
        self.assertEqual(final_status("passed"), PENDING_DEFENSE)
        self.assertTrue(defense_passed(2, 3))
        self.assertFalse(defense_passed(1, 3))
        self.assertTrue(defense_passed(2, 2))
        self.assertFalse(defense_passed(1, 2))


if __name__ == "__main__":
    unittest.main()
