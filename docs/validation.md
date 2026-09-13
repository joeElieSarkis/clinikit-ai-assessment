# Validation record

Browser checks were completed locally on 12 September 2026; automated checks were extended for hosting on 13 September 2026. The Python suite uses a fixed reference time of **2026-09-12 11:00, Asia/Beirut**. The browser uses real local time.

## Automated checks

- 67 backend tests pass. This includes all ten supplied example messages, typed API input, state transitions, repeated requests, session ownership, expired/stale proposals, availability rechecks, conflicting appointment times, holds, unavailable model handling, and hosting checks.
- Ten supplied example intents match in offline demo evaluation. None changes an appointment without confirmation. Full observed responses and decision records are in `demo-results.json`.
- The frontend passes TypeScript checking and a Vite production build.
- The OpenAI adapter contract is tested with a mock client. **No live OpenAI requests were tested because no API key was configured.** The ten-example demo result must not be presented as an LLM benchmark.
- The testing dependencies emit two upstream deprecation warnings. No failing tests were suppressed.

## Hosting checks

- A simulated Render origin can create a session and complete an opening-hours conversation through the API. An unrelated origin is rejected.
- A configured custom origin works alongside local development; wildcard origins, paths, and embedded credentials are rejected.
- With the frontend built, the Python application serves the page, its JavaScript asset, and the health endpoint. Requests for `.env` and backend source files return 404.
- The repository includes a Docker build and a Render Free service configuration. Docker is not installed on the development laptop, so the container image has **not** been built or run locally. The frontend build and Python application have been tested separately.
- No public deployment, cold start, or hosted browser flow has been verified. The deployment guide lists these remaining checks.

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
