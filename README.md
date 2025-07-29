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

- `IMAGE_USERNAME`: 私有仓库用户名
- `IMAGE_PASSWORD`: 私有仓库密码
- `HTTPS_PROXY`: HTTP代理地址

## API 使用方法

### 查询镜像完整信息

**请求**:

```
GET /image-info?image=nginx:latest
```

**参数**:

- `image`: 镜像名称（必须，格式为 `name:tag` 或 `name`，如果不指定标签，将使用 `latest`）
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
GET /image-size?image=nginx:latest
```

**参数**:

- `image`: 镜像名称（必须，格式为 `name:tag` 或 `name`，如果不指定标签，将使用 `latest`）
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
- `404`: 镜像不存在或无权访问
- `500`: 服务器内部错误