"""선택 기능: 사내 시스템 연동을 가정한 Performance Station MCP 서버."""

from fastmcp import FastMCP

from .tools import PerformanceTools

mcp = FastMCP("performance-station")
tools = PerformanceTools()


@mcp.tool
def get_test_run(run_id: str) -> dict:
    """테스트 ID의 성능 지표를 조회합니다."""
    return tools.get_test_run(run_id)


@mcp.tool
def retrieve_performance_guide(question: str) -> list[dict]:
    """성능검증 가이드와 런북에서 근거를 검색합니다."""
    return [item.model_dump() for item in tools.retrieve_docs(question)]


if __name__ == "__main__":
    mcp.run(transport="stdio")

