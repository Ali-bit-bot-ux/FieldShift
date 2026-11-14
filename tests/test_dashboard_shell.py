import unittest


class TestDashboardShell(unittest.TestCase):
    def test_frontend_tab_function_exists(self):
        from dashboard.rotation_planner_tab import render_rotation_planner_tab
        self.assertTrue(callable(render_rotation_planner_tab))

    def test_facade_function_exists_for_integrator(self):
        from modules.fieldshift_facade import get_fieldshift_recommendation
        self.assertTrue(callable(get_fieldshift_recommendation))


if __name__ == "__main__":
    unittest.main()
