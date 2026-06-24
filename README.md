# BioMimetix AI

BioMimetix AI is a local biomimicry exploration app with a React frontend and a FastAPI backend.

## App Structure

- `biomimetix/frontend`: the main visual React/Vite interface
- `biomimetix/backend/api.py`: the HTTP API used by the React app
- `biomimetix/backend/app.py`: optional legacy Streamlit interface
- `biomimetix/backend/core.py`: shared biomimicry, Gemini, image, and research logic

## Environment

Create `biomimetix/backend/.env`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
# Optional:
# GEMINI_MODEL=gemini-2.5-flash-lite
# GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
```

The real `.env` file is ignored by git.

## Run Locally

Start the backend:

```bash
cd biomimetix/backend
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```bash
cd biomimetix/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`.

## Health Checks

- API health: `http://127.0.0.1:8000/api/health`
- Generated images are served from `http://127.0.0.1:8000/generated_images/...`

The React app shows whether the backend is reachable and whether Gemini is configured.
