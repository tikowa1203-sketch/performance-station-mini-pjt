from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from .config import settings
from .retriever import HybridRetriever
from .schemas import ContextItem


class PerformanceTools:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or settings.data_dir
        self.retriever = HybridRetriever(self.data_dir)
        self.runs: dict[str, dict[str, Any]] = json.loads(
            (self.data_dir / "test_runs.json").read_text(encoding="utf-8")
        )
        self.incidents: list[dict[str, Any]] = json.loads(
            (self.data_dir / "incidents.json").read_text(encoding="utf-8")
        )

    def retrieve_docs(
        self, question: str, top_k: int = 4, use_expansion: bool = True
    ) -> list[ContextItem]:
        return self.retriever.search(question, top_k=top_k, use_expansion=use_expansion)

    def get_test_run(self, run_id: str) -> dict[str, Any]:
        run_id = run_id.upper()
        return self.runs.get(run_id, {"error": f"테스트 ID {run_id}를 찾을 수 없습니다."})

    def calculate_kpis(self, run: dict[str, Any]) -> dict[str, Any]:
        if "error" in run:
            return run
        target = float(run.get("target_tps", 0))
        actual = float(run.get("actual_tps", 0))
        achievement = actual / target * 100 if target else 0
        checks = {
            "throughput": actual >= target,
            "avg_response": float(run.get("avg_response_sec", 999)) <= 1.0,
            "error_rate": float(run.get("error_rate_pct", 999)) <= 0.1,
            "cpu": float(run.get("was_cpu_pct", 999)) <= 70.0,
        }
        passed = sum(checks.values())
        verdict = "PASS" if passed == 4 else "CONDITIONAL PASS" if passed >= 3 else "FAIL"
        return {
            "achievement_pct": round(achievement, 1),
            "verdict": verdict,
            "checks": checks,
            "headroom_tps": round(max(target - actual, 0), 1),
        }

    def find_similar_incidents(self, text: str, limit: int = 2) -> list[dict[str, Any]]:
        tokens = set(re.findall(r"[가-힣A-Za-z0-9]+", text.lower()))
        ranked: list[tuple[int, dict[str, Any]]] = []
        for incident in self.incidents:
            haystack = " ".join(
                incident["symptoms"] + incident["keywords"] + [incident["service"]]
            ).lower()
            score = sum(1 for token in tokens if token in haystack)
            ranked.append((score, incident))
        return [item for score, item in sorted(ranked, key=lambda x: x[0], reverse=True)[:limit] if score]

    @staticmethod
    def estimate_vusers(tps: float, response_sec: float, think_sec: float) -> dict[str, float]:
        vusers = tps * (response_sec + think_sec)
        return {
            "tps": tps,
            "response_sec": response_sec,
            "think_sec": think_sec,
            "required_vusers": round(vusers),
        }

    @staticmethod
    def draft_change_plan(question: str) -> dict[str, Any]:
        return {
            "requested_change": question,
            "impact": "운영 서비스 처리량과 연결 상태에 영향을 줄 수 있음",
            "prechecks": ["현재 지표 백업", "영향 범위 확인", "롤백 담당자 지정"],
            "rollback": "기존 설정 복원 후 기준 부하로 재검증",
            "execution": "승인 전 실행 금지",
        }

    def as_langchain_tools(self):
        """ReAct 에이전트가 bind_tools 할 수 있는 도메인 도구 목록."""
        toolkit = self

        @tool
        def retrieve_docs(question: str) -> str:
            """성능검증 표준과 런북에서 관련 근거를 검색한다."""
            return json.dumps(
                [item.model_dump() for item in toolkit.retrieve_docs(question)],
                ensure_ascii=False,
            )

        @tool
        def get_test_run(run_id: str) -> str:
            """테스트 ID로 측정 지표를 조회한다."""
            return json.dumps(toolkit.get_test_run(run_id), ensure_ascii=False)

        @tool
        def calculate_vusers(tps: float, response_sec: float, think_sec: float) -> str:
            """목표 TPS 재현에 필요한 VUser를 계산한다."""
            return json.dumps(
                toolkit.estimate_vusers(tps, response_sec, think_sec), ensure_ascii=False
            )

        return [retrieve_docs, get_test_run, calculate_vusers]


RUN_ID_RE = re.compile(r"\b[A-Z]{2,10}-(?:LOAD|MAX|HA)-\d{3}(?![A-Za-z0-9-])", re.I)


def extract_run_id(question: str) -> str | None:
    match = RUN_ID_RE.search(question)
    return match.group(0).upper() if match else None
