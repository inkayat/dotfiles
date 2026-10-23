#!/usr/bin/env python3
"""Read-only project-folder tree. These tests do not exercise sidebar mutation."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "herdr" / "project-sidebar" / "tree.py"


def load():
    spec = importlib.util.spec_from_file_location("project_tree", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def meta(task, **overrides):
    fields = {
        "project": "/repos/alter",
        "herdr_session": "default",
        "herdr_workspace_id": "wEF",
        "herdr_tab_id": "wEF:t9",
        "herdr_pane_id": "wEF:pC",
        "endpoint_task_id": task,
        "worktree": "/work/alter-task",
    }
    fields.update(overrides)
    return fields


class TreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load()

    def test_background_tab_and_cwd_mismatch_still_appear_under_distinct_projects(self):
        """Dropping a background tab or a cwd mismatch would hide a live assigned worker."""
        rows = self.mod.assigned_rows(
            session="default",
            metas={
                "alter-author": meta("alter-author"),
                "alter-reviewer": meta(
                    "alter-reviewer",
                    project="/repos/alter",
                    herdr_workspace_id="wFV",
                    herdr_tab_id="wFV:t2",
                    herdr_pane_id="wFV:p2",
                    worktree="/work/alter-review",
                ),
                "other-alpha": meta(
                    "other-alpha",
                    project="/repos/blue/alpha",
                    herdr_workspace_id="w2",
                    herdr_tab_id="w2:t1",
                    herdr_pane_id="w2:p1",
                    worktree="/work/blue",
                ),
                "red-alpha": meta(
                    "red-alpha",
                    project="/repos/red/alpha",
                    herdr_workspace_id="w3",
                    herdr_tab_id="w3:t1",
                    herdr_pane_id="w3:p1",
                    worktree="/work/red",
                ),
            },
            panes=[
                {"pane_id": "wEF:pC", "workspace_id": "wEF", "tab_id": "wEF:t9", "cwd": "/home", "foreground_cwd": "/home"},
                {"pane_id": "wFV:p2", "workspace_id": "wFV", "tab_id": "wFV:t2", "cwd": "/work/alter-review", "foreground_cwd": "/repos/alter"},
                {"pane_id": "w2:p1", "workspace_id": "w2", "tab_id": "w2:t1"},
                {"pane_id": "w3:p1", "workspace_id": "w3", "tab_id": "w3:t1"},
                {"pane_id": "w9:p1", "workspace_id": "w9", "tab_id": "w9:t1"},
            ],
            workspaces=[
                {"workspace_id": "wEF", "label": "~", "pane_count": 2, "active_tab_id": "wEF:t1"},
                {"workspace_id": "wFV", "label": "review", "pane_count": 1, "active_tab_id": "wFV:t2"},
                {"workspace_id": "w2", "pane_count": 1, "active_tab_id": "w2:t1"},
                {"workspace_id": "w3", "pane_count": 1, "active_tab_id": "w3:t1"},
            ],
            agents=[
                {"pane_id": "wEF:pC", "agent_status": "working", "name": "author"},
                {"pane_id": "wFV:p2", "agent_status": "idle"},
            ],
        )
        by_project = {}
        for row in rows:
            by_project.setdefault(row["project"], []).append(row["task"])
        self.assertEqual(by_project["/repos/alter"], ["alter-author", "alter-reviewer"])
        self.assertIn("/repos/blue/alpha", by_project)
        self.assertIn("/repos/red/alpha", by_project)
        self.assertNotIn("w9:p1", [row["pane_id"] for row in rows])

    def test_stale_and_duplicate_endpoints_are_not_live_rows(self):
        """A missing or twice-claimed pane must not be shown as an assigned worker."""
        rows = self.mod.assigned_rows(
            session="default",
            metas={
                "gone": meta("gone", herdr_pane_id="w1:p9"),
                "one": meta("one", herdr_workspace_id="w1", herdr_tab_id="w1:t1", herdr_pane_id="w1:p1", project="/repos/one"),
                "two": meta("two", herdr_workspace_id="w1", herdr_tab_id="w1:t1", herdr_pane_id="w1:p1", project="/repos/two"),
            },
            panes=[{"pane_id": "w1:p1", "workspace_id": "w1", "tab_id": "w1:t1"}],
            workspaces=[{"workspace_id": "w1", "pane_count": 1, "active_tab_id": "w1:t1"}],
            agents=[],
        )
        self.assertEqual(rows, [])
        self.assertGreaterEqual(self.mod.last_skipped()["stale"], 1)
        self.assertGreaterEqual(self.mod.last_skipped()["ambiguous"], 1)

    def test_render_folds_and_strips_controls(self):
        """A collapsed folder that still prints children, or a raw escape, would be the wrong tree."""
        rows = [
            {"project": "/repos/alter", "label": "alter", "task": "author\x1b[31m", "pane_id": "wEF:pC", "activity": "working"},
            {"project": "/repos/alter", "label": "alter", "task": "reviewer", "pane_id": "wFV:p2", "activity": "idle"},
        ]
        shown = self.mod.render(rows, collapsed=set())
        text = "\n".join(shown)
        self.assertIn("alter/", text)
        self.assertIn("author", text)
        self.assertNotIn("\x1b", text)
        folded = self.mod.render(rows, collapsed={"/repos/alter"})
        self.assertNotIn("reviewer", "\n".join(folded))
        state = self.mod.TreeState(rows)
        self.mod.handle_key(state, "enter")
        self.assertIn("/repos/alter", state.collapsed)
        self.mod.handle_key(state, "enter")
        self.assertNotIn("/repos/alter", state.collapsed)

    def test_tree_display_does_not_relax_sidebar_mutation(self):
        """Showing a background-tab worker must not label or move its mixed workspace."""
        spec = importlib.util.spec_from_file_location(
            "project_sidebar_mutation", ROOT / "herdr" / "project-sidebar" / "reconcile.py")
        sidebar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sidebar)
        plan = sidebar.plan(
            home="/homes/fm",
            session="default",
            journals={"alter-author": {
                "version": "1",
                "task_id": "alter-author",
                "projection_id": "igowBFVwAmz11Hc2d7eMVQ",
            }},
            metas={"alter-author": meta("alter-author")},
            workspaces=[{"workspace_id": "wEF", "label": "~", "pane_count": 2, "number": 1, "active_tab_id": "wEF:t1"}],
            panes=[{"pane_id": "wEF:pC", "workspace_id": "wEF", "tab_id": "wEF:t9", "cwd": "/home", "foreground_cwd": "/home"}],
        )
        self.assertEqual(plan.workspace_tokens, {})
        self.assertEqual(plan.moves, [])

    def test_refresh_shows_a_new_worker_without_losing_the_fold(self):
        """A viewer that loads once would keep a closed agent on screen forever."""
        first = [{"project": "/repos/alter", "label": "alter", "task": "author", "pane_id": "p1", "activity": "working"}]
        state = self.mod.TreeState(first)
        self.mod.handle_key(state, "enter")
        self.assertIn("/repos/alter", state.collapsed)
        state.selected = 4
        second = first + [{"project": "/repos/other", "label": "other", "task": "new-worker", "pane_id": "p2", "activity": "idle"}]
        self.mod.refresh_state(state, second)
        text = "\n".join(state.lines())
        self.assertIn("new-worker", text)
        self.assertNotIn("author", text)
        self.assertIn("/repos/alter", state.collapsed)
        self.assertLess(state.selected, len(state.lines()))


if __name__ == "__main__":
    unittest.main()
