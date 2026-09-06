from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.project_manager import ProjectManager


class ProjectManagerTopicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manager = ProjectManager()
        self.manager.projects_directory = Path(self.temp_dir.name)

    def test_topic_is_persisted_without_losing_metadata(self) -> None:
        self.assertTrue(self.manager.create_project("demo"))

        metadata_path = self.manager.projects_directory / "demo" / "project.json"
        before = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertTrue(self.manager.save_topic("demo", "  Du lịch Việt Nam  "))
        self.assertEqual(self.manager.load_topic("demo"), "Du lịch Việt Nam")

        after = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(after["name"], before["name"])
        self.assertEqual(after["version"], before["version"])
        self.assertEqual(after["created_at"], before["created_at"])
        self.assertEqual(after["topic"], "Du lịch Việt Nam")
        self.assertIn("updated_at", after)

    def test_missing_or_invalid_topic_returns_empty_string(self) -> None:
        self.assertTrue(self.manager.create_project("demo"))
        metadata_path = self.manager.projects_directory / "demo" / "project.json"

        metadata_path.write_text("{not-json", encoding="utf-8")
        self.assertEqual(self.manager.load_topic("demo"), "")
        self.assertEqual(self.manager.load_topic("missing"), "")


if __name__ == "__main__":
    unittest.main()
