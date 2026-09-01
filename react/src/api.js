/* Everything that talks to agent/web.py.
 *
 * Requests go to /api/... and Vite proxies them to the Python process, so
 * the browser stays on one origin and nothing here needs a base URL.
 */

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return unwrap(response);
}

async function get(path) {
  return unwrap(await fetch(path));
}

async function unwrap(response) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* an empty body, or an HTML error page from the dev server */
  }

  if (!response.ok) {
    const detail = data && data.detail;
    if (typeof detail === "string") throw new Error(detail);

    // A 500 with no JSON body is almost always the Vite dev proxy failing to
    // reach the Python process, not the agent failing. Saying "HTTP 500"
    // sends you looking in the wrong place; say which process is missing.
    if (response.status === 500 && !data) {
      throw new Error(
        "The agent API is not answering on port 8000. Start it from the " +
          "repository root, and leave that terminal open — the device " +
          "verification code is printed there."
      );
    }
    throw new Error(`HTTP ${response.status}`);
  }
  return data;
}

export const health = () => get("/api/health");
export const roster = () => get("/api/roster");
export const signIn = (phone) => post("/api/session", { phone });
export const reset = (phone, scope) => post("/api/reset", { phone, scope });
export const audit = (phone) =>
  get(`/api/audit?limit=80&phone=${encodeURIComponent(phone)}`);

/* --- one turn, with the agent's own progress as it happens ---------------
 *
 * brain.reply_to reports "Thinking…" and "Calling list_tasks…" through its
 * on_status callback; the API forwards each one as a server-sent event. So
 * this reads the response as a stream rather than waiting for the whole
 * body, and calls onStatus as each update lands.
 *
 * Resolves with the final { reply, pending, trusted_device }.
 */
export async function sendMessage({ phone, message, onStatus, signal }) {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, message }),
    signal,
  });

  if (!response.ok) {
    // An error before the stream started — a 400 or 503 with a JSON body.
    throw new Error(await errorText(response));
  }
  if (!response.body) {
    throw new Error("This browser cannot read a streaming response.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  let failure = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Events are separated by a blank line. Keep the trailing fragment —
    // a chunk boundary can land in the middle of one.
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const event = parseEvent(chunk);
      if (!event) continue;

      if (event.name === "status" && onStatus) onStatus(event.data);
      else if (event.name === "reply") result = event.data;
      else if (event.name === "error") failure = event.data;
    }
  }

  if (failure) throw new Error(String(failure));
  if (!result) throw new Error("The agent closed the connection without answering.");
  return result;
}

function parseEvent(chunk) {
  let name = "message";
  const dataLines = [];

  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }

  if (dataLines.length === 0) return null;
  try {
    return { name, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

async function errorText(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* fall through to the status code */
  }
  return `HTTP ${response.status}`;
}
