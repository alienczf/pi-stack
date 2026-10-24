"""Prime projects must not fall through to the legacy Pi control plane."""
from support import EngineCase
from prime_support import project


class PrimeDispatchTests(EngineCase):
    def test_legacy_new_on_prime_project_reports_unwired_before_any_pi_call(self):
        result = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = project.load_project(self.project_file)
        config.info.backend = "prime"
        project.save_project(self.index, config)
        self.stub.requests.clear()
        result = self.run_streams("new", "unsupported-prime")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not wired", result.stderr)
        self.assertEqual(self.stub.requests, [])
        self.assertFalse((self.home / "unsupported-prime").exists())
