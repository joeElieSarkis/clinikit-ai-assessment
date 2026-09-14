# CliniKit reception

A clinic appointment assistant built with React, TypeScript, FastAPI, and Gemini. It handles booking, rescheduling, cancellation, opening hours, availability, and requests for a receptionist.

This repository covers **Exercise 1** of the CliniKit AI trainee assessment. All clinic data and appointments are fictional. **Exercise 2 is not included.**

## Run locally

Requirements: Python 3.11+, Node.js 22.12+, and npm. Tested with Python 3.12 and Node.js 22.18.

Copy `.env.example` to `.env` on first setup. For live interpretation, configure a Google AI Studio key from a project on the Free tier with billing disabled:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=your-own-key
GEMINI_MODEL=gemini-3.5-flash-lite
```

For a quick run without an API key, set `AI_PROVIDER=demo` instead. The interface labels this **Offline demo**; it uses a limited rule interpreter. See [Gemini setup](docs/gemini.md) for key configuration, quotas, and troubleshooting.

From the repository root, in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
npm --prefix frontend ci
.\.venv\Scripts\python.exe run.py
```

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
npm --prefix frontend ci
.venv/bin/python run.py
```

Open [the interface](http://127.0.0.1:5173/) or [the API documentation](http://127.0.0.1:8000/docs). Ctrl+C stops both services. Restart after changing Python code or `.env`; frontend changes reload automatically. Ports 8000 and 5173 must be available.

VS Code tasks are included under **Terminal → Run Task → Run reception / Test reception**.

## Approach

Gemini extracts intent, doctor, date, time, appointment reference, and ambiguity/hold flags into a validated schema. Python resolves dates in Beirut time, checks the mock schedule, asks for missing details, and constructs responses from the results. Short doctor/date/time replies fill the active request locally; compound corrections use the model.

Booking, rescheduling, and cancellation require confirmation of an exact proposal. A chat message cannot change an appointment. Holds persist through clarification, multiple matching visits trigger a selection question, and failed requests can be retried without losing earlier validated details. Every new message invalidates the previous confirmation token.

The directory and schedule are structured data queried directly. There is no document corpus or RAG pipeline. [Approach and technical decisions](docs/approach.md) covers prompting, state handling, assumptions, and production improvements.

## Try it

- **Book:** “Book Dr. George Monday at 4 pm.” Review the date and time, then select **Confirm appointment**.
- **Reschedule:** “Move my appointment from Monday to Wednesday.” If several visits match, identify one by doctor, time, or list position.
- **Cancel:** “Cancel my appointment with Dr. Karim.” The visit stays active until cancellation is confirmed.
- **Hold:** “Book me Friday at 4 but don’t confirm anything yet.” Reply “Maya”, then “4 pm”. Selecting an available alternative keeps the request on hold until an explicit request to resume.
- **Clinic questions:** “What time does the clinic close?” or “Do you have anything available after 5 tomorrow?”
- **Handoff:** “Can somebody from the clinic call me?” This records a mock request; it does not arrange a real callback.

**View decision** shows extracted fields, policy checks, the selected action, and mock-tool results. Dates use the current Beirut clock, so “tomorrow” on Saturday resolves to Sunday, when the mock clinic is closed. The reset control starts a fresh sample patient session.

## Validation

| Check | Result | Evidence |
| --- | --- | --- |
| Backend tests | 151 passed | [Validation record](docs/validation.md) |
| Live Gemini 3.5 Flash-Lite examples | 11/11 workflow intents, 1/1 additional entity case, no unconfirmed mutations | [Recorded results](docs/gemini-flash-lite-assessment-results.json) |
| Live conversation | Held booking, clarification, confirmation, rescheduling, cancellation, and handoff passed; four model calls | [Conversation trace](docs/gemini-flash-lite-conversation-results.json) |
| Frontend | TypeScript, production build, formatting, and desktop/mobile browser checks passed | [Validation record](docs/validation.md) |

The live example run covers the nine example messages, the additional ambiguous case in the brief, and one “pencil me in” paraphrase. Ten cases used Gemini and one handoff used local routing. The remaining nine extended cases have not been evaluated on Flash-Lite. These are small regression checks, not a general language accuracy estimate.

The offline baseline matched [10/10 supplied cases](docs/demo-results.json), but only [14/20 intents and 6/9 entity cases](docs/demo-extended-results.json) in the extended set. Its unfamiliar hold-phrase failure produced a proposal but no appointment change. Earlier 3.6 Flash results and provider failures remain in the [validation record](docs/validation.md).

Run local checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.evaluate --provider demo --output work/demo-results.json
npm --prefix frontend run build
npm --prefix frontend run format:check
```

For a live conversation check after configuring Gemini:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluate_conversations --provider gemini --output work/conversation-results.json
```

This normally uses four model calls, spaced 12 seconds apart. The adapter permits one extra attempt for HTTP 502/503/504; quota errors are not automatically retried. See [evaluation instructions](docs/gemini.md) for the extended suite and saved failure records.

## Deployment

The included Dockerfile and Render configuration serve the built React interface and Python API as one Free web service. GitHub Pages alone cannot run the Python API. [Deployment instructions](docs/deployment.md) cover server secrets, service configuration, and checks for the public URL.

The production frontend build and Python hosting checks passed locally. A Docker image and public deployment have not been verified. A hosted demo is optional for the assessment.

## Limits and configuration

- Sessions, appointments, and handoffs live in process memory and reset when the server restarts. There is no real patient login, calendar integration, notification delivery, or medical advice.
- Only fictional messages should be used. In Gemini mode, the current message, active draft, and up to eight recent messages are sent to Google. The API key stays on the server; `.env` is excluded from Git and the Docker image.
- Free API quotas and capacity still apply. Google's [pricing](https://ai.google.dev/gemini-api/docs/pricing), [billing](https://ai.google.dev/gemini-api/docs/billing), and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) describe the account restrictions. Provider errors never silently switch the model or enable the offline baseline.
- An optional OpenAI adapter uses the same extraction contract. Set `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL` to use it. It may incur API charges and has only been tested with a mock client.

The main implementation is in `backend/app/engine.py`, the extraction prompt in `backend/app/prompts/extract.md`, and the interface in `frontend/src/App.tsx` and `frontend/src/styles.css`.
