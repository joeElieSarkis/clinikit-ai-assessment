FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    AI_PROVIDER=gemini
WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt \
    && useradd --create-home --uid 10001 reception
COPY backend/__init__.py ./backend/__init__.py
COPY backend/app ./backend/app
COPY serve.py ./
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
USER reception
EXPOSE 10000
CMD ["python", "serve.py"]
