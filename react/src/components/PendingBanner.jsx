import React, { useEffect, useState } from "react";

/** The write that is waiting for a human.
 *
 * Nothing here decides anything. Every button sends an ordinary message down
 * the ordinary path, and brain.py reads it exactly as it reads a message
 * typed by hand — a yes is still a yes read in code, and permissions are
 * still re-checked at the moment the write runs. This is a shortcut for
 * typing, never a second way in.
 *
 * The buttons appear in one language, the one the person was just writing in.
 * Offering "Yes / أي / No" together asks somebody mid-conversation to pick a
 * language before they can answer a yes-or-no question. Both words are in
 * brain.AFFIRMATIVE and brain.NEGATIVE, so either set works identically.
 *
 * Two shapes, because the agent has two:
 *
 *   ordinary write     -> yes / no
 *   point of no return -> the exact phrase, typed. "ok" is what someone
 *                         sends while half-reading a notification, and
 *                         approving a client deliverable is not something to
 *                         do by reflex. Anything that is not the phrase
 *                         cancels.
 */

const WORDS = {
  en: {
    waiting: "Waiting for your confirmation",
    final: "Final — this cannot be undone",
    yes: "Yes, do it",
    no: "No",
    confirm: "Confirm",
    cancel: "Cancel",
    copied: "copied",
    copy: "copy",
    why: "Nothing has changed yet.",
    whyFinal:
      "This one is final, so a yes will not do it. Type the phrase above " +
      "exactly. Anything else cancels — including “yes”, which is the reflex " +
      "this gate exists to interrupt.",
    typeHere: "Type the confirmation phrase exactly",
  },
  ar: {
    waiting: "بانتظار تأكيدك",
    final: "إجراء نهائي — ما ينعاد",
    yes: "أي، سوّها",
    no: "لا",
    confirm: "تأكيد",
    cancel: "إلغاء",
    copied: "تم النسخ",
    copy: "نسخ",
    why: "ما تغيّر شي لحد الحين.",
    whyFinal:
      "هذا إجراء نهائي، و«أي» ما تكفي. اكتب العبارة اللي فوق بالضبط. أي شي " +
      "ثاني يلغي الطلب — حتى «أي»، وهذا بالضبط اللي هالبوابة موجودة عشانه.",
    typeHere: "اكتب عبارة التأكيد بالضبط",
  },
};

export default function PendingBanner({ pending, busy, language = "en", onSay }) {
  const [typed, setTyped] = useState("");
  const [copied, setCopied] = useState(false);

  // A new held action starts with an empty box — never with the last one's
  // text still sitting in it, ready to be sent by accident.
  useEffect(() => {
    setTyped("");
    setCopied(false);
  }, [pending.tool, pending.summary]);

  const ar = language === "ar";
  const t = ar ? WORDS.ar : WORDS.en;
  const dir = ar ? "rtl" : "ltr";

  const final = Boolean(pending.needs_phrase);
  const matches = typed.trim() === pending.phrase;

  // The word actually sent. Both sets are in brain.py's own lists, so the
  // agent cannot tell which button was pressed — only what was said.
  const YES = ar ? "أي" : "yes";
  const NO = ar ? "لا" : "no";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(pending.phrase);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked — the phrase is on screen anyway
    }
  };

  return (
    <div className={final ? "pending final" : "pending"} dir={dir}>
      <div className="eyebrow">{final ? t.final : t.waiting}</div>

      <p className="pending-what" dir="auto">{pending.summary}</p>
      <div className="pending-tool" dir="ltr">{pending.tool}</div>

      {final ? (
        <>
          <div className="phrase-chip">
            <span dir="rtl">{pending.phrase}</span>
            <button type="button" onClick={copy}>
              {copied ? t.copied : t.copy}
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
              aria-label={t.typeHere}
            />
            <button type="submit" className="btn danger" disabled={!matches || busy}>
              {t.confirm}
            </button>
            <button
              type="button"
              className="btn quiet"
              disabled={busy}
              onClick={() => onSay(NO)}
            >
              {t.cancel}
            </button>
          </form>

          <div className="pending-why">{t.whyFinal}</div>
        </>
      ) : (
        <>
          <div className="pending-actions">
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => onSay(YES)}
            >
              {t.yes}
            </button>
            <button
              type="button"
              className="btn quiet"
              disabled={busy}
              onClick={() => onSay(NO)}
            >
              {t.no}
            </button>
          </div>

          <div className="pending-why">{t.why}</div>
        </>
      )}
    </div>
  );
}
