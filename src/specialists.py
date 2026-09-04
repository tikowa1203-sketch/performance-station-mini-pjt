from __future__ import annotations

from dataclasses import dataclass

from .schemas import Route


@dataclass(frozen=True)
class SpecialistSpec:
    name: str
    route: Route
    mission: str
    default_tools: tuple[str, ...]


# 수평 확장의 핵심: 새 기능은 SpecialistSpec과 Tool을 옆으로 추가한다.
SPECIALISTS = {
    Route.KNOWLEDGE: SpecialistSpec(
        "Knowledge Agent",
        Route.KNOWLEDGE,
        "표준·런북을 검색해 절차와 근거를 설명",
        ("retrieve_docs",),
    ),
    Route.ANALYSIS: SpecialistSpec(
        "Analysis Agent",
        Route.ANALYSIS,
        "테스트 지표를 계산하고 유사 장애와 비교해 병목 가설 작성",
        ("get_test_run", "calculate_kpis", "find_similar_incidents", "retrieve_docs"),
    ),
    Route.REPORT: SpecialistSpec(
        "Report Agent",
        Route.REPORT,
        "측정 결과를 결론 우선의 5문장 보고로 변환",
        ("get_test_run", "calculate_kpis", "retrieve_docs"),
    ),
    Route.CHANGE: SpecialistSpec(
        "Change Agent",
        Route.CHANGE,
        "위험 변경의 영향·사전 점검·롤백 계획을 만들고 승인 요청",
        ("retrieve_docs", "draft_change_plan"),
    ),
}

