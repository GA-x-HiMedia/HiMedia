"""Defines the agent's tools and access controls."""

from __future__ import annotations

from . import himedia
from .identity import allowed, is_client, phone_of

# Check whether the user can access a specific item.

NOT_YOURS = {
    "refused": "NOT_VISIBLE_TO_YOU",
    "reason": (
        "That item is not one this person can see. Do not describe it, guess "
        "at it, or confirm that it exists."
    ),
}


def _visible_task_ids(person: dict) -> set[str]:
    """Returns task IDs visible to the user."""
    tasks = himedia.list_tasks(phone=phone_of(person), open_only=False)["data"]
    return {task["id"] for task in tasks}


def _visible_version_ids(person: dict) -> set[str]:
    """Returns version IDs visible to the user."""
    return {v["id"] for v in himedia.list_versions(phone=phone_of(person))}


def _visible_project_ids(person: dict) -> set[str]:
    return {p["id"] for p in himedia.list_projects(phone=phone_of(person))}


def _speaker(comment: dict, client: bool) -> str:
    """Returns the appropriate speaker name for the user."""
    if not client:
        return comment.get("author_name")
    return "your team" if comment.get("author_kind") == "client" else "the production team"


# Read tools.


def run_who_am_i(person: dict, args: dict) -> dict:
    return {
        "name": person["user"]["full_name"],
        "company": person["company"]["name"],
        "role": person["role"]["key"],
        "audience": person["audience"],
        "counts": person.get("counts", {}),
    }


