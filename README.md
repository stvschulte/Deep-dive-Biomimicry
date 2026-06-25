---
title: Deep Dive Biomimicry
emoji: 🌿
colorFrom: green
colorTo: teal
sdk: streamlit
sdk_version: "1.41.1"
app_file: streamlit_app.py
pinned: false
---

# BioMimetix AI

BioMimetix AI is a hosted Streamlit app for biomimicry exploration. The Streamlit app is the end-user frontend.

## App Structure

- `streamlit_app.py`: Streamlit Community Cloud entrypoint
- `biomimetix/backend/app.py`: Streamlit end-user interface
- `biomimetix/backend/core.py`: shared biomimicry, Gemini, image, and research logic
- `biomimetix/frontend`: optional React/Vite prototype
- `biomimetix/backend/api.py`: optional FastAPI API for the React prototype

## Streamlit Cloud Deployment

Use these settings on Streamlit Community Cloud:

- Main file path: `streamlit_app.py`
- Python dependencies: root `requirements.txt`
- Secrets:

```toml
GEMINI_API_KEY = "your_gemini_api_key_here"
# Optional:
# GEMINI_MODEL = "gemini-2.5-flash-lite"
# GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
```

After changing secrets, reboot the app.

## Run Streamlit Locally

Create `biomimetix/backend/.env`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

Then run:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Optional React Prototype

The React/Vite prototype is not the Streamlit-hosted frontend. To run it locally:

```bash
cd biomimetix/backend
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000

cd ../frontend
npm install
npm run dev
```
