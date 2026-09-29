"""Structure-aware, token-based chunking for academic PDF parser output."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from service.core.rag.utils import encoder, num_tokens_from_string


POSITION_TAG = re.compile(r"@@(?P<pages>[0-9-]+)\t[0-9.\t]+##")
HEADING = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?(?P<name>abstract|introduction|"
    r"related\s+work|background|method(?:ology)?|approach|experiments?|"
    r"experimental\s+(?:setup|results)|results?(?:\s+and\s+discussion)?|"
    r"discussion|conclusions?|references)\s*[:.]?\s*$", re.I)
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?；;])\s*|(?<=[.])\s+(?=[A-Z0-9])")
CANONICAL = {
    "abstract": "Abstract", "introduction": "Introduction",
    "related work": "Related Work", "background": "Related Work",
    "method": "Method", "methodology": "Method", "approach": "Method",
    "experiment": "Experiments", "experiments": "Experiments",
    "experimental setup": "Experiments", "experimental results": "Results",
    "result": "Results", "results": "Results", "results and discussion": "Results",
    "discussion": "Results", "conclusion": "Conclusion",
    "conclusions": "Conclusion", "references": "References",
}


@dataclass(frozen=True)
class PaperChunk:
    content: str
    section: str
    page: int | None


@dataclass(frozen=True)
class _Unit:
    text: str
    # Headings, tables and short paragraphs are atomic context, not overlap material.
    overlap_eligible: bool


def recognize_section(text: str) -> str | None:
    candidate = re.sub(r"\s+", " ", POSITION_TAG.sub("", text).strip())
    match = HEADING.match(candidate)
    return CANONICAL[match.group("name").lower()] if match else None


def _is_table(text: str) -> bool:
    body = POSITION_TAG.sub("", text).strip()
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines:
        return False
    pipe_rows = sum(line.count("|") >= 2 for line in lines)
    tab_rows = sum("\t" in line for line in lines)
    return pipe_rows >= 2 or tab_rows >= 2


def _token_slices(text: str, limit: int, suffix: str = "") -> list[str]:
    """Hard fallback for a single sentence longer than the token budget."""
    suffix_tokens = num_tokens_from_string(suffix)
    content_limit = max(1, limit - suffix_tokens)
    tokens = encoder.encode(text)
    return [
        f"{encoder.decode(tokens[i:i + content_limit]).strip()}{suffix}"
        for i in range(0, len(tokens), content_limit)
    ]


def _semantic_units(text: str, limit: int, *, heading: bool = False) -> list[_Unit]:
    tag_text = "".join(match.group(0) for match in POSITION_TAG.finditer(text))
    body = POSITION_TAG.sub("", text).strip()
    if not body:
        return []
    tagged = f"{body}{tag_text}"
    token_count = num_tokens_from_string(tagged)
    short_paragraph = token_count <= max(12, round(limit * 0.18))
    if heading or _is_table(text) or short_paragraph:
        return [_Unit(tagged, False)]

    sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(body) if part.strip()]
    units: list[_Unit] = []
    for sentence in sentences or [body]:
        sentence_with_position = f"{sentence}{tag_text}"
        if num_tokens_from_string(sentence_with_position) <= limit:
            units.append(_Unit(sentence_with_position, True))
        else:
            # A pathological long sentence cannot keep a sentence boundary. Token
            # slicing is deterministic and still guarantees the configured limit.
            units.extend(
                _Unit(part, True) for part in _token_slices(sentence, limit, tag_text)
            )
    return units


def _trailing_overlap(units: list[_Unit], target_tokens: int) -> list[_Unit]:
    selected: list[_Unit] = []
    used = 0
    for unit in reversed(units):
        if not unit.overlap_eligible:
            break
        size = num_tokens_from_string(unit.text)
        # Prefer a complete sentence near 10%; never let overlap consume a large
        # fraction of the next chunk merely because the last sentence is long.
        if size > max(target_tokens * 2, 1) or (selected and used + size > target_tokens):
            break
        selected.append(unit)
        used += size
        if used >= target_tokens:
            break
    return list(reversed(selected))


def _split_section(paragraphs: list[tuple[str, bool]], limit: int, overlap_ratio: float) -> list[str]:
    all_units: list[_Unit] = []
    for paragraph, is_heading in paragraphs:
        all_units.extend(_semantic_units(paragraph, limit, heading=is_heading))

    chunks: list[str] = []
    current: list[_Unit] = []
    overlap_target = max(1, round(limit * overlap_ratio))

    def content(items: list[_Unit]) -> str:
        return "\n".join(item.text for item in items).strip()

    for unit in all_units:
        candidate = content([*current, unit])
        if current and num_tokens_from_string(candidate) > limit:
            chunks.append(content(current))
            overlap = _trailing_overlap(current, overlap_target)
            if overlap and num_tokens_from_string(content([*overlap, unit])) <= limit:
                current = [*overlap, unit]
            else:
                current = [unit]
        else:
            current.append(unit)
    if current:
        chunks.append(content(current))
    return chunks


def structure_aware_chunks(
    sections: Iterable[tuple[str, str]],
    max_tokens: int = 512,
    overlap_ratio: float = 0.10,
) -> list[PaperChunk]:
    """Chunk within recognized paper sections using tokens and sentence overlap.

    Overlap is computed independently for every section, so content from e.g.
    ``Method`` can never leak into ``Experiments``. Unstructured/scanned input
    returns an empty list and keeps the existing general chunker fallback.
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if not 0 <= overlap_ratio < 1:
        raise ValueError("overlap_ratio must be in [0, 1)")

    groups: list[tuple[str, list[tuple[str, bool]]]] = []
    recognized = 0
    for text, position in sections:
        heading = recognize_section(text)
        tagged = text if POSITION_TAG.search(text) else text + (position or "")
        if heading:
            recognized += 1
            groups.append((heading, [(tagged, True)]))
        else:
            if not groups:
                groups.append(("Front Matter", []))
            groups[-1][1].append((tagged, False))

    if recognized < 2:
        return []

    result: list[PaperChunk] = []
    for name, paragraphs in groups:
        for content in _split_section(paragraphs, max_tokens, overlap_ratio):
            match = POSITION_TAG.search(content)
            page = int(match.group("pages").split("-")[0]) if match else None
            result.append(PaperChunk(content, name, page))
    return result
