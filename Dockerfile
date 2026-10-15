FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=10000 \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libc6-dev libpq-dev \
    && apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY main.py ./
COPY backend/ ./backend/
COPY pipelines/ ./pipelines/
COPY assets/brand/ ./assets/brand/
COPY --from=frontend /build/dist ./frontend/dist/
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 10000
CMD ["python", "main.py"]
