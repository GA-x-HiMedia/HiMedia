import React from "react";
import { clockOf } from "../format.jsx";

/** The tail of audit.log for this person.
 *
 * Every tool call the agent makes is written to that file — who asked, which
 * tool, with what arguments, what came back, how long it took, and whether it
 * was allowed. This panel only reads it. When a refusal looks surprising,
 * this is the row that explains it.
 */
export default function AuditPanel({ entries, path, onRefresh, loading }) {
  const calls = entries.filter((entry) => entry.tool);

  return (
    <div className="panel-scroll">
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <h3 className="panel-title" style={{ flex: 1 }}>
          Audit trail
        </h3>
        <button type="button" className="btn-ghost" onClick={onRefresh} disabled={loading}>
          {loading ? "…" : "Refresh"}
        </button>
      </div>

      <div className="tool-meta" style={{ marginBottom: 12 }}>
        {calls.length} tool call{calls.length === 1 ? "" : "s"} in{" "}
        <code style={{ fontFamily: "var(--mono)" }}>{path || "audit.log"}</code>
      </div>

      {calls.length === 0 && (
        <div className="empty">
          Nothing logged for this number yet. Ask a question and it will appear
          here.
        </div>
      )}

      {calls
        .slice()
        .reverse()
        .map((entry, index) => (
          <div
            key={`${entry.ts}-${index}`}
            className={`audit-row ${entry.allowed ? "allowed" : "refused"}`}
          >
            <div className="audit-tool">{entry.tool}</div>
            <div className="audit-meta">
              {clockOf(entry.ts)} · {entry.allowed ? "allowed" : "refused"}
              {entry.duration_ms ? ` · ${Math.round(entry.duration_ms)}ms` : ""}
            </div>
            {entry.args && Object.keys(entry.args).length > 0 && (
              <div className="audit-args">{JSON.stringify(entry.args)}</div>
            )}
            {entry.result_summary && (
              <div className="audit-args" style={{ opacity: 0.8 }}>
                {String(entry.result_summary).slice(0, 140)}
              </div>
            )}
          </div>
        ))}
    </div>
  );
}
