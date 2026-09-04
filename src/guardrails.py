from __future__ import annotations

import re
from dataclasses import dataclass


INJECTION_PATTERNS = (
    r"이전\s*(지시|명령).*무시",
    r"system\s*(prompt|message)",
    r"시스템\s*프롬프트",
    r"ignore\s+(all|previous)",
    r"reveal\s+(your|the)\s+prompt",
    r"DAN\b",
)

SECRET_PATTERNS = (
    r"api\s*key",
    r"access\s*key",
    r"secret\s*key",
    r"비밀번호",
    r"패스워드",
    r"토큰",
    r"주민\s*(등록)?\s*번호",
    r"(?:개인|직원|담당자|온콜).*전화번호",
)

RISKY_ACTION_PATTERNS = (
    r"운영.*(재기동|중지|롤백|변경|배포)",
    r"(설정|pool|thread).*(바꿔|변경|적용)",
    r"트래픽.*(전환|차단)",
    r"DB.*(재기동|kill|종료)",
)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    sanitized_text: str
    reason: str = ""
    risky_action: bool = False


def mask_pii(text: str) -> str:
    """출력과 로그에 남을 수 있는 대표 개인정보를 마스킹한다."""
    text = re.sub(r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)", "[PHONE]", text)
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text
    )
    text = re.sub(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)", "[RRN]", text)
    return text


def inspect_input(text: str) -> GuardrailResult:
    normalized = text.strip()
    if any(re.search(pattern, normalized, re.I) for pattern in INJECTION_PATTERNS):
        return GuardrailResult(
            allowed=False,
            sanitized_text="[BLOCKED_INJECTION]",
            reason="프롬프트 인젝션 또는 내부 지침 탈취 요청",
        )
    if any(re.search(pattern, normalized, re.I) for pattern in SECRET_PATTERNS):
        return GuardrailResult(
            allowed=False,
            sanitized_text=mask_pii(normalized),
            reason="자격증명 또는 민감정보 조회 요청",
        )
    risky = any(re.search(pattern, normalized, re.I) for pattern in RISKY_ACTION_PATTERNS)
    return GuardrailResult(True, mask_pii(normalized), risky_action=risky)


def safe_output(text: str) -> str:
    """출력 단계에서는 실제 값(전화번호·이메일·주민번호)만 마스킹한다.

    SECRET_PATTERNS는 '비밀번호를 알려줘' 같은 요청 문구 탐지용이며,
    출력에도 그대로 적용하면 로그인 방법 같은 정상 안내문(예: "ID와 비밀번호를
    입력합니다")까지 자격증명 유출로 오탐되어 정상 답변이 통째로 막힌다.
    """
    return mask_pii(text)
