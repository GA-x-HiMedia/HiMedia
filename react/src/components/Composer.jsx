import React, { useEffect, useRef } from "react";
import { isArabic } from "../format.jsx";

const STAFF = [
  "What am I working on?",
  "Has the client replied?",
  "Which version are they waiting for?",
  "شنو التاسكات اللي عندي؟",
];

const CLIENT = [
  "What am I waiting on?",
  "What do I need to approve?",
  "Show me the latest versions",
  "وين وصل الشغل؟",
];

/** The message box — and, while a device is unverified, the code box.
 *
 * The verification path is not a separate screen. A code is an ordinary
 * message to the agent, exactly as it is over WhatsApp; this only changes
 * what the input looks like, so the person knows six digits are wanted.
 */
export default function Composer({
  value,
  onChange,
  onSend,
  busy,
  audience,
  awaitingCode,
  disabled,
}) {
  const box = useRef(null);

  useEffect(() => {
    const node = box.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 150)}px`;
  }, [value]);

  const submit = () => {
    if (!busy && value.trim()) onSend(value.trim());
  };

  if (awaitingCode) {
    const digits = value.replace(/\D/g, "").slice(0, 6);
    return (
      <div className="composer">
        <div className="callout">
          <b>This device has not been verified yet.</b> A six-digit code was
          issued and printed by the API process — look in the terminal running{" "}
          <code>uvicorn agent.web:app</code>, not in this chat. It is delivered
          out of band on purpose: a code sent down the same channel would prove
          nothing, since whoever holds the number would simply read it.
        </div>
        <form
          className="code-entry"
          onSubmit={(event) => {
            event.preventDefault();
            if (digits.length === 6 && !busy) onSend(digits);
          }}
        >
          <input
            className="input"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            value={digits}
            onChange={(event) => onChange(event.target.value)}
            disabled={busy}
            aria-label="Six-digit verification code"
            autoFocus
          />
          <button type="submit" className="btn" disabled={digits.length !== 6 || busy}>
            Verify device
          </button>
        </form>
      </div>
    );
  }

  const prompts = audience === "client" ? CLIENT : STAFF;

  return (
    <div className="composer">
      <div className="chips">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="chip"
            disabled={busy || disabled}
            dir={isArabic(prompt) ? "rtl" : "ltr"}
            onClick={() => onSend(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="entry">
        <textarea
          ref={box}
          rows={1}
          placeholder="Ask about tasks, versions, or what needs your decision…"
          value={value}
          dir={isArabic(value) ? "rtl" : "ltr"}
          disabled={busy || disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button
          type="button"
          className="send"
          onClick={submit}
          disabled={busy || disabled || !value.trim()}
          aria-label="Send"
          title="Send"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
