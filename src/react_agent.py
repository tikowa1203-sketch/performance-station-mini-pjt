from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent

from .config import settings
from .tools import PerformanceTools


SYSTEM_PROMPT = """당신은 Performance Station ReAct 분석 Agent다.
질문을 해결하는 데 필요한 도구만 자율적으로 선택해 호출한다.
도구 결과와 검색 근거에 없는 수치나 원인을 만들지 않는다.
운영 변경을 실행하지 말고 Change Agent의 승인 흐름을 안내한다.
"""


def build_react_executor():
    """Day 3 ReAct 패턴의 Bedrock 실행기. AWS 자격증명이 필요하다."""
    llm = ChatBedrockConverse(
        model=settings.model_id,
        region_name=settings.region,
        temperature=0,
    )
    tools = PerformanceTools().as_langchain_tools()
    return create_react_agent(model=llm, tools=tools)


def ask(question: str) -> str:
    executor = build_react_executor()
    result = executor.invoke(
        {"messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)]},
        {"recursion_limit": 8},
    )
    return str(result["messages"][-1].content)

