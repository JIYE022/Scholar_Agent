"""Shared model-provider configuration with legacy environment fallbacks."""
import os


def get_model_api_key() -> str | None:
    return os.getenv("SILICONFLOW_API_KEY") or os.getenv("DASHSCOPE_API_KEY")


def get_model_base_url() -> str:
    return (
        os.getenv("SILICONFLOW_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL")
        or "https://api.siliconflow.cn/v1"
    )
