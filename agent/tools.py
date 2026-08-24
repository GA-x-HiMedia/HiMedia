"""
The tool catalogue (Chapters 25-26). Nine tools: identity, plus read/write
pairs across tasks, projects, and reviews/versions.

Filtering here (`tools_for`) is a convenience, not a lock — it stops the
model wasting a turn or claiming a capability it doesn't have. The real
boundary is the sandbox API itself: every handler passes the CALLER'S OWN
phone number, never one from `args`, and HiMedia decides what data comes
back or whether a write is actually allowed. A caller can hold
reviews:write scope and still get a clean 403 from decide_version if
their approval_rank is too low for that review stage (Chapter 10 — rank
is separate from read/write scope) — the check below controls what gets
OFFERED, never what the API ultimately PERMITS.

Phase 3 adds the four write tools (update_task_status, comment_on_task,
comment_on_version, decide_version) and their `describe()` previews.
Every write tool is caught by brain.py's confirm-before-write flow — none
of them ever run on the first ask.
"""
from __future__ import annotations

from . import himedia
from .identity import allowed

# --- Read handlers ----------------------------------------------------------


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


# --- Write handlers (Phase 3) -----------------------------------------------
# Every one of these is only ever called from brain.py's confirmed-write
# path — never directly from the first model tool_call.


def run_update_task_status(person: dict, args: dict) -> dict:
    task = himedia.patch(f"/v1/tasks/{args['task_id']}", {"status": args["status"]})
    return {"id": task["id"], "title": task["title"], "status": task["status"]}


def run_comment_on_task(person: dict, args: dict) -> dict:
    body = {
        "body": args["body"],
        "author_phone": person["user"]["phone"],
        "client_visible": args.get("client_visible", False),
    }
    himedia.post(f"/v1/tasks/{args['task_id']}/comments", body)
    return {"posted": True, "task_id": args["task_id"]}


def run_comment_on_version(person: dict, args: dict) -> dict:
    body = {"body": args["body"], "author_phone": person["user"]["phone"]}
    if args.get("timecode_seconds") is not None:
        body["timecode_seconds"] = args["timecode_seconds"]
    himedia.post(f"/v1/versions/{args['version_id']}/comments", body)
    return {"posted": True, "version_id": args["version_id"]}


def run_decide_version(person: dict, args: dict) -> dict:
    body = {"decision": args["decision"], "actor_phone": person["user"]["phone"]}
    if args.get("note"):
        body["note"] = args["note"]
    himedia.post(f"/v1/versions/{args['version_id']}/decision", body)
    return {"version_id": args["version_id"], "decision": args["decision"]}


# --- Catalogue ----------------------------------------------------------

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
            "name": "update_task_status",
            "description": (
                "Move a task to a new status. You will be asked to confirm with the "
                "person before this actually runs. Do NOT use this to approve or reject "
                "a client deliverable version — use decide_version for that."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "e.g. tsk_0001 — from a prior list_tasks result, never invented."},
                    "status": {
                        "type": "string",
                        "enum": ["backlog", "todo", "in_progress", "in_review",
                                 "client_review", "done", "cancelled"],
                    },
                },
                "required": ["task_id", "status"],
                "additionalProperties": False,
            },
        },
        "needs": ("tasks", "write"),
        "audience": "internal",
        "writes": True,
        "run": run_update_task_status,
    },
    {
        "type": "function",
        "function": {
            "name": "comment_on_task",
            "description": (
                "Post a comment on a task. Internal production discussion by default — "
                "only set client_visible=true if the person explicitly wants the client "
                "to see it. Requires confirmation before it runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "body": {"type": "string", "minLength": 1, "maxLength": 4000},
                    "client_visible": {"type": "boolean"},
                },
                "required": ["task_id", "body"],
                "additionalProperties": False,
            },
        },
        "needs": ("tasks", "write"),
        "audience": "internal",
        "writes": True,
        "run": run_comment_on_task,
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
    {
        "type": "function",
        "function": {
            "name": "comment_on_version",
            "description": (
                "Leave a note on a specific version, optionally anchored to a timecode "
                "in seconds. This is the client feedback channel — both staff and client "
                "roles with review access use it. Requires confirmation before it runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "version_id": {"type": "string"},
                    "body": {"type": "string", "minLength": 1, "maxLength": 4000},
                    "timecode_seconds": {"type": "integer", "minimum": 0},
                },
                "required": ["version_id", "body"],
                "additionalProperties": False,
            },
        },
        "needs": ("reviews", "write"),
        "audience": "both",
        "writes": True,
        "run": run_comment_on_version,
    },
    {
        "type": "function",
        "function": {
            "name": "decide_version",
            "description": (
                "Approve a version, or send it back with changes requested (a note is "
                "required in that case). The API may still refuse this even though the "
                "tool was offered — approval rank is checked server-side, separately "
                "from read/write scope. Requires confirmation before it runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "version_id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["approve", "request_changes"]},
                    "note": {"type": "string", "maxLength": 4000},
                },
                "required": ["version_id", "decision"],
                "additionalProperties": False,
            },
        },
        "needs": ("reviews", "write"),
        "audience": "both",
        "writes": True,
        "run": run_decide_version,
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
    filtered list, never the full catalogue. Closes the gap where a model
    asks for a tool it saw in an earlier conversation."""
    return next((t for t in available if t["function"]["name"] == name), None)


def describe(tool_name: str, args: dict) -> str:
    """One-line, human-readable preview of a pending write, shown to the
    person before anything actually happens."""
    if tool_name == "update_task_status":
        return f"Move task {args.get('task_id')} to '{args.get('status')}'"
    if tool_name == "comment_on_task":
        return f"Post on task {args.get('task_id')}: \u201c{args.get('body', '')}\u201d"
    if tool_name == "comment_on_version":
        at = f" at {args['timecode_seconds']}s" if args.get("timecode_seconds") is not None else ""
        return f"Post on version {args.get('version_id')}{at}: \u201c{args.get('body', '')}\u201d"
    if tool_name == "decide_version":
        note = f" \u2014 \u201c{args['note']}\u201d" if args.get("note") else ""
        return f"{args.get('decision')} version {args.get('version_id')}{note}"
    return f"{tool_name}({args})"
