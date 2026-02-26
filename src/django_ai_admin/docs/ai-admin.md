0) Production Plan (New)

Detailed production roadmap by releases, unified runtime contract, and security policy:
- `docs/ai-admin_production_plan.md`

---

1) What This Is

An embedded AI assistant for Django Admin:
- AI button in the top bar opens a right-side drawer.
- Free-form questions are converted into ORM queries by an LLM.
- Execution runs only inside a read-only transaction (`SET LOCAL transaction_read_only = on`).
- Chat history and model/key settings are available in admin.
- No custom HTML templates required for the chat UI; drawer and UI are generated dynamically (JS/HTML string).

---

2) Key Features (MVP)
- Right-side drawer in Admin, chat list, and input box.
- Create a new chat or open an existing chat.
- Generate Python ORM code from user questions.
- Execute ORM in read-only mode only (hard DB-level write blocking).
- Logs: who asked what, duration, result/error.
- Settings: API key, model, temperature, max_tokens, timeout.

---

3) Architecture (High-Level)
- `ai_assistant/` as a standalone Django app inside the current project.
- Components:
- Manifest Builder: collects project models/fields into memory.
- LLM Connector: calls GPT model via Chat Completions API.
- Executor: isolated `exec()` of ORM snippet in a read-only transaction.
- Admin Panel: top-bar button + right-side drawer (dynamic HTML/JS).
- Storage: `Chat` and `Message` for history; `AIConfig` for settings.
- API: minimal JSON endpoints for chats/messages/settings check.

---

4) Requirements
- Django 3.2+ (recommended: 4.x/5.x).
- PostgreSQL (read-only transactions via `SET LOCAL transaction_read_only = on`).
- LLM transport: OpenAI-compatible Chat Completions API.
- Staff access to admin.

---

5) Install and Wire-Up (No Implementation Code)
1. Add `ai_assistant` to `INSTALLED_APPS`.
2. Include URL prefix `/ai-assistant/` in project root routes.
3. Include assistant static assets (icon + minimal JS/CSS).
4. Restrict assistant routes to `is_staff`.
5. In admin, open AI Assistant -> Settings, then set API key and model.
6. AI button appears in top bar; clicking opens the right-side drawer.

---

6) Settings (Settings Panel)
- `api_key`: provider key (OpenAI).
- `model`: model name (for example, `gpt-4o-mini`).
- `temperature`: 0.0-1.0 (default 0.2-0.3).
- `max_tokens`: model response token limit.
- `timeout_sec`: LLM request timeout.
- (Optional) `provider`: OpenAI/Local/Ollama (future use).
- Settings access: superuser only.
- Key is stored securely and masked in UI (last 4 characters).

---

7) Data Model (Storage Entities)
- `AIConfig`: singleton settings record.
- `Chat`: owner (user), title, `created_at`, `updated_at`.
- `Message`: chat, `role in {system,user,assistant}`, content, `created_at`.
- Indexes on owner and `updated_at` for fast chat list retrieval.

---

8) Manifest (LLM Context)
- Build at startup: iterate `apps.get_models()` and collect compact schema:
- `{ "<App>.<Model>": ["id", "username", "date_joined", ...], ... }`
- Stored in process memory.
- Refreshed on `post_migrate`.
- Pass compressed manifest in the system prompt (full once at session start or relevant fragments).

---

9) UX Flow
1. Click AI in header -> right-side drawer opens.
2. Chat list at top + `+ New Chat` button.
3. Input at bottom: send question -> typing state -> answer and (if needed) tabular data.
4. Click any chat in list to load history and continue conversation.
5. Chat title is updated after the first stable response (short summary title).

---

10) API (JSON) - Surface
- `GET /ai-assistant/api/chats` - list user chats (`id`, `title`, `updated_at`).
- `POST /ai-assistant/api/chats` - create new chat (optional `title`).
- `GET /ai-assistant/api/chats/{id}` - message history (pagination).
- `POST /ai-assistant/api/chats/{id}/message` - send user message and receive assistant response.
- `GET /ai-assistant/api/settings/check` - verify key/model configuration.
- All routes are `is_staff` only.

---

11) Prompting (Operational)

System (once at session initialization):
- Role: "You are a Python/Django ORM expert. Write concise, correct read-only ORM code. Never write data."
- Rules:
- read-only methods only (`aggregate`, `filter`, `annotate`, `values`, `values_list`);
- limit result sets by default (<= 100 rows);
- output a short explanation plus a `result` object (number/list/dict).
- Include model structure (compressed manifest of allowed models/fields).

User (each request):
- Natural-language data question.

Assistant (expected model output):
- Short user-facing explanation.
- Clear Python ORM snippet (read-only) that returns `result`.

(Code is stored/transferred as text and executed on backend inside read-only transaction.)

---

12) Execution (Read-Only Guarantees)
- For every request:
1. open transaction (`atomic`);
2. run `SET LOCAL transaction_read_only = on`;
3. execute ORM code via `exec()` in a narrow environment (`__builtins__` restricted to safe minimum; only allowed models/helpers exposed);
4. collect `result`.
- Post-processing:
- if number -> return as number;
- if list/dict -> enforce row limit (`<= MAX_ROWS`, e.g. 100), truncate overly long fields;
- return short text + `result` as JSON.

---

13) Limits and Controls
- DB `statement_timeout` (for example, 5000 ms).
- `MAX_ROWS` for tables (for example, 100).
- Per-user rate limit (for example, 20 requests/minute).
- Field truncation and PII masking by policy.
- No imports/network/files in `exec()` (strict execution environment).

---

14) Logging and Audit
- Save in `QueryLog`/`Message`:
- `user`, `chat_id`,
- original question,
- generated ORM fragment,
- duration, row count/truncation, errors.
- Metrics:
- p95 response time,
- error rate,
- query frequency.

---

15) Testing (Acceptance)
- Read-only enforcement: intentional `update()` attempt in executed code -> error "cannot execute UPDATE in a read-only transaction".
- Baseline scenarios:
- "How many registrations today?" -> correct number.
- "Users with 6-digit username" -> count + up to 100 IDs.
- "With avatar / without avatar" -> counts and percentages sum correctly.
- Large result sets -> truncated response; UI shows "Show more" (next page/retry flow).
- Failure cases (no key, LLM timeout, invalid code) -> friendly message + correct logging.

---

16) Deployment
- Install `ai_assistant` and include URLs.
- Configure static assets (icon + minimal drawer JS/CSS).
- Set API key and model in AI Assistant -> Settings.
- Verify staff-only access.
- Run smoke tests (3-5 typical questions).

---

17) Roadmap (Post-MVP)
- Export button for CSV/JSON.
- Charts (PNG images) in answers.
- Suggested prompts and favorite queries.
- Multi-provider support and model profiles (`fast`/`accurate`).
- Caching for popular queries.
- Long-running jobs via Celery.

---

18) SLA and Safety
- Every request executes in read-only transaction (hard guarantee).
- No raw shell/file/external network access from `exec()`.
- Keys and settings accessible only to superusers.
- Logs exclude secrets and PII.

---

19) Acceptance Criteria
- AI button in header; drawer opens/closes without reload.
- New chat is created on first message; history loads immediately.
- Any DB write attempt inside execution is blocked at PostgreSQL level.
- Responses are concise and accurate; large results are truncated by limits.
- Model/key settings can be changed without restart and apply to new queries.

---

20) Notes
- MVP has no DSL/AST/Explorer layer. Free input -> LLM code -> safe execution.
- Later, add optional validation layer and RAG for project business terminology.
