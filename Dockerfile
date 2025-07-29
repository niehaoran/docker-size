FROM python:3.9-slim

# 安装依赖
RUN apt-get update && apt-get install -y \
    skopeo \
    jq \
    bc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制应用代码
COPY app.py .
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["python", "app.py"] 