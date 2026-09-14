# Validation record

Offline browser checks were completed on 12 September 2026; hosting checks followed on 13 September, and live Gemini checks on 14–15 September. The Python suite uses fixed reference times of **2026-09-12 11:00** and **2026-09-14 14:00, Asia/Beirut**. The Monday clock reproduces a real conversation failure that the original Saturday fixture missed. Live conversation evaluation uses the current Beirut time; the retry browser fixture uses a fixed Monday clock.

## Automated checks

- 151 backend tests pass. This includes the supplied example messages, typed API input, state transitions, repeated requests, session ownership, expired/stale proposals, availability rechecks, conflicting appointment times, holds, provider recovery, hosting checks, the Gemini adapter contract, daily-quota handling, bounded server-error retry, and the conversation recovery checks below.
- Ten supplied example intents match in offline demo evaluation. None changes an appointment without confirmation. Full observed responses and decision records are in `demo-results.json`.
- The frontend passes TypeScript checking and a Vite production build.
- The OpenAI adapter contract is tested with a mock client. **No live OpenAI requests were tested because no API key was configured.** The ten-example demo result must not be presented as an LLM benchmark.
- The Gemini adapter is tested with an HTTP mock transport: schema and credential placement, limited history, missing keys, blocked/truncated/invalid output, provider errors, quota cooldowns, no automatic fallback, and unchanged confirmation requirements. Live model evidence is recorded separately below.
- The evaluation command supports Gemini and an extended set of ten additional paraphrase/entity cases. It records raw extraction and distinguishes local routing from model interpretation. `--limit` supports smaller runs within a daily quota.
- The extended **offline** evaluation was run and deliberately retains its failures: 14/20 intent matches, 6/9 entity-case matches, and zero unconfirmed mutations. One unfamiliar hold phrase yields a proposal, despite the intended hold. The evaluator correctly exits with code 1; this is a baseline limitation, not a failing unit test that was hidden. Full traces are in `demo-extended-results.json`. These extra cases have now been inspected during development, so they are a regression set rather than an independent held-out benchmark.
- The testing dependencies emit two upstream deprecation warnings. No failing tests were suppressed.
- The final local run also reported a permission warning while writing pytest's optional cache. All 151 tests completed successfully; the warning concerns the local cache directory, not an application failure.

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
- At the end of this initial run, reschedule/cancel completion and short follow-ups remained unverified live. They were subsequently completed with Flash-Lite in the 15 September checks below. The original results file remains unchanged.

## Conversation recovery — 14 September 2026

A regression occurred when the current day was Monday: the seeded visit was the following Monday, but the original-visit search resolved the bare weekday to today. A subsequent reference reply retained that failed date filter and repeated the same question.

Regression tests now verify:

- A bare Monday matches actual Monday visits. Explicit “this Monday” and calendar dates retain their stated meaning.
- Multiple visits produce a list of real doctors, dates, and times. Replies such as “Karim”, “Dr. Krim”, “the second one”, “10 am”, and “the morning one” select from that list without a copied reference or provider call.
- Multiple visits with the same doctor require another detail. Selecting the original visit’s time preserves a separately requested Wednesday destination and time.
- Reference replies with trailing punctuation recover from failed date/doctor/time searches. Unknown and cancelled references never select another visit implicitly.
- Greetings return “Hi!” without a provider request. Greetings and acknowledgements preserve an outstanding appointment-selection question. Every new message still invalidates old confirmation tokens.
- A hold stated during clarification survives the eventual selection. Selection alone never mutates an appointment; the completed reschedule still requires its exact confirmation token.
- The supplied examples run through the FastAPI endpoints under the Monday clock with expected actions and no unconfirmed changes. Missing-doctor/date/time follow-ups, “dr georg”, “tmrw”, ambiguous “4”, and the Friday booking hold are also exercised.

These regression checks use the offline interpreter or a mock provider, including simulated provider outages for bounded replies. Subsequent live evidence is recorded separately below; the original 3.6 extended result is unchanged. Free-form selection among multiple appointments still has less live coverage than the bounded local choices.

## Provider recovery and live Flash-Lite checks — 15 September 2026

- A held Friday booking followed by “Maya” failed against Gemini 3.6 Flash. A diagnostic generation returned HTTP 503 `UNAVAILABLE`, with a high-demand explanation. This was a provider capacity failure, distinct from the earlier daily-quota response.
- Explicit doctor, date, time, and visible slot replies now fill an active request locally. Regression tests cover “Maya”, “Dr. Maya”, quoted names, ambiguous “4”, “4 pm”, and the nearest available alternative while preserving the hold. Compound corrections still use the configured model.
- HTTP 502/503/504 can receive one extra attempt after one second, within a configured 20-second budget. Other errors do not automatically retry. A second 3.6 conversation still failed on explicit resume; the partial trace is retained in [gemini-conversation-results.json](gemini-conversation-results.json).
- **Gemini 3.5 Flash-Lite completed all 12 conversation steps**, including a held enquiry, doctor/time clarification, a 17:00 alternative, explicit resume, booking confirmation, rescheduling, cancellation, and mock callback. It used **four model calls and four HTTP requests**. Every appointment change required confirmation, and the original Karim visit remained unchanged. The full trace is in [gemini-flash-lite-conversation-results.json](gemini-flash-lite-conversation-results.json).
- Flash-Lite also matched **11/11 workflow intents** and **1/1 additional entity case** with **zero unconfirmed mutations**. This run covers ten supplied examples plus “pencil me in”, using ten model calls and one local handoff. See [gemini-flash-lite-assessment-results.json](gemini-flash-lite-assessment-results.json). The remaining nine extended cases were not rerun on the new model.
- The default, example configuration, local model setting, and Render configuration now select `gemini-3.5-flash-lite` explicitly. Provider failure never switches to another model or the offline baseline.
- A browser test with an explicitly labelled injected failure verified **Retry message**. A George/Monday/16:00 proposal was invalidated when “Actually, make it Wednesday” failed with a simulated 503. Clicking retry produced a new George/Wednesday/16:00 proposal, preserving doctor/time without changing any appointment. Tests also verify that a different new message does not inherit the suspended draft and that the old confirmation token stays invalid.
- A separate browser check against the real Flash-Lite backend completed “Book me Friday at 4 but don’t confirm anything yet” → “Maya” → “4 pm” → 17:00 slot selection. The initial request used Gemini; bounded follow-ups stayed local. The UI requested am/pm, offered the nearby available times, and retained the hold after a slot click. No confirmation control or new appointment appeared.
- Errors expose safe diagnostic categories and HTTP status in the decision log; provider bodies and API keys are never displayed. Quota failures, timeouts, connection errors, invalid responses, and setup problems have distinct messages.

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

The rule baseline handles a bounded set of English expressions. Live model evidence covers a small regression sample, not a held-out language benchmark; free API capacity can still fail or reach its quota. The schedule, appointments, and handoffs are mocked; no patient identity, real notification, shared clinical calendar, holiday calendar, medical advice, or database is implemented. Safety-critical production guarantees require a real persistence and authorization architecture and broader testing.
