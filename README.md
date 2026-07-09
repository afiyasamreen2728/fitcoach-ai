# FitCoach AI

A custom GPT-style fitness coaching assistant. FastAPI backend, streaming
responses from Anthropic's Claude API, plain HTML/CSS/JS frontend, packaged
in Docker and deployable to AWS App Runner.

## Architecture

```
browser (frontend/index.html)
   │  fetch POST /api/chat  (JSON: {messages: [...]})
   ▼
FastAPI backend (backend/main.py)
   │  streams via Anthropic Messages API
   ▼
Anthropic Claude API
```

The backend streams tokens back to the browser as Server-Sent Events, so
text renders progressively instead of appearing all at once. The API key
lives only in a server-side environment variable — it is never sent to the
browser or committed to version control.

## 1. Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your real ANTHROPIC_API_KEY

uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 — the backend serves the frontend directly.

## 2. Run with Docker

```bash
docker build -t fitcoach-ai .
docker run -p 8000:8000 --env-file backend/.env fitcoach-ai
```

Open http://localhost:8000.

Never bake the `.env` file into the image — it's excluded via
`.dockerignore`. Secrets are injected at runtime with `--env-file` (or an
AWS-managed secret store in production, see below).

## 3. Deploy to AWS App Runner

These steps assume you have the AWS CLI configured (`aws configure`) and
Docker installed.

### a. Push the image to Amazon ECR

```bash
# Create a repository (one-time)
aws ecr create-repository --repository-name fitcoach-ai

# Authenticate Docker to ECR
aws ecr get-login-password --region <your-region> | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.<your-region>.amazonaws.com

# Build, tag, and push
docker build -t fitcoach-ai .
docker tag fitcoach-ai:latest <account-id>.dkr.ecr.<your-region>.amazonaws.com/fitcoach-ai:latest
docker push <account-id>.dkr.ecr.<your-region>.amazonaws.com/fitcoach-ai:latest
```

### b. Create the App Runner service

Console path: **AWS App Runner → Create service → Container registry →
Amazon ECR** → select the `fitcoach-ai` image.

- **Port**: `8000`
- **Environment variables**: add `ANTHROPIC_API_KEY` as a secret (App Runner
  supports referencing AWS Secrets Manager values directly — don't paste the
  raw key into a plaintext env var in the console for a real deployment).
- **CPU/Memory**: 1 vCPU / 2 GB is enough for a demo workload.

Or via CLI:

```bash
aws apprunner create-service \
  --service-name fitcoach-ai \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "<account-id>.dkr.ecr.<your-region>.amazonaws.com/fitcoach-ai:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentSecrets": {
          "ANTHROPIC_API_KEY": "arn:aws:secretsmanager:<region>:<account-id>:secret:anthropic-api-key"
        }
      }
    },
    "AutoDeploymentsEnabled": true
  }'
```

App Runner will provision a public HTTPS URL
(`https://<id>.<region>.awsapprunner.com`) once the service is running —
that's the URL for your concept note and submission.

### c. Store the secret in AWS Secrets Manager (recommended)

```bash
aws secretsmanager create-secret \
  --name anthropic-api-key \
  --secret-string '{"ANTHROPIC_API_KEY":"your_real_key"}'
```

Reference this ARN in the App Runner service's `RuntimeEnvironmentSecrets`
instead of pasting the key as plaintext, so it never appears in the console,
CloudFormation template, or CLI history in cleartext.

## Security checklist

- [x] API key read from `ANTHROPIC_API_KEY` env var, never hardcoded
- [x] `.env` excluded from git (`.gitignore`) and Docker image (`.dockerignore`)
- [x] Frontend never receives or references the API key
- [ ] Before going beyond a demo: restrict CORS `allow_origins` to your real
      frontend domain instead of `"*"`
- [ ] Before going beyond a demo: move the API key into AWS Secrets Manager
      rather than a plaintext App Runner environment variable

## Project structure

```
fitcoach-ai/
├── backend/
│   ├── main.py           # FastAPI app, /api/chat streaming endpoint
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html        # Chat UI, streams tokens progressively
├── Dockerfile
├── .dockerignore
└── README.md
```
