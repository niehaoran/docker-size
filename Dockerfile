# 使用指定的skopeo镜像
FROM quay.io/skopeo/stable:latest

# 安装Python和其他需要的依赖
RUN microdnf install -y python3 python3-pip jq bc curl || \
    dnf install -y python3 python3-pip jq bc curl || \
    yum install -y python3 python3-pip jq bc curl && \
    (microdnf clean all || dnf clean all || yum clean all)

WORKDIR /app

# 复制应用代码
COPY app.py .
COPY requirements.txt .
COPY start.sh .

# 确保启动脚本可执行
RUN chmod +x start.sh

# 安装Python依赖
RUN pip3 install --no-cache-dir -r requirements.txt \
    && pip3 install --no-cache-dir pysocks requests[socks]

# 确保 Python 可执行文件路径正确
ENV PATH="/usr/bin:${PATH}"

# API认证环境变量（可选）
# ENV API_KEY="your-secret-api-key"

# 缓存配置（可选）
# ENV CACHE_TYPE=simple   # 可选值: simple, redis, null（禁用缓存）
# ENV CACHE_TIMEOUT=3600  # 缓存过期时间，单位：秒
# ENV CACHE_REDIS_URL=redis://localhost:6379/0  # 如果使用Redis缓存后端

# 暴露端口
EXPOSE 8000

# 完全覆盖基础镜像的 ENTRYPOINT
ENTRYPOINT []

# 使用启动脚本
CMD ["/bin/bash", "./start.sh"] 