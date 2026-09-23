# Scholar_agent 后端

Scholar_agent 是一个面向研究生的文献知识管理与检索增强问答系统。

## 🚀 快速启动

### 环境要求

- Docker 和 Docker Compose
- 至少 4GB 可用内存
- 10GB 可用磁盘空间

### 启动步骤

1. **克隆项目并进入目录**
```bash
cd Scholar_agent/backend
```

2. **.env 配置文件**
```bash
SILICONFLOW_API_KEY="your-api-key"
SILICONFLOW_BASE_URL="https://api.siliconflow.cn/v1"
RERANK_MODEL="Qwen/Qwen3-Reranker-4B"
SILICONFLOW_RERANK_URL="https://api.siliconflow.cn/v1/rerank"
```

`SILICONFLOW_API_KEY` 需要同时具有聊天、Embedding 和
`Qwen/Qwen3-Reranker-4B` 重排服务的调用权限。为兼容已有部署，代码仍会
回退读取旧的 `DASHSCOPE_API_KEY` 与 `DASHSCOPE_BASE_URL`，但新环境建议使用
`SILICONFLOW_*` 命名。完整的可调参数见 `.env.example`。

> 切块策略只会在文档入库时执行。升级后请重新上传/重建已有文档索引，
> 才能让历史文档使用 128-token、章节内句子级重叠的新切块。

3. **修改docker-compose.yml中的nltk本地路径**
```bash

# 修改为你的nltk_data路径
- /your/path/to/nltk_data:/usr/local/nltk_data

```

4. **启动所有服务**
```bash
# 启动所有服务（首次启动会自动构建镜像）
docker compose up -d --build

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f scholar_agent_api
```

4. **等待服务完全启动**
```bash
# 检查服务健康状态
curl http://localhost:8000/docs
```

### 服务说明

项目包含以下服务：
- **scholar_agent_api**: 主应用服务 (端口: 8000)
- **gsk_pg**: PostgreSQL 数据库
- **es01**: Elasticsearch 搜索引擎  
- **redis**: Redis 缓存

### 停止服务

```bash
# 停止所有服务
docker compose down

# 停止并删除数据卷（注意：这会删除所有数据）
docker compose down -v
```

## 🔧 开发调试

### 查看日志
```bash
# 查看所有服务日志
docker compose logs

# 查看特定服务日志
docker compose logs scholar_agent_api
docker compose logs gsk_pg
docker compose logs es01
docker compose logs redis

# 实时跟踪日志
docker compose logs -f scholar_agent_api
```

### 进入容器调试
```bash
# 进入主应用容器
docker compose exec scholar_agent_api bash

# 进入数据库容器
docker compose exec gsk_pg psql -U postgres -d gsk
```

### 重新构建服务
```bash
# 重新构建并启动
docker compose up --build -d

# 仅重新构建特定服务
docker compose build scholar_agent_api
docker compose up -d scholar_agent_api
```

## 📋 常见问题

1. **端口被占用**: 确保8000端口未被其他程序占用
2. **内存不足**: Elasticsearch需要至少1GB内存，建议系统有4GB+可用内存
3. **首次启动慢**: 首次启动需要下载镜像和初始化数据，请耐心等待
4. **服务连接失败**: 等待所有服务完全启动后再测试API

## 🎯 访问地址

- API文档: http://localhost:8000/docs
