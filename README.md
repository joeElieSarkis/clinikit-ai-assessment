# Reception / CliniKit

A clinic appointment assistant for **Exercise 1** of the CliniKit AI trainee assessment. React + TypeScript on the patient side; Python + FastAPI and Gemini for intent and entity extraction.

The central design choice: **understanding a request does not authorize an appointment change**. The assistant extracts structured information, validates it against a mock schedule, and prepares a proposal. Only an explicit confirmation of that exact proposal can create, move, or cancel a visit.

All patients, doctors, clinic hours, appointments, and handoffs are fictional. This is an assessment demonstration. Exercise 2 is not included.

## Connect Gemini

The live configuration uses **Gemini 2.5 Flash**. Create a key in [Google AI Studio](https://aistudio.google.com/apikey) using a project on the **Free tier with billing disabled**. Copy `.env.example` to `.env` once and fill in:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=your-own-key
GEMINI_MODEL=gemini-2.5-flash
```

Follow [gemini.md](docs/gemini.md) for setup and live checks. The backend sends the current fictional message, active draft, and up to eight recent messages to Google. The API key remains on the server and `.env` is excluded from Git and the Docker image. Google lists free input/output usage for this model, with account quotas and free-tier data-use terms; use only fictional patient information. See [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [billing](https://ai.google.dev/gemini-api/docs/billing).

Gemini interprets intent and entities. Python validates the schedule, controls changes, and constructs replies from verified results. A missing key is a setup error; a provider failure never silently switches to rules. **A live Gemini evaluation is still pending a real key.**

For an explicit offline baseline, set `AI_PROVIDER=demo` in `.env`. It requires no API key, shows **Offline demo**, and has limited English rule matching. Its results are not an LLM benchmark.

## Run locally

Requirements: **Python 3.11+**, **Node.js 22.12+** (tested with Python 3.12 and Node 22.18), and npm. Configure `.env` above before starting the server.

From the repository root, on Windows PowerShell:

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

Open **http://127.0.0.1:5173**. Interactive API documentation is at **http://127.0.0.1:8000/docs**. Stop both services with Ctrl+C. Restart the launcher after changing Python code or `.env`; Vite refreshes frontend changes automatically. Ports 8000 and 5173 must be free.

VS Code includes **Run reception** and **Test reception** tasks under *Terminal → Run Task*. Open the repository folder, not just the frontend.

For a built interface served by Python alone:

```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000. Build before starting the server.

## Share a free hosted demo

The repository includes a Docker build and a Render configuration for **one Free web service** serving both the React interface and Python API. It sets `AI_PROVIDER=gemini` and prompts for `GEMINI_API_KEY` as a server secret. Use a Free-tier Google project; selecting a model in code does not control account billing. No paid database or other service is configured.

Follow [deployment.md](docs/deployment.md) after pushing your repository yourself. GitHub Pages can host static frontend files, but cannot run this project's Python API on its own. Render's free service sleeps after inactivity, so the first visit can take about a minute to load; sample sessions reset when the server restarts.

**Deployment status:** prepared and checked locally; no public deployment has been created or verified.

## Optional alternative provider

The existing OpenAI adapter remains available for comparison. It is not part of the free Gemini setup. To use it, set these values in the root `.env`:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-own-key
OPENAI_MODEL=gpt-4.1-mini
```

Restart the backend. The interface should say **OpenAI**. `.env` is ignored by Git; keys are never sent to the frontend. Use fictional messages: in this mode, the current message and up to eight recent conversation messages are sent to OpenAI. `store=False` is set on requests; this is not a claim of zero provider retention or healthcare compliance. API calls use the configured account and may incur charges.

The adapter uses the Responses API with Pydantic Structured Outputs. The model is configurable; choose a model that supports those features. A refusal, timeout, or invalid output clears the proposal and returns a safe error. It never silently switches to demo mode.

**Live model quality has not yet been evaluated with a real key.** Unit tests mock the provider to verify the integration contract and failure path. Demo mode is a bounded English rule interpreter, not an LLM or a claim of broad language understanding.

## Try it

1. **Booking:** “Book Dr. George Monday at 4 pm.” Review the proposed date and press **Confirm appointment**. A bare “4” asks for am/pm.
2. **Rescheduling:** “Move my appointment from Monday to Wednesday.” Choose an available time, review the old and new visit, and confirm. The original reference is preserved.
3. **Cancellation:** “Cancel my appointment with Dr. Karim.” The visit remains active until **Confirm cancellation** is selected.
4. **Hold:** “I might want to see Dr. George Monday at 4 pm, but don’t book anything yet.” No proposal or appointment change is created. A hold persists across short follow-ups until an explicit request to resume.
5. **Facts and handoff:** Ask opening hours or request a person. The latter records a mock handoff and explicitly says no real person was contacted.

Use **Decision log** to inspect extracted fields, policy checks, selected actions, and actual mock tool results. The log describes execution; it does not expose private model reasoning. On mobile, expand **Your visits & clinic details** to see appointments. The reset control starts a fresh sample patient.

Relative dates resolve against the current Beirut time. “Tomorrow” on Saturday is Sunday, when this mock clinic is closed. The automated examples freeze the clock so results are repeatable.

## Validation and results

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.evaluate --provider demo --output docs/demo-results.json
npm --prefix frontend run build
npm --prefix frontend run format:check
```

- **86 passing backend tests**: assessment examples, multi-turn flows, confirmation requirements, repeat requests, session isolation, schedule conflicts, invalid dates/times, unknown doctors, holds, provider failures, hosted origins, serving the built interface, and the Gemini integration contract.
- **10/10 supplied example intents matched** in demo mode; **0 unconfirmed appointment mutations**. Full responses and traces are in [demo-results.json](docs/demo-results.json). These hand-picked examples are a smoke evaluation, not a general accuracy estimate.
- On the **extended offline evaluation**, only **14/20 intents** and **6/9 checked entity cases** match; see [demo-extended-results.json](docs/demo-extended-results.json). In particular, a less familiar hold phrase still produces a proposal in the baseline, although it does not change an appointment. These failures are preserved rather than reported as passing checks, and show why live Gemini evaluation is required.
- Browser checks cover booking, rescheduling, cancellation, dialogs, and responsive layouts. Details and limitations are in [validation.md](docs/validation.md).
- Two upstream deprecation warnings occur in the Starlette testing dependencies; the tests pass.

To evaluate actual model output after configuring a key, explicitly run:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluate --provider gemini --suite extended --output docs/gemini-results.json
```

The extended evaluation adds ten paraphrase/entity cases to the ten supplied examples. It records raw extraction, entity checks, local policy routing, and failures separately. Live cases are spaced 12 seconds apart by default; adjust `--delay` to the project's quota. An unavailable provider stops the run and saves the observed failure rather than retrying or substituting demo results.

## Project guide

| File | Responsibility |
| --- | --- |
| `backend/app/models.py` | Typed input, extraction, proposals, and responses |
| `backend/app/interpreter.py` | Interchangeable demo and OpenAI extraction |
| `backend/app/gemini.py` | Gemini REST adapter, structured validation, and quota handling |
| `backend/app/providers.py` | Explicit provider selection for the server and evaluation |
| `backend/app/prompts/extract.md` | Intent rules, entity rules, trust boundary, examples |
| `backend/app/engine.py` | Conversation state, policy checks, proposal and confirmation |
| `backend/app/clinic.py` | Mock facts, schedule, and 30-minute conflict checks |
| `backend/app/dates.py` | Date normalization and time disambiguation |
| `backend/app/main.py` | API, validation, session isolation, idempotency |
| `frontend/src/App.tsx` | Conversation, visit ledger, and decision inspector |
| `frontend/src/styles.css` | Custom responsive interface, local fonts, reduced motion |

See [approach.md](docs/approach.md) for decisions, assumptions, and production improvements. AI assistance was used in implementation and review; the architecture, prompt, tests, and limitations are documented for discussion. No claim is made that the system understands every possible patient message.
