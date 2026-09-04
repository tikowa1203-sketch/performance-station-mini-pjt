from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import PerformanceStationAgent  # noqa: E402
from src.config import settings  # noqa: E402
from src.retriever import tokenize  # noqa: E402


@dataclass
class CaseResult:
    id: str
    category: str
    passed: bool
    trait_score: float
    tools_ok: bool
    forbidden_ok: bool
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    tools_used: list[str]
    missing_traits: list[str]
    answer: str


def terms(text: str) -> set[str]:
    return set(tokenize(text))


def trait_hit(trait: str, answer: str) -> bool:
    """오프라인 LLM-as-Judge 대체: 핵심 내용어의 50% 이상 또는 구문 일치."""
    if trait.lower() in answer.lower():
        return True
    expected = {term for term in terms(trait) if len(term) > 1}
    actual = terms(answer)
    return bool(expected) and len(expected & actual) / len(expected) >= 0.5


def overlap(left: str, right: str) -> float:
    left_terms, right_terms = terms(left), terms(right)
    if not left_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms)


def judge(row: dict[str, str], response) -> CaseResult:
    expected_traits = [item.strip() for item in row["expected_traits"].split(";") if item.strip()]
    missing = [trait for trait in expected_traits if not trait_hit(trait, response.answer)]
    trait_score = 1 - len(missing) / max(len(expected_traits), 1)

    expected_tools = {item.strip() for item in row["expected_tools"].split(";") if item.strip()}
    tools_ok = expected_tools.issubset(set(response.tools_used))
    forbidden = [item.strip() for item in row["forbidden"].split(";") if item.strip()]
    forbidden_ok = not any(item.lower() in response.answer.lower() for item in forbidden)

    context_scores = [overlap(row["input"], item.text) for item in response.contexts]
    context_precision = (
        sum(score >= 0.05 for score in context_scores) / len(context_scores)
        if context_scores
        else (1.0 if not expected_tools or "retrieve_docs" not in expected_tools else 0.0)
    )
    joined_context = " ".join(item.text for item in response.contexts)
    context_recall = min(1.0, overlap(" ".join(expected_traits), joined_context) * 2.0)
    if not response.contexts and "retrieve_docs" not in expected_tools:
        context_recall = 1.0

    evidence_text = joined_context + " " + " ".join(
        json.dumps(item.output, ensure_ascii=False, default=str) for item in response.trace
        if item.step.startswith("tool.")
    )
    faithfulness = min(1.0, overlap(response.answer, evidence_text) * 1.8 + 0.25)
    answer_relevancy = min(1.0, overlap(row["input"] + " " + row["expected_traits"], response.answer) * 1.8)

    passed = trait_score >= 0.65 and tools_ok and forbidden_ok
    return CaseResult(
        id=row["id"],
        category=row["category"],
        passed=passed,
        trait_score=round(trait_score, 3),
        tools_ok=tools_ok,
        forbidden_ok=forbidden_ok,
        context_precision=round(context_precision, 3),
        context_recall=round(context_recall, 3),
        faithfulness=round(faithfulness, 3),
        answer_relevancy=round(answer_relevancy, 3),
        tools_used=response.tools_used,
        missing_traits=missing,
        answer=response.answer,
    )


def mean(items: list[CaseResult], field: str) -> float:
    return round(sum(getattr(item, field) for item in items) / max(len(items), 1), 3)


def render_report(profile: str, results: list[CaseResult], use_bedrock: bool) -> str:
    passed = sum(item.passed for item in results)
    metrics = {
        "context_precision": mean(results, "context_precision"),
        "context_recall": mean(results, "context_recall"),
        "faithfulness": mean(results, "faithfulness"),
        "answer_relevancy": mean(results, "answer_relevancy"),
    }
    mode_note = (
        "> 이 리포트는 실제 AWS Bedrock 호출로 생성한 결과입니다(USE_BEDROCK=true). "
        "RAGAS 지표는 자체 Judge 기반 근사치이며, RAGAS 라이브러리로 재계산하려면 "
        "`ragas_evaluate.py`를 실행합니다."
        if use_bedrock
        else "> 이 리포트는 자격증명 없이 재현 가능한 RAGAS 호환 오프라인 프록시 평가입니다. "
        "실제 RAGAS+Bedrock 평가는 `ragas_evaluate.py`로 별도 실행합니다."
    )
    lines = [
        f"# {profile} RAGAS 평가 리포트",
        "",
        mode_note,
        "",
        "## 요약",
        "",
        f"- 인-아웃 세트 통과: **{passed}/{len(results)} ({passed / len(results) * 100:.1f}%)**",
        f"- context_precision: **{metrics['context_precision']:.3f}**",
        f"- context_recall: **{metrics['context_recall']:.3f}**",
        f"- faithfulness: **{metrics['faithfulness']:.3f}**",
        f"- answer_relevancy: **{metrics['answer_relevancy']:.3f}**",
        "",
        "## 케이스별 결과",
        "",
        "| ID | 분류 | 통과 | Trait | Tool | 금지어 | 누락 Trait |",
        "|---:|---|:---:|---:|:---:|:---:|---|",
    ]
    for item in results:
        lines.append(
            f"| {item.id} | {item.category} | {'PASS' if item.passed else 'FAIL'} | "
            f"{item.trait_score:.2f} | {'Y' if item.tools_ok else 'N'} | "
            f"{'Y' if item.forbidden_ok else 'N'} | {', '.join(item.missing_traits) or '-'} |"
        )
    lines += [
        "",
        "## 해석",
        "",
        "- `round1`: 키워드 검색과 최소 도구만 사용한 기준선입니다.",
        "- `round2`: 쿼리 확장·하이브리드 검색·KPI 계산·유사 장애 비교·가드레일을 결합한 개선 버전입니다.",
        "- 프록시 지표는 빠른 회귀 테스트용이며 제출 직전 AWS 자격증명 환경에서 실제 RAGAS를 실행해야 합니다.",
    ]
    return "\n".join(lines) + "\n"


def run(profile: str) -> list[CaseResult]:
    agent = PerformanceStationAgent(profile=profile)
    with (PROJECT_ROOT / "evaluation/test_queries.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return [judge(row, agent.query(row["input"], f"eval-{profile}-{row['id']}")) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["round1", "round2", "all"], default="all")
    args = parser.parse_args()
    profiles = ["round1", "round2"] if args.profile == "all" else [args.profile]
    result_dir = PROJECT_ROOT / "evaluation/results"
    result_dir.mkdir(parents=True, exist_ok=True)
    for profile in profiles:
        results = run(profile)
        (PROJECT_ROOT / f"evaluation/{profile}_report.md").write_text(
            render_report(profile, results, settings.use_bedrock), encoding="utf-8"
        )
        (result_dir / f"{profile}.json").write_text(
            json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{profile}: {sum(item.passed for item in results)}/{len(results)} passed")


if __name__ == "__main__":
    main()
