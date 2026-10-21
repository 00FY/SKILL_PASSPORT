# GitHub Pages frontend and Render backend

The frontend uses GitHub Pages. The FastAPI backend runs as a Render Docker web service. Keep the backend at one Uvicorn worker because jobs, quiz attempts and rate limits live in memory.

## 1. Create the Render service

Create a Blueprint in the Render dashboard from `https://github.com/00FY/SKILL_PASSPORT` on `main`. Render reads the root `render.yaml` and builds `backend/Dockerfile`.

The Blueprint selects the free plan, generates a persistent HMAC secret in the service environment, and sets the browser origin to `https://00fy.github.io`. Add `GITHUB_TOKEN` in Render's Environment settings if you want higher GitHub API limits. LLM keys are optional. Never place these secrets in frontend variables or repository files.

Wait for the health check to pass. Open the assigned service URL with `/api/health` appended and confirm that it returns `"status": "healthy"`. Copy the actual service origin, such as `https://<assigned-service>.onrender.com`, without `/api`.

## 2. Publish the frontend

In the GitHub repository:

1. Open Settings > Pages and choose **GitHub Actions** as the source.
2. Open Settings > Secrets and variables > Actions > Variables. Set `SKILL_PASSPORT_API_URL` to the actual Render service origin from step 1.
3. Run **Deploy frontend to GitHub Pages** under Actions. You can also supply `backend_url` for a manual run. Later pushes that change the frontend redeploy it automatically.

Until a backend URL is configured or supplied, the workflow skips deployment so it cannot publish an app pointing at a missing API.

The expected Pages address is `https://00fy.github.io/SKILL_PASSPORT/`. Confirm the final address in the deployment's output.

The workflow builds assets with the `/SKILL_PASSPORT/` base path. `VITE_API_BASE_URL` sends every API call, including PDF exports, to Render. Local development keeps using the existing Vite proxy on port 8000 when this variable is absent.

## Operating limits

Render free services can sleep when idle. The first request can take longer while the service starts. Jobs, assessment attempts and uploaded-certificate records expire on a restart or redeploy. An environment-stored HMAC key keeps existing passport signatures verifiable.

The Docker service runs as a non-root user. Assessment code runs in a separate Python process with Linux resource limits. This deployment does not provide a Docker daemon for an additional container per assessment. Use a dedicated isolated runner for stronger isolation before handling untrusted production assessment traffic.

Free-tier memory is limited. This Blueprint processes one repository analysis at a time and limits repository size to 100 MB. Public deployment does not add authentication: keep the existing rate limits enabled and adjust them for your pilot.

## References

- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render free service limits](https://render.com/docs/free)
- [Vite deployment to GitHub Pages](https://vite.dev/guide/static-deploy.html#github-pages)
