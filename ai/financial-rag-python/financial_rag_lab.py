#!/usr/bin/env python3
"""금융공학 RAG 실습용 Python 예제.

외부 의존성 없이 동작하는 간단한 RAG 파이프라인:
1) 문서 로드
2) 문단 기반 청킹
3) TF-IDF 유사도 검색
4) 근거 포함 응답 생성
"""

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse  # 커맨드라인 인수 파싱 라이브러리 (--query, --top-k 등)
import math      # log, sqrt 함수 — TF-IDF 계산에 사용합니다
import re        # 정규식 — 텍스트에서 토큰(단어) 추출에 사용합니다
from dataclasses import dataclass  # @dataclass 데코레이터 — 청크 구조체 정의에 사용합니다
from pathlib import Path            # 파일/디렉터리 경로 조작 및 파일 읽기용
from typing import Iterable         # 타입 힌트: Iterable 제네릭 타입


# 한글·영문·숫자·특수문자(%, -, .)를 포함한 토큰 추출용 정규식
WORD_RE = re.compile(r"[A-Za-z가-힣0-9%.-]+")
# 토큰이 없는 경우(빈 질의 등) 0으로 나누지 않도록 최소 분모를 1로 고정한다.
MIN_TERM_COUNT = 1
# 응답 생성 시 각 청크에서 표시할 최대 텍스트 길이 (문자 수)
MAX_SNIPPET_LENGTH = 180


@dataclass
class Chunk:
    """하나의 문서 청크를 나타내는 데이터 클래스."""
    source: str   # 출처 파일 이름 (예: "market_report.txt")
    index: int    # 같은 소스 내 청크 순서 번호 (1부터 시작)
    text: str     # 청크의 실제 텍스트 내용


def tokenize(text: str) -> list[str]:
    """텍스트를 소문자 토큰 목록으로 변환합니다.

    WORD_RE 정규식으로 한글·영문·숫자 단어를 추출하고 소문자로 정규화합니다.
    """
    return [w.lower() for w in WORD_RE.findall(text)]  # 정규식 매칭 후 소문자 변환


def load_documents(data_dir: Path) -> list[tuple[str, str]]:
    """지정 디렉터리에서 .txt/.md 파일을 모두 로드하여 (파일명, 내용) 튜플 목록을 반환합니다.

    Raises:
        FileNotFoundError: 디렉터리가 존재하지 않거나 디렉터리가 아닌 경우
        ValueError: 디렉터리에 .txt/.md 파일이 없는 경우
    """
    if not data_dir.exists() or not data_dir.is_dir():
        # 디렉터리가 없거나 경로가 디렉터리가 아닌 경우 예외 발생
        raise FileNotFoundError(f"데이터 디렉터리를 찾을 수 없습니다: {data_dir}")

    docs: list[tuple[str, str]] = []
    for path in sorted(data_dir.glob("*")):  # 알파벳 순으로 정렬하여 모든 파일 순회
        if path.suffix.lower() not in {".txt", ".md"}:  # .txt/.md 이외 파일 건너뜀
            continue
        docs.append((path.name, path.read_text(encoding="utf-8")))
        # (파일명, UTF-8 인코딩 텍스트) 튜플을 목록에 추가

    if not docs:
        # 유효한 파일이 없으면 예외 발생
        raise ValueError(f"문서 파일(.txt/.md)이 없습니다: {data_dir}")
    return docs  # 로드된 문서 목록 반환


