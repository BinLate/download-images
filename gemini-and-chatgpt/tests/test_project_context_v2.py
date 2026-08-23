import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from context_store import load_context, new_context, save_context
from project_context_scan import freshness, scan_project, slice_context


class ProjectContextV2Tests(unittest.TestCase):
    def make_repo(self, root: Path):
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "src" / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
        (root / "tests" / "test_app.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
        (root / "package.json").write_text(json.dumps({
            "name": "demo-app",
            "scripts": {"lint": "eslint .", "test": "vitest run", "build": "vite build"},
            "dependencies": {"react": "1"},
            "devDependencies": {"vitest": "1"},
        }), encoding="utf-8")
        (root / "package-lock.json").write_text("{}", encoding="utf-8")
        (root / ".env.example").write_text("API_TOKEN=example-only\nDB_URL=postgres://example\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("Use project conventions.\n", encoding="utf-8")

    def test_scan_discovers_stack_commands_modules_and_names_only_env(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            data = scan_project(root)
            self.assertEqual(data["schema_version"], "2.1.0")
            self.assertEqual(data["project"]["name"], "demo-app")
            self.assertIn("React", data["stack"]["frameworks"])
            self.assertIn("npm run test", data["commands"]["test"])
            self.assertIn("API_TOKEN", data["environment"]["required_variable_names"])
            serialized = json.dumps(data)
            self.assertNotIn("example-only", serialized)
            self.assertNotIn("postgres://example", serialized)
            self.assertTrue(any(m["path"] == "src" for m in data["modules"]))
            self.assertTrue(data["discovery"]["sources"])

    def test_freshness_detects_changed_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            data = scan_project(root)
            save_context(root, data, timestamp=data["updated_at"])
            self.assertEqual(freshness(root, load_context(root))["status"], "FRESH")
            (root / "package.json").write_text('{"name":"changed"}', encoding="utf-8")
            state = freshness(root, load_context(root))
            self.assertEqual(state["status"], "STALE")
            self.assertTrue(any(x.startswith("changed:package.json") for x in state["reasons"]))

    def test_freshness_detects_new_source_file_topology(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            data = scan_project(root)
            save_context(root, data, timestamp=data["updated_at"])
            (root / "src" / "new_module.py").write_text("x=2\n", encoding="utf-8")
            state = freshness(root, load_context(root))
            self.assertEqual(state["status"], "STALE")
            self.assertIn("source-inventory-changed", state["reasons"])

    def test_lazy_slice_excludes_unrequested_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            data = scan_project(root)
            result = slice_context(data, ["commands"])
            self.assertEqual(set(result["context"]), {"commands"})
            self.assertNotIn("modules", result["context"])
            self.assertNotIn("environment", result["context"])

    def test_legacy_context_upgrades_without_secret_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = {
                "schema_version": "2.0.0",
                "project": {"name": "demo", "root": str(root), "repository": None},
                "architecture": {"summary": "", "components": [], "boundaries": [], "constraints": []},
                "conventions": {"coding": [], "testing": [], "git": []},
                "commands": {"install": [], "lint": [], "typecheck": [], "test": [], "build": []},
                "decisions": [], "known_risks": [],
                "environment": {"required_variable_names": []}, "updated_at": "2026-08-20T00:00:00+00:00",
            }
            (root / ".ai").mkdir()
            (root / ".ai" / "project-context.json").write_text(json.dumps(legacy), encoding="utf-8")
            upgraded = load_context(root)
            self.assertEqual(upgraded["schema_version"], "2.1.0")
            self.assertIn("provenance", upgraded)
            self.assertIn("discovery", upgraded)

    def test_scanner_ignores_tool_and_runtime_folders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            (root / "gemini-and-chatgpt" / "scripts").mkdir(parents=True)
            (root / "gemini-and-chatgpt" / "scripts" / "secret.py").write_text("x=1", encoding="utf-8")
            (root / ".agents" / "skills" / "gemini-and-chatgpt").mkdir(parents=True)
            (root / ".agents" / "skills" / "gemini-and-chatgpt" / "SKILL.md").write_text("ignored", encoding="utf-8")
            data = scan_project(root)
            paths = [x["path"] for x in data["discovery"]["sources"]]
            self.assertFalse(any(p.startswith("gemini-and-chatgpt/") for p in paths))
            self.assertFalse(any(p.startswith(".agents/") for p in paths))

    def test_orchestrator_standard_classification_creates_fresh_context(self):
        from orchestrator import classify_and_route, initialize_task
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_repo(root)
            task = initialize_task(root, "Add a feature across several files", "feature")
            state = classify_and_route(root, task_id=task["identity"]["id"], estimated_files=4, estimated_components=2)
            self.assertEqual(state["lifecycle"]["current_state"], "PLANNING")
            context = load_context(root)
            self.assertEqual(freshness(root, context)["status"], "FRESH")

    def test_orchestrator_simple_classification_preserves_proportional_bypass(self):
        from orchestrator import classify_and_route, initialize_task
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "one.py").write_text("x=1\n", encoding="utf-8")
            task = initialize_task(root, "Fix typo in one file", "small fix")
            state = classify_and_route(root, task_id=task["identity"]["id"], estimated_files=1, estimated_components=1)
            self.assertEqual(state["lifecycle"]["current_state"], "IMPLEMENTING")
            self.assertFalse((root / ".ai" / "project-context.json").exists())


if __name__ == "__main__":
    unittest.main()
