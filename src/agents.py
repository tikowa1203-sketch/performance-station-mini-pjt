from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from .config import Settings
from .schemas import AnswerDraft, Route, RouteDecision
from .specialists import SPECIALISTS

VALID_TOOLS = frozenset(
    {
        "retrieve_docs",
        "get_test_run",
        "calculate_kpis",
        "find_similar_incidents",
        "estimate_vusers",
        "draft_change_plan",
    }
)


@dataclass(frozen=True)
class ExecutionPlan:
    route: Route
    steps: list[str]
    tools: list[str]


class Supervisor:
    """결정적 기본 라우팅과 선택적 LLM 구조화 라우팅을 제공한다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def route(self, question: str, risky_action: bool = False) -> RouteDecision:
        if risky_action:
            return RouteDecision(
                route=Route.CHANGE,
                reason="운영 변경 가능성이 있는 요청",
                tools=["retrieve_docs", "draft_change_plan"],
            )
        if self.settings.use_bedrock:
            return self._llm_route(question)
        return self._rule_route(question)

    @staticmethod
    def _rule_route(question: str) -> RouteDecision:
        lowered = question.lower()
        if any(word in lowered for word in ("임원", "보고용", "5문장", "요약 보고")):
            return RouteDecision(
                route=Route.REPORT,
                reason="의사결정자용 보고 요청",
                tools=["get_test_run", "calculate_kpis", "retrieve_docs"],
            )
        if re.search(r"\b[A-Z]{2,10}-(?:LOAD|MAX|HA)-\d{3}(?![A-Za-z0-9-])", question, re.I) or any(
            word in lowered
            for word in ("원인 분석", "병목", "성능 결과", "pass", "fail", "판정")
        ):
            return RouteDecision(
                route=Route.ANALYSIS,
                reason="테스트 지표 분석 또는 판정 요청",
                tools=[
                    "get_test_run",
                    "calculate_kpis",
                    "find_similar_incidents",
                    "retrieve_docs",
                ],
            )
        return RouteDecision(
            route=Route.KNOWLEDGE,
            reason="성능검증 지식 또는 절차 문의",
            tools=["retrieve_docs"],
        )

    def _llm_route(self, question: str) -> RouteDecision:
        from langchain_aws import ChatBedrockConverse

        llm = ChatBedrockConverse(
            model=self.settings.model_id,
            region_name=self.settings.region,
            temperature=0,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "성능검증 문의를 knowledge, analysis, report, change 중 하나로 분류하라. "
                    "운영 변경은 change다. "
                    "tools 필드에는 반드시 다음 도구 이름 중에서만 정확히 그대로(철자·대소문자 동일) "
                    "골라서 넣는다. 목록에 없는 이름은 절대 만들어내지 않는다: "
                    "retrieve_docs(문서 검색), get_test_run(테스트 ID 조회), "
                    "calculate_kpis(KPI/PASS-FAIL 계산, get_test_run 결과 필요), "
                    "find_similar_incidents(유사 장애 검색), "
                    "estimate_vusers(VUser 계산), draft_change_plan(변경 계획 작성).",
                ),
                ("human", "{question}"),
            ]
        )
        # Day 1 LCEL + Pydantic 구조화 출력 패턴
        chain = prompt | llm.with_structured_output(RouteDecision)
        return chain.invoke({"question": question})

    @staticmethod
    def make_plan(decision: RouteDecision, profile: str = "round2") -> ExecutionPlan:
        # LLM 구조화 라우팅은 Route 전체를 반환할 수 있어 BLOCKED 등 미등록 라우트가 들어올 수 있다.
        specialist = SPECIALISTS.get(decision.route, SPECIALISTS[Route.KNOWLEDGE])
        # LLM이 존재하지 않는 도구 이름을 지어낼 수 있어 알려진 도구만 신뢰한다.
        # Specialist의 기본 도구는 해당 Route의 완전한 근거 수집 계약이므로 항상 포함하고,
        # LLM이 추가로 요청한 유효한 도구가 있으면 덧붙인다(LLM이 일부만 골라도 누락되지 않도록).
        requested = [tool for tool in decision.tools if tool in VALID_TOOLS]
        tools = list(dict.fromkeys([*specialist.default_tools, *requested]))
        if profile == "round1":
            tools = [tool for tool in tools if tool in {"retrieve_docs", "get_test_run"}]
        steps = ["질문 안전성 검사", f"{specialist.name} 선택: {specialist.mission}"]
        steps.extend(f"{tool} 실행" for tool in tools)
        steps.append("근거와 불확실성을 분리해 답변 작성")
        return ExecutionPlan(specialist.route, steps, tools)


class BedrockSynthesizer:
    """운영 모드에서 Tool 결과를 구조화 답변으로 합성한다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def synthesize(
        self, question: str, route: Route, evidence: dict[str, Any], memory: str
    ) -> AnswerDraft:
        from langchain_aws import ChatBedrockConverse

        llm = ChatBedrockConverse(
            model=self.settings.model_id,
            region_name=self.settings.region,
            temperature=0,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 Performance Station 성능검증 전문가다. 제공된 근거(evidence)만 사용하며 "
                    "근거에 없는 수치나 절차는 만들어내지 않는다. "
                    "question이 요구한 값(TPS, 응답시간, 오류율, CPU 등 evidence에 있는 수치)은 summary나 "
                    "evidence 항목에 빠짐없이 그대로 포함한다. "
                    "VUser를 계산한 경우 계산식과 함께 '반올림 기준'(예: 소수점 첫째 자리에서 반올림)을 "
                    "evidence 또는 summary에 명시한다. "
                    "문서를 따옴표로 직접 인용할 때는 evidence의 documents 항목에 실제로 등장하는 "
                    "문구만 그대로 인용하고, 근거에 없는 문장을 지어내 특정 문서나 '표준 가이드'를 "
                    "출처로 붙이지 않는다. 정확한 원문이 없으면 따옴표 인용 대신 자신의 말로 설명한다. "
                    "관측 사실, 가설, 확인 방법을 구분하고 근거가 없으면 모른다고 답한다. "
                    "운영 변경은 승인 전 실행했다고 표현하지 않는다.",
                ),
                (
                    "human",
                    "route={route}\nquestion={question}\nmemory={memory}\nevidence={evidence}",
                ),
            ]
        )
        chain = prompt | llm.with_structured_output(AnswerDraft)
        return chain.invoke(
            {
                "route": route.value,
                "question": question,
                "memory": memory or "없음",
                "evidence": json.dumps(evidence, ensure_ascii=False),
            }
        )


def render_draft(draft: AnswerDraft) -> str:
    lines = [f"종합 판단: {draft.verdict}", "", draft.summary]
    if draft.evidence:
        lines += ["", "근거"] + [f"- {item}" for item in draft.evidence]
    if draft.recommendations:
        lines += ["", "권고"] + [f"- {item}" for item in draft.recommendations]
    if draft.uncertainty:
        lines += ["", f"유의사항: {draft.uncertainty}"]
    return "\n".join(lines)
