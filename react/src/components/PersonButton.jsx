import React from "react";
import { initials, prettyRole } from "../format.jsx";

/** One person in a list. Used both on the sign-in card and in the rail. */
export default function PersonButton({ person, selected, onSelect }) {
  return (
    <button
      type="button"
      className={selected ? "person selected" : "person"}
      onClick={() => onSelect(person.phone)}
      title={`${person.name} · ${prettyRole(person.role)} · ${person.phone}`}
    >
      <span className={`disc ${person.client_side ? "client" : "internal"}`}>
        {initials(person.name)}
      </span>
      <span style={{ minWidth: 0 }}>
        <span className="person-name">{person.name}</span>
        <span className="person-role">
          {prettyRole(person.role)}
          {person.trusted_device ? " · verified" : ""}
        </span>
      </span>
    </button>
  );
}
