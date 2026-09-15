# CliniKit AI assessment

Two exercises in one repository: a conversational appointment assistant and a machine-learning study of appointment attendance.

| Exercise | Implementation | Review |
| --- | --- | --- |
| **1 · Conversational AI** | Python/FastAPI in `backend/`, React/TypeScript in `frontend/src/` | [Approach](docs/approach.md), [validation](docs/validation.md) |
| **2 · Machine learning** | Training, inference, tests, and results in `ml/` | [Run instructions](ml/README.md), [model card](ml/model-card.md) |

The website opens on Reception. Select **Attendance study** in the sidebar, or **Part 2** on mobile, to open the ML report. Its threshold explorer uses validation results; the recorded test result stays fixed.

## Setup

Requirements: **Python 3.12**, **Node.js 22.12+**, and npm. From the repository root in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt -r ml/requirements.txt
npm --prefix frontend ci
```

On macOS/Linux, create the environment with `python3 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` in the commands. Part 1 alone needs only `requirements-lock.txt`; ML libraries are not installed in the web deployment.

Copy `.env.example` to `.env` on first setup. For live conversational interpretation:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=your-own-key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Use a Google AI Studio project on the Free tier with billing disabled. See [Gemini setup](docs/gemini.md) for configuration and quotas. Alternatively, set `AI_PROVIDER=demo` for the limited offline rule interpreter. The UI labels that mode explicitly. **Part 2 needs no API key.**

## Exercise 1 · Reception

```powershell
.\.venv\Scripts\python.exe run.py
```

Open [Reception](http://127.0.0.1:5173/) or the [API documentation](http://127.0.0.1:8000/docs). Ctrl+C stops both services. Restart after changing Python code or `.env`; frontend changes reload automatically.

Gemini extracts intent and structured fields. Python resolves dates in Beirut time, checks the mock schedule, and constructs responses from the results. Missing or ambiguous details trigger clarification. Short doctor/date/time replies fill an active request locally. Booking, rescheduling, and cancellation require explicit confirmation of an exact proposal; chat messages cannot change appointments.

Try:

- “Can I see Dr. George tomorrow afternoon?”
- “Move my appointment from Monday to Wednesday.”
- “Cancel my appointment with Dr. Karim.”
- “Book me Friday at 4 but don’t confirm anything yet.” Then “Maya” and “4 pm”.
- “What time does the clinic close?” or “Can somebody from the clinic call me?”

**View decision** shows structured fields, policy checks, actions, and mock-tool results. Part 1's clinic details and appointments are fictional; no real callback is arranged. Dates use the current Beirut clock, and the sample clinic is closed on Sunday.

## Exercise 2 · Appointment attendance

The report is available at [Attendance study](http://127.0.0.1:5173/attendance/) while the app runs. It can also be opened directly from `frontend/public/attendance/index.html` in a browser without a server or internet connection.

To reproduce training, place the employer-supplied `CliniKit_NoShow_Dataset.csv` in `ml/data/`, or pass its existing path:

```powershell
.\.venv\Scripts\python.exe -m ml.train --data "ml/data/CliniKit_NoShow_Dataset.csv"
.\.venv\Scripts\python.exe -m ml.predict --input ml/examples/appointments.csv --output work/predictions.csv
```

The raw dataset and trained binary are excluded from Git. The supplied dataset is required to reproduce training. Recorded aggregate results, figures, and synthetic example predictions are included for review.

The pipeline validates the data, keeps identical predictor profiles together, and compares a prior baseline with logistic regression, random forest, and gradient boosting. It selects using training cross-validation, calibrates on training predictions, chooses a threshold on validation data, and evaluates the frozen choice on a separate test set. See the [protocol](ml/protocol.md) and [model card](ml/model-card.md).

## Results

| Check | Recorded result |
| --- | --- |
| Part 1 backend tests | 151 passed |
| Live conversational examples | 11/11 workflow intents and 1/1 additional entity case; no unconfirmed mutations |
| Live multi-turn conversation | Held booking, clarification, confirmation, rescheduling, cancellation, and mock handoff passed |
| Part 2 tests | 11 passed |
| Selected attendance model | Logistic regression, calibrated using training-only predictions |
| Held-out attendance ranking | Average precision **0.340** versus baseline **0.160**; ROC AUC **0.660** |
| Attendance operating point | **75.0% recall**, **19.7% precision**, **366/600 appointments flagged** |

The attendance model finds 72 of 96 no-shows but also flags 294 attendees. That workload is high; the result demonstrates predictive signal, not readiness for clinical deployment. The report includes uncertainty, feature importance, subgroup checks, and a validation threshold explorer.

Conversational evidence and its limits are in [Part 1 validation](docs/validation.md). ML checks are in [Part 2 validation](ml/validation.md); metrics, dependency versions, and source/split hashes are in [results.json](ml/results/results.json). Earlier provider failures and weaker offline-baseline results are retained.

## Checks and project tools

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run build
npm --prefix frontend run format:check
```

VS Code tasks include **Run reception**, **Test reception**, **Train attendance model**, **Predict example appointments**, and **Test assessment**. For a live conversation regression check, see [Gemini evaluation](docs/gemini.md).

## Deployment and limitations

The Dockerfile and Render configuration serve Reception and the static attendance report from one Free web service. [Deployment instructions](docs/deployment.md) cover setup and hosted checks. The frontend and Python hosting have been checked locally; no public deployment or Docker build has been verified. Hosting is optional for the assessment. GitHub Pages alone cannot run the Python reception API.

Reception stores sessions in memory and resets them on restart. In Gemini mode, fictional conversation text is sent to Google; the key remains server-side and `.env` is excluded from Git and the image. Free API quotas and availability still apply. There is no automatic model/provider fallback. The optional OpenAI adapter has only been tested with a mock client and may incur API charges.

The attendance dataset lacks patient IDs, dates, and event timestamps. Its model assumes reminder status is known before scoring and is intended only to demonstrate staff-reviewed outreach. It does not alter appointments or contact patients. See the [model card](ml/model-card.md) for feature timing, calibration, evaluation limits, and a proposed production integration.
