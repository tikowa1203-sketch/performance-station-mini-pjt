from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from .schemas import ContextItem


TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9_.%-]+")
QUERY_EXPANSIONS = {
    "티피에스": ["TPS", "처리량"],
    "tps": ["처리량", "throughput"],
    "느려": ["응답시간", "병목", "지연"],
    "cpu": ["자원 사용률", "컴퓨팅 포화"],
    "디비": ["DB", "Connection Pool", "SQL"],
    "db": ["Connection Pool", "SQL", "Wait Event"],
    "죽었": ["장애", "가용성", "Failover"],
    "전환": ["가용성", "L4", "Failover"],
    "임원": ["종합 판정", "보고", "권고"],
}


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    source: str
    text: str
    title: str = ""


def tokenize(text: str) -> list[str]:
    base = [token.lower() for token in TOKEN_RE.findall(text)]
    korean_bigrams: list[str] = []
    for token in base:
        if re.fullmatch(r"[가-힣]{3,}", token):
            korean_bigrams.extend(token[i : i + 2] for i in range(len(token) - 1))
    return base + korean_bigrams


def expand_query(query: str) -> str:
    additions: list[str] = []
    lowered = query.lower()
    for key, values in QUERY_EXPANSIONS.items():
        if key in lowered:
            additions.extend(values)
    return f"{query} {' '.join(dict.fromkeys(additions))}".strip()


MIN_SECTION_BODY_CHARS = 40


def extract_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def merge_short_sections(sections: list[str]) -> list[str]:
    """헤딩만 있고 본문이 거의 없는 절은 다음 절에 합쳐 얇은 청크가 단독으로 상위 랭크되는 것을 막는다."""
    merged: list[str] = []
    buffer = ""
    for section in sections:
        combined = f"{buffer}\n\n{section}".strip() if buffer else section
        body = "\n".join(combined.splitlines()[1:]).strip()
        if len(body) < MIN_SECTION_BODY_CHARS:
            buffer = combined
            continue
        merged.append(combined)
        buffer = ""
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{buffer}".strip()
        else:
            merged.append(buffer)
    return merged


class HybridRetriever:
    """BM25 + 로컬 의미 벡터 + RRF + 근거 리랭킹으로 구성한 경량 RAG."""

    def __init__(self, data_dir: Path, chunk_size: int = 750):
        self.chunks = self._load_chunks(data_dir, chunk_size)
        self.tokenized = [tokenize(chunk.text) for chunk in self.chunks]
        self.bm25 = BM25Okapi(self.tokenized)
        self.doc_vectors = [Counter(tokens) for tokens in self.tokenized]

    @staticmethod
    def _load_chunks(data_dir: Path, chunk_size: int) -> list[Chunk]:
        chunks: list[Chunk] = []
        for path in sorted(data_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = extract_title(text)
            raw_sections = [
                s.strip() for s in re.split(r"(?=^##?\s)", text, flags=re.M) if s.strip()
            ]
            sections = merge_short_sections(raw_sections)
            for index, section in enumerate(sections):
                for offset in range(0, len(section), chunk_size):
                    part = section[offset : offset + chunk_size].strip()
                    if part:
                        chunks.append(
                            Chunk(
                                doc_id=f"{path.stem}:{index}:{offset // chunk_size}",
                                source=path.name,
                                text=part,
                                title=title,
                            )
                        )
        if not chunks:
            raise ValueError(f"검색할 Markdown 문서가 없습니다: {data_dir}")
        return chunks

    def search(self, query: str, top_k: int = 4, use_expansion: bool = True) -> list[ContextItem]:
        expanded = expand_query(query) if use_expansion else query
        query_tokens = tokenize(expanded)
        bm25_scores = self.bm25.get_scores(query_tokens)
        query_vector = Counter(query_tokens)
        semantic_scores = [self._cosine(query_vector, vector) for vector in self.doc_vectors]

        bm25_rank = sorted(range(len(self.chunks)), key=lambda i: bm25_scores[i], reverse=True)
        semantic_rank = sorted(
            range(len(self.chunks)), key=lambda i: semantic_scores[i], reverse=True
        )
        rrf: dict[int, float] = Counter()
        for rank, index in enumerate(bm25_rank[:12], start=1):
            rrf[index] += 1 / (60 + rank)
        for rank, index in enumerate(semantic_rank[:12], start=1):
            rrf[index] += 1 / (60 + rank)

        candidates = sorted(rrf, key=rrf.get, reverse=True)[: max(top_k * 3, 6)]
        query_set = set(query_tokens)

        def rerank(index: int) -> float:
            coverage = len(query_set & set(self.tokenized[index])) / max(len(query_set), 1)
            title_tokens = set(tokenize(self.chunks[index].title))
            title_bonus = 0.15 if query_set & title_tokens else 0
            return rrf[index] + coverage * 0.2 + title_bonus

        ranked = sorted(candidates, key=rerank, reverse=True)[:top_k]
        return [
            ContextItem(
                doc_id=self.chunks[index].doc_id,
                source=self.chunks[index].source,
                text=self.chunks[index].text,
                score=round(rerank(index), 4),
            )
            for index in ranked
        ]

    @staticmethod
    def _cosine(left: Counter[str], right: Counter[str]) -> float:
        dot = sum(value * right.get(key, 0) for key, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

