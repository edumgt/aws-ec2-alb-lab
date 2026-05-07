#!/usr/bin/env python3
"""금융공학 RAG 실습용 Python 예제.

외부 의존성 없이 동작하는 간단한 RAG 파이프라인:
1) 문서 로드
2) 문단 기반 청킹
3) TF-IDF 유사도 검색
4) 근거 포함 응답 생성
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


WORD_RE = re.compile(r"[A-Za-z가-힣0-9%.-]+")
# 토큰이 없는 경우(빈 질의 등) 0으로 나누지 않도록 최소 분모를 1로 고정한다.
MIN_TERM_COUNT = 1
MAX_SNIPPET_LENGTH = 180


@dataclass
class Chunk:
    source: str
    index: int
    text: str


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def load_documents(data_dir: Path) -> list[tuple[str, str]]:
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"데이터 디렉터리를 찾을 수 없습니다: {data_dir}")

    docs: list[tuple[str, str]] = []
    for path in sorted(data_dir.glob("*")):
        if path.suffix.lower() not in {".txt", ".md"}:
            continue
        docs.append((path.name, path.read_text(encoding="utf-8")))

    if not docs:
        raise ValueError(f"문서 파일(.txt/.md)이 없습니다: {data_dir}")
    return docs


def chunk_document(source: str, text: str, max_chars: int) -> list[Chunk]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []

    buffer = ""
    # 출력 시 사람이 읽기 쉽게 source#1 형태를 쓰기 위해 1부터 시작한다.
    chunk_idx = 1
    for para in paragraphs:
        candidate = para if not buffer else f"{buffer}\n\n{para}"
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(Chunk(source=source, index=chunk_idx, text=buffer))
            chunk_idx += 1

        if len(para) <= max_chars:
            buffer = para
        else:
            # max_chars보다 긴 단락은 슬라이싱
            for i in range(0, len(para), max_chars):
                part = para[i : i + max_chars]
                chunks.append(Chunk(source=source, index=chunk_idx, text=part))
                chunk_idx += 1
            buffer = ""

    if buffer:
        chunks.append(Chunk(source=source, index=chunk_idx, text=buffer))

    return chunks


def build_chunks(docs: Iterable[tuple[str, str]], max_chars: int) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for source, content in docs:
        all_chunks.extend(chunk_document(source, content, max_chars=max_chars))
    return all_chunks


def compute_idf(chunks: list[Chunk]) -> dict[str, float]:
    doc_freq: dict[str, int] = {}
    for chunk in chunks:
        unique_tokens = set(tokenize(chunk.text))
        for token in unique_tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1

    n = len(chunks)
    return {token: math.log((1 + n) / (1 + freq)) + 1 for token, freq in doc_freq.items()}


def vectorize(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1

    norm = max(sum(tf.values()), MIN_TERM_COUNT)
    return {token: (count / norm) * idf.get(token, 0.0) for token, count in tf.items()}


def cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    if not v1 or not v2:
        return 0.0

    common = set(v1).intersection(v2)
    dot = sum(v1[t] * v2[t] for t in common)
    n1 = math.sqrt(sum(x * x for x in v1.values()))
    n2 = math.sqrt(sum(x * x for x in v2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def retrieve(query: str, chunks: list[Chunk], top_k: int) -> list[tuple[Chunk, float]]:
    idf = compute_idf(chunks)
    q_vec = vectorize(tokenize(query), idf)

    scored: list[tuple[Chunk, float]] = []
    for chunk in chunks:
        c_vec = vectorize(tokenize(chunk.text), idf)
        score = cosine_sim(q_vec, c_vec)
        if score > 0:
            scored.append((chunk, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def generate_answer(query: str, evidences: list[tuple[Chunk, float]]) -> str:
    if not evidences:
        return (
            "질문과 관련된 근거를 찾지 못했습니다. "
            "문서 범위를 늘리거나 질문을 더 구체화해 주세요."
        )

    lines = [f"질문: {query}", "", "[근거 기반 요약]"]
    for i, (chunk, score) in enumerate(evidences, start=1):
        snippet = chunk.text.replace("\n", " ").strip()
        if len(snippet) > MAX_SNIPPET_LENGTH:
            snippet = snippet[:MAX_SNIPPET_LENGTH] + "..."
        lines.append(
            f"{i}. ({chunk.source}#{chunk.index}, score={score:.3f}) {snippet}"
        )

    lines.extend(
        [
            "",
            "[응답 가이드]",
            "- 위 근거를 기반으로 위험-수익 균형, 분산투자, 시장국면을 함께 설명하세요.",
            "- 실제 의사결정 전에는 최신 데이터와 리스크 한도를 반드시 재검증하세요.",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="금융공학 RAG 실습 CLI")
    parser.add_argument(
        "--data-dir",
        default="ai/financial-rag-python/data",
        help="RAG 문서 디렉터리 경로",
    )
    parser.add_argument("--query", required=True, help="질문 텍스트")
    parser.add_argument("--top-k", type=int, default=3, help="반환할 상위 근거 개수")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=500,
        help="청크 최대 길이(문자 수)",
    )
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k는 1 이상이어야 합니다.")
    if args.max_chars < 100:
        parser.error("--max-chars는 100 이상을 권장합니다.")
    return args


def main() -> None:
    args = parse_args()
    docs = load_documents(Path(args.data_dir))
    chunks = build_chunks(docs, max_chars=args.max_chars)
    evidence = retrieve(args.query, chunks, top_k=args.top_k)
    print(generate_answer(args.query, evidence))


if __name__ == "__main__":
    main()
