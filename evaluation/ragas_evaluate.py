"""실제 Bedrock 기반 RAGAS 평가. AWS 자격증명이 있는 환경에서 실행한다."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from datasets import Dataset
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import build_agent  # noqa: E402


def main() -> None:
    agent = build_agent("round2")
    with (PROJECT_ROOT / "evaluation/test_queries.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    records = []
    for row in rows:
        response = agent.query(row["input"], f"ragas-{row['id']}")
        records.append(
            {
                "question": row["input"],
                "answer": response.answer,
                "contexts": [item.text for item in response.contexts],
                "ground_truth": row["expected_traits"].replace(";", ". "),
            }
        )
    region = os.getenv("AWS_REGION", "us-east-1")
    llm = ChatBedrockConverse(
        model=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        region_name=region,
        temperature=0,
    )
    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0", region_name=region
    )
    result = evaluate(
        Dataset.from_list(records),
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )
    output = PROJECT_ROOT / "evaluation/results/ragas_bedrock.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_pandas().to_csv(output, index=False, encoding="utf-8-sig")
    print(output)


if __name__ == "__main__":
    main()

