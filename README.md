# Reception / CliniKit

A clinic appointment assistant for **Exercise 1** of the CliniKit AI trainee assessment. React + TypeScript on the patient side; Python + FastAPI behind the conversation.

The central design choice: **understanding a request does not authorize an appointment change**. The assistant extracts structured information, validates it against a mock schedule, and prepares a proposal. Only an explicit confirmation of that exact proposal can create, move, or cancel a visit.

All patients, doctors, clinic hours, appointments, and handoffs are fictional. This is a local demonstration. Exercise 2 is not included.

## Run locally

Requirements: **Python 3.11+**, **Node.js 22.12+** (tested with Python 3.12 and Node 22.18), and npm. No API key is needed for demo mode.

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

## Enable the language model

Copy `.env.example` to `.env` in the repository root. Set:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-own-key
OPENAI_MODEL=gpt-4.1-mini
```

Restart the backend. The interface should say **LLM mode**. `.env` is ignored by Git; keys are never sent to the frontend. Use fictional messages: in this mode, the current message and up to eight recent conversation messages are sent to OpenAI. `store=False` is set on requests; this is not a claim of zero provider retention or healthcare compliance. API calls use the configured account and may incur charges.

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

- **61 passing backend tests**: assessment examples, multi-turn flows, confirmation requirements, repeat requests, session isolation, schedule conflicts, invalid dates/times, unknown doctors, holds, and provider failures.
- **10/10 supplied example intents matched** in demo mode; **0 unconfirmed appointment mutations**. Full responses and traces are in [demo-results.json](docs/demo-results.json). These hand-picked examples are a smoke evaluation, not a general accuracy estimate.
- Browser checks cover booking, rescheduling, cancellation, dialogs, and responsive layouts. Details and limitations are in [validation.md](docs/validation.md).
- Two upstream deprecation warnings occur in the Starlette testing dependencies; the tests pass.

To evaluate actual model output after configuring a key, explicitly run:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluate --provider openai --output docs/openai-results.json
```

## Project guide

| File | Responsibility |
| --- | --- |
| `backend/app/models.py` | Typed input, extraction, proposals, and responses |
| `backend/app/interpreter.py` | Interchangeable demo and OpenAI extraction |
| `backend/app/prompts/extract.md` | Intent rules, entity rules, trust boundary, examples |
| `backend/app/engine.py` | Conversation state, policy checks, proposal and confirmation |
| `backend/app/clinic.py` | Mock facts, schedule, and 30-minute conflict checks |
| `backend/app/dates.py` | Date normalization and time disambiguation |
| `backend/app/main.py` | API, validation, session isolation, idempotency |
| `frontend/src/App.tsx` | Conversation, visit ledger, and decision inspector |
| `frontend/src/styles.css` | Custom responsive interface, local fonts, reduced motion |

See [approach.md](docs/approach.md) for decisions, assumptions, and production improvements. AI assistance was used in implementation and review; the architecture, prompt, tests, and limitations are documented for discussion. No claim is made that the system understands every possible patient message.
