"""Color-independent sidebar states, including provisional imported keys."""
import unittest

from guardian.results_ui import (
    AMBER, BLUE, GREEN, RED, sidebar_status,
)


class SidebarStatusTests(unittest.TestCase):
    def test_verified_success_has_icon_label_and_green_accent(self):
        state = sidebar_status(True, True)
        self.assertEqual((state.icon, state.label, state.accent),
                         ("✓", "Correcta", GREEN))

    def test_verified_failure_has_icon_label_and_red_accent(self):
        state = sidebar_status(True, False)
        self.assertEqual((state.icon, state.label, state.accent),
                         ("×", "Incorrecta", RED))

    def test_unverified_match_never_claims_correct(self):
        state = sidebar_status(False, True)
        self.assertEqual((state.icon, state.label, state.accent),
                         ("≈", "Coincide con clave", BLUE))
        self.assertNotIn("correct", state.label.lower())

    def test_unverified_difference_never_claims_wrong(self):
        state = sidebar_status(False, False)
        self.assertEqual((state.icon, state.label, state.accent),
                         ("≠", "Difiere de clave", AMBER))
        self.assertNotIn("incorrect", state.label.lower())

    def test_every_state_has_distinct_icon_and_nonempty_label(self):
        states = [sidebar_status(v,c) for v in (False,True) for c in (False,True)]
        self.assertEqual(len(set(x.icon for x in states)), 4)
        self.assertTrue(all(x.label for x in states))


if __name__ == "__main__":
    unittest.main()