def chunk_document(source: str, text: str, max_chars: int) -> list[Chunk]:
    """하나의 문서 텍스트를 문단(빈 줄 기준) 단위로 청킹합니다.

    문단을 buffer에 누적하다가 max_chars를 초과하면 청크를 확정합니다.
    max_chars보다 긴 단락은 슬라이싱하여 분리합니다.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # 빈 줄("\n\n")을 기준으로 문단 분리, 앞뒤 공백 제거, 빈 문단 제외
    chunks: list[Chunk] = []  # 결과 청크 목록 초기화

    buffer = ""  # 현재 누적 중인 텍스트 버퍼
    # 출력 시 사람이 읽기 쉽게 source#1 형태를 쓰기 위해 1부터 시작한다.
    chunk_idx = 1  # 청크 순서 번호 (source 내에서 1부터 시작)
    for para in paragraphs:  # 각 문단에 대해 순서대로 처리
        candidate = para if not buffer else f"{buffer}\n\n{para}"
        # 버퍼가 있으면 현재 문단을 추가한 후보 문자열 생성, 없으면 문단 자체가 후보
        if len(candidate) <= max_chars:
            # 후보 길이가 max_chars 이하이면 버퍼에 누적 (아직 청크 확정 안 함)
            buffer = candidate
            continue

        if buffer:
            # 버퍼가 있을 때 현재 문단을 추가하면 초과 → 버퍼를 청크로 확정
            chunks.append(Chunk(source=source, index=chunk_idx, text=buffer))
            chunk_idx += 1  # 청크 순서 번호 증가

        if len(para) <= max_chars:
            # 현재 문단 자체가 max_chars 이하이면 새 버퍼로 설정
            buffer = para
        else:
            # max_chars보다 긴 단락은 슬라이싱
            for i in range(0, len(para), max_chars):
                part = para[i : i + max_chars]  # max_chars 크기로 슬라이싱
                chunks.append(Chunk(source=source, index=chunk_idx, text=part))
                chunk_idx += 1
            buffer = ""  # 슬라이싱 처리 후 버퍼 초기화

    if buffer:
        # 마지막 남은 버퍼를 청크로 확정
        chunks.append(Chunk(source=source, index=chunk_idx, text=buffer))

    return chunks  # 생성된 청크 목록 반환


def build_chunks(docs: Iterable[tuple[str, str]], max_chars: int) -> list[Chunk]:
    """여러 문서를 청킹하여 하나의 청크 목록으로 합칩니다."""
    all_chunks: list[Chunk] = []  # 전체 청크를 담을 리스트 초기화
    for source, content in docs:  # 각 (파일명, 내용) 튜플 처리
        all_chunks.extend(chunk_document(source, content, max_chars=max_chars))
        # 각 문서의 청크를 전체 목록에 추가
    return all_chunks


def compute_idf(chunks: list[Chunk]) -> dict[str, float]:
    """전체 청크에서 각 토큰의 IDF(역문서 빈도) 값을 계산합니다.

    IDF = log((1 + N) / (1 + df)) + 1  (스무딩 적용)
    N: 전체 청크 수, df: 해당 토큰이 등장한 청크 수
    """
    doc_freq: dict[str, int] = {}  # 토큰 → 등장 청크 수 매핑
    for chunk in chunks:           # 각 청크에 대해
        unique_tokens = set(tokenize(chunk.text))  # 중복 제거된 토큰 집합
        for token in unique_tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1  # 해당 토큰의 문서 빈도 증가

    n = len(chunks)  # 전체 청크 수
    return {token: math.log((1 + n) / (1 + freq)) + 1 for token, freq in doc_freq.items()}
    # 스무딩 처리된 IDF 값 계산: 빈도 높을수록 낮은 값(희귀 단어일수록 높은 값)


def vectorize(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """토큰 목록을 TF-IDF 벡터(토큰 → 가중치 딕셔너리)로 변환합니다.

    TF(단어 빈도) = 토큰 등장 횟수 / 총 토큰 수
    TF-IDF = TF × IDF
    """
    tf: dict[str, int] = {}  # 토큰 → 등장 횟수 매핑
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1  # 각 토큰의 등장 횟수 계산

    norm = max(sum(tf.values()), MIN_TERM_COUNT)
    # 총 토큰 수 (0으로 나누기 방지를 위해 최소값 MIN_TERM_COUNT=1 보장)
    return {token: (count / norm) * idf.get(token, 0.0) for token, count in tf.items()}
    # 각 토큰의 TF(count/norm)에 IDF를 곱하여 TF-IDF 벡터 반환 (IDF 없는 토큰은 0)


def cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    """두 TF-IDF 벡터 간의 코사인 유사도를 계산하여 반환합니다.

    코사인 유사도 = 내적(dot product) / (||v1|| × ||v2||)
    두 벡터 중 하나라도 비어 있거나 크기가 0이면 0.0을 반환합니다.
    """
    if not v1 or not v2:   # 빈 벡터 처리 (유사도 0)
        return 0.0

    common = set(v1).intersection(v2)   # 두 벡터에 공통으로 존재하는 토큰 집합
    dot = sum(v1[t] * v2[t] for t in common)  # 공통 토큰에 대해서만 내적 계산
    n1 = math.sqrt(sum(x * x for x in v1.values()))  # v1의 L2 노름(크기)
    n2 = math.sqrt(sum(x * x for x in v2.values()))  # v2의 L2 노름(크기)
    if n1 == 0 or n2 == 0:  # 벡터 크기가 0이면 나눗셈 불가 → 유사도 0 반환
        return 0.0
    return dot / (n1 * n2)  # 코사인 유사도 = 내적 / (크기의 곱)


def retrieve(query: str, chunks: list[Chunk], top_k: int) -> list[tuple[Chunk, float]]:
    """질문과 가장 유사한 상위 top_k 청크를 TF-IDF 코사인 유사도 기준으로 반환합니다."""
    idf = compute_idf(chunks)                   # 전체 청크 기반 IDF 사전 계산
    q_vec = vectorize(tokenize(query), idf)     # 질문 텍스트를 TF-IDF 벡터로 변환

    scored: list[tuple[Chunk, float]] = []  # (청크, 유사도 점수) 쌍의 목록
    for chunk in chunks:
        c_vec = vectorize(tokenize(chunk.text), idf)  # 청크 텍스트를 TF-IDF 벡터로 변환
        score = cosine_sim(q_vec, c_vec)              # 질문 벡터와 청크 벡터 간 코사인 유사도 계산
        if score > 0:                                 # 유사도가 0보다 큰 청크만 후보에 포함
            scored.append((chunk, score))

    scored.sort(key=lambda item: item[1], reverse=True)  # 유사도 내림차순 정렬 (가장 관련 있는 청크 먼저)
    return scored[:top_k]  # 상위 top_k개 반환


def generate_answer(query: str, evidences: list[tuple[Chunk, float]]) -> str:
    """검색된 근거 청크를 바탕으로 응답 텍스트를 생성하여 반환합니다.

    근거 청크가 없으면 재시도를 안내하는 메시지를 반환합니다.
    """
    if not evidences:
        # 관련 청크가 없으면 검색 범위 확대 또는 질문 구체화 안내 메시지 반환
        return (
            "질문과 관련된 근거를 찾지 못했습니다. "
            "문서 범위를 늘리거나 질문을 더 구체화해 주세요."
        )

    lines = [f"질문: {query}", "", "[근거 기반 요약]"]  # 응답 헤더 라인 초기화
    for i, (chunk, score) in enumerate(evidences, start=1):  # 근거 청크를 1번부터 순서대로 출력
        snippet = chunk.text.replace("\n", " ").strip()  # 줄바꿈을 공백으로 변환하여 한 줄로 표시
        if len(snippet) > MAX_SNIPPET_LENGTH:
            snippet = snippet[:MAX_SNIPPET_LENGTH] + "..."  # 최대 길이 초과 시 "..."으로 생략
        lines.append(
            f"{i}. ({chunk.source}#{chunk.index}, score={score:.3f}) {snippet}"
            # 순서 번호·출처·청크 번호·유사도 점수·텍스트 스니펫 형식으로 출력
        )

    lines.extend(
        [
            "",
            "[응답 가이드]",
            "- 위 근거를 기반으로 위험-수익 균형, 분산투자, 시장국면을 함께 설명하세요.",
            # 금융공학 관점에서 응답 시 고려해야 할 핵심 개념 안내
            "- 실제 의사결정 전에는 최신 데이터와 리스크 한도를 반드시 재검증하세요.",
            # RAG 결과는 참고용임을 명시하는 면책 안내
        ]
    )
    return "\n".join(lines)  # 모든 라인을 줄바꿈으로 연결하여 최종 응답 문자열 반환


def parse_args() -> argparse.Namespace:
    """커맨드라인 인수를 파싱하고 유효성을 검사하여 반환합니다."""
    parser = argparse.ArgumentParser(description="금융공학 RAG 실습 CLI")
    parser.add_argument(
        "--data-dir",
        default="ai/financial-rag-python/data",  # 기본 문서 디렉터리 경로
        help="RAG 문서 디렉터리 경로",
    )
    parser.add_argument("--query", required=True, help="질문 텍스트")  # 필수 인수: 검색 질문
    parser.add_argument("--top-k", type=int, default=3, help="반환할 상위 근거 개수")
    # 반환할 최상위 관련 청크 수 (기본값: 3)
    parser.add_argument(
        "--max-chars",
        type=int,
        default=500,
        help="청크 최대 길이(문자 수)",  # 하나의 청크가 가질 수 있는 최대 문자 수
    )
    args = parser.parse_args()  # 커맨드라인 인수 파싱 실행

    if args.top_k < 1:
        parser.error("--top-k는 1 이상이어야 합니다.")  # top_k가 0 이하이면 오류
    if args.max_chars < 100:
        parser.error("--max-chars는 100 이상을 권장합니다.")  # 청크가 너무 작으면 오류
    return args


def main() -> None:
    """메인 실행 함수: 인수 파싱 → 문서 로드 → 청킹 → 검색 → 응답 출력."""
    args = parse_args()                                           # 커맨드라인 인수 파싱
    docs = load_documents(Path(args.data_dir))                    # 데이터 디렉터리에서 문서 로드
    chunks = build_chunks(docs, max_chars=args.max_chars)         # 문서를 청크로 분할
    evidence = retrieve(args.query, chunks, top_k=args.top_k)     # TF-IDF 유사도로 관련 청크 검색
    print(generate_answer(args.query, evidence))                  # 근거 기반 응답 생성 및 출력


if __name__ == "__main__":
    main()  # 스크립트를 직접 실행할 때만 main() 호출
