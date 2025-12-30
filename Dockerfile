FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

RUN npm install -g pnpm

COPY web/ ./

RUN pnpm install --frozen-lockfile || pnpm install

RUN pnpm run build

FROM python:3.13-slim AS backend

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/
COPY main.py ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

COPY --from=frontend-builder /app/web/dist ./web/dist

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
