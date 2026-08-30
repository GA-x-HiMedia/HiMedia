import React, { useCallback, useEffect, useRef, useState } from "react";

import * as api from "./api.js";
import { initials, prettyRole } from "./format.jsx";

import AuditPanel from "./components/AuditPanel.jsx";
import Composer from "./components/Composer.jsx";
import Logo from "./components/Logo.jsx";
import Message from "./components/Message.jsx";
import PendingBanner from "./components/PendingBanner.jsx";
import Rail from "./components/Rail.jsx";
import StatusLine from "./components/StatusLine.jsx";
import ToolPanel from "./components/ToolPanel.jsx";

/* Who the chat opens as. There is no sign-in screen: the agent still needs a
 * number, because a number is the only thing that decides what anyone can
 * see, so one is chosen here and the rail on the left switches it.
 *
 * Override without touching this file:  VITE_DEFAULT_PHONE=+97333000020 npm run dev
 */
const DEFAULT_PHONE = import.meta.env.VITE_DEFAULT_PHONE || "+97333000003";

/* Which number the page came back to last. Without this, removing the sign-in
 * screen means every reload silently jumps back to the default person — the
 * conversation is not lost (memory.py still has it, server-side) but it looks
 * lost, which is worse. Only the number is kept here; nothing about what that
 * person may see is decided in the browser. */
const LAST_PHONE = "himedia.lastPhone";

const rememberPhone = (phone) => {
  try {
    window.localStorage.setItem(LAST_PHONE, phone);
  } catch {
    /* private window, or storage blocked — the default is still fine */
  }
};

const recallPhone = () => {
  try {
    return window.localStorage.getItem(LAST_PHONE);
  } catch {
    return null;
  }
};

let nextId = 1;
const makeMessage = (from, text, extra = {}) => ({
  id: nextId++,
  from,
  text,
  at: Date.now(),
  ...extra,
});

/* A reply that reports a completed write, a refusal, or the device challenge
 * is worth colouring differently from an ordinary answer. Matched on the
 * phrases brain.py and identity.py actually produce — nothing is guessed
 * from the model's free text. */
function toneOf(reply) {
  const text = (reply || "").trim();
  if (/^(Done|تم)\b/.test(text)) return "done";
  if (/^(Cancelled|تم الإلغاء|ألغيت)/.test(text)) return "refused";
  if (/(Could not do that|تعذّر|no longer have permission|ما عندك صلاحية)/.test(text)) {
    return "refused";
  }
  if (/(verification code|رمز تحقق|Device verified|تم التحقق|code was wrong|الرمز مو صحيح)/.test(text)) {
    return "gate";
  }
  if (/(could not find your number|ما لقيت رقمك)/i.test(text)) return "refused";
  return "agent";
}

