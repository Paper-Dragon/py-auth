# 阶段1: 构建前端
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# 安装 pnpm
RUN npm install -g pnpm

# 复制前端依赖文件
COPY web/package.json web/pnpm-lock.yaml* ./

# 安装依赖
RUN pnpm install --frozen-lockfile || pnpm install

# 复制前端源码
COPY web/ ./

# 构建前端
RUN pnpm run build

# 阶段2: 构建后端
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml .

# 安装Python依赖
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir \
    fastapi>=0.115.0 \
    "uvicorn[standard]>=0.32.0" \
    sqlalchemy>=2.0.36 \
    pymysql>=1.1.1 \
    cryptography>=43.0.0 \
    "python-jose[cryptography]>=3.3.0" \
    "passlib[bcrypt]>=1.7.4" \
    python-multipart>=0.0.12 \
    pydantic>=2.9.0 \
    pydantic-settings>=2.6.0 \
    python-dotenv>=1.0.0 \
    jinja2>=3.1.4 \
    aiofiles>=24.1.0

# 复制应用代码
COPY app/ ./app/
COPY main.py .
COPY client/ ./client/

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/web/dist ./web/dist

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
