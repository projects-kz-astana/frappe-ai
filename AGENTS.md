# Frappe AI - Agents

Agents turn the AI Clients you already configured in Frappe AI into tool-using
assistants. An agent receives a message, calls the LLM, lets it read and write
Frappe data through a fixed set of permission-checked tools, loops until the
model is done, and returns a final answer. Conversations are persisted, bounded
by a rolling summary, and run in the background so the desk stays responsive.

Agents reuse the client registry initialised at boot (`frappe_ai/boot.py` →
`frappe_ai.clients`). No new API keys or SDK setup is required. Point an agent
at an existing **AI Client** and it uses that client's provider, model, and
credentials.

## Architecture

```
frappe_ai/agent/
├── runner.py       AgentRunner. The LLM + tool-dispatch loop (supports Anthropic & OpenAI clients, as Gemini models don't support using Agents)
├── tools.py        Generic Frappe tools + JSON schemas + provider conversion
├── prompts.py      System prompt builder (loads the linked Agent Prompt)
├── memory.py       Conversation window + rolling LLM summarisation
├── permissions.py  has_permission assertions used by every mutating tool
├── jobs.py         frappe.enqueue entry point (run_agent)
└── api.py          Whitelisted chat() and get_messages()
```

| DocType | Purpose |
|---|---|
| Agent | Defines an agent: which AI Client, which prompt, tool allow-list, limits |
| Agent Prompt | Stores reusable system prompts (supports placeholders) |
| Agent Tool | Child table on Agent; the per-agent tool allow-list |
| Agent Session | One conversation: user, status, model, context, rolling summary |
| Agent Message | One turn: role, content, tool calls, latency, tokens |

### Supported providers

The tool-use loop is implemented for **Anthropic** and **OpenAI** AI Clients.
Anthropic uses the Messages API `tool_use` protocol; OpenAI uses Chat
Completions `tool_calls`. Google clients are rejected at validation time (they
can still be used for plain chat and RAG through the rest of Frappe AI).

## Setup

### 1. Create an AI Client

Use any existing Anthropic or OpenAI **AI Client** (see the main README). The
agent inherits its model and API key.

### 2. Create an Agent Prompt

Open **Agent Prompt** and create a record. The prompt is plain text and supports
these placeholders, substituted per request:

- `{user}` - the session user's email
- `{company}` - the user's default Company (blank if unset)
- `{date}` - today's date
- `{context}` - JSON of the session's `context_json` field

Example:

```
You are an operations assistant for {company} on {date}, helping {user}.
Use the provided tools to read and modify records. Never guess data.
```

If an agent has no Agent Prompt linked, a safe built-in default is used.

### 3. Create an Agent

Open **Agent** and fill in:

- **AI Client** - the Anthropic/OpenAI client to use
- **Agent Prompt** - optional; the system prompt
- **Max Iterations** - tool-use loops allowed before the agent must answer (default 10)
- **Max Tokens** - per-response output cap (default 4096)
- **Temperature** - optional; leave 0 for the provider default
- **Allow All Tools** - when checked the agent can use every registered tool.
  Uncheck it and list specific tools in the **Allowed Tools** table to restrict
  the agent.

## Tools

Every tool operates on **any** DocType and enforces `frappe.has_permission`
against the session user before reading or writing. Mutating tools commit on
success. A permission failure is returned to the model as a tool error (not a
500), so the agent reports it instead of crashing.

| Tool | Action |
|---|---|
| `list_doctypes` | List DocTypes the user can read |
| `get_doctype_fields` | Inspect a DocType's fields before reading/writing |
| `search_documents` | Search a DocType by keyword and/or filters |
| `get_document` | Fetch one record by name |
| `count_documents` | Count records matching filters |
| `create_document` | Create a record (requires create permission) |
| `update_document` | Update a record (requires write permission) |
| `submit_document` | Submit a submittable doc (requires submit permission) |
| `cancel_document` | Cancel a submitted doc (requires cancel permission) |
| `run_report` | Run a saved Report and return rows |
| `list_my_tasks` | List ToDo tasks assigned to the user |

