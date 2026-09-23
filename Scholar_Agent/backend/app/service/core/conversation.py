"""Conversation-memory selection and standalone-query rewriting."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

import jieba
from openai import OpenAI
from sqlalchemy import text

from service.core.rag.utils import encoder, num_tokens_from_string
from utils import logger
from utils.database import get_db
from utils.model_config import get_model_api_key, get_model_base_url


@dataclass(frozen=True)
class ConversationTurn:
    user: str
    assistant: str


@dataclass(frozen=True)
class ConversationContext:
    search_query: str
    recent_turns: list[ConversationTurn]
    relevant_turns: list[ConversationTurn]
    earlier_summary: str


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _truncate_tokens(value: str, budget: int) -> str:
    if budget <= 0:
        return ""
    tokens = encoder.encode(value or "")
    return encoder.decode(tokens[:budget])


def _turn_tokens(turn: ConversationTurn) -> int:
    return num_tokens_from_string(turn.user) + num_tokens_from_string(turn.assistant) + 8


def _fit_newest(turns: list[ConversationTurn], budget: int, limit: int) -> list[ConversationTurn]:
    selected: list[ConversationTurn] = []
    used = 0
    for turn in reversed(turns[-limit:] if limit else []):
        cost = _turn_tokens(turn)
        if selected and used + cost > budget:
            break
        if cost > budget:
            continue
        selected.append(turn)
        used += cost
    return list(reversed(selected))


def _fit_ranked(turns: list[ConversationTurn], budget: int, limit: int) -> list[ConversationTurn]:
    selected: list[ConversationTurn] = []
    used = 0
    for turn in turns:
        cost = _turn_tokens(turn)
        if cost <= budget - used:
            selected.append(turn)
            used += cost
        if len(selected) >= limit:
            break
    return selected


def _terms(value: str) -> set[str]:
    english = re.findall(r"[A-Za-z0-9_]{2,}", value.lower())
    chinese = [token.strip() for token in jieba.lcut(value) if len(token.strip()) >= 2]
    return set(english + chinese)


def _relevance(question: str, turn: ConversationTurn) -> float:
    query_terms = _terms(question)
    if not query_terms:
        return 0.0
    turn_terms = _terms(f"{turn.user} {turn.assistant}")
    return len(query_terms & turn_terms) / max(len(query_terms), 1)


def load_conversation(session_id: str, user_id: str, limit: int = 40) -> list[ConversationTurn]:
    db = next(get_db())
    try:
        owner = db.execute(
            text("SELECT user_id FROM sessions WHERE session_id = :session_id"),
            {"session_id": session_id},
        ).fetchone()
        if owner and str(owner.user_id) != str(user_id):
            raise PermissionError("Session does not belong to the authenticated user")

        rows = db.execute(
            text(
                "SELECT user_question, model_answer FROM messages "
                "WHERE session_id = :session_id ORDER BY created_at DESC LIMIT :limit"
            ),
            {"session_id": session_id, "limit": limit},
        ).fetchall()
        return [
            ConversationTurn(str(row.user_question), str(row.model_answer))
            for row in reversed(rows)
        ]
    finally:
        db.close()


def _client() -> OpenAI:
    return OpenAI(
        api_key=get_model_api_key(),
        base_url=get_model_base_url(),
    )


def _format_turns(turns: list[ConversationTurn]) -> str:
    return "\n".join(
        f"用户：{turn.user}\n助手：{turn.assistant}" for turn in turns
    )


def rewrite_query(question: str, turns: list[ConversationTurn]) -> str:
    """Resolve references/ellipsis without adding facts or answering the question."""
    if not turns:
        return question
    history = _truncate_tokens(
        _format_turns(turns), _env_int("QUERY_REWRITE_HISTORY_TOKENS", 700)
    )
    try:
        completion = _client().chat.completions.create(
            model=os.getenv("CHAT_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是检索查询改写器。仅消解当前问题中的指代和省略，将其改写为可独立检索的查询。"
                        "不得回答问题，不得引入历史中没有出现的新事实；若无需改写，原样返回。只输出查询文本。"
                    ),
                },
                {"role": "user", "content": f"最近对话：\n{history}\n\n当前问题：{question}"},
            ],
            stream=False,
            timeout=30,
        )
        rewritten = (completion.choices[0].message.content or "").strip().strip('"“”')
        return rewritten or question
    except Exception as exc:
        logger.warning("Query rewriting failed; using the original question: %s", exc)
        return question


def summarize_earlier_history(turns: list[ConversationTurn]) -> str:
    if not turns:
        return ""
    output_budget = _env_int("HISTORY_SUMMARY_TOKENS", 300)
    source = _truncate_tokens(
        _format_turns(turns), _env_int("HISTORY_SUMMARY_SOURCE_TOKENS", 2000)
    )
    try:
        completion = _client().chat.completions.create(
            model=os.getenv("CHAT_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "压缩以下较早对话，只保留用户目标、已明确的指代对象和未解决问题。"
                        "历史助手回答可能不准确，不要把它总结为已证实事实。"
                    ),
                },
                {"role": "user", "content": source},
            ],
            stream=False,
            timeout=30,
        )
        return _truncate_tokens(completion.choices[0].message.content or "", output_budget)
    except Exception as exc:
        logger.warning("History summarization failed; using a bounded extract: %s", exc)
        return _truncate_tokens(source, output_budget)


def prepare_conversation_context(
    session_id: str, user_id: str, question: str
) -> ConversationContext:
    turns = load_conversation(
        session_id, user_id, limit=_env_int("HISTORY_MAX_STORED_TURNS", 40)
    )
    if not turns:
        return ConversationContext(question, [], [], "")

    recent = _fit_newest(
        turns,
        _env_int("HISTORY_RECENT_TOKEN_BUDGET", 800),
        _env_int("HISTORY_RECENT_TURNS", 4),
    )
    recent_ids = {id(turn) for turn in recent}
    older = [turn for turn in turns if id(turn) not in recent_ids]

    relevant_candidates = sorted(older, key=lambda turn: _relevance(question, turn), reverse=True)
    relevant_candidates = [turn for turn in relevant_candidates if _relevance(question, turn) > 0]
    relevant = _fit_ranked(
        relevant_candidates,
        _env_int("HISTORY_RELEVANT_TOKEN_BUDGET", 400),
        _env_int("HISTORY_RELEVANT_TURNS", 3),
    )
    relevant_ids = {id(turn) for turn in relevant}
    summary_source = [turn for turn in older if id(turn) not in relevant_ids]

    rewrite_history = [*relevant, *recent]
    return ConversationContext(
        search_query=rewrite_query(question, rewrite_history),
        recent_turns=recent,
        relevant_turns=relevant,
        earlier_summary=summarize_earlier_history(summary_source),
    )
