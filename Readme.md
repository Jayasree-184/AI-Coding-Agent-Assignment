# AI Coding Agent — EasyNotes: Organize & Search

An AI agent that explores an existing codebase, plans an improvement, implements
it, and verifies the result — applied here to
[node-easy-notes-app](https://github.com/callicoder/node-easy-notes-app) to
satisfy the request: *"Improve the application so users can better organise
and search their notes."*

## Architecture

Two files make up the agent:

- **`agent/agent.py`** — the orchestration loop. Sends the task to an LLM
  (Groq's `llama-3.3-70b-versatile`, free tier — chosen to avoid any paid
  API dependency) along with a set of tool definitions. The model decides,
  turn by turn, which tool to call. Every call is executed for real against
  the filesystem and the result is fed back to the model, until it calls a
  `finish` tool signalling the task is complete.
- **`agent/tools.py`** — the actual capabilities the agent has: `list_files`,
  `read_file`, `grep` (read-only, for exploration) and `write_file` (for
  implementation). All paths are resolved and checked against the target
  repo root so the agent can't write outside it.

No part of the repository's exploration is hardcoded — the agent decides
which files to list, search, and read based on what it discovers, the same
way a developer would.

## Agent workflow

```
explore (list_files / grep / read_file)
     ↓
reason about architecture + decide a plan
     ↓
implement (write_file)
     ↓
finish(plan, summary)
```

The system prompt enforces this order explicitly: the agent is instructed
to read a file in full before modifying it, to match the project's existing
language/conventions (a real failure mode we hit and fixed — see below),
and to keep new routes/functions actually wired into the app rather than
dangling and unused.

A retry layer catches malformed tool calls (an occasional issue with the
free model) and nudges the model to retry with valid JSON, rather than
crashing the run.

## How the repository is explored

On a fresh clone, a typical run:
1. Calls `list_files` to see the whole tree (`app/controllers`, `app/models`,
   `app/routes`, `server.js`, `package.json`, etc.)
2. `grep`s for relevant keywords (e.g. `note`, `search`) to find where core
   logic lives
3. `read_file`s the specific files it intends to modify
   (`note.model.js`, `note.controller.js`, `note.routes.js`) in full
4. Only then writes changes

## What the agent implemented

- **Tags**: `tags: [String]` added to the Mongoose schema
- **Search**: a MongoDB text index (`title`, `content`, `tags`) plus a new
  `GET /notes/search?query=...` endpoint, backed by `$text: { $search }`
- All original endpoints (`create`, `findAll`, `findOne`, `update`,
  `delete`) preserved and verified unchanged

## Assumptions & trade-offs

- **Search over categories**: given a single unguided request, full-text
  search + tags covers "organise and search" more directly than a rigid
  category taxonomy would; tags double as light-weight organisation.
- **Free LLM over a paid one**: chosen deliberately to keep the assignment
  cost-free. The trade-off is lower reliability — a smaller open model is
  more prone to malformed tool-call syntax than a frontier model would be.
  This is handled with a retry loop rather than assumed away.
- **MongoDB text index vs. a dedicated search service**: appropriate for
  this app's scale; a production system with heavier search needs would
  warrant Elasticsearch or similar, which was out of scope here.

## Known limitations

- On one run, the agent initially wrote new files with a `.ts` extension
  in a plain JavaScript project — caught during manual verification (not
  automatically detected by the agent), and fixed by tightening the system
  prompt to explicitly state the project's existing language/extension and
  requiring the agent to match it.
- On another run, the agent used an `express.Router()` pattern for the new
  route file, while the original codebase's convention was
  `module.exports = (app) => {...}`. This broke the contract `server.js`
  expects (`require('./app/routes/note.routes.js')(app)`) and was corrected
  by hand rather than by re-running the agent, since it was a fast, isolated
  fix. In a stricter version of this agent, a post-write verification step
  (e.g. actually requiring/running the modified files, or running existing
  tests) would catch this automatically — noted as a natural next
  improvement rather than implemented here, given the assignment's time box.

## How to run

```bash
cd agent
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...      # free key from console.groq.com

python agent.py <path-to-target-repo> "Improve the application so users can better organise and search their notes."
```

The target repo should be a fresh, unmodified clone for a clean run. Verify
the result with:

```bash
cd <target-repo>
npm install
node server.js
```

Requires a local MongoDB instance (Community Edition, free) for the app
itself to run — this is a pre-existing requirement of the original
application, not something introduced by the agent.