#!/usr/bin/env python3
"""Behavior tests for the FirstMate-only project sidebar reconciler.

The production change that should fail each test is named in the docstring.
Expectations are hand-written literals. The tests run the real planner and,
where noted, the real reconcile command against a fake herdr transport.
"""

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "herdr" / "project-sidebar" / "reconcile.py"


def load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("project_sidebar", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def journal(task, **overrides):
    fields = {
        "version": "2",
        "task_id": task,
        "projection_id": "AbCdEfGhIjKlMnOpQrStUv",
        "home": "/homes/fm",
        "session": "lab",
        "workspace_id": "w1",
        "tab_id": "w1:t1",
        "pane_id": "w1:p1",
        "parent_workspace_id": "w0",
        "parent_label": "parent",
        "workspace_label": "proj · p:AbCdEfGhIjKlMnOpQrStUv",
        "task_label": "fm-" + task,
    }
    fields.update(overrides)
    return fields


def meta(task, **overrides):
    fields = {
        "project": "/repos/store/alpha",
        "herdr_session": "lab",
        "herdr_workspace_id": "w1",
        "herdr_tab_id": "w1:t1",
        "herdr_pane_id": "w1:p1",
        "endpoint_task_id": task,
    }
    fields.update(overrides)
    return fields


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load()

    def test_verified_space_is_labeled_and_foreign_is_untouched(self):
        """Dropping the journal/workspace match would label a foreign row."""
        plan = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={"web": journal("web")},
            metas={"web": meta("web")},
            workspaces=[
                {"workspace_id": "w9", "label": "alpha", "pane_count": 1, "number": 1},
                {"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 2},
            ],
            panes=[
                {"pane_id": "w9:p1", "workspace_id": "w9"},
                {"pane_id": "w1:p1", "workspace_id": "w1"},
            ],
        )
        self.assertEqual(plan.workspace_tokens, {"w1": {"project": "alpha"}})
        self.assertEqual(plan.pane_tokens, {"w1:p1": {"project": "alpha"}})
        self.assertEqual(plan.moves, [])
        self.assertNotIn("w9", plan.workspace_tokens)

    def test_mixed_workspace_is_not_moved_or_space_labeled(self):
        """Treating pane_count as optional would reorder a shared workspace."""
        plan = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={"web": journal("web")},
            metas={"web": meta("web")},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 2, "number": 1}],
            panes=[
                {"pane_id": "w1:p1", "workspace_id": "w1"},
                {"pane_id": "w1:p2", "workspace_id": "w1"},
            ],
        )
        self.assertEqual(plan.workspace_tokens, {})
        self.assertEqual(plan.moves, [])
        self.assertEqual(plan.pane_tokens, {"w1:p1": {"project": "alpha"}})

    def test_equal_basenames_stay_distinct_and_form_separate_blocks(self):
        """Grouping by basename would merge two alpha checkouts into one block."""
        plan = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={
                "a": journal("a", workspace_id="w2", tab_id="w2:t1", pane_id="w2:p1"),
                "a2": journal(
                    "a2",
                    workspace_id="w5",
                    tab_id="w5:t1",
                    pane_id="w5:p1",
                    projection_id="AaBbCcDdEeFfGgHhIiJjKk",
                ),
                "b": journal(
                    "b",
                    workspace_id="w4",
                    tab_id="w4:t1",
                    pane_id="w4:p1",
                    projection_id="ZzYyXxWwVvUuTtSsRrQqPp",
                ),
            },
            metas={
                "a": meta("a", project="/repos/red/alpha", herdr_workspace_id="w2", herdr_tab_id="w2:t1", herdr_pane_id="w2:p1"),
                "a2": meta("a2", project="/repos/red/alpha", herdr_workspace_id="w5", herdr_tab_id="w5:t1", herdr_pane_id="w5:p1"),
                "b": meta("b", project="/repos/blue/alpha", herdr_workspace_id="w4", herdr_tab_id="w4:t1", herdr_pane_id="w4:p1"),
            },
            workspaces=[
                {"workspace_id": "w1", "label": "foreign", "pane_count": 1, "number": 1},
                {"workspace_id": "w2", "label": "a", "pane_count": 1, "number": 2},
                {"workspace_id": "w3", "label": "other", "pane_count": 1, "number": 3},
                {"workspace_id": "w4", "label": "b", "pane_count": 1, "number": 4},
                {"workspace_id": "w5", "label": "a2", "pane_count": 1, "number": 5},
            ],
            panes=[
                {"pane_id": "w2:p1", "workspace_id": "w2"},
                {"pane_id": "w4:p1", "workspace_id": "w4"},
                {"pane_id": "w5:p1", "workspace_id": "w5"},
            ],
        )
        self.assertEqual(plan.workspace_tokens["w2"]["project"], "alpha/red")
        self.assertEqual(plan.workspace_tokens["w4"]["project"], "alpha/blue")
        self.assertEqual(plan.workspace_tokens["w5"]["project"], "alpha/red")
        self.assertEqual(plan.order, ["w1", "w2", "w5", "w3", "w4"])
        self.assertEqual(plan.moves, [{"workspace_ids": ["w5"], "before_workspace_id": "w3"}])
        self.assertNotIn("w1", plan.workspace_tokens)
        self.assertNotIn("w3", plan.workspace_tokens)

    def test_second_pass_does_not_move_an_already_contiguous_block(self):
        """Repeating a move after the block is together would churn workspace order."""
        journals = {
            "a": journal("a", workspace_id="w2", tab_id="w2:t1", pane_id="w2:p1"),
            "a2": journal(
                "a2",
                workspace_id="w3",
                tab_id="w3:t1",
                pane_id="w3:p1",
                projection_id="AaBbCcDdEeFfGgHhIiJjKk",
            ),
        }
        metas = {
            "a": meta("a", herdr_workspace_id="w2", herdr_tab_id="w2:t1", herdr_pane_id="w2:p1"),
            "a2": meta("a2", herdr_workspace_id="w3", herdr_tab_id="w3:t1", herdr_pane_id="w3:p1"),
        }
        workspaces = [
            {"workspace_id": "w1", "label": "foreign", "pane_count": 1, "number": 1},
            {"workspace_id": "w2", "label": "a", "pane_count": 1, "number": 2, "tokens": {"project": "alpha"}},
            {"workspace_id": "w3", "label": "a2", "pane_count": 1, "number": 3, "tokens": {"project": "alpha"}},
        ]
        panes = [
            {"pane_id": "w2:p1", "workspace_id": "w2", "tokens": {"project": "alpha"}},
            {"pane_id": "w3:p1", "workspace_id": "w3", "tokens": {"project": "alpha"}},
        ]
        plan = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals=journals,
            metas=metas,
            workspaces=workspaces,
            panes=panes,
        )
        self.assertEqual(plan.moves, [])
        self.assertEqual(plan.workspace_tokens, {})
        self.assertEqual(plan.pane_tokens, {})
        self.assertTrue(plan.set_view)

    def test_stale_or_disagreed_endpoint_is_refused(self):
        """A missing live pane or a meta/journal mismatch must not be tagged."""
        stale = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={"web": journal("web", pane_id="w1:p9")},
            metas={"web": meta("web", herdr_pane_id="w1:p9")},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p1", "workspace_id": "w1"}],
        )
        self.assertEqual(stale.workspace_tokens, {})
        self.assertEqual(stale.pane_tokens, {})
        self.assertEqual(stale.moves, [])

        disagreed = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={"web": journal("web")},
            metas={"web": meta("web", herdr_workspace_id="w8")},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p1", "workspace_id": "w1"}],
        )
        self.assertEqual(disagreed.workspace_tokens, {})
        self.assertEqual(disagreed.moves, [])

        other_session = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={"web": journal("web", session="default")},
            metas={"web": meta("web", herdr_session="default")},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p1", "workspace_id": "w1"}],
        )
        self.assertEqual(other_session.moves, [])
        self.assertEqual(other_session.workspace_tokens, {})

    def test_two_journals_claiming_one_workspace_are_not_labeled(self):
        """A second binding on the same workspace would otherwise tag a mixed space."""
        plan = self.mod.plan(
            home="/homes/fm",
            session="lab",
            journals={
                "web": journal("web"),
                "api": journal(
                    "api",
                    pane_id="w1:p1",
                    projection_id="ZzYyXxWwVvUuTtSsRrQqPp",
                ),
            },
            metas={
                "web": meta("web"),
                "api": meta("api", project="/repos/other/beta"),
            },
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p1", "workspace_id": "w1"}],
        )
        self.assertEqual(plan.workspace_tokens, {})
        self.assertEqual(plan.pane_tokens, {})
        self.assertEqual(plan.moves, [])

    def test_current_home_v1_journal_labels_a_live_single_pane_space(self):
        """Rejecting a 3-line version 1 journal drops a live FirstMate space."""
        plan = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={
                "herdr-project-sidebar": {
                    "version": "1",
                    "task_id": "herdr-project-sidebar",
                    "projection_id": "igowBFVwAmz11Hc2d7eMVQ",
                }
            },
            metas={
                "herdr-project-sidebar": meta(
                    "herdr-project-sidebar",
                    project="/repos/dotfiles",
                    herdr_session="default",
                    herdr_workspace_id="wFY",
                    herdr_tab_id="wFY:t2",
                    herdr_pane_id="wFY:p2",
                    worktree="/work/dotfiles",
                )
            },
            workspaces=[
                {"workspace_id": "wEF", "label": "~", "pane_count": 2, "number": 1},
                {"workspace_id": "wFY", "label": "task", "pane_count": 1, "number": 2, "active_tab_id": "wFY:t2"},
            ],
            panes=[
                {"pane_id": "wFY:p2", "workspace_id": "wFY", "tab_id": "wFY:t2", "cwd": "/work/dotfiles"},
            ],
        )
        loaded = self.mod.parse_journal(
            "version=1\ntask_id=herdr-project-sidebar\nprojection_id=igowBFVwAmz11Hc2d7eMVQ\n",
            "herdr-project-sidebar",
            "/homes/fm",
        )
        self.assertEqual(loaded["version"], "1")
        parsed_meta = self.mod.parse_meta(
            "project=/repos/dotfiles\nworktree=/work/dotfiles\nwindow=default:wFY:p2\n"
            "herdr_session=default\nherdr_workspace_id=wFY\nherdr_tab_id=wFY:t2\n"
            "herdr_pane_id=wFY:p2\nendpoint_task_id=herdr-project-sidebar\n",
            "herdr-project-sidebar",
        )
        self.assertEqual(parsed_meta["worktree"], "/work/dotfiles")
        self.assertEqual(plan.workspace_tokens, {"wFY": {"project": "dotfiles"}})
        self.assertEqual(plan.pane_tokens, {"wFY:p2": {"project": "dotfiles"}})
        self.assertNotIn("wEF", plan.workspace_tokens)
        self.assertEqual(plan.moves, [])

    def test_v1_reused_stale_mixed_and_colliding_endpoints_stay_untouched(self):
        """A version 1 token must not authorize a pane whose cwd or identity disagrees."""
        journal_v1 = {
            "version": "1",
            "task_id": "web",
            "projection_id": "igowBFVwAmz11Hc2d7eMVQ",
        }
        base_meta = meta(
            "web",
            herdr_session="default",
            herdr_workspace_id="w1",
            herdr_tab_id="w1:t2",
            herdr_pane_id="w1:p2",
            worktree="/work/dotfiles",
        )
        reused = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={"web": journal_v1},
            metas={"web": base_meta},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "cwd": "/somewhere/else"}],
        )
        self.assertEqual(reused.workspace_tokens, {})
        self.assertEqual(reused.pane_tokens, {})
        self.assertGreaterEqual(reused.skipped.get("reused", 0), 1)

        stale = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={"web": journal_v1},
            metas={"web": base_meta},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p9", "workspace_id": "w1", "tab_id": "w1:t2", "cwd": "/work/dotfiles"}],
        )
        self.assertEqual(stale.workspace_tokens, {})
        self.assertGreaterEqual(stale.skipped.get("stale", 0), 1)

        mixed = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={"web": journal_v1},
            metas={"web": base_meta},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 2, "number": 1}],
            panes=[{"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "cwd": "/work/dotfiles"}],
        )
        self.assertEqual(mixed.workspace_tokens, {})
        self.assertEqual(mixed.moves, [])

        collision = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={
                "web": journal_v1,
                "api": {"version": "1", "task_id": "api", "projection_id": "ZzYyXxWwVvUuTtSsRrQqPp"},
            },
            metas={
                "web": base_meta,
                "api": meta("api", herdr_session="default", herdr_workspace_id="w1", herdr_tab_id="w1:t2", herdr_pane_id="w1:p2", worktree="/work/dotfiles", project="/repos/other/beta"),
            },
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1}],
            panes=[{"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "cwd": "/work/dotfiles"}],
        )
        self.assertEqual(collision.workspace_tokens, {})
        self.assertEqual(collision.pane_tokens, {})
        self.assertGreaterEqual(collision.skipped.get("ambiguous", 0), 1)

    def test_v1_static_cwd_cannot_override_a_contradictory_foreground_cwd(self):
        """A launch cwd that still matches must not hide a foreground cwd elsewhere."""
        journal_v1 = {
            "version": "1",
            "task_id": "web",
            "projection_id": "igowBFVwAmz11Hc2d7eMVQ",
        }
        info = meta(
            "web",
            herdr_session="default",
            herdr_workspace_id="w1",
            herdr_tab_id="w1:t2",
            herdr_pane_id="w1:p2",
            worktree="/work/dotfiles",
        )
        disagreed = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={"web": journal_v1},
            metas={"web": info},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1, "active_tab_id": "w1:t2"}],
            panes=[{
                "pane_id": "w1:p2",
                "workspace_id": "w1",
                "tab_id": "w1:t2",
                "cwd": "/work/dotfiles",
                "foreground_cwd": "/somewhere/else",
            }],
        )
        self.assertEqual(disagreed.workspace_tokens, {})
        self.assertEqual(disagreed.pane_tokens, {})
        self.assertGreaterEqual(disagreed.skipped.get("reused", 0), 1)

        fresh = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={"web": journal_v1},
            metas={"web": info},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1, "active_tab_id": "w1:t2"}],
            panes=[{
                "pane_id": "w1:p2",
                "workspace_id": "w1",
                "tab_id": "w1:t2",
                "cwd": "/launch/elsewhere",
                "foreground_cwd": "/work/dotfiles",
            }],
        )
        self.assertEqual(fresh.workspace_tokens, {"w1": {"project": "alpha"}})

        absent = self.mod.plan(
            home="/homes/fm",
            session="default",
            journals={"web": journal_v1},
            metas={"web": info},
            workspaces=[{"workspace_id": "w1", "label": "task", "pane_count": 1, "number": 1, "active_tab_id": "w1:t2"}],
            panes=[{"pane_id": "w1:p2", "workspace_id": "w1", "tab_id": "w1:t2", "cwd": "/work/dotfiles"}],
        )
        self.assertEqual(absent.workspace_tokens, {"w1": {"project": "alpha"}})

    def test_agent_view_sorts_by_project_and_does_not_filter(self):
        """A filter in the view would hide ordinary agents."""
        view = self.mod.agent_view("fm.project-sidebar")
        self.assertEqual(view["source"], "fm.project-sidebar")
        self.assertNotIn("filter", view)
        self.assertEqual(view["sort"], [
            {"field": {"token": "project"}, "order": "asc"},
            {"field": "workspace_order", "order": "asc"},
        ])

    def test_clear_names_only_our_source(self):
        """An empty clear would drop another tool's agent view."""
        self.assertEqual(self.mod.clear_view("fm.project-sidebar"), {"source": "fm.project-sidebar"})

    def test_view_change_allows_inactive_and_own_only(self):
        """Replacing a foreign or unreadable owner would drop that server-wide view."""
        own = "fm.project-sidebar"
        self.assertTrue(self.mod.view_change_allowed(
            {"result": {"type": "agent_view", "active": False}}, own))
        self.assertTrue(self.mod.view_change_allowed(
            {"result": {"type": "agent_view", "active": True, "source": own}}, own))
        self.assertFalse(self.mod.view_change_allowed(
            {"result": {"type": "agent_view", "active": True, "source": "other-tool", "label": "foreign"}}, own))
        self.assertFalse(self.mod.view_change_allowed({"result": {"type": "agent_view", "active": True}}, own))
        self.assertFalse(self.mod.view_change_allowed({}, own))
        self.assertFalse(self.mod.view_change_allowed({"error": {"code": "unavailable"}}, own))


