# HiMedia AI Agent
 
**General Assembly × JoinFuture Solutions W.L.L., Two-Week Capstone**
Students: Sara Alnajjar, Reem AlShehabi, Zainab Mohammed.
 
## What it does
 
Hussain Media makes films for clients like Bank of Salam. Staff and clients both want quick answers, like *what am I working on today? has the client replied? which version are they waiting for?*, without opening a dashboard. This agent answers those questions correctly for whoever is asking, changes data only after they explicitly say yes, and never shows anyone more than they're allowed to see.
 
It also includes a separate document Q&A tool that answers questions from the project handbook and brief, using only what's written in them.
 
You can talk to it two ways: a terminal, or the React browser chat window. Both go through the same identity, permission, and safety logic underneath.
 
## Setup
 
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
 
Edit `.env`:
 
- `HIMEDIA_API_KEY`: the shared class key from the handbook
- `OPENAI_API_KEY`: a real key, needed to generate answers
- `GEMINI_API_KEY`: optional alternative to OpenAI
## Try it out
 
See the 13 seeded people and their roles/permissions, pulled live from the API:
 
```bash
python -m agent.roster
```
 
Have a real conversation in the terminal as different people, and watch each one get a correctly different answer based on their permissions:
 
```bash
python -m agent.cli
```
 
## What it can do
 
Six read-only tools, filtered to what the caller is actually allowed to see:
 
| Tool | Needs |
|---|---|
| `who_am_i` | none |
| `list_tasks` | `tasks:read` |
| `get_task_notes` | `tasks:read` |
| `list_projects` | `projects:read` |
| `list_versions` | `reviews:read` |
| `get_review_notes` | `reviews:read` |
 
Five write tools, layered on top:
 
| Tool | Needs |
|---|---|
| `create_task` | `tasks:write` |
| `update_task_status` | `tasks:write` |
| `comment_on_task` | `tasks:write` |
| `comment_on_version` | `reviews:write` |
| `decide_version` | `reviews:write` |
 
## Safety: nothing changes without a yes
 
When the agent wants to run a write tool, it doesn't run it right away. It previews what it's about to do and waits for the next message to confirm.
 
```bash
python -m agent.cli
# sign in as Khalid (+97333000003) and try:
#   "move task tsk_0001 to done"
# then confirm with "yes", or cancel with "no"
```
 
A few actions are hard to undo or send something straight to a client (approving/rejecting a version, cancelling a task, moving a task to client review, posting a client-visible comment). Those require typing an exact confirmation phrase instead of just "yes". Everything else confirms normally.
 
The agent also refuses cleanly whenever someone asks for something outside their permissions, and never tries to find a workaround. A test suite specifically tries to trick it into leaking one person's data to another (wrong company, wrong role, internal notes, etc.) and every attempt is checked and blocked.
 
## Ask questions about the project documents
 
Separately from the agent above, there's a small tool that answers questions from the project files (handbook, brief, and other docs in `data/docs`).
 
Build the index once (and again whenever a document changes):
 
```bash
python -m src.rag.main ingest
```
 
Then ask a question:
 
```bash
python -m src.rag.main query "What does an editor's role allow?"
```
 
Or run `python -m src.rag.main` with no arguments to ask questions in a loop.
 
## Running the chat interface
 
```bash
uvicorn agent.web:app --reload --port 8000
# in a second terminal:
cd react && npm install && npm run dev
```
 
Open the address Vite prints (normally `http://localhost:5173`). Keep the `uvicorn` server running, since the UI talks to it.
 
## Tests
 
```bash
pytest -v                        # no network needed
RUN_LIVE_TESTS=1 pytest -v -s    # + real sandbox and model
```

Tests skip rather than fail when what they need is missing: the sandbox ones need `RUN_LIVE_TESTS=1`, and the leak conversations additionally need a model key. A run with no key still covers every permission and filtering check.

Each leak fix was verified by taking it back out and re-running its test. All of them failed without their fix, so none is passing by accident.
 
## What's not finished
 
- **Device trust is basic.** A new phone/device gets a one-time code before it's trusted; after that, anyone holding that number is treated as that person. The code is currently written to the server log rather than sent out of band.
- **No persistent storage.** Conversation history and pending confirmations live in memory, so restarting the server clears them.
- **Confirmation matching is a fixed word list** ("yes"/"no" and a few variants), not full language understanding.
- **Leak checks match words, not meaning.** A reply saying "your editor" instead of a name, or "twelve days overdue" instead of a figure, passes every check and is still a leak. The real defence is that those values are filtered out before the prompt is built, so the model never receives them.
## Project layout
 
```
agent/
  config.py, himedia.py, identity.py   # config, API wrapper, phone -> person + permissions
  roster.py, explore.py                # look-around scripts
  tools.py, memory.py, brain.py        # tool catalogue, conversation state, agent loop
  web.py                               # the live chat entry point
  cli.py, demo.py                      # terminal harness + scripted walkthrough
react/                                  # the browser chat UI (React + Vite)
src/rag/
  ingest.py, query.py, main.py         # document Q&A: build index, ask questions
data/docs/                              # handbook, brief, and other source documents
tests/                                  # pytest suite, including the leak-prevention tests
.env.example
requirements.txt
```
 

