# Validation record

Validated locally on 12 September 2026. The Python suite uses a fixed reference time of **2026-09-12 11:00, Asia/Beirut**. The browser uses real local time.

## Automated checks

- 61 backend tests pass. This includes all ten supplied example messages, typed API input, state transitions, repeated requests, session ownership, expired/stale proposals, availability rechecks, conflicting appointment times, holds, and unavailable model handling.
- Ten supplied example intents match in offline demo evaluation. None changes an appointment without confirmation. Full observed responses and decision records are in `demo-results.json`.
- The frontend passes TypeScript checking and a Vite production build.
- The OpenAI adapter contract is tested with a mock client. **No live OpenAI requests were tested because no API key was configured.** The ten-example demo result must not be presented as an LLM benchmark.
- The testing dependencies emit two upstream deprecation warnings. No failing tests were suppressed.

## Browser checks

Checked through the local browser against the running React and Python services:

- Booking shows the exact doctor, date, and time before confirmation; confirmation adds one visit.
- Rescheduling shows the original and new visit, updates the existing appointment, and retains its reference.
- Cancellation requires its explicit confirmation and marks the selected visit cancelled.
- Decision log displays actual structured fields, checks, and mock-tool results.
- Escape closes the modal, and reset asks before switching sample sessions.
- Optional WebMCP `read_reception_state` returns the visible sample state, rejects unexpected arguments, and has no mutation capability.

Responsive checks cover desktop and mobile layouts. These checks are not a formal accessibility audit or proof of universal browser compatibility.

## Known limits

The rule baseline handles a bounded set of English expressions. The LLM still requires a real evaluation. The schedule, appointments, and handoffs are mocked; no patient identity, real notification, shared clinical calendar, holiday calendar, medical advice, or database is implemented. Safety-critical production guarantees require a real persistence and authorization architecture and broader testing.
