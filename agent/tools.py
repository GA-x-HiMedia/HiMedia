"""
The tool catalogue (Chapters 25-26). Ten tools: identity, plus read/write
pairs across tasks, projects, and reviews/versions. (The README's Phase 2/3
tables list nine — get_task_notes is the tenth, restored from an earlier
branch of this work because nothing else reads task comments, which is where
`client_visible: false` internal discussion lives.)

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
from .identity import allowed, is_client, phone_of

# --- May this person open this exact row? -----------------------------------
#
# The list endpoints take phone= and the sandbox filters them for us. The
# by-id endpoints (/v1/tasks/{id}, /v1/versions/{id}, and their comment
# sub-resources) do NOT — they trust our API key and hand over anything we
# name. Without the gate below, a client who names an internal task id learns
# its title, its state and every staff note on it, and a client at one company
# can reach another company's work (PERMISSIONS.md: "Neither should ever see
# the other's projects, tasks, or versions").
#
# The fix is the one the whole project rests on: ask the API what this person
# can see, using their OWN phone number, and refuse anything not in that list.

NOT_YOURS = {
    "refused": "NOT_VISIBLE_TO_YOU",
    "reason": (
        "That item is not one this person can see. Do not describe it, guess "
        "at it, or confirm that it exists."
    ),
}


def _visible_task_ids(person: dict) -> set[str]:
    tasks = himedia.list_tasks(phone=phone_of(person), open_only=False)["data"]
    return {task["id"] for task in tasks}


def _visible_version_ids(person: dict) -> set[str]:
    return {v["id"] for v in himedia.list_versions(phone=phone_of(person))}


def _speaker(comment: dict, client: bool) -> str:
    """Who said it, at the level of detail this caller may have. A client is
    told which SIDE spoke, never which person — staff names are internal
    (README client voice: "Never mention internal drafts, staff names, costs")."""
    if not client:
        return comment.get("author_name")
    return "your team" if comment.get("author_kind") == "client" else "the production team"


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
        # Belt and braces. Version comments are not documented to carry the
        # client_visible flag the way task comments do, but if any row does
        # carry it we honour it rather than discovering the hard way that they
        # sometimes do. An absent flag is left alone; only an explicit false is
        # dropped.
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
    """The conversation attached to one task.

    client_visible_only is set from the caller's audience and never from args.
    The API does NOT apply the audience rule for us: confirmed live against
    tsk_0002, where the unfiltered call returned an internal comment in full,
    author name included (QUESTIONS.md carries the evidence). This is the only
    path in the project that reads task comments.
    """
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


# --- Write handlers (Phase 3) -----------------------------------------------
# Every one of these is only ever called from brain.py's confirmed-write
# path — never directly from the first model tool_call.


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
    # The sandbox does NOT check company on a write: without this gate a client
    # at one company can approve another company's version just by naming its
    # id. Reads are filtered by ?phone=; writes are not filtered at all.
    if version_id not in _visible_version_ids(person):
        return NOT_YOURS

    himedia.decide_version(
        version_id,
        decision=args["decision"],
        actor_phone=phone_of(person),            # never args
        note=args.get("note"),
    )
    return {"version_id": version_id, "decision": args["decision"]}


# --- Which writes are a point of no return? ---------------------------------
#
# Destructiveness is a property of the ACTION, not of the tool: moving a task
# to in_progress and moving it to client_review are the same tool and are not
# remotely the same act. So this is decided from the tool AND its arguments,
# and the catalogue entries below carry either a flag or a predicate.
#
# The rule, applied consistently: a write needs the typed phrase when it is
# irreversible, or when it crosses the line to the client and cannot be
# un-sent. Everything else keeps the ordinary yes/no. Gating more than that is
# not extra safety — people who are asked to retype a phrase ten times a day
# stop reading it, and then it protects nothing.
#
# Note nothing the agent can do deletes anything: its whole write surface is
# PATCH /v1/tasks/{id} and three POSTs, and the API offers no way to delete a
# task or a version at any level. (It does expose DELETE /v1/users/{id}, which
# this agent neither offers nor calls — checked against the API's own schema.)
# So "cancelled" is the nearest thing to destroying work that any of these
# actions can reach.

POINT_OF_NO_RETURN_STATUSES = {
    "client_review",   # the client can now see it; you cannot un-send it
    "cancelled",       # the nearest thing to deleting work this API offers
}


def _status_is_final(args: dict) -> bool:
    return args.get("status") in POINT_OF_NO_RETURN_STATUSES


def _comment_reaches_the_client(args: dict) -> bool:
    # An internal note is cheap to get wrong. One the client can read is not.
    return bool(args.get("client_visible"))


def is_destructive(tool_name: str, args: dict) -> bool:
    """Does this exact call need the typed confirmation phrase?

    Looked up by NAME in the real catalogue rather than read off a tool dict
    handed to us, so the answer cannot be spoofed by a forged tool. Anything
    not found, or a write tool that forgot to declare itself, is treated as
    destructive — a missed classification should fail towards asking, never
    towards acting.
    """
    tool = next((t for t in ALL_TOOLS if t["function"]["name"] == tool_name), None)
    if tool is None:
        return True
    if not tool["writes"]:
        return False

    verdict = tool.get("destructive", True)
    return bool(verdict(args)) if callable(verdict) else bool(verdict)


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
        # Internal discussion is ordinary. Publishing a line to the client is
        # not, and cannot be taken back.
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
        # Deliberately NOT gated. It is the highest-frequency write in the
        # project and it only ADDS information — a wrong note is answered with
        # another note. Putting a phrase in front of every comment is how a
        # confirmation gate becomes muscle memory.
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
        # Always. It decides on the client's behalf and there is no undo.
        "destructive": True,
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


def may_act_on(person: dict, args: dict) -> bool:
    """Can this caller touch the row these arguments name?

    Called before a write is PREVIEWED, not just before it runs. Without it the
    agent will happily read back "Approve version ver_teaser_v1?" to someone at
    another company — refusing only after they say yes. The preview itself is
    an answer, so it has to be gated too.
    """
    task_id = args.get("task_id")
    if task_id is not None and task_id not in _visible_task_ids(person):
        return False

    version_id = args.get("version_id")
    if version_id is not None and version_id not in _visible_version_ids(person):
        return False

    return True


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
