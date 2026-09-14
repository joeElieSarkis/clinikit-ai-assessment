# Gemini setup and evaluation

## Create a free-tier key

1. Open [Google AI Studio API keys](https://aistudio.google.com/apikey) and sign in.
2. Create an API key for a Google project. Check that the project's billing tier is **Free**. Do not link a billing account, prepay, or enable a paid tier for this assessment.
3. In the repository root, copy `.env.example` to `.env` if `.env` does not already exist. Keep an existing file and edit its values instead of overwriting a saved key.
4. Set `AI_PROVIDER=gemini`, paste the key after `GEMINI_API_KEY=`, and keep `GEMINI_MODEL=gemini-3.5-flash-lite`. Save the file. Do not paste the key into chat, screenshots, the frontend, or a GitHub file.
5. Stop the local launcher with Ctrl+C, then restart with `.\.venv\Scripts\python.exe run.py`. Python does not automatically reload changed code or `.env` values in this launcher.

The **Gemini** badge identifies the configured provider. Open `/api/health` on the Python server to check `mode: gemini` and the model name. Neither the badge nor the health endpoint calls Google; a successful message is needed to verify the key and actual model access.

Google's [pricing](https://ai.google.dev/gemini-api/docs/pricing) lists free input and output for Gemini 3.5 Flash-Lite. The [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) lists structured output support. The [billing guide](https://ai.google.dev/gemini-api/docs/billing) explains that the key inherits its project's billing tier. The app cannot determine that tier from the key, so a free-model label in code alone is not a spending guarantee. These terms were checked on 15 September 2026. The default was changed explicitly to Flash-Lite after it passed the live conversation that repeatedly failed on 3.6 Flash with HTTP 503 high-demand errors. There is no automatic model fallback.

## What the model does

The backend uses `generateContent` with a JSON schema and validates the returned object with Pydantic. Gemini extracts the intent, doctor, requested date/time, original date, appointment reference, and hold/ambiguity flags. The system prompt is separate from the untrusted patient JSON. Only the latest eight conversation messages and active draft are included.

Gemini does not receive booking tools and does not write arbitrary patient-facing claims. The Python workflow checks actual mock availability and constructs replies from those results. Confirmations still identify one exact proposal and recheck availability. This is a constrained conversational AI workflow, not an autonomous clinical agent.

There is no RAG pipeline: this exercise has a small structured doctor directory and schedule, not a document collection. Queries use the mock clinic functions directly. A future policy/FAQ document collection would justify retrieval and source citations; appointment availability should still come from a scheduling service rather than a document search.

## Try language variation

Use a fresh sample session for independent examples:

- “Could you pencil me in with Doctor Maya on Tuesday at noon?”
- “I'd like to push my Monday visit back to Wednesday.”
- “Please scrap my visit with Karim.”
- “Reserve George for Monday at 4, but leave it unconfirmed for now.”
- “Please book my regular physician. You know who I mean.”

Inspect **Decision log**. An interpreted request should show `gemini structured output`; greetings, explicit handoff, bounded appointment selection, and explicit doctor/date/time replies within an active request use `local routing policy` instead. For example, “Maya” can fill the doctor in a held Friday booking without another model request. Compound corrections still go to the model. Check the extracted doctor/date, whether ambiguous information triggered a question, and whether held requests left appointments unchanged. A schema-valid answer can still be wrong, so review these fields against the patient's words.

For a multi-turn check, ask to book George next Monday without a time, answer “4”, then “4 pm”. Confirm only after the exact visit is displayed. Next, change the date, cancel the visit, and try a held enquiry. Check that a simple “yes” never directly changes the schedule.

## Reproducible evaluation

From the project root:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluate --provider gemini --suite extended --limit 3 --output work/gemini-smoke-results.json
```

The command above runs only three cases to conserve daily quota. Omit `--limit 3` for the full suite of ten supplied examples plus ten additional paraphrase/entity cases. The fixed reference time is Saturday, 12 September 2026 at 11 am in Beirut. Each case starts a fresh session. The result records raw model extraction, intent matches, checked entities, interpreter calls versus local routing, prompt hash, latency in decision records, provider errors, and any unconfirmed mutation. It does not measure general language accuracy or replace the manual multi-turn checks. Use a new output file when comparing prompt revisions.

Live calls are spaced 12 seconds apart by default. Use `--delay 20`, for example, if the project's quota is lower. The adapter retries HTTP 502/503/504 once, after one second, within a configured 20-second request budget. It does not retry quota, authentication, timeout, or invalid-output failures automatically. An unresolved provider failure stops the evaluation and saves a partial result with a nonzero exit code.

For a complete conversation using the current Beirut clock:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluate_conversations --provider gemini --output work/conversation-results.json
```

This normally uses four model calls. It checks a held booking, doctor/time clarification, explicit resume, booking confirmation, rescheduling, cancellation, and mock handoff. It records actual HTTP attempts separately from model interpretation calls, and stops on the first failed step. For the offline workflow check, use `--provider demo --delay 0`.

## Quotas and errors

- A shared two-second request cooldown limits bursts. A Google 429 response starts a 60-second cooldown; the provider's actual minute/day limits still apply and may take longer to reset.
- The earlier 3.6 Flash run reported `GenerateRequestsPerDayPerProjectPerModel-FreeTier` with a limit of **20**. Its initial suite used 19 model requests and a browser booking used one, after which another request hit the daily quota. This is historical evidence for that project/model; Flash-Lite's current limits must be checked separately in AI Studio.
- [Daily quotas reset at midnight Pacific time](https://ai.google.dev/gemini-api/docs/rate-limits). A short provider retry hint does not override an exhausted daily quota. The app distinguishes a detected daily limit from a temporary rate limit.
- Provider failures invalidate the old proposal and suspend earlier validated details. **Retry message** resends the failed text with a new request ID and restores those details; it never restores an old confirmation token. A different new message discards the suspended context. No appointment changes on either path.
- Error copy distinguishes a slow request, connection failure, server failure, invalid response, quota, and setup problem. Decision records include safe categories and HTTP status, never raw provider bodies or credentials. The offline baseline is never substituted automatically.
- The free tier may use submitted content for product improvement. All tests and demos must use fictional messages; this setup is not for real patient data.
- Keep `GEMINI_API_KEY` in local `.env` or Render's server environment. On Render, `render.yaml` asks for it as a secret (`sync: false`). It is absent from the frontend build and committed files.

## Current evidence

The current **Gemini 3.5 Flash-Lite** configuration passed:

- **11/11 workflow intent checks**, **1/1 additional checked entity case**, and **0 unconfirmed mutations**: ten supplied examples plus “pencil me in”. Ten cases called Gemini and one handoff used local routing. See [gemini-flash-lite-assessment-results.json](gemini-flash-lite-assessment-results.json).
- The complete conversation: held Friday booking → Maya → time clarification → alternative selection → explicit resume → confirmed booking → confirmed reschedule → confirmed cancellation → mock callback. It used **four model calls and four HTTP requests**, preserved Karim's original visit, and required a separate confirmation for each change. See [gemini-flash-lite-conversation-results.json](gemini-flash-lite-conversation-results.json).

These live checks completed on 15 September 2026. The full 20-case extended suite has **not** been run on Flash-Lite; neither this small regression sample nor mocked tests establishes general language accuracy or guaranteed free-tier availability. Multiple-visit selection and provider recovery have additional deterministic and API tests, including simulated outages.

Historical evidence is retained separately. The initial 3.6 Flash evaluation matched 20/20 workflow intents and 8/9 entity cases; its overly cautious “pencil me in” hold led to a prompt clarification. See [gemini-results.json](gemini-results.json). A later 3.6 conversation failed with HTTP 503 even after the bounded retry; see [gemini-conversation-results.json](gemini-conversation-results.json). These are not Flash-Lite scores.

The expanded offline baseline scored 14/20 intent matches and 6/9 entity cases, with zero unconfirmed mutations. Its unfamiliar hold-phrase failure still produced a proposal. These are separate recorded results, not substitutes for the live model evidence.
