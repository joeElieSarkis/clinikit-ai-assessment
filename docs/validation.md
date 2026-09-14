# Validation record

Offline browser checks were completed on 12 September 2026; hosting checks followed on 13 September, and live Gemini checks on 14 September. The Python suite uses a fixed reference time of **2026-09-12 11:00, Asia/Beirut**. The browser uses real local time.

## Automated checks

- 87 backend tests pass. This includes all ten supplied example messages, typed API input, state transitions, repeated requests, session ownership, expired/stale proposals, availability rechecks, conflicting appointment times, holds, unavailable model handling, hosting checks, and the Gemini adapter contract, including distinct daily-quota handling.
- Ten supplied example intents match in offline demo evaluation. None changes an appointment without confirmation. Full observed responses and decision records are in `demo-results.json`.
- The frontend passes TypeScript checking and a Vite production build.
- The OpenAI adapter contract is tested with a mock client. **No live OpenAI requests were tested because no API key was configured.** The ten-example demo result must not be presented as an LLM benchmark.
- The Gemini adapter is tested with an HTTP mock transport: schema and credential placement, limited history, missing keys, blocked/truncated/invalid output, provider errors, quota cooldowns, no automatic fallback, and unchanged confirmation requirements. Live model evidence is recorded separately below.
- The evaluation command supports Gemini and an extended set of ten additional paraphrase/entity cases. It records raw extraction and distinguishes local routing from model interpretation. `--limit` supports smaller runs within a daily quota.
- The extended **offline** evaluation was run and deliberately retains its failures: 14/20 intent matches, 6/9 entity-case matches, and zero unconfirmed mutations. One unfamiliar hold phrase yields a proposal, despite the intended hold. The evaluator correctly exits with code 1; this is a baseline limitation, not a failing unit test that was hidden. Full traces are in `demo-extended-results.json`. These extra cases have now been inspected during development, so they are a regression set rather than an independent held-out benchmark.
- The testing dependencies emit two upstream deprecation warnings. No failing tests were suppressed.

## Hosting checks

- A simulated Render origin can create a session and complete an opening-hours conversation through the API. An unrelated origin is rejected.
- A configured custom origin works alongside local development; wildcard origins, paths, and embedded credentials are rejected.
- With the frontend built, the Python application serves the page, its JavaScript asset, and the health endpoint. Requests for `.env` and backend source files return 404.
- The repository includes a Docker build and a Render Free service configuration. Docker is not installed on the development laptop, so the container image has **not** been built or run locally. The frontend build and Python application have been tested separately.
- No public deployment, cold start, or hosted browser flow has been verified. The deployment guide lists these remaining checks.

## Live Gemini checks — 14 September 2026

- Google's model listing accepted the key. A generation request for 2.5 Flash returned HTTP 404 with a message saying that model was unavailable to new users and recommending 3.6 Flash. The default, local configuration, and Render configuration were migrated to `gemini-3.6-flash`.
- The initial live extended evaluation completed: **20/20 workflow intents**, **8/9 checked entity cases**, **0 unconfirmed mutations**, and no interpretation failures. Nineteen cases called Gemini; one explicit handoff used local routing. `gemini-results.json` contains the actual raw extractions and traces. The evaluator exited with code 1 because one entity case failed.
- The failed case was “Could you pencil me in with Doctor Maya on Tuesday at noon?” Gemini set `hold=true`, preventing a proposal. The prompt was clarified to distinguish polite booking requests from actual requests to wait. The recorded full-suite result remains the initial run, before that prompt change.
- In the browser after the prompt change, that request produced `hold=false`, doctor Maya, date Tuesday, and time noon. The UI displayed **15 September 2026 at 12 pm** and left the existing appointment unchanged until confirmation. Pressing **Confirm appointment** added sample visit `CK-B2E7ABCD` while preserving Karim's visit. The decision record showed `gemini structured output` for interpretation and `confirmation policy` for the mutation.
- The next browser request, “Could we move that visit with Maya to Wednesday at 3 pm?”, hit Google's daily quota. Both existing appointments remained unchanged and no proposal was left behind. A diagnostic response identified the quota as `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit **20**. No further generation tests were attempted after identifying that daily limit.
- **Still pending:** live reschedule/cancel completion, short follow-up language tests, and a complete evaluation of the revised prompt. These await quota reset. A passing offline or mocked test is not presented as proof that the live model completes those flows.

## Browser checks

Checked through the local browser against the running React and Python services:

- Booking shows the exact doctor, date, and time before confirmation; confirmation adds one visit.
- Rescheduling shows the original and new visit, updates the existing appointment, and retains its reference.
- Cancellation requires its explicit confirmation and marks the selected visit cancelled.
- Decision log displays actual structured fields, checks, and mock-tool results.
- Escape closes the modal, and reset asks before switching sample sessions.
- At 390 × 844, the composer is within the first viewport and the document has no horizontal overflow. The mobile visit disclosure exposes the same live appointment state.
- A held booking enquiry shows available times while the proposal remains null and the existing appointment remains unchanged.
- Optional WebMCP `read_reception_state` returns the visible sample state, rejects unexpected arguments, and has no mutation capability.

Responsive checks cover 1440 × 900 desktop and 390 × 844 mobile layouts. These checks are not a formal accessibility audit or proof of universal browser compatibility.

## Known limits

The rule baseline handles a bounded set of English expressions. The LLM still requires a real evaluation. The schedule, appointments, and handoffs are mocked; no patient identity, real notification, shared clinical calendar, holiday calendar, medical advice, or database is implemented. Safety-critical production guarantees require a real persistence and authorization architecture and broader testing.
