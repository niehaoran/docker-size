# 放弃多阶段构建，直接使用skopeo镜像
FROM quay.io/skopeo/stable:latest

# 安装Python和其他需要的依赖
RUN dnf install -y python3 python3-pip jq bc curl && \
    dnf clean all

WORKDIR /app

# 复制应用代码
COPY app.py .
COPY requirements.txt .

# 安装Python依赖
RUN pip3 install --no-cache-dir -r requirements.txt \
    && pip3 install --no-cache-dir pysocks requests[socks]

# 暴露端口
EXPOSE 8000

# 确保skopeo可用
RUN which skopeo && skopeo --version

# 启动服务
CMD ["python3", "app.py"] 