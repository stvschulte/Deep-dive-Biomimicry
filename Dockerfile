# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /build
COPY biomimetix/frontend/package*.json ./
RUN npm ci --quiet
COPY biomimetix/frontend/ .
RUN npm run build

# ── Stage 2: Python API runtime ───────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app/biomimetix/backend

# Install only what the API needs (no streamlit)
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    google-genai \
    pillow \
    python-dotenv \
    pydantic

# Copy backend source
COPY biomimetix/backend/ .

# Copy built React app — api.py looks for Path(__file__).parents[1]/frontend/dist
# which resolves to /app/biomimetix/frontend/dist
COPY --from=frontend /build/dist /app/biomimetix/frontend/dist

# Writable dir for generated images
RUN mkdir -p generated_images

ENV PORT=8000
EXPOSE $PORT

CMD uvicorn api:app --host 0.0.0.0 --port ${PORT}
