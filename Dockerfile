# 前端构建
FROM node:22-alpine AS frontend-builder
WORKDIR /app/web
ENV CI=true
RUN npm install -g pnpm
COPY web/ ./
RUN pnpm install --frozen-lockfile || pnpm install && pnpm run build

# 后端
FROM python:3.14-slim
WORKDIR /app
ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app/ ./app/
COPY main.py ./
COPY --from=frontend-builder /app/web/dist ./web/dist

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop"]
