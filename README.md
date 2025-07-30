# Docker 镜像大小查询服务

这是一个基于 skopeo 的 Docker 镜像大小查询服务。它提供了一个 RESTful API，用于获取 Docker 镜像的详细信息，包括大小、层信息等。

## 功能特点

- 查询 Docker 镜像的详细信息和大小
- 支持私有仓库认证
- 支持代理设置
- 返回完整的 skopeo 信息
- 计算压缩和未压缩大小

## 构建镜像

```bash
docker build -t docker-size-service .
```

## 运行服务

```bash
docker run -d --name docker-size -p 8000:8000 docker-size-service
```

### 环境变量（可选）

- `API_KEY`: API访问密钥，用于API认证
- `IMAGE_USERNAME`: 私有仓库用户名
- `IMAGE_PASSWORD`: 私有仓库密码
- `HTTPS_PROXY`: HTTP代理地址
- `CACHE_TYPE`: 缓存类型，可选值: simple(内存缓存), redis(Redis缓存), null(禁用缓存)，默认为simple
- `CACHE_TIMEOUT`: 缓存过期时间，单位为秒，默认3600秒(1小时)
- `CACHE_REDIS_URL`: Redis连接URL，当CACHE_TYPE=redis时必须设置

## API 使用方法

### 查询镜像完整信息

**请求**:

```
GET /image-info?image=nginx:latest&api_key=your-api-key
```

**参数**:

- `image`: 镜像名称（必须，格式为 `name:tag` 或 `name`，如果不指定标签，将使用 `latest`）
- `api_key`: API访问密钥（如果设置了API_KEY环境变量，则此参数必须）
- `username`: 私有仓库用户名（可选，优先于环境变量）
- `password`: 私有仓库密码（可选，优先于环境变量）
- `proxy`: 代理地址（可选，优先于环境变量）

**响应示例**:

```json
{
  "status": "success",
  "image": "nginx:latest",
  "compressed_size": 54321,
  "compressed_size_mb": 52.07,
  "uncompressed_size": 98765,
  "uncompressed_size_mb": 94.20,
  "raw_data": {
    // 完整的 skopeo 返回数据
  }
}
```

### 仅查询镜像大小

**请求**:

```
GET /image-size?image=nginx:latest&api_key=your-api-key
```

**参数**:

- `image`: 镜像名称（必须，格式为 `name:tag` 或 `name`，如果不指定标签，将使用 `latest`）
- `api_key`: API访问密钥（如果设置了API_KEY环境变量，则此参数必须）
- `username`: 私有仓库用户名（可选，优先于环境变量）
- `password`: 私有仓库密码（可选，优先于环境变量）
- `proxy`: 代理地址（可选，优先于环境变量）

**响应示例**:

```json
{
  "status": "success",
  "image": "nginx:latest",
  "compressed_size": 54321,
  "compressed_size_mb": 52.07,
  "estimated_uncompressed_size": 92345,
  "estimated_uncompressed_size_mb": 88.52
}
```

## 错误处理

服务会返回适当的 HTTP 状态码和错误信息：

- `400`: 请求参数错误
- `401`: API认证失败
- `404`: 镜像不存在或无权访问
- `500`: 服务器内部错误

## API认证说明

如果设置了`API_KEY`环境变量，所有API请求都需要提供相应的`api_key`参数。这可以防止未经授权的访问。

**启用API认证**:

```bash
# 在Docker容器启动时设置API密钥
docker run -d --name docker-size -p 8000:8000 -e API_KEY="your-secret-key" docker-size-service
```

**使用认证**:

所有API请求都需要添加`api_key`参数:

```
/image-info?image=nginx:latest&api_key=your-secret-key
/image-size?image=nginx:latest&api_key=your-secret-key
```

如果未设置`API_KEY`环境变量，则不需要提供`api_key`参数。

## 缓存功能

本服务内置缓存功能，可以大幅提高查询速度，减少对Docker Registry的请求压力。

### 缓存相关API

**查看缓存状态**:

```
GET /cache-info?api_key=your-api-key
```

**清除缓存**:

```
GET /cache-clear?api_key=your-api-key
```

### 缓存配置

缓存可以通过环境变量配置:

```bash
# 使用内存缓存（默认）
docker run -d --name docker-size -p 8000:8000 -e CACHE_TIMEOUT=7200 docker-size-service

# 使用Redis缓存
docker run -d --name docker-size -p 8000:8000 \
  -e CACHE_TYPE=redis \
  -e CACHE_REDIS_URL=redis://redis-server:6379/0 \
  docker-size-service
  
# 禁用缓存
docker run -d --name docker-size -p 8000:8000 -e CACHE_TYPE=null docker-size-service
```

### 缓存响应头

API响应包含以下与缓存相关的HTTP头:

- `X-Cache-Status`: 表示缓存状态，`HIT`表示命中缓存，`MISS`表示未命中
- `X-Cache-TTL`: 缓存生存时间（秒）
- `X-Cache-Type`: 使用的缓存类型