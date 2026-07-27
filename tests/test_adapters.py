from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lightthecandle import __version__  # noqa: E402


class AgentAdapterContractTest(unittest.TestCase):
    def load_json(self, relative_path: str) -> dict:
        return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))

    def test_manifests_share_identity_and_release(self) -> None:
        codex = self.load_json(".codex-plugin/plugin.json")
        claude = self.load_json(".claude-plugin/plugin.json")

        self.assertEqual(codex["name"], "lightthecandle")
        self.assertEqual(claude["name"], codex["name"])
        self.assertEqual(codex["version"].split("+", 1)[0], __version__)
        self.assertEqual(claude["version"], __version__)
        self.assertEqual(claude["author"], codex["author"])

    def test_claude_marketplace_installs_this_plugin_root(self) -> None:
        marketplace = self.load_json(".claude-plugin/marketplace.json")

        self.assertEqual(marketplace["name"], "lightthecandle")
        self.assertEqual(len(marketplace["plugins"]), 1)
        plugin = marketplace["plugins"][0]
        self.assertEqual(plugin["name"], "lightthecandle")
        self.assertEqual(plugin["source"], "./")

    def test_adapters_do_not_add_automatic_execution_surfaces(self) -> None:
        codex = self.load_json(".codex-plugin/plugin.json")
        claude = self.load_json(".claude-plugin/plugin.json")
        automatic_surfaces = {
            "agents",
            "commands",
            "experimental",
            "hooks",
            "lspServers",
            "mcpServers",
            "settings",
        }

        self.assertTrue(automatic_surfaces.isdisjoint(codex))
        self.assertTrue(automatic_surfaces.isdisjoint(claude))
        self.assertTrue((ROOT / "scripts" / "ltc.py").is_file())
        self.assertTrue((ROOT / "skills" / "lightthecandle" / "SKILL.md").is_file())

    def test_shared_skill_documents_both_adapter_contracts(self) -> None:
        skill = (ROOT / "skills" / "lightthecandle" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("$lightthecandle", skill)
        self.assertIn("/lightthecandle:lightthecandle", skill)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", skill)
        self.assertNotIn("/Users/", skill)


if __name__ == "__main__":
    unittest.main()
