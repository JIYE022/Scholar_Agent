import time
import uuid
from utils import logger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from router import chat_rt
from router import user_rt
from router import history_rt
from router import evaluation_rt
from router import comparison_rt
from router import external_search_rt
from service.upload_task_service import start_upload_worker, stop_upload_worker
import os

# 从环境变量获取 root_path
root_path = os.getenv("ROOT_PATH", "http://localhost:8000")

app = FastAPI(
    title="Scholar_agent",
    description="研究生文献知识管理与检索增强问答系统",
    root_path=root_path,
)

# 添加请求ID中间件
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # 优先使用调用方传入的请求 ID，否则自动生成
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    # 保存到 request，接口函数可以继续读取
    request.state.request_id = request_id

    start_time = time.perf_counter()

    logger.info(
        f"[request_id={request_id}] "
        f"request started: {request.method} {request.url.path}"
    )

    try:
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"[request_id={request_id}] "
            f"request completed: "
            f"{request.method} {request.url.path}, "
            f"status={response.status_code}, "
            f"elapsed_ms={elapsed_ms:.2f}"
        )

        # 将请求 ID返回给前端，方便根据错误响应查日志
        response.headers["X-Request-ID"] = request_id
        return response

    except Exception:
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.exception(
            f"[request_id={request_id}] "
            f"request failed: "
            f"{request.method} {request.url.path}, "
            f"elapsed_ms={elapsed_ms:.2f}"
        )
        raise

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，生产环境中应该设置具体的源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)


@app.on_event("startup")
def start_background_workers():
    start_upload_worker()


@app.on_event("shutdown")
def stop_background_workers():
    stop_upload_worker()

app.include_router(chat_rt.router)
app.include_router(user_rt.router)
app.include_router(history_rt.router)
app.include_router(evaluation_rt.router)
app.include_router(comparison_rt.router)
app.include_router(external_search_rt.router)

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
