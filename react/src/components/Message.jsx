import React from "react";
import { Markdown, clockOf, dirOf } from "../format.jsx";

/** One line in the transcript.
 *
 * `kind` decides the colour, and each colour means what it means everywhere
 * else in the brand: green for a write that went through, red for a refusal,
 * peach for the device challenge — something to read before acting.
 */
export default function Message({ message }) {
  if (message.kind === "note") {
    return <div className={message.bad ? "note bad" : "note"}>{message.text}</div>;
  }

  const mine = message.from === "me";
  const tone = mine ? "mine" : message.kind || "agent";

  return (
    <div className={mine ? "row mine" : "row"}>
      <div className={`bubble ${tone}`} dir={dirOf(message.text)}>
        <Markdown text={message.text} />
      </div>
      <span className="stamp">{clockOf(message.at)}</span>
    </div>
  );
}