class CommandTests(unittest.TestCase):
    def test_reconcile_does_not_focus_rename_or_close(self):
        """A focus, rename, or close in the command log would steal the user's place."""
        mod = load()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            state = home / "state"
            state.mkdir(parents=True)
            resolved = str(home.resolve())
            (state / "web.herdr-presentation").write_text(textwrap.dedent("""\
                version=2
                task_id=web
                projection_id=AbCdEfGhIjKlMnOpQrStUv
                home=%s
                session=lab
                workspace_id=w1
                tab_id=w1:t1
                pane_id=w1:p1
                parent_workspace_id=w0
                parent_label=parent
                workspace_label=ignored
                task_label=fm-web
                """ % resolved))
            (state / "web.meta").write_text(textwrap.dedent("""\
                project=/repos/store/alpha
                herdr_session=lab
                herdr_workspace_id=w1
                herdr_tab_id=w1:t1
                herdr_pane_id=w1:p1
                endpoint_task_id=web
                """))
            log = Path(tmp) / "herdr.log"
            fake = Path(tmp) / "herdr"
            fake.write_text(textwrap.dedent("""\
                #!/bin/sh
                printf '%s\\n' "$*" >> "$FAKE_HERDR_LOG"
                case "$1 $2" in
                  "workspace list")
                    printf '%s\\n' '{"result":{"workspaces":[{"workspace_id":"w9","label":"foreign","pane_count":1,"number":1},{"workspace_id":"w1","label":"task","pane_count":1,"number":2}]}}'
                    ;;
                  "pane list")
                    printf '%s\\n' '{"result":{"panes":[{"pane_id":"w9:p1","workspace_id":"w9"},{"pane_id":"w1:p1","workspace_id":"w1"}]}}'
                    ;;
                esac
                exit 0
                """))
            fake.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "FAKE_HERDR_LOG": str(log),
                "HERDR_BIN_PATH": str(fake),
                "PROJECT_SIDEBAR_HOME": str(home),
                "PROJECT_SIDEBAR_SESSION": "lab",
                "PROJECT_SIDEBAR_SOCKET_SEND": str(Path(tmp) / "socket"),
            })
            socket_log = Path(tmp) / "socket.log"
            socket = Path(tmp) / "socket"
            socket.write_text("#!/bin/sh\ncat >> \"$SOCKET_LOG\"\nprintf '%s\\n' '{\"result\":{\"type\":\"agent_view\",\"active\":false}}'\n")
            socket.chmod(0o755)
            env["SOCKET_LOG"] = str(socket_log)
            result = subprocess.run(
                ["python3", str(MODULE), "reconcile"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            logged = log.read_text()
            self.assertIn("workspace report-metadata w1 --source fm.project-sidebar --token project=alpha", logged)
            self.assertIn("pane report-metadata w1:p1 --source fm.project-sidebar --token project=alpha", logged)
            self.assertNotIn("report-metadata w9", logged)
            self.assertNotIn("workspace.move", logged)
            for forbidden in ("focus", "rename", "close"):
                self.assertNotIn(forbidden, logged)
            lines = [json.loads(line) for line in socket_log.read_text().splitlines() if line.strip()]
            self.assertEqual([line["method"] for line in lines], ["agent.view.clear", "agent.view.set"])
            self.assertEqual(lines[0]["params"], {"source": "fm.project-sidebar"})
            self.assertNotIn("filter", lines[1]["params"])

    def test_reconcile_does_not_replace_a_foreign_agent_view(self):
        """An unconditional agent.view.set would drop another tool's server-wide view."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            state = home / "state"
            state.mkdir(parents=True)
            resolved = str(home.resolve())
            (state / "web.herdr-presentation").write_text(textwrap.dedent("""\
                version=2
                task_id=web
                projection_id=AbCdEfGhIjKlMnOpQrStUv
                home=%s
                session=lab
                workspace_id=w1
                tab_id=w1:t1
                pane_id=w1:p1
                parent_workspace_id=w0
                parent_label=parent
                workspace_label=ignored
                task_label=fm-web
                """ % resolved))
            (state / "web.meta").write_text(
                "project=/repos/store/alpha\nherdr_session=lab\nherdr_workspace_id=w1\n"
                "herdr_tab_id=w1:t1\nherdr_pane_id=w1:p1\nendpoint_task_id=web\n"
            )
            log = Path(tmp) / "herdr.log"
            fake = Path(tmp) / "herdr"
            fake.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_HERDR_LOG\"\n"
                "case \"$1 $2\" in\n"
                "  \"workspace list\") printf '%s\\n' '{\"result\":{\"workspaces\":[{\"workspace_id\":\"w1\",\"label\":\"task\",\"pane_count\":1,\"number\":1}]}}' ;;\n"
                "  \"pane list\") printf '%s\\n' '{\"result\":{\"panes\":[{\"pane_id\":\"w1:p1\",\"workspace_id\":\"w1\"}]}}' ;;\n"
                "esac\nexit 0\n"
            )
            fake.chmod(0o755)
            socket_log = Path(tmp) / "socket.log"
            socket = Path(tmp) / "socket"
            socket.write_text(
                "#!/bin/sh\ncat >> \"$SOCKET_LOG\"\n"
                "printf '%s\\n' '{\"result\":{\"type\":\"agent_view\",\"active\":true,\"source\":\"other-tool\",\"label\":\"foreign\"}}'\n"
            )
            socket.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "FAKE_HERDR_LOG": str(log),
                "HERDR_BIN_PATH": str(fake),
                "PROJECT_SIDEBAR_HOME": str(home),
                "PROJECT_SIDEBAR_SESSION": "lab",
                "PROJECT_SIDEBAR_SOCKET_SEND": str(socket),
                "SOCKET_LOG": str(socket_log),
            })
            result = subprocess.run(
                ["python3", str(MODULE), "reconcile"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            logged = log.read_text()
            self.assertIn("workspace report-metadata w1 --source fm.project-sidebar --token project=alpha", logged)
            sent = socket_log.read_text()
            self.assertIn("agent.view.clear", sent)
            self.assertNotIn("agent.view.set", sent)


if __name__ == "__main__":
    unittest.main()
