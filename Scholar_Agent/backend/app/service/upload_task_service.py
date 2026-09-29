import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import xxhash
from sqlalchemy import select

from database.knowledgebase_operations import create_paper
from models.knowledgebase import KnowledgeBase
from schemas.paper import PaperMetadataCreate
from service.core.chat import get_redis_client
from service.core.file_parse import execute_insert_process
from service.core.rag.utils.es_conn import ESConnection
from utils import logger
from utils.database import SessionLocal


TASK_KEY_PREFIX = "upload_task:"
LOCK_KEY_PREFIX = "upload_lock:"
QUEUE_KEY = "upload_tasks:queue"
PROCESSING_KEY = "upload_tasks:processing"
TASK_TTL_SECONDS = 7 * 24 * 60 * 60
LOCK_TTL_SECONDS = 2 * 24 * 60 * 60

_worker_thread: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_stop_event = threading.Event()


def create_task_id() -> str:
    return uuid.uuid4().hex


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _lock_key(user_id: str, file_name: str) -> str:
    fingerprint = hashlib.sha256(f"{user_id}\0{file_name}".encode("utf-8")).hexdigest()
    return f"{LOCK_KEY_PREFIX}{fingerprint}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_task(redis_task_id: str, **updates: Any) -> None:
    redis_client = get_redis_client()
    mapping = {
        key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        for key, value in updates.items()
        if value is not None
    }
    mapping["updated_at"] = _now()
    redis_client.hset(_task_key(redis_task_id), mapping=mapping)
    redis_client.expire(_task_key(redis_task_id), TASK_TTL_SECONDS)


def enqueue_upload_task(
    *,
    task_id: str,
    user_id: str,
    session_id: str,
    file_name: str,
    file_path: str,
    final_path: str,
    metadata: Optional[PaperMetadataCreate],
) -> None:
    redis_client = get_redis_client()
    lock_key = _lock_key(user_id, file_name)
    if not redis_client.set(lock_key, task_id, nx=True, ex=LOCK_TTL_SECONDS):
        existing_task_id = redis_client.get(lock_key)
        raise RuntimeError(f"该文件正在处理中，任务ID: {existing_task_id}")

    created_at = _now()
    try:
        _write_task(
            task_id,
            task_id=task_id,
            user_id=user_id,
            session_id=session_id,
            file_name=file_name,
            file_path=file_path,
            final_path=final_path,
            metadata=metadata.model_dump(mode="json") if metadata else {},
            status="queued",
            stage="queued",
            progress=5,
            message="文件已保存，等待解析",
            created_at=created_at,
        )
        redis_client.lpush(QUEUE_KEY, task_id)
    except Exception:
        redis_client.delete(lock_key)
        redis_client.delete(_task_key(task_id))
        raise


def get_upload_task(task_id: str) -> Optional[dict[str, Any]]:
    task = get_redis_client().hgetall(_task_key(task_id))
    if not task:
        return None

    public_fields = {
        "task_id",
        "user_id",
        "session_id",
        "file_name",
        "status",
        "stage",
        "progress",
        "message",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "error",
        "result",
    }
    result: dict[str, Any] = {key: value for key, value in task.items() if key in public_fields}
    if "progress" in result:
        result["progress"] = int(result["progress"])
    for key in ("result",):
        if result.get(key):
            try:
                result[key] = json.loads(result[key])
            except json.JSONDecodeError:
                pass
    return result


def _cleanup_es(session_id: str, file_name: str) -> None:
    try:
        doc_id = xxhash.xxh64(file_name.encode("utf-8")).hexdigest()
        deleted = ESConnection().delete(
            {"doc_id": doc_id},
            indexName=session_id,
            knowledgebaseId=session_id,
        )
        logger.info(f"上传失败补偿清理 ES 完成: file={file_name}, deleted={deleted}")
    except Exception as exc:
        logger.exception(f"上传失败补偿清理 ES 失败: file={file_name}, error={exc}")


def _release_lock(task: dict[str, str]) -> None:
    get_redis_client().delete(_lock_key(task["user_id"], task["file_name"]))


def _mark_existing_task_succeeded(task_id: str, paper: KnowledgeBase) -> None:
    _write_task(
        task_id,
        status="succeeded",
        stage="completed",
        progress=100,
        message="论文已完成入库",
        completed_at=_now(),
        result={
            "paper_id": paper.id,
            "file_name": paper.file_name,
            "chunk_count": 0,
            "recovered": True,
        },
    )


