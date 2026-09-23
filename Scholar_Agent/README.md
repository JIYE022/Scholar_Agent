# Scholar_agent

Scholar_agent 是面向研究生的文献知识管理与检索增强问答系统。

## 启动后端

```powershell
cd backend
docker compose up -d --build
```

查看后端日志：

```powershell
docker compose logs -f scholar_agent_api
```

## 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认地址：http://localhost:5181/

后端 API 文档：http://localhost:8000/docs

## Docker 服务名称

- `scholar_agent_api`：FastAPI 后端
- `gsk_pg`：PostgreSQL
- `gsk-es-01`：Elasticsearch
- `gsk_redis`：Redis

为了继续使用已有 PostgreSQL 数据卷，数据库内部名称暂时保留为 `gsk`。它只是兼容性标识，不是项目展示名称。