def run_list_tasks(person: dict, args: dict) -> list[dict]:
    tasks = himedia.list_tasks(
        phone=phone_of(person),                  # never args
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
    projects = himedia.list_projects(phone=phone_of(person), status=args.get("status"))
    return [
        {"id": p["id"], "name": p["name"], "status": p["status"], "due": p.get("due_on")}
        for p in projects
    ]


def run_list_versions(person: dict, args: dict) -> list[dict]:
    versions = himedia.list_versions(
        phone=phone_of(person),                  # never args
        project_id=args.get("project_id"),
        state=args.get("state"),
    )
    client = is_client(person)

    rows = []
    for v in versions:
        row = {
            "id": v["id"], "version_no": v.get("version_no"), "state": v.get("state"),
        }
        # published_to_client is always true in what a client gets back, so for
        # them it is noise; for staff it is the difference between "the client
        # is waiting on this" and "the client cannot see it".
        if not client:
            row["published_to_client"] = v.get("published_to_client")
        rows.append(row)
    return rows


def run_get_review_notes(person: dict, args: dict):
    version_id = args["version_id"]
    if version_id not in _visible_version_ids(person):
        return NOT_YOURS

    notes = himedia.list_version_comments(
        version_id, unresolved_only=args.get("unresolved_only", False)
    )
    client = is_client(person)
    if client:
        # Hide explicitly internal comments from clients.
        notes = [n for n in notes if n.get("client_visible") is not False]
    return [
        {
            "author": _speaker(n, client),
            "body": n["body"],
            "at_seconds": n.get("timecode_seconds"), "resolved": n["resolved"],
        }
        for n in notes
    ]


def run_get_task_notes(person: dict, args: dict) -> dict:
    """Returns comments for a task visible to the user."""
    task_id = args["task_id"]
    if task_id not in _visible_task_ids(person):
        return NOT_YOURS

    client = is_client(person)
    task = himedia.get_task(task_id)
    comments = himedia.list_task_comments(task_id, client_visible_only=client)

    return {
        "title": task["title"],
        "status": task["status"],
        "project": task.get("project_name"),
        "notes": [
            {
                "from": _speaker(c, client),
                "body": c["body"],
                "on": (c.get("created_at") or "")[:10],
            }
            for c in comments
        ],
    }


# Write tools run only after confirmation.


def run_create_task(person: dict, args: dict) -> dict:
    """Create a task in a project this caller can actually see.

    The project is gated exactly like every other write here: the API does not
    check company on a write, so without this a staff member could file a task
    into another company's project just by naming its id.

    Deliberately narrow. The model may set a title, a project, a priority, a
    due date and a description. It may NOT set `status` or `client_visible`,
    which the endpoint would accept: either one reaches the client the moment
    the task exists, and that is not something to do on a first ask. Making a
    task client-facing stays the job of update_task_status, which has its own
    point-of-no-return gate.
    """
    project_id = args["project_id"]
    if project_id not in _visible_project_ids(person):
        return NOT_YOURS

    task = himedia.create_task(
        title=args["title"],
        project_id=project_id,
        description=args.get("description"),
        priority=args.get("priority"),
        due_on=args.get("due_on"),
    )
    return {
        "id": task["id"], "title": task["title"],
        "status": task.get("status"), "project": task.get("project_name"),
    }


def run_update_task_status(person: dict, args: dict) -> dict:
    task_id = args["task_id"]
    if task_id not in _visible_task_ids(person):
        return NOT_YOURS

    task = himedia.update_task(task_id, {"status": args["status"]})
    return {"id": task["id"], "title": task["title"], "status": task["status"]}


def run_comment_on_task(person: dict, args: dict) -> dict:
    task_id = args["task_id"]
    if task_id not in _visible_task_ids(person):
        return NOT_YOURS

    himedia.add_task_comment(
        task_id,
        body=args["body"],
        author_phone=phone_of(person),           # never args
        client_visible=args.get("client_visible", False),
    )
    return {"posted": True, "task_id": task_id}


def run_comment_on_version(person: dict, args: dict) -> dict:
    version_id = args["version_id"]
    if version_id not in _visible_version_ids(person):
        return NOT_YOURS

    himedia.add_version_comment(
        version_id,
        body=args["body"],
        author_phone=phone_of(person),           # never args
        timecode_seconds=args.get("timecode_seconds"),
    )
    return {"posted": True, "version_id": version_id}


def run_decide_version(person: dict, args: dict) -> dict:
    version_id = args["version_id"]
    # Verify that the version belongs to the user's visible data.
    if version_id not in _visible_version_ids(person):
        return NOT_YOURS

    himedia.decide_version(
        version_id,
        decision=args["decision"],
        actor_phone=phone_of(person),            # never args
        note=args.get("note"),
    )
    return {"version_id": version_id, "decision": args["decision"]}


# Actions that require stronger confirmation.

POINT_OF_NO_RETURN_STATUSES = {
    "client_review",  # Makes the task visible to the client.
    "cancelled",      # Cancels the task.
}


def _status_is_final(args: dict) -> bool:
    return args.get("status") in POINT_OF_NO_RETURN_STATUSES


def _comment_reaches_the_client(args: dict) -> bool:
    """Checks whether a comment will be visible to the client."""
    return bool(args.get("client_visible"))


def is_destructive(tool_name: str, args: dict) -> bool:
    """Checks whether an action needs stronger confirmation."""
    tool = next((t for t in ALL_TOOLS if t["function"]["name"] == tool_name), None)
    if tool is None:
        return True
    if not tool["writes"]:
        return False

    verdict = tool.get("destructive", True)
    return bool(verdict(args)) if callable(verdict) else bool(verdict)


# Tool catalogue.


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
            "name": "create_task",
            "description": (
                "Create a new task in a project. project_id must come from a prior "
                "list_projects result, never invented. The task is created as internal "
                "production work — if the client should see it, use update_task_status "
                "afterwards. Requires confirmation before it runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                    "project_id": {
                        "type": "string",
                        "description": "e.g. prj_0001 — from a prior list_projects result.",
                    },
                    "description": {"type": "string", "maxLength": 4000},
                    "priority": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high", "urgent"],
                    },
                    "due_on": {"type": "string", "description": "YYYY-MM-DD."},
                },
                "required": ["title", "project_id"],
                "additionalProperties": False,
            },
        },
        "needs": ("tasks", "write"),
        "audience": "internal",
        "writes": True,
        # Only adds work, and adds it internally: no client can see it, and a
        # task filed by mistake is answered by cancelling it. Not a point of no
        # return, so it keeps the ordinary yes/no.
        "destructive": False,
        "run": run_create_task,
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
        # Harmless moving a task to todo or in_progress; a point of no return
        # moving it to client_review (the client sees it) or cancelled.
        "destructive": _status_is_final,
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
        # Stronger confirmation if the client can see the comment.
        "destructive": _comment_reaches_the_client,
        "run": run_comment_on_task,
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_notes",
            "description": (
                "The conversation attached to one task — what was said about it and "
                "when. Use after list_tasks for 'what did they say about it', 'has the "
                "client replied', 'what changes were asked for'. task_id must come from "
                "a prior list_tasks result, never invented. This returns notes on a "
                "TASK; for feedback on a video version use get_review_notes instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "e.g. tsk_0002 — from a prior list_tasks result."},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        "needs": ("tasks", "read"),
        "audience": "both",
        "writes": False,
        "run": run_get_task_notes,
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
        # Version comments are reversible by adding another comment.
        "destructive": False,
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
        # Always requires stronger confirmation.
        "destructive": True,
        "run": run_decide_version,
    },
]


def tools_for(person: dict) -> list[dict]:
    """Returns the tools available to the current user."""
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


def may_act_on(person: dict, args: dict) -> bool:
    """Checks whether the user can act on the requested item."""
    task_id = args.get("task_id")
    if task_id is not None and task_id not in _visible_task_ids(person):
        return False

    version_id = args.get("version_id")
    if version_id is not None and version_id not in _visible_version_ids(person):
        return False

    return True


def public_part(tool: dict) -> dict:
    """Returns only the tool definition visible to the AI."""
    return {"type": tool["type"], "function": tool["function"]}


def find_tool(name: str, available: list[dict]) -> dict | None:
    """Finds a tool from the user's available tools."""
    return next((t for t in available if t["function"]["name"] == name), None)


def describe(tool_name: str, args: dict) -> str:

    """Creates a readable preview of a pending action.
    person before anything actually happens."""
    if tool_name == "create_task":
        return (f"Create task \u201c{args.get('title', '')}\u201d "
                f"in project {args.get('project_id')}")
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
