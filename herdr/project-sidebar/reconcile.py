#!/usr/bin/env python3
"""Label and order verified FirstMate spaces. Display only.

Ownership comes from a configured home's version-2 presentation journal plus
the matching task record, checked against the live session. A workspace label
or a project-looking path is not ownership. Mixed and foreign rows are not
moved. This is contiguous ordering, not a native sidebar section.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SOURCE = "fm.project-sidebar"
TOKEN = "project"
JOURNAL_SUFFIX = ".herdr-presentation"
META_SUFFIX = ".meta"
JOURNAL_KEYS = (
    "version",
    "task_id",
    "projection_id",
    "home",
    "session",
    "workspace_id",
    "tab_id",
    "pane_id",
    "parent_workspace_id",
    "parent_label",
    "workspace_label",
    "task_label",
)
META_KEYS = (
    "project",
    "herdr_session",
    "herdr_workspace_id",
    "herdr_tab_id",
    "herdr_pane_id",
    "endpoint_task_id",
)


class Plan:
    def __init__(self, workspace_tokens, pane_tokens, moves, order, set_view, skipped=None):
        self.workspace_tokens = workspace_tokens
        self.pane_tokens = pane_tokens
        self.moves = moves
        self.order = order
        self.set_view = set_view
        self.skipped = skipped or {"stale": 0, "reused": 0, "ambiguous": 0, "unproven": 0}


def agent_view(source):
    return {
        "source": source,
        "label": "projects",
        "sort": [
            {"field": {"token": TOKEN}, "order": "asc"},
            {"field": "workspace_order", "order": "asc"},
        ],
    }


def clear_view(source):
    return {"source": source}


def view_change_allowed(response, our_source):
    """True only when a source-scoped clear shows the view is inactive or already ours.

    A foreign source in that response means the clear was a no-op. Missing or
    malformed results are unknown and must not be replaced. This is not atomic.
    """
    result = response.get("result") if isinstance(response, dict) else None
    if not isinstance(result, dict) or result.get("type") != "agent_view":
        return False
    if not result.get("active"):
        return True
    return result.get("source") == our_source


def view_source():
    plugin = os.environ.get("HERDR_PLUGIN_ID", "").strip()
    if plugin:
        return "plugin:" + plugin
    return SOURCE


def _field(text, key):
    prefix = key + "="
    found = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(found) != 1:
        return None
    return found[0]


def _projection_id_ok(token):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    return isinstance(token, str) and len(token) == 22 and all(ch in alphabet for ch in token)


def parse_journal(text, task_id, home):
    lines = text.splitlines()
    if len(lines) == 3:
        version = _field(text, "version")
        found_task = _field(text, "task_id")
        projection_id = _field(text, "projection_id")
        if version != "1" or found_task != task_id or not _projection_id_ok(projection_id):
            return None
        return {"version": "1", "task_id": task_id, "projection_id": projection_id}
    if len(lines) != 12:
        return None
    fields = {key: _field(text, key) for key in JOURNAL_KEYS}
    if any(value is None for value in fields.values()):
        return None
    if fields["version"] != "2" or fields["task_id"] != task_id:
        return None
    if fields["task_label"] != "fm-" + task_id:
        return None
    if not _projection_id_ok(fields["projection_id"]):
        return None
    if fields["home"] != home:
        return None
    for key in ("session", "workspace_id", "tab_id", "pane_id", "parent_workspace_id"):
        if not fields[key] or any(ch.isspace() for ch in fields[key]):
            return None
    return fields


def parse_meta(text, task_id):
    fields = {key: _field(text, key) for key in META_KEYS}
    if any(fields[key] is None for key in META_KEYS if key != "endpoint_task_id"):
        return None
    if fields["endpoint_task_id"] not in (None, task_id):
        return None
    if not fields["project"].startswith("/"):
        return None
    for key in ("worktree", "window"):
        value = _field(text, key)
        if value:
            fields[key] = value
    return fields


def display_labels(paths):
    names = {path: Path(path).name or "project" for path in paths}
    counts = {}
    for name in names.values():
        counts[name] = counts.get(name, 0) + 1
    labels = {}
    for path, name in names.items():
        if counts[name] == 1:
            labels[path] = name
        else:
            parent = Path(path).parent.name or "root"
            labels[path] = name + "/" + parent
    again = {}
    for label in labels.values():
        again[label] = again.get(label, 0) + 1
    for path, label in list(labels.items()):
        if again[label] > 1:
            digest = hashlib.sha256(path.encode()).hexdigest()[:6]
            labels[path] = label + "/" + digest
    for path, label in labels.items():
        if len(label) > 80:
            labels[path] = label[:73] + "/" + hashlib.sha256(path.encode()).hexdigest()[:6]
    return labels


def _ordered(workspaces):
    return [row["workspace_id"] for row in sorted(workspaces, key=lambda row: row.get("number", 0))]


def _desired(order, project_of):
    grouped = {}
    for workspace_id in order:
        key = project_of.get(workspace_id)
        if key:
            grouped.setdefault(key, []).append(workspace_id)
    emitted = set()
    desired = []
    for workspace_id in order:
        if workspace_id in emitted:
            continue
        key = project_of.get(workspace_id)
        if not key:
            desired.append(workspace_id)
            emitted.add(workspace_id)
            continue
        for member in grouped[key]:
            if member not in emitted:
                desired.append(member)
                emitted.add(member)
    return desired


def _moves(order, desired, verified):
    current = list(order)
    moves = []
    if current == desired:
        return moves
    project_of = {}
    # verified maps workspace -> project key
    for workspace_id, key in verified.items():
        project_of[workspace_id] = key
    seen = set()
    for workspace_id in current:
        key = project_of.get(workspace_id)
        if not key or key in seen:
            continue
        seen.add(key)
        members = [item for item in current if project_of.get(item) == key]
        first = current.index(members[0])
        if current[first:first + len(members)] == members:
            continue
        anchor = next(item for item in current[first + 1:] if item not in members)
        followers = [item for item in members[1:] if item in current]
        if not followers or any(item not in verified for item in followers):
            continue
        moves.append({"workspace_ids": followers, "before_workspace_id": anchor})
        block = [item for item in current if item not in followers]
        at = block.index(anchor)
        current = block[:at] + followers + block[at:]
    return moves


def _cwd_matches(pane, worktree):
    wanted = str(worktree).rstrip("/")
    if not wanted:
        return False
    foreground = pane.get("foreground_cwd")
    if isinstance(foreground, str) and foreground.strip():
        return foreground.rstrip("/") == wanted
    cwd = pane.get("cwd")
    return isinstance(cwd, str) and cwd.rstrip("/") == wanted


def plan(home, session, journals, metas, workspaces, panes):
    pane_ids = {row["pane_id"]: row for row in panes}
    spaces = {row["workspace_id"]: row for row in workspaces}
    verified = {}
    pane_of = {}
    skipped = {"stale": 0, "reused": 0, "ambiguous": 0, "unproven": 0}
    claims = {}
    for task_id, record in journals.items():
        parsed = record
        info = metas.get(task_id)
        if parsed.get("version") == "1":
            if parsed.get("task_id") != task_id or not _projection_id_ok(parsed.get("projection_id")):
                skipped["unproven"] += 1
                continue
            if not info or info.get("herdr_session") != session:
                skipped["unproven"] += 1
                continue
            workspace_id = info.get("herdr_workspace_id")
            pane_id = info.get("herdr_pane_id")
            tab_id = info.get("herdr_tab_id")
            worktree = info.get("worktree")
            if not all((workspace_id, pane_id, tab_id, worktree, info.get("project"))):
                skipped["unproven"] += 1
                continue
            window = info.get("window")
            if window and window != session + ":" + pane_id:
                skipped["reused"] += 1
                continue
            pane = pane_ids.get(pane_id)
            space = spaces.get(workspace_id)
            if not pane or not space or pane.get("workspace_id") != workspace_id:
                skipped["stale"] += 1
                continue
            if pane.get("tab_id") and pane.get("tab_id") != tab_id:
                skipped["reused"] += 1
                continue
            if space.get("active_tab_id") and space.get("active_tab_id") != tab_id:
                skipped["reused"] += 1
                continue
            if not _cwd_matches(pane, worktree):
                skipped["reused"] += 1
                continue
            claims.setdefault(workspace_id, []).append(task_id)
            verified[workspace_id] = info["project"]
            pane_of[pane_id] = info["project"]
            continue
        if parsed.get("session") != session or parsed.get("home") != home:
            continue
        if not info:
            continue
        if info.get("herdr_session") != parsed["session"]:
            continue
        if info.get("herdr_workspace_id") != parsed["workspace_id"]:
            continue
        if info.get("herdr_pane_id") != parsed["pane_id"]:
            continue
        if info.get("herdr_tab_id") != parsed["tab_id"]:
            continue
        pane = pane_ids.get(parsed["pane_id"])
        space = spaces.get(parsed["workspace_id"])
        if not pane or not space or pane.get("workspace_id") != parsed["workspace_id"]:
            continue
        claims.setdefault(parsed["workspace_id"], []).append(task_id)
        verified[parsed["workspace_id"]] = info["project"]
        pane_of[parsed["pane_id"]] = info["project"]

    for workspace_id, tasks in claims.items():
        if len(tasks) > 1:
            skipped["ambiguous"] += 1
            verified.pop(workspace_id, None)
            for pane_id, row in list(pane_ids.items()):
                if row.get("workspace_id") == workspace_id:
                    pane_of.pop(pane_id, None)

    labels = display_labels(sorted(set(verified.values()) | set(pane_of.values())))
    workspace_tokens = {}
    single = {}
    for workspace_id, project in verified.items():
        space = spaces[workspace_id]
        if space.get("pane_count") != 1:
            continue
        single[workspace_id] = project
        label = labels[project]
        current = (space.get("tokens") or {}).get(TOKEN)
        if current != label:
            workspace_tokens[workspace_id] = {TOKEN: label}
    pane_tokens = {}
    for pane_id, project in pane_of.items():
        space = spaces.get(pane_ids[pane_id]["workspace_id"], {})
        if space.get("pane_count") != 1 and pane_ids[pane_id]["workspace_id"] not in single:
            # Exact pane in a mixed workspace may still be labeled.
            pass
        label = labels[project]
        current = (pane_ids[pane_id].get("tokens") or {}).get(TOKEN)
        if current != label:
            pane_tokens[pane_id] = {TOKEN: label}
    order = _ordered(workspaces)
    moves = _moves(order, _desired(order, single), single)
    return Plan(workspace_tokens, pane_tokens, moves, _desired(order, single), bool(pane_of), skipped)


def _read_kv_file(path, allowed):
    if not path.is_file() or path.is_symlink():
        return None
    text = path.read_text()
    return text


def load_home(home):
    root = Path(home)
    try:
        home_id = str(root.resolve())
    except OSError:
        return None, {}, {}
    state = root / "state"
    journals = {}
    metas = {}
    if not state.is_dir():
        return home_id, journals, metas
    for path in state.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        name = path.name
        if name.startswith("."):
            continue
        if name.endswith(JOURNAL_SUFFIX):
            task_id = name[: -len(JOURNAL_SUFFIX)]
            text = path.read_text()
            parsed = parse_journal(text, task_id, home_id)
            if parsed:
                journals[task_id] = parsed
        elif name.endswith(META_SUFFIX):
            task_id = name[: -len(META_SUFFIX)]
            text = path.read_text()
            parsed = parse_meta(text, task_id)
            if parsed:
                project = parsed["project"]
                project_path = Path(project)
                if project_path.exists():
                    parsed["project"] = str(project_path.resolve())
                metas[task_id] = parsed
    return home_id, journals, metas


def _herdr(*args):
    binary = os.environ.get("HERDR_BIN_PATH") or "herdr"
    result = subprocess.run([binary, *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "herdr failed")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _rows(payload, key):
    result = payload.get("result", payload)
    return result.get(key, [])


def _panes(workspaces):
    found = {}
    for row in workspaces:
        for pane in _rows(_herdr("pane", "list", "--workspace", row["workspace_id"]), "panes"):
            found[pane["pane_id"]] = pane
    if not found:
        for pane in _rows(_herdr("pane", "list"), "panes"):
            found[pane["pane_id"]] = pane
    return list(found.values())


def _send(method, params):
    body = json.dumps({"id": "fm.project-sidebar", "method": method, "params": params})
    override = os.environ.get("PROJECT_SIDEBAR_SOCKET_SEND")
    if override:
        result = subprocess.run([override], input=body + "\n", text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "socket send failed")
        return json.loads(result.stdout) if result.stdout.strip() else {}
    socket_path = os.environ.get("HERDR_SOCKET_PATH", "")
    script = Path(__file__).with_name("socket_call.py")
    result = subprocess.run(
        [sys.executable, str(script), socket_path],
        input=body + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "socket call failed")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _report(kind, target, tokens):
    args = [kind, "report-metadata", target, "--source", SOURCE]
    for key, value in tokens.items():
        args.extend(["--token", key + "=" + value])
    _herdr(*args)


def _clear_tokens(kind, target):
    _herdr(kind, "report-metadata", target, "--source", SOURCE, "--clear-token", TOKEN)


def configured_home():
    override = os.environ.get("PROJECT_SIDEBAR_HOME", "").strip()
    if override:
        return override
    config = os.environ.get("PROJECT_SIDEBAR_CONFIG", "").strip()
    if not config:
        directory = os.environ.get("HERDR_PLUGIN_CONFIG_DIR", "").strip()
        if directory:
            config = str(Path(directory) / "config.toml")
    if not config or not Path(config).is_file():
        return ""
    for line in Path(config).read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("home"):
            _, _, value = stripped.partition("=")
            return value.strip().strip("\"'")
    return ""


def current_session():
    override = os.environ.get("PROJECT_SIDEBAR_SESSION", "").strip()
    if override:
        return override
    socket_path = os.environ.get("HERDR_SOCKET_PATH", "")
    marker = "/sessions/"
    if marker in socket_path and socket_path.endswith("/herdr.sock"):
        return Path(socket_path).parent.name
    if socket_path:
        return "default"
    return os.environ.get("HERDR_SESSION", "")


def reconcile():
    home = configured_home()
    session = current_session()
    if not home or not session:
        print("project-sidebar: home or session is not configured; leaving the sidebar unchanged", file=sys.stderr)
        return 0
    home_id, journals, metas = load_home(home)
    workspaces = _rows(_herdr("workspace", "list"), "workspaces")
    panes = _panes(workspaces)
    decided = plan(home_id, session, journals, metas, workspaces, panes)
    for workspace_id, tokens in decided.workspace_tokens.items():
        _report("workspace", workspace_id, tokens)
    for pane_id, tokens in decided.pane_tokens.items():
        _report("pane", pane_id, tokens)
    for move in decided.moves:
        _send("workspace.move_block", move)
    counts = decided.skipped
    print(
        "project-sidebar: labeled_spaces={0} labeled_panes={1} skipped_stale={2} skipped_reused={3} skipped_ambiguous={4} skipped_unproven={5}".format(
            len(decided.workspace_tokens),
            len(decided.pane_tokens),
            counts.get("stale", 0),
            counts.get("reused", 0),
            counts.get("ambiguous", 0),
            counts.get("unproven", 0),
        ),
        file=sys.stderr,
    )
    if decided.set_view:
        source = view_source()
        try:
            observed = _send("agent.view.clear", clear_view(source))
        except Exception as exc:
            print("project-sidebar: agent view owner unknown; not replacing it: " + str(exc), file=sys.stderr)
        else:
            if view_change_allowed(observed, source):
                _send("agent.view.set", agent_view(source))
            else:
                print("project-sidebar: leaving a foreign or unknown agent view unchanged", file=sys.stderr)
    return 0


def clear():
    home = configured_home()
    session = current_session()
    if not home or not session:
        return 0
    _home_id, journals, _metas = load_home(home)
    workspaces = _rows(_herdr("workspace", "list"), "workspaces")
    panes = _panes(workspaces)
    # Clear only endpoints this home can still prove, and only our token.
    proven_spaces = {task["workspace_id"] for task in journals.values() if task["session"] == session}
    proven_panes = {task["pane_id"] for task in journals.values() if task["session"] == session}
    live_spaces = {row["workspace_id"] for row in workspaces}
    live_panes = {row["pane_id"] for row in panes}
    for workspace_id in sorted(proven_spaces & live_spaces):
        tokens = next((row.get("tokens") or {} for row in workspaces if row["workspace_id"] == workspace_id), {})
        if TOKEN in tokens:
            _clear_tokens("workspace", workspace_id)
    for pane_id in sorted(proven_panes & live_panes):
        tokens = next((row.get("tokens") or {} for row in panes if row["pane_id"] == pane_id), {})
        if TOKEN in tokens:
            _clear_tokens("pane", pane_id)
    _send("agent.view.clear", clear_view(view_source()))
    return 0


def main(argv):
    command = argv[1] if len(argv) > 1 else "reconcile"
    if command == "reconcile":
        return reconcile()
    if command == "clear":
        return clear()
    print("usage: reconcile.py reconcile|clear", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:
        print("project-sidebar: " + str(exc), file=sys.stderr)
        sys.exit(1)
