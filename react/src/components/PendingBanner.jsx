import React, { useEffect, useState } from "react";

/** The write that is waiting for a human.
 *
 * Nothing here decides anything. Every button sends an ordinary message down
 * the ordinary path, and brain.py reads it exactly as it reads a message
 * typed by hand — a yes is still a yes read in code, and permissions are
 * still re-checked at the moment the write runs. This is a shortcut for
 * typing, never a second way in.
 *
 * Two shapes, because the agent has two:
 *
 *   ordinary write   -> yes / no
 *   point of no return -> the exact phrase, typed. "ok" is what someone
 *                        sends while half-reading a notification, and
 *                        approving a client deliverable is not something to
 *                        do by reflex. Anything that is not the phrase
 *                        cancels.
 */
export default function PendingBanner({ pending, busy, onSay }) {
  const [typed, setTyped] = useState("");
  const [copied, setCopied] = useState(false);

  // A new held action starts with an empty box — never with the last one's
  // text still sitting in it, ready to be sent by accident.
  useEffect(() => {
    setTyped("");
    setCopied(false);
  }, [pending.tool, pending.summary]);

  const final = Boolean(pending.needs_phrase);
  const matches = typed.trim() === pending.phrase;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(pending.phrase);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked — the phrase is on screen anyway
    }
  };

  return (
    <div className={final ? "pending final" : "pending"}>
      <div className="eyebrow">
        {final ? "Final — this cannot be undone" : "Waiting for your confirmation"}
      </div>

      <p className="pending-what">{pending.summary}</p>
      <div className="pending-tool">{pending.tool}</div>

      {final ? (
        <>
          <div className="phrase-chip">
            <span dir="rtl">{pending.phrase}</span>
            <button type="button" onClick={copy}>
              {copied ? "copied" : "copy"}
            </button>
          </div>

          <form
            className="phrase-box"
            onSubmit={(event) => {
              event.preventDefault();
              if (matches && !busy) onSay(typed.trim());
            }}
          >
            <input
              className={matches ? "input match" : "input"}
              dir="rtl"
              placeholder={pending.phrase}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              disabled={busy}
              aria-label="Type the confirmation phrase exactly"
            />
            <button type="submit" className="btn danger" disabled={!matches || busy}>
              Confirm
            </button>
            <button
              type="button"
              className="btn quiet"
              disabled={busy}
              onClick={() => onSay("no")}
            >
              Cancel
            </button>
          </form>

          <div className="pending-why">
            This one is final, so a yes will not do it. Type the phrase above
            exactly. Anything else cancels — including “yes”, which is the
            reflex this gate exists to interrupt.
          </div>
        </>
      ) : (
        <>
          <div className="pending-actions">
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => onSay("yes")}
            >
              Yes, do it
            </button>
            <button
              type="button"
              className="btn quiet"
              disabled={busy}
              onClick={() => onSay("أي")}
              dir="rtl"
            >
              أي
            </button>
            <button
              type="button"
              className="btn quiet"
              disabled={busy}
              onClick={() => onSay("no")}
            >
              No
            </button>
          </div>

          <div className="pending-why">
            Nothing has changed yet. The write runs only after you say yes, the
            yes is read in code rather than by the model, and your permissions
            are checked again at that moment.
          </div>
        </>
      )}
    </div>
  );
}