export default function App() {
  const [people, setPeople] = useState([]);
  const [health, setHealth] = useState(null);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState("");

  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const [pending, setPending] = useState(null);
  const [codeIssued, setCodeIssued] = useState(false);

  const [tab, setTab] = useState("tools");
  const [auditEntries, setAuditEntries] = useState([]);
  const [auditPath, setAuditPath] = useState("");
  const [auditLoading, setAuditLoading] = useState(false);

  const [railOpen, setRailOpen] = useState(false);
  const [asideOpen, setAsideOpen] = useState(false);

  const bottom = useRef(null);

  /* --- becoming somebody ------------------------------------------------- */

  const signIn = useCallback(async (phone) => {
    setBusy(true);
    setRailOpen(false);
    try {
      const found = await api.signIn(phone);
      setSession(found);
      rememberPhone(found.phone);
      setPending(found.pending);
      setCodeIssued(false);
      setDraft("");
      setAuditEntries([]);

      // memory.py keeps the conversation server-side, so switching back to
      // somebody mid-demo — or just reloading the page — picks up where they
      // left off rather than pretending it is a first meeting.
      const restored = (found.history || [])
        .filter((turn) => typeof turn.content === "string" && turn.content)
        .map((turn) =>
          makeMessage(turn.role === "user" ? "me" : "agent", turn.content, {
            kind: turn.role === "user" ? undefined : toneOf(turn.content),
          })
        );

      setMessages([
        ...restored,
        makeMessage(
          "system",
          `Speaking as ${found.name} — ${prettyRole(found.role)} at ${found.company}. ` +
            `${found.offered} of ${found.total} tools survived the permission filter.`,
          { kind: "note" }
        ),
      ]);
      return true;
    } catch (broke) {
      setBootError(broke.message);
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  /* --- opening straight into the conversation ---------------------------- */

  const boot = useCallback(async () => {
    setBooting(true);
    setBootError("");
    try {
      const [directory, state] = await Promise.all([api.roster(), api.health()]);
      setPeople(directory.people);
      setHealth(state);

      const wanted = recallPhone() || DEFAULT_PHONE;
      const start =
        directory.people.find((person) => person.phone === wanted) ||
        directory.people.find((person) => person.phone === DEFAULT_PHONE) ||
        directory.people[0];

      if (!start) throw new Error("The directory came back empty.");
      await signIn(start.phone);
    } catch (broke) {
      setBootError(broke.message);
    } finally {
      setBooting(false);
    }
  }, [signIn]);

  useEffect(() => {
    boot();
  }, [boot]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status, pending]);

  /* --- one turn ---------------------------------------------------------- */

  const send = async (text) => {
    if (!session || busy || !text.trim()) return;

    setDraft("");
    setBusy(true);
    setStatus("Thinking…");
    setMessages((current) => [...current, makeMessage("me", text)]);

    try {
      const answer = await api.sendMessage({
        phone: session.phone,
        message: text,
        onStatus: setStatus,
      });

      setMessages((current) => [
        ...current,
        makeMessage("agent", answer.reply, { kind: toneOf(answer.reply) }),
      ]);
      setPending(answer.pending || null);

      // The device gate answers before the agent does. Once it has issued a
      // code, the composer asks for six digits instead of a question.
      if (!answer.trusted_device) setCodeIssued(true);
      if (answer.trusted_device !== session.trusted_device) {
        setSession((current) => ({ ...current, trusted_device: answer.trusted_device }));
        if (answer.trusted_device) {
          setCodeIssued(false);
          setPeople((current) =>
            current.map((person) =>
              person.phone === session.phone
                ? { ...person, trusted_device: true }
                : person
            )
          );
        }
      }

      if (tab === "audit") refreshAudit();
    } catch (broke) {
      setMessages((current) => [
        ...current,
        makeMessage("system", broke.message, { kind: "note", bad: true }),
      ]);
    } finally {
      setBusy(false);
      setStatus(null);
    }
  };

  /* --- starting over ----------------------------------------------------- */

  const startOver = async (scope) => {
    if (!session) return;
    try {
      const result = await api.reset(session.phone, scope);
      setMessages([
        makeMessage(
          "system",
          scope === "device"
            ? "Conversation cleared, and this device has to verify itself again."
            : `Conversation cleared. Still speaking as ${session.name}.`,
          { kind: "note" }
        ),
      ]);
      setPending(null);
      setCodeIssued(false);
      setSession((current) => ({ ...current, trusted_device: result.trusted_device }));
      if (scope === "device") {
        setPeople((current) =>
          current.map((person) =>
            person.phone === session.phone ? { ...person, trusted_device: false } : person
          )
        );
      }
    } catch (broke) {
      setMessages((current) => [
        ...current,
        makeMessage("system", broke.message, { kind: "note", bad: true }),
      ]);
    }
  };

  /* --- the audit tail ---------------------------------------------------- */

  const refreshAudit = useCallback(async () => {
    if (!session) return;
    setAuditLoading(true);
    try {
      const tail = await api.audit(session.phone);
      setAuditEntries(tail.entries);
      setAuditPath(tail.path);
    } catch {
      /* the panel simply stays as it was */
    } finally {
      setAuditLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (tab === "audit") refreshAudit();
  }, [tab, refreshAudit]);

  /* --- before the first conversation exists ------------------------------ */

  if (!session) {
    return (
      <div className="boot">
        <div className="boot-card">
          <Logo large subtitle="Production assistant" />
          {booting ? (
            <>
              <div className="boot-line">Connecting to the agent…</div>
              <div className="pulse">
                <i />
                <i />
                <i />
              </div>
            </>
          ) : (
            <>
              <div className="note bad" style={{ marginTop: 18 }}>
                {bootError || "The agent is not answering."}
              </div>
              <p className="boot-hint">
                Start the API from the repository root with{" "}
                <code>uvicorn agent.web:app --reload --port 8000</code>, then
                try again.
              </p>
              <button type="button" className="btn" onClick={boot}>
                Try again
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  const awaitingCode = !session.trusted_device && codeIssued;

  return (
    <div className="shell">
      <Rail
        people={people}
        current={session.phone}
        onSelect={signIn}
        open={railOpen}
        health={health}
      />

      {(railOpen || asideOpen) && (
        <div
          className="scrim"
          onClick={() => {
            setRailOpen(false);
            setAsideOpen(false);
          }}
        />
      )}

      <main className="chat">
        <header className="chat-head">
          <button
            type="button"
            className="icon-btn only-narrow rail-toggle"
            onClick={() => setRailOpen(true)}
            aria-label="People"
          >
            ☰
          </button>

          <span className={`disc lg ${session.audience === "client" ? "client" : "internal"}`}>
            {initials(session.name)}
          </span>

          <div className="who">
            <b>{session.name}</b>
            <span>
              {prettyRole(session.role)} · {session.company} · {session.phone}
            </span>
          </div>

          <span className={`badge ${session.audience === "client" ? "client" : "internal"}`}>
            {session.audience}
          </span>
          <span className={`badge ${session.trusted_device ? "verified" : "unverified"}`}>
            {session.trusted_device ? "device verified" : "device unverified"}
          </span>

          <button
            type="button"
            className="btn-ghost"
            onClick={() => startOver("conversation")}
            disabled={busy}
            title="Forget this conversation and any held write"
          >
            New chat
          </button>

          <button
            type="button"
            className="icon-btn only-narrow aside-toggle"
            onClick={() => setAsideOpen(true)}
            aria-label="Permissions"
          >
            ⚙
          </button>
        </header>

        <div className="transcript">
          {messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
          {busy && <StatusLine status={status} />}
          <div ref={bottom} />
        </div>

        {pending && <PendingBanner pending={pending} busy={busy} onSay={send} />}

        <Composer
          value={draft}
          onChange={setDraft}
          onSend={send}
          busy={busy}
          audience={session.audience}
          awaitingCode={awaitingCode}
          disabled={false}
        />
      </main>

      <aside className={asideOpen ? "aside open" : "aside"}>
        <div className="tabs">
          <button
            type="button"
            className={tab === "tools" ? "tab on" : "tab"}
            onClick={() => setTab("tools")}
          >
            Access
          </button>
          <button
            type="button"
            className={tab === "audit" ? "tab on" : "tab"}
            onClick={() => setTab("audit")}
          >
            Audit
          </button>
          <div style={{ flex: 1 }} />
          <button
            type="button"
            className="tab"
            onClick={() => startOver("device")}
            title="Make this number verify its device again"
          >
            Reset device
          </button>
        </div>

        {tab === "tools" ? (
          <ToolPanel session={session} />
        ) : (
          <AuditPanel
            entries={auditEntries}
            path={auditPath}
            loading={auditLoading}
            onRefresh={refreshAudit}
          />
        )}
      </aside>
    </div>
  );
}
