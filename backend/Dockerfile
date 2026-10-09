# ===== 知南·Echo 多阶段构建（build context 必须是项目根目录）=====
# docker build -f backend/Dockerfile -t zhinan-echo .

# ---- 阶段1：前端构建 ----
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --registry=https://registry.npmmirror.com || npm install
COPY frontend/ .
RUN npm run build

# ---- 阶段2：后端运行镜像 ----
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/run.py .
COPY --from=frontend /web/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