def _process_task(task_id: str) -> None:
    redis_client = get_redis_client()
    task = redis_client.hgetall(_task_key(task_id))
    if not task:
        return

    db = SessionLocal()
    try:
        existing = db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.user_id == task["user_id"],
                KnowledgeBase.file_name == task["file_name"],
            )
        ).scalar_one_or_none()
        if existing:
            if os.path.isfile(task["file_path"]):
                os.remove(task["file_path"])
            _mark_existing_task_succeeded(task_id, existing)
            _release_lock(task)
            return

        parse_path = task["file_path"]
        if not os.path.isfile(parse_path) and os.path.isfile(task["final_path"]):
            parse_path = task["final_path"]
        if not os.path.isfile(parse_path):
            raise FileNotFoundError(f"待解析文件不存在: {task['file_name']}")

        metadata_data = json.loads(task.get("metadata") or "{}")
        metadata = PaperMetadataCreate.model_validate(metadata_data) if metadata_data else None

        _write_task(
            task_id,
            status="processing",
            stage="parsing",
            progress=15,
            message="正在解析文档并生成向量",
            started_at=_now(),
        )
        logger.info(f"[upload_task={task_id}] Processing file: {task['file_path']}")

        chunk_count = execute_insert_process(
            parse_path,
            task["file_name"],
            task["session_id"],
            metadata.model_dump(mode="json") if metadata else None,
        )

        if parse_path != task["final_path"]:
            os.replace(parse_path, task["final_path"])

        _write_task(
            task_id,
            status="processing",
            stage="database",
            progress=90,
            message="向量已入库，正在保存论文信息",
        )
        paper = create_paper(db, task["user_id"], task["file_name"], metadata)

        _write_task(
            task_id,
            status="succeeded",
            stage="completed",
            progress=100,
            message="论文上传并解析完成",
            completed_at=_now(),
            result={
                "paper_id": paper.id,
                "file_name": task["file_name"],
                "chunk_count": chunk_count,
            },
        )
        _release_lock(task)
        logger.info(
            f"[upload_task={task_id}] 上传链路完成: "
            f"file={task['file_name']}, chunks={chunk_count}, paper_id={paper.id}"
        )
    except Exception as exc:
        db.rollback()
        _cleanup_es(task["session_id"], task["file_name"])
        for path_key in ("file_path", "final_path"):
            candidate = task.get(path_key)
            if candidate and os.path.isfile(candidate):
                try:
                    os.remove(candidate)
                except OSError as cleanup_error:
                    logger.warning(f"清理失败文件失败: path={candidate}, error={cleanup_error}")
        _write_task(
            task_id,
            status="failed",
            stage="failed",
            progress=100,
            message="论文解析或入库失败",
            error=str(exc),
            completed_at=_now(),
        )
        _release_lock(task)
        logger.exception(f"[upload_task={task_id}] 上传链路失败: {exc}")
    finally:
        db.close()


def _recover_interrupted_tasks(redis_client) -> None:
    interrupted = redis_client.lrange(PROCESSING_KEY, 0, -1)
    for task_id in interrupted:
        task = redis_client.hgetall(_task_key(task_id))
        redis_client.lrem(PROCESSING_KEY, 0, task_id)
        if not task or task.get("status") in {"succeeded", "failed"}:
            continue
        _write_task(
            task_id,
            status="queued",
            stage="queued",
            progress=5,
            message="服务重启，任务已重新排队",
        )
        redis_client.lrem(QUEUE_KEY, 0, task_id)
        redis_client.lpush(QUEUE_KEY, task_id)


def _worker_loop() -> None:
    redis_client = get_redis_client()
    try:
        _recover_interrupted_tasks(redis_client)
    except Exception as exc:
        logger.exception(f"恢复上传任务失败，将继续重试队列: {exc}")

    while not _stop_event.is_set():
        try:
            task_id = redis_client.brpoplpush(QUEUE_KEY, PROCESSING_KEY, timeout=1)
            if not task_id:
                continue
            try:
                _process_task(task_id)
            finally:
                redis_client.lrem(PROCESSING_KEY, 0, task_id)
        except Exception as exc:
            logger.exception(f"上传任务工作线程异常: {exc}")
            time.sleep(2)


def start_upload_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="upload-task-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("上传任务工作线程已启动")


def stop_upload_worker() -> None:
    _stop_event.set()
    thread = _worker_thread
    if thread and thread.is_alive():
        thread.join(timeout=2)
