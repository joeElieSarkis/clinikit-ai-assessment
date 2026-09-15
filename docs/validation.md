# Part 1 · Validation

Local checks were completed between 12 and 15 September 2026. Unit tests use fixed Beirut reference times; the recorded multi-turn live evaluation uses the clock at execution time.

## Automated checks

**151 backend tests pass.** They cover the assessment examples, input validation, ambiguous appointment selection, doctor/date/time follow-ups, holds, stale or expired proposals, availability rechecks, conflicts, session isolation, request deduplication, provider recovery, and hosting behavior.

Provider tests use mock HTTP responses. They check schema validation, credential placement, blocked or incomplete responses, daily quotas, bounded retries, and unchanged confirmation requirements. The optional OpenAI adapter has no live evaluation.

The frontend passes TypeScript checking, the Vite production build, and formatting checks. A separate frontend test starts Vite and verifies the attendance report routes and Reception root. The Python test dependencies emit two upstream deprecation warnings.

## Recorded live results

| Check | Result | Evidence |
| --- | --- | --- |
| Gemini 3.5 Flash-Lite assessment cases | 11/11 workflow intents; 1/1 additional entity case; zero unconfirmed mutations | [Assessment trace](gemini-flash-lite-assessment-results.json) |
| Gemini 3.5 Flash-Lite conversation | All 12 steps passed; four model calls and four HTTP requests | [Conversation trace](gemini-flash-lite-conversation-results.json) |

The assessment run covers the supplied examples plus “pencil me in.” Ten cases used Gemini; one explicit handoff used local routing. The conversation covers a held booking, doctor/time clarification, alternative selection, explicit resume, booking confirmation, rescheduling, cancellation, and a mock callback. Each mutation required its own confirmation, and the original Karim visit was preserved.

These are small regression samples. The full 20-case extended suite has not been run on Flash-Lite, and the results do not establish general language accuracy or guaranteed API availability.

## Earlier results and failures

| Configuration | Observed result | Evidence |
| --- | --- | --- |
| Offline supplied examples | 10/10 intent matches; zero unconfirmed mutations | [Baseline trace](demo-results.json) |
| Offline extended cases | 14/20 intents; 6/9 entity cases; zero unconfirmed mutations | [Extended baseline trace](demo-extended-results.json) |
| Gemini 3.6 Flash extended cases | 20/20 intents; 8/9 entity cases; zero unconfirmed mutations | [Earlier model trace](gemini-results.json) |
| Gemini 3.6 Flash conversation | Stopped on HTTP 503 after a bounded retry | [Partial conversation trace](gemini-conversation-results.json) |

The extended offline baseline failed to recognize one unfamiliar hold phrase and prepared a proposal. Confirmation was still required, but the hold behavior was incorrect. The earlier Gemini run interpreted “pencil me in” too cautiously as a hold; that prompted a clarification in the extraction prompt. Later 3.6 Flash requests hit a daily quota and repeated capacity errors. The configured model was changed explicitly to Flash-Lite after its live conversation passed. Earlier failures remain recorded rather than being counted as current-model successes.

## Conversation regression checks

- Original weekdays match stored visits, including next Monday when today is Monday. References with trailing punctuation recover from failed searches.
- Multiple matches produce actual visit choices. Doctor names, common typos, times, and list positions select an original visit without overwriting the requested destination.
- “Book me Friday at 4 but don’t confirm anything yet” followed by “Maya,” “4 pm,” and an available slot retains the hold and leaves appointments unchanged.
- Greetings and acknowledgements preserve an outstanding clarification while invalidating stale confirmation tokens.
- Provider errors invalidate proposals. Explicit retry restores earlier details for the failed message; a different message does not inherit them.

These cases have deterministic and API coverage, including simulated outages. Browser checks against Flash-Lite also verified held booking follow-ups. Free-form selection among multiple visits has less live coverage than bounded local choices.

## Browser and hosting checks

Booking, rescheduling, and cancellation were checked through the browser with explicit confirmation. The decision inspector shows the actual structured fields and mock-tool results. Escape closes dialogs, reset asks before starting another session, and the mobile visit disclosure exposes the same appointment state. Desktop and 390 × 844 mobile layouts were inspected; this is not a formal accessibility audit.

A simulated hosted origin completed an hours request. Unrelated origins were rejected, and malformed origin configuration failed validation. The built FastAPI application served Reception, its assets, the health endpoint, and the attendance report; requests for `.env` and backend source returned 404.

A later development-only routing failure returned Reception at `/attendance/`. It is fixed and covered by the Vite regression test. Navigation to Part 2 and back was verified on port 5173. The Docker image and a public deployment have not been tested.

## Limits

The schedule, appointments, sessions, and handoffs are mocked. Free API quotas and capacity can interrupt conversations. The offline interpreter covers a bounded set of English expressions. There is no real patient identity, notification system, shared clinical calendar, database, holiday calendar, or medical advice. Production requirements are described in the [approach](approach.md).
