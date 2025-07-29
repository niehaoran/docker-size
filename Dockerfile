# Stage 1: 从quay.io/skopeo/stable复制skopeo二进制文件
FROM quay.io/skopeo/stable:latest as skopeo_builder

# Stage 2: 构建我们的应用
FROM python:3.9-slim

# 从builder阶段复制skopeo二进制文件
COPY --from=skopeo_builder /usr/bin/skopeo /usr/local/bin/skopeo

# 安装依赖
RUN apt-get update && apt-get install -y \
    jq \
    bc \
    curl \
    python3-socks \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制应用代码
COPY app.py .
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pysocks requests[socks]

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["python", "app.py"] 