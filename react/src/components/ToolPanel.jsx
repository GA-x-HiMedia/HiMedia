import React from "react";
import { prettyRole } from "../format.jsx";

/** What this person may actually do.
 *
 * The list comes from tools_for() — the same filtered list brain.py hands the
 * model on every message. The struck-through rows were removed before the
 * model was called at all, which is why it cannot claim a power it does not
 * have: it never saw the tool.
 */
export default function ToolPanel({ session }) {
  const { tools, offered, total, permissions } = session;
  const percent = total ? Math.round((offered / total) * 100) : 0;

  const grants = Object.entries(permissions || {})
    .filter(([, level]) => level && level !== "none")
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="panel-scroll">
      <h3 className="panel-title">Tools after filtering</h3>
      <div className="tally">
        {offered}
        <span> of {total} offered</span>
      </div>
      <div className="meter">
        <i style={{ width: `${percent}%` }} />
      </div>

      {tools.map((tool) => {
        const classes = ["tool-row"];
        if (!tool.available) classes.push("off");
        else if (tool.destructive === "yes") classes.push("final");
        else if (tool.writes) classes.push("write");

        return (
          <div key={tool.name} className={classes.join(" ")} title={tool.description}>
            <span className="pip" />
            <span style={{ minWidth: 0 }}>
              <div className="tool-name">{tool.name}</div>
              <div className="tool-meta">
                {tool.available
                  ? [
                      tool.needs || "no permission needed",
                      tool.writes ? "changes data" : "read only",
                      tool.destructive === "yes"
                        ? "needs the phrase"
                        : tool.destructive === "sometimes"
                        ? "phrase for final calls"
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")
                  : tool.audience !== "both" && tool.audience !== session.audience
                  ? `${tool.audience} only`
                  : `needs ${tool.needs}`}
              </div>
            </span>
          </div>
        );
      })}

      <div className="key">
        <span>
          <i style={{ background: "var(--green)" }} /> read
        </span>
        <span>
          <i style={{ background: "var(--orange)" }} /> write
        </span>
        <span>
          <i style={{ background: "var(--red)" }} /> final
        </span>
        <span>
          <i style={{ background: "var(--warm-grey)" }} /> filtered out
        </span>
      </div>

      <h3 className="panel-title" style={{ marginTop: 24 }}>
        Live permissions
      </h3>
      <div className="tool-meta">
        {prettyRole(session.role_name || session.role)}
        {session.approval_rank != null ? ` · approval rank ${session.approval_rank}` : ""}
      </div>
      <div className="perm-list">
        {grants.length === 0 && <span className="perm">none</span>}
        {grants.map(([module, level]) => (
          <span key={module} className={level === "write" ? "perm write" : "perm"}>
            {module}:{level}
          </span>
        ))}
      </div>
      <div className="tool-meta" style={{ marginTop: 10 }}>
        Re-read from the API every 60 seconds, so a change of role takes effect
        within a minute — including between being asked to confirm a write and
        confirming it.
      </div>
    </div>
  );
}
