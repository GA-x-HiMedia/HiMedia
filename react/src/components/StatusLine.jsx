import React from "react";

/* What the agent is doing right now, said in the language of the work rather
 * than the language of the code.
 *
 * brain.reply_to reports its progress as "Calling list_tasks…" — a tool name,
 * which is the right thing for the terminal harness and for the audit trail
 * and the wrong thing to show a client. Rashid at Batelco has no reason to
 * learn the internal vocabulary of a system he is a customer of, and a tool
 * name hints at machinery he cannot use and should not be thinking about.
 *
 * The permission filter already guarantees no tool he is barred from can ever
 * appear here — a tool he cannot use is never offered to the model, so it can
 * never be called. This is not that. This is not narrating the plumbing to
 * somebody who came to ask about a video.
 *
 * The real tool names are still in the Audit panel, where the operator can
 * read them, and in audit.log, where they are the record.
 */

const PHRASES = {
  who_am_i: "Checking your account…",
  list_tasks: "Looking up your tasks…",
  get_task_notes: "Reading the notes…",
  list_projects: "Looking up your projects…",
  list_versions: "Checking the latest versions…",
  get_review_notes: "Reading the review notes…",
  create_task: "Preparing a new task…",
  update_task_status: "Preparing a status change…",
  comment_on_task: "Preparing your comment…",
  comment_on_version: "Preparing your note…",
  decide_version: "Preparing your decision…",
};

export default function StatusLine({ status }) {
  const call = /^Calling (.+?)…?$/.exec(status || "");

  // An unrecognised tool falls back to something neutral rather than to the
  // raw name — a tool added later must not start leaking by default.
  const text = call
    ? PHRASES[call[1]] || "Looking that up…"
    : status || "Thinking…";

  return (
    <div className="status" role="status" aria-live="polite">
      <span className="pulse">
        <i />
        <i />
        <i />
      </span>
      <span>{text}</span>
    </div>
  );
}
