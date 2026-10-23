#!/usr/bin/env python3
"""Read-only project folder tree. It does not move rows or set an agent view."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconcile

_SKIPPED = {"stale": 0, "ambiguous": 0, "unproven": 0}


def last_skipped():
    return dict(_SKIPPED)


def _clean(text):
    return "".join(ch for ch in str(text) if ch == " " or (ch.isprintable() and ch not in "\x1b\x7f"))


def assigned_rows(session, metas, panes, workspaces, agents):
    global _SKIPPED
    skipped = {"stale": 0, "ambiguous": 0, "unproven": 0}
    pane_ids = {row.get("pane_id"): row for row in panes}
    spaces = {row.get("workspace_id"): row for row in workspaces}
    agents_by_pane = {row.get("pane_id"): row for row in agents}
    claims = {}
    for task_id, info in metas.items():
        if info.get("herdr_session") != session or not str(info.get("project", "")).startswith("/"):
            skipped["unproven"] += 1
            continue
        pane_id = info.get("herdr_pane_id")
        workspace_id = info.get("herdr_workspace_id")
        tab_id = info.get("herdr_tab_id")
        if not pane_id or not workspace_id or not tab_id:
            skipped["unproven"] += 1
            continue
        claims.setdefault(pane_id, []).append(task_id)
    rows = []
    for pane_id, task_ids in claims.items():
        if len(task_ids) != 1:
            skipped["ambiguous"] += 1
            continue
        task_id = task_ids[0]
        info = metas[task_id]
        pane = pane_ids.get(pane_id)
        space = spaces.get(info["herdr_workspace_id"])
        if not pane or not space or pane.get("workspace_id") != info["herdr_workspace_id"]:
            skipped["stale"] += 1
            continue
        if pane.get("tab_id") and pane.get("tab_id") != info["herdr_tab_id"]:
            skipped["stale"] += 1
            continue
        agent = agents_by_pane.get(pane_id) or {}
        activity = agent.get("agent_status") or pane.get("agent_status") or "unobserved"
        rows.append({
            "project": info["project"],
            "task": info.get("endpoint_task_id") or task_id,
            "pane_id": pane_id,
            "activity": activity,
        })
    labels = reconcile.display_labels(sorted({row["project"] for row in rows}))
    for row in rows:
        row["label"] = labels[row["project"]]
    rows.sort(key=lambda row: (row["label"], row["task"]))
    _SKIPPED = skipped
    return rows


class TreeState:
    def __init__(self, rows):
        self.rows = rows
        self.collapsed = set()
        self.selected = 0

    def lines(self):
        return render(self.rows, self.collapsed, self.selected)


def render(rows, collapsed, selected=0):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["project"], []).append(row)
    lines = []
    index = 0
    for project in sorted(grouped, key=lambda item: grouped[item][0]["label"]):
        children = grouped[project]
        label = _clean(children[0]["label"])
        marker = "▸" if project in collapsed else "▾"
        pointer = ">" if index == selected else " "
        lines.append(pointer + " " + marker + " " + label + "/")
        index += 1
        if project in collapsed:
            continue
        for child in children:
            pointer = ">" if index == selected else " "
            lines.append(pointer + "   " + _clean(child["task"]) + "  " + _clean(child["activity"]))
            index += 1
    return lines or ["  no assigned workers"]


def refresh_state(state, rows):
    state.rows = rows
    visible = _visible_projects(state.rows, state.collapsed)
    if not visible:
        state.selected = 0
    elif state.selected >= len(visible):
        state.selected = len(visible) - 1
    return state


def handle_key(state, key):
    visible = _visible_projects(state.rows, state.collapsed)
    count = len(visible)
    if key in ("j", "down") and state.selected + 1 < count:
        state.selected += 1
    elif key in ("k", "up") and state.selected > 0:
        state.selected -= 1
    elif key in ("enter", " ", "h", "l", "left", "right"):
        project = visible[state.selected] if visible else None
        if project:
            if project in state.collapsed:
                state.collapsed.remove(project)
            else:
                state.collapsed.add(project)
    return state


def _visible_projects(rows, collapsed):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["project"], row["label"])
    visible = []
    for project in sorted(grouped, key=lambda item: grouped[item]):
        visible.append(project)
        if project not in collapsed:
            visible.extend([None] * sum(1 for row in rows if row["project"] == project))
    return visible


def _herdr(*args):
    binary = os.environ.get("HERDR_BIN_PATH") or "herdr"
    result = subprocess.run([binary, *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "herdr failed")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _rows(payload, key):
    result = payload.get("result", payload)
    return result.get(key, [])


def load_live():
    home = reconcile.configured_home()
    session = reconcile.current_session()
    if not home or not session:
        return [], "home or session is not configured"
    _home_id, _journals, metas = reconcile.load_home(home)
    workspaces = _rows(_herdr("workspace", "list"), "workspaces")
    panes = []
    found = {}
    for row in workspaces:
        for pane in _rows(_herdr("pane", "list", "--workspace", row["workspace_id"]), "panes"):
            found[pane.get("pane_id")] = pane
    panes = list(found.values())
    try:
        agents = _rows(_herdr("agent", "list"), "agents")
    except Exception:
        agents = []
    return assigned_rows(session, metas, panes, workspaces, agents), ""


def draw(state):
    # setraw disables output postprocessing, so a bare LF leaves the cursor
    # in the previous column. CR restores column 0.
    sys.stdout.write("\x1b[H\x1b[2J")
    sys.stdout.write("Projects\r\n")
    sys.stdout.write("\r\n".join(state.lines()) + "\r\n")
    sys.stdout.write("\r\nj/k move  enter fold  r refresh  q quit\r\n")
    sys.stdout.flush()


def main(argv):
    rows, warning = load_live()
    state = TreeState(rows)
    if warning:
        print(warning, file=sys.stderr)
    if not sys.stdin.isatty() or "--once" in argv:
        print("\n".join(state.lines()))
        return 0
    import termios
    import tty
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        draw(state)
        import select
        while True:
            ready, _, _ = select.select([fd], [], [], 2.0)
            if not ready:
                try:
                    refreshed, refresh_warning = load_live()
                except Exception as exc:
                    print("project-tree: refresh failed: " + str(exc), file=sys.stderr)
                else:
                    if refresh_warning:
                        print(refresh_warning, file=sys.stderr)
                    else:
                        refresh_state(state, refreshed)
                        draw(state)
                continue
            key = sys.stdin.read(1)
            if key in ("q", "\x03"):
                break
            if key == "\r":
                key = "enter"
            if key == "r":
                try:
                    refreshed, refresh_warning = load_live()
                except Exception as exc:
                    print("project-tree: refresh failed: " + str(exc), file=sys.stderr)
                else:
                    if not refresh_warning:
                        refresh_state(state, refreshed)
                draw(state)
                continue
            handle_key(state, key)
            draw(state)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:
        print("project-tree: " + str(exc), file=sys.stderr)
        sys.exit(1)
