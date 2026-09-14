# Gemini setup and evaluation

## Create a free-tier key

1. Open [Google AI Studio API keys](https://aistudio.google.com/apikey) and sign in.
2. Create an API key for a Google project. Check that the project's billing tier is **Free**. Do not link a billing account, prepay, or enable a paid tier for this assessment.
3. In the repository root, copy `.env.example` to `.env` if `.env` does not already exist. Keep an existing file and edit its values instead of overwriting a saved key.
4. Set `AI_PROVIDER=gemini`, paste the key after `GEMINI_API_KEY=`, and keep `GEMINI_MODEL=gemini-3.6-flash`. Save the file. Do not paste the key into chat, screenshots, the frontend, or a GitHub file.
5. Stop the local launcher with Ctrl+C, then restart with `.\.venv\Scripts\python.exe run.py`. Python does not automatically reload changed code or `.env` values in this launcher.

The **Gemini** badge identifies the configured provider. Open `/api/health` on the Python server to check `mode: gemini` and the model name. Neither the badge nor the health endpoint calls Google; a successful message is needed to verify the key and actual model access.

Google's [pricing](https://ai.google.dev/gemini-api/docs/pricing) lists free input and output for Gemini 3.6 Flash. The [billing guide](https://ai.google.dev/gemini-api/docs/billing) explains that the key inherits its project's billing tier. The app cannot determine that tier from the key, so a free-model label in code alone is not a spending guarantee. These terms were checked on 14 September 2026. A real generation request rejected Gemini 2.5 Flash for this new account and recommended 3.6 Flash, which worked.

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

Inspect **Decision log**. An interpreted request should show `gemini structured output`; explicit handoff and a few guards use `local routing policy` instead. Check the extracted doctor/date, whether ambiguous information triggered a question, and whether held requests left appointments unchanged. A schema-valid answer can still be wrong, so review these fields against the patient's words.

For a multi-turn check, ask to book George next Monday without a time, answer “4”, then “4 pm”. Confirm only after the exact visit is displayed. Next, change the date, cancel the visit, and try a held enquiry. Check that a simple “yes” never directly changes the schedule.

## Reproducible evaluation

From the project root:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluate --provider gemini --suite extended --limit 3 --output work/gemini-smoke-results.json
```

The command above runs only three cases to conserve daily quota. Omit `--limit 3` for the full suite of ten supplied examples plus ten additional paraphrase/entity cases. The fixed reference time is Saturday, 12 September 2026 at 11 am in Beirut. Each case starts a fresh session. The result records raw model extraction, intent matches, checked entities, interpreter calls versus local routing, prompt hash, latency in decision records, provider errors, and any unconfirmed mutation. It does not measure general language accuracy or replace the manual multi-turn checks. Use a new output file when comparing prompt revisions.

Live calls are spaced 12 seconds apart by default. Use `--delay 20`, for example, if the project's quota is lower. No paid fallback or automatic provider retry is configured. A provider failure stops the evaluation and saves a partial result with a nonzero exit code.

## Quotas and errors

- A shared two-second request cooldown limits bursts. A Google 429 response starts a 60-second cooldown; the provider's actual minute/day limits still apply and may take longer to reset.
- This account reported `GenerateRequestsPerDayPerProjectPerModel-FreeTier` with a limit of **20** for Gemini 3.6 Flash. The initial full suite used 19 model requests and the corrected browser booking used one. The subsequent reschedule check was blocked by the daily quota. This limit is specific to the tested project/model, not a promise about every account.
- [Daily quotas reset at midnight Pacific time](https://ai.google.dev/gemini-api/docs/rate-limits). For the observed 14 September 2026 limit, that corresponds to 15 September at 10 am in Beirut. A short provider retry hint does not override an exhausted daily quota. The app explains a detected daily limit separately from a temporary rate limit.
- Timeouts, rejected requests, blocked responses, truncated output, or invalid JSON clear the current draft/proposal and return an unavailable message. The offline baseline is never substituted automatically.
- The free tier may use submitted content for product improvement. All tests and demos must use fictional messages; this setup is not for real patient data.
- Keep `GEMINI_API_KEY` in local `.env` or Render's server environment. On Render, `render.yaml` asks for it as a secret (`sync: false`). It is absent from the frontend build and committed files.

## Current evidence

Mock-transport tests verify the request schema, credential placement, refusal/error handling, quotas, and confirmation safeguards. The initial live Gemini 3.6 Flash evaluation matched 20/20 workflow intents and 8/9 checked entity cases, with no unconfirmed mutations. One of the 20 cases used local handoff routing; 19 called Gemini. The failed entity case conservatively treated “pencil me in” as a hold. The prompt was clarified, and a subsequent live browser check correctly created a review proposal and changed the appointment only after confirmation. See `gemini-results.json` and `validation.md`.

The complete suite was not rerun after the prompt clarification. Live rescheduling/cancellation completion and short multi-turn follow-ups remain to be checked after the daily quota resets. Those flows pass offline/mocked backend tests and were exercised earlier with the offline browser, but that is not equivalent to live model validation.

The expanded offline baseline scored 14/20 intent matches and 6/9 entity cases, with zero unconfirmed mutations. Its unfamiliar hold-phrase failure still produced a proposal. These are separate recorded results, not substitutes for the live model evidence.