Results are capped at 50 rows to keep token usage bounded.

## Usage

### From the Desk

Open an **Agent** record and click **Chat** in the top-right. A dialog opens; type
a message and press Send. The request is queued, the agent runs in the background,
and the reply streams back over Frappe realtime when the job finishes. The widget
(`public/js/agent_chat.js`, `frappe.ui.AgentChat`) is loaded on every desk page,
so you can also launch it from your own scripts:

```javascript
const chat = new frappe.ui.AgentChat("Ops Assistant");
chat.show();
```

UI components have already been added to explore how desk-wide agents can be added and accessed inside the following components, and hooked inside `hooks.py` under `app_include_js`:
- `frappe_ai/public/js/agent_chat.js`
- `frappe_ai/public/js/agent_launcher.js`

### From JavaScript (frappe.call)

```javascript
frappe.call({
    method: "frappe_ai.agent.api.chat",
    args: { agent: "Ops Assistant", message: "List my open tasks", session: "new" },
    callback: (r) => {
        const session = r.message.session; // reuse this for follow-ups
    },
});

frappe.realtime.on("agent_response", (data) => {
    if (data.status === "done") console.log(data.content);
});
```

`chat` returns immediately with `{ "session": "...", "status": "queued" }`. Pass
the returned session name back on the next call to continue the same conversation;
pass `"new"` to start a fresh one.

### From Python

```python
# Asynchronous: returns the session, runs in a worker:
from frappe_ai.agent.api import chat
res = chat(agent="Ops Assistant", message="How many open Leads are there?")
session = res["session"]

# Synchronous: runs inline and returns the final answer string:
from frappe_ai.agent.runner import AgentRunner
answer = AgentRunner(session).run("And how many were created this week?")
```

### HTTP

```
POST /api/method/frappe_ai.agent.api.chat
{ "agent": "Ops Assistant", "message": "hello", "session": "new" }
→ { "message": { "session": "AGENT-SESS-00001", "status": "queued" } }
```

## How a turn runs

1. `api.chat` creates an Agent Session (if `session == "new"`) and enqueues
   `agent.jobs.run_agent` on the `long` queue.
2. The job calls `frappe.set_user(user)` so every tool runs with the requesting
   user's permissions, then builds the system prompt (prompt + tool catalogue +
   rolling summary) and loads the recent conversation window.
3. `AgentRunner` calls the LLM. While the model returns tool calls, each is
   dispatched through `tools.REGISTRY`, results are fed back, and the loop repeats
   up to **Max Iterations**.
4. The final text is persisted, the session is marked `Completed`, and an
   `agent_response` realtime event fires on the user's channel.
5. After the turn, `memory.update_summary` collapses old messages into the
   session summary once the message count crosses the threshold, keeping context
   bounded across long conversations.

On any error the session is set to `Error`, the traceback is logged via
`frappe.log_error`, and an `agent_response` event with `status: "error"` is sent.

## Permissions

- Agents and Agent Prompts are managed by **System Manager**.
- Agent Sessions and Agent Messages are owner-scoped: a user sees only their own.
- Tools never bypass Frappe permissions. They assert read/create/write/submit/cancel rights against the session user before acting.

## Smoke test

```python
# bench --site <site> console
import frappe
frappe.set_user("Administrator")

from frappe_ai.agent.api import chat
res = chat(agent="Ops Assistant", message="How many User records exist?")
print(res)  # {"session": "AGENT-SESS-xxxxx", "status": "queued"}

import time; time.sleep(10)
print(frappe.db.get_value("Agent Session", res["session"], "status"))  # Completed

for m in frappe.get_all("Agent Message", filters={"session": res["session"]}, fields=["role", "content"], order_by="creation asc"):
    print(m.role, ":", (m.content or "")[:80])
```

Make sure a worker is processing the `long` queue (`bench worker --queue long`)
and the linked AI Client's account has API credit.
