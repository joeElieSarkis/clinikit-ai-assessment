# Free demo deployment

This configuration runs the React interface and Python API together as one Render **Free** web service. The source code can live in a GitHub repository. Reviewers receive one HTTPS link and do not need to install anything or keep the developer's laptop running.

## GitHub Pages and this project

[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) is free for public repositories on GitHub Free. It publishes static HTML, CSS, and JavaScript; it [does not run server-side Python](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).

This project needs its Python API for conversations, proposals, confirmations, and sample appointments. Uploading the frontend to Pages alone would not provide those features. Splitting the frontend onto Pages and the API onto another host is possible, but would require additional URL and cross-origin configuration. The included deployment serves both from one origin instead.

## Deploy when ready

1. Push this project to your own GitHub repository. The repository root should contain `Dockerfile`, `render.yaml`, `backend`, and `frontend`. Exclude `.env`, `.venv`, `node_modules`, and `work`; the supplied `.gitignore` already does this. No push is performed by the local setup.
2. Create a free account at [Render](https://dashboard.render.com/). Keep the free workspace plan and do not add a payment method. If the account requires payment verification or an upgrade to continue, stop and reassess the hosting choice.
3. Choose **New → Blueprint**, connect the GitHub repository, and select the branch containing `render.yaml`.
4. Review the generated resources before deploying: exactly one web service named `clinikit-reception`, Docker runtime, **Free** instance, Frankfurt region, and `AI_PROVIDER=demo`. No database, disk, or paid service is needed.
5. Deploy the blueprint. Render builds the frontend and starts the Python server. The service dashboard provides its public `onrender.com` URL after a successful deployment; use the actual URL shown there.
6. Complete the browser checks below before adding that link to a submission.

The included [Blueprint configuration](https://render.com/docs/blueprint-spec) disables automatic deployment after later pushes. To publish an update, push it yourself and use **Manual Deploy → Deploy latest commit** in the service dashboard.

## Keep it free

- Use the **Free** instance and the free workspace plan. Do not add paid services or a payment method.
- Leave `AI_PROVIDER=demo`. This bounded rule interpreter makes no model API calls. The optional OpenAI adapter is a separate feature that may incur API charges and is not enabled by this deployment.
- Use the supplied `onrender.com` address; purchasing a domain is unnecessary.
- [Render's free limits](https://render.com/docs/free) include 750 instance hours per workspace per month, shared by its free web services. Bandwidth and build usage also have limits. Without a payment method, exceeding those limits suspends services or disables builds instead of billing for extra usage.
- After 15 minutes without traffic, the service sleeps. A new visit wakes it, which usually takes about one minute. No uptime guarantee is implied.

Hosting terms were checked on 13 September 2026. Confirm the dashboard still shows Free before creating the service.

## What the container does

`Dockerfile` builds the frontend with Node, then copies only the built assets and required backend files into a Python image. It runs as a non-root user. `.dockerignore` restricts the build context to the needed source and manifests.

`serve.py` starts one Uvicorn worker on `0.0.0.0` and the host's `PORT` (default 10000). The application serves both `/` and `/api` from the same origin. Render supplies `RENDER_EXTERNAL_URL`, which the API accepts as its hosted origin. For another host or a custom domain, set `PUBLIC_ORIGIN` to the exact HTTPS origin, without a path.

Appointments and sessions are intentionally held in memory. Sleeping, restarting, or redeploying resets them. Each new session starts with fictional sample data; this is not a real clinic scheduling service.

## Check the deployed link

1. Open the public URL in a private browser window. Allow the initial wake-up to finish. Confirm the interface shows **Demo mode**.
2. Visit `/api/health` on that same domain and confirm the status is `ok`.
3. Ask opening hours. Book an available weekday slot, confirm it, then reschedule and cancel the sample appointment using the explicit confirmation controls.
4. Send “I might want to see Dr. George tomorrow at 4, but don't book anything yet.” Confirm no appointment changes without approval; the response can ask for clarification or explain a closed date.
5. Open the site on a phone and check the composer and visit disclosure. Refresh during an active session and check it still loads.

The production frontend build and Python hosting checks passed locally. A Docker build and public deployment have not yet been verified. After deployment, record the actual URL, date, and observed checks in `docs/validation.md`.
