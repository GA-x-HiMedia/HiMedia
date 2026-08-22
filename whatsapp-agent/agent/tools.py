"""
The tool catalogue — Phase 2 scope (Chapters 25-26): read-only tools only.
Write tools (update_task_status, comment_on_task, comment_on_version,
decide_version) and the confirm-before-write flow are Phase 3 material
("write tools... confirm before every write" — Days 6-7) and are
deliberately not here yet.

Filtering here (`tools_for`) is a convenience, not a lock — it stops the
model wasting a turn or claiming a capability it doesn't have. The real
boundary is the sandbox API itself: every handler passes the CALLER'S OWN
phone number, never one from `args`, and HiMedia decides what data comes
back.
"""
from __future__ import annotations

from . import himedia
from .identity import allowed

# --- Handlers ---------------------------------------------------------------
# Every handler takes (person, args) and returns a small, trimmed result —
# never the whole underlying row ("return less than you fetched").


def run_who_am_i(person: dict, args: dict) -> dict:
    return {
        "name": person["user"]["full_name"],
        "company": person["company"]["name"],
        "role": person["role"]["key"],
        "audience": person["audience"],
        "counts": person.get("counts", {}),
    }


def run_list_tasks(person: dict, args: dict) -> list[dict]:
    tasks = himedia.get(
        "/v1/tasks",
        phone=person["user"]["phone"],
        status=args.get("status"),
        open_only=args.get("open_only", True),
    )["data"]
    return [
        {
            "id": t["id"], "title": t["title"], "status": t["status"],
            "priority": t.get("priority"), "due": t.get("due_on"),
            "project": t.get("project_name"),
        }
        for t in tasks
    ]


def run_list_projects(person: dict, args: dict) -> list[dict]:
    projects = himedia.get(
        "/v1/projects", phone=person["user"]["phone"], status=args.get("status")
    )["data"]
    return [
        {"id": p["id"], "name": p["name"], "status": p["status"], "due": p.get("due_on")}
        for p in projects
    ]


def run_list_versions(person: dict, args: dict) -> list[dict]:
    versions = himedia.get(
        "/v1/versions",
        phone=person["user"]["phone"],
        project_id=args.get("project_id"),
        state=args.get("state"),
    )["data"]
    return [
        {
            "id": v["id"], "version_no": v.get("version_no"), "state": v.get("state"),
            "published_to_client": v.get("published_to_client"),
        }
        for v in versions
    ]


def run_get_review_notes(person: dict, args: dict) -> list[dict]:
    notes = himedia.get(
        f"/v1/versions/{args['version_id']}/comments",
        unresolved_only=args.get("unresolved_only", False),
    )["data"]
    return [
        {
            "author": n["author_name"], "body": n["body"],
            "at_seconds": n.get("timecode_seconds"), "resolved": n["resolved"],
        }
        for n in notes
    ]


# --- Catalogue ------------------------------------------------------------
# Every entry keeps a "writes" flag even though every tool below is False
# right now — Phase 3 adds write tools into this same list, and brain.py's
# loop will branch on this flag then. No behaviour depends on it yet.

ALL_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "who_am_i",
            "description": (
                "Identity, role, and pending-item counts for the person currently "
                "talking to you. Call this once at the start of a conversation to "
                "greet them correctly — do not call it repeatedly in the same turn."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        "needs": None,
        "audience": "both",
        "writes": False,
        "run": run_who_am_i,
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": (
                "For internal staff: the tasks assigned to the person speaking. For a "
                "client contact: the tasks shared with their organisation. Use for 'my "
                "tasks', 'what am I working on', 'what's due'. Do NOT use to look up a "
                "colleague's workload — it only ever returns what the caller themselves "
                "is allowed to see."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["backlog", "todo", "in_progress", "in_review",
                                 "client_review", "done", "cancelled"],
                    },
                    "open_only": {
                        "type": "boolean",
                        "description": "Hide done/cancelled tasks. Defaults to true.",
                    },
                },
                "additionalProperties": False,
            },
        },
        "needs": ("tasks", "read"),
        "audience": "both",
        "writes": False,
        "run": run_list_tasks,
    },
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": (
                "Projects visible to the caller. Internal staff see their company's "
                "projects; a client sees only the projects being made for them, across "
                "every vendor working with their organisation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["active", "on_hold", "done", "cancelled"]},
                },
                "additionalProperties": False,
            },
        },
        "needs": ("projects", "read"),
        "audience": "both",
        "writes": False,
        "run": run_list_projects,
    },
    {
        "type": "function",
        "function": {
            "name": "list_versions",
            "description": (
                "Deliverable versions visible to the caller. A client only ever sees "
                "versions explicitly published to their organisation — never drafts, "
                "never internal_review versions, no matter how the question is phrased."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "state": {
                        "type": "string",
                        "enum": ["draft", "internal_review", "client_review", "approved", "changes_requested"],
                    },
                },
                "additionalProperties": False,
            },
        },
        "needs": ("reviews", "read"),
        "audience": "both",
        "writes": False,
        "run": run_list_versions,
    },
    {
        "type": "function",
        "function": {
            "name": "get_review_notes",
            "description": (
                "Feedback comments on one specific version, in the order they refer to "
                "in the video. Use unresolved_only=true for 'what's left?'. version_id "
                "must come from a prior list_versions result — never invent one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "version_id": {"type": "string"},
                    "unresolved_only": {"type": "boolean"},
                },
                "required": ["version_id"],
                "additionalProperties": False,
            },
        },
        "needs": ("reviews", "read"),
        "audience": "both",
        "writes": False,
        "run": run_get_review_notes,
    },
]


def tools_for(person: dict) -> list[dict]:
    """The tools this person may use, for this message (Chapter 26).
    Mechanical, no per-tool special cases: offered iff the audience matches
    and their LIVE permissions map satisfies what the tool needs."""
    usable = []
    for tool in ALL_TOOLS:
        if tool["audience"] != "both" and tool["audience"] != person["audience"]:
            continue
        if tool["needs"] is not None:
            module, level = tool["needs"]
            if not allowed(person, module, level):
                continue
        usable.append(tool)
    return usable


def public_part(tool: dict) -> dict:
    """Only what the model is allowed to see — never `needs`, `audience`,
    `writes`, or `run`, which are ours."""
    return {"type": tool["type"], "function": tool["function"]}


def find_tool(name: str, available: list[dict]) -> dict | None:
    """Only offered tools may run — look the request up in THIS turn's
    filtered list, never the full catalogue."""
    return next((t for t in available if t["function"]["name"] == name), None)
