import React from "react";

import Logo from "./Logo.jsx";
import PersonButton from "./PersonButton.jsx";

/** The list of people you can be, always visible.
 *
 * Switching is the fastest way to show what the whole project is for: ask the
 * same question as an editor and as the client, and read the two answers next
 * to each other.
 */
export default function Rail({ people, current, onSelect, open, health }) {
  const groups = [];
  for (const person of people) {
    const last = groups[groups.length - 1];
    if (!last || last.company !== person.company) {
      groups.push({ company: person.company, client: person.client_side, people: [person] });
    } else {
      last.people.push(person);
    }
  }

  return (
    <aside className={open ? "rail open" : "rail"}>
      <div className="rail-head">
        <Logo subtitle="Production assistant" />
      </div>

      <div className="rail-scroll">
        {groups.map((group) => (
          <div key={group.company}>
            <div className="people-group" style={{ paddingInline: 6 }}>
              {group.company}
              {group.client ? " · client" : ""}
            </div>
            {group.people.map((person) => (
              <PersonButton
                key={person.phone}
                person={person}
                selected={person.phone === current}
                onSelect={onSelect}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="rail-foot">
        {health ? (
          <>
            <div>
              model <code style={{ fontFamily: "var(--mono)" }}>{health.model}</code>
            </div>
            {!health.model_key && (
              <div style={{ color: "var(--red)" }}>no model key — replies will fail</div>
            )}
            {!health.sandbox_key && (
              <div style={{ color: "var(--red)" }}>no sandbox key</div>
            )}
          </>
        ) : (
          <div>connecting to the agent…</div>
        )}
      </div>
    </aside>
  );
}
