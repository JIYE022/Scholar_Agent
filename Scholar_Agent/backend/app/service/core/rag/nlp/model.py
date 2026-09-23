from openai import OpenAI
import numpy as np
from typing import List
import requests

import os
from dotenv import load_dotenv
from utils.model_config import get_model_api_key, get_model_base_url
load_dotenv()

def get_chat_completion_block(session_id, question, references):
    """
    结合知识库内容生成回答，并在回答中标注引用来源。

    :param question: 用户问题
    :param references: 知识库内容，格式为 [{"id": 1, "content": "..."}, ...]
    :return: 模型的回答
    """
    try:
        
        # 初始化 OpenAI 客户端
        client = OpenAI(
            api_key=get_model_api_key(),
            base_url=get_model_base_url()
        )
        # 格式化参考内容
        formatted_references = "\n".join([f"[{ref['id']}] {ref['content']}" for ref in references])
    
        # 构造提示词
        
    
        # 调用模型生成回答
        completion = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
    
        return completion.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"

def rerank_similarity(query: str, texts: List[str], model_name: str | None = None):
    """Score query-document pairs with SiliconFlow's Qwen3 reranker.

    The API sorts its response by relevance, so scores are restored to the
    original candidate order before they are returned.
    """
    if not texts:
        return np.array([], dtype=float), None

    api_key = get_model_api_key()
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY is required for Cross-Encoder reranking")

    model = model_name or os.getenv("RERANK_MODEL", "Qwen/Qwen3-Reranker-4B")
    endpoint = os.getenv(
        "SILICONFLOW_RERANK_URL", "https://api.siliconflow.cn/v1/rerank"
    )
    request_body = {
        "model": model,
        "query": query,
        "documents": texts,
        "instruction": os.getenv(
            "RERANK_INSTRUCTION",
            "Given a research question, rank the passages by how well they answer it.",
        ),
        "top_n": len(texts),
        "return_documents": False,
    }
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=float(os.getenv("RERANK_TIMEOUT_SECONDS", "30")),
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if len(results) != len(texts):
        raise RuntimeError(
            f"Cross-Encoder returned {len(results)} scores for {len(texts)} documents"
        )

    scores = np.zeros(len(texts), dtype=float)
    for item in results:
        index = int(item["index"])
        if index < 0 or index >= len(texts):
            raise RuntimeError(f"Cross-Encoder returned invalid document index {index}")
        scores[index] = float(item["relevance_score"])
    return scores, None




def generate_embedding(text: str | List[str], api_key: str = None, base_url: str = None, model_name: str = "BAAI/bge-m3", encoding_format: str = "float", max_batch_size: int = 10):
    """
    生成文本的向量嵌入
    
    Args:
        text: 单个文本或文本列表
        api_key: API密钥
        base_url: API基础URL
        model_name: 模型名称
        dimensions: 向量维度
        encoding_format: 编码格式
        max_batch_size: 最大批量大小，默认按 10 条请求一批
    
    Returns:
        单个文本时返回向量，文本列表时返回向量列表
    """
    api_key = get_model_api_key()
    base_url = get_model_base_url()

    # 初始化 OpenAI 客户端
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    # 如果是单个文本，直接处理
    if isinstance(text, str):
        try:
            completion = client.embeddings.create(
                model=model_name,
                input=text,
                encoding_format=encoding_format
            )
            return completion.data[0].embedding
        except Exception as e:
            print(f"OpenAI API 请求失败: {e}")
            return None
    
    # 如果是文本列表，需要分批处理
    if isinstance(text, list):
        all_embeddings = []
        
        # 分批处理
        for i in range(0, len(text), max_batch_size):
            batch = text[i:i + max_batch_size]
            
            try:
                completion = client.embeddings.create(
                    model=model_name,
                    input=batch,
                    encoding_format=encoding_format
                )
                
                # 收集这一批的向量
                batch_embeddings = [item.embedding for item in completion.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                print(f"OpenAI API 批量请求失败 (batch {i//max_batch_size + 1}): {e}")
                # 如果批量失败，为这一批添加空向量
                all_embeddings.extend([None] * len(batch))
        
        return all_embeddings


# 示例调用
if __name__ == "__main__":
    # 示例调用
    question = "法国的首都是哪里？"
    references = [
        {"id": 1, "content": "法国的首都是巴黎。"},
        {"id": 2, "content": "巴黎是欧洲的文化中心之一。"},
    ]
    session_id = "sd"
    
    response = get_chat_completion_block(session_id, question, references)
    print(response)
