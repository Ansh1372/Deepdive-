"""
Custom RAG Evaluation Script for VideoMind.
Measures: Faithfulness, Answer Relevancy, Context Precision.
Uses Groq LLM as the evaluator (no RAGAS dependency issues).

Usage: cd video-mind && python -m backend.evaluation.evaluate
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from backend.ingest.router import ingest
from backend.processing.chunker import chunk_text
from backend.retrieval.vectorstore import create_vectorstore
from backend.retrieval.retriever import create_hybrid_retriever
from backend.reranker.reranker import rerank
from backend.retrieval.query_transform import rewrite_query, generate_multi_queries
from backend.retrieval.compressor import compress_docs
from backend.generation.chain import build_chain, get_llm
from backend.evaluation.test_data import RAG_ARTICLE_SOURCE, RAG_TEST_SET


def run_pipeline(question: str, retriever, chunks, chain):
    """Run the full RAG pipeline for a single question."""
    rewritten = rewrite_query(question, "No previous conversation.")
    multi_queries = generate_multi_queries(rewritten)
    all_queries = [rewritten] + multi_queries

    all_docs = []
    seen = set()
    for q in all_queries:
        docs = retriever.invoke(q)
        for doc in docs:
            h = hash(doc.page_content)
            if h not in seen:
                seen.add(h)
                all_docs.append(doc)

    reranked_docs, _, _ = rerank(rewritten, all_docs, top_k=4)
    compressed_docs = compress_docs(rewritten, reranked_docs)
    if not compressed_docs:
        compressed_docs = reranked_docs

    context = "\n\n".join(doc.page_content for doc in compressed_docs)
    answer = chain.invoke({"context": context, "question": question, "chat_history": "No previous conversation."})

    contexts = [doc.page_content for doc in compressed_docs]
    return answer, contexts, context


def evaluate_faithfulness(question, answer, context, llm):
    """Score 0-1: Is the answer supported by the context?"""
    prompt = f"""Given the context and the answer, rate how faithful the answer is to the context.
A faithful answer only contains information that can be found in or inferred from the context.

Context: {context[:2000]}

Answer: {answer}

Rate faithfulness from 0.0 to 1.0 where:
- 1.0 = completely faithful, all claims are supported by context
- 0.0 = completely unfaithful, makes up information not in context

Respond with ONLY a number between 0.0 and 1.0:"""

    response = llm.invoke(prompt)
    try:
        score = float(response.content.strip())
        return min(max(score, 0.0), 1.0)
    except ValueError:
        return 0.5


def evaluate_relevancy(question, answer, llm):
    """Score 0-1: Does the answer actually address the question?"""
    prompt = f"""Given the question and the answer, rate how relevant the answer is to the question.

Question: {question}
Answer: {answer}

Rate relevancy from 0.0 to 1.0 where:
- 1.0 = perfectly answers the question
- 0.0 = completely irrelevant to the question

Respond with ONLY a number between 0.0 and 1.0:"""

    response = llm.invoke(prompt)
    try:
        score = float(response.content.strip())
        return min(max(score, 0.0), 1.0)
    except ValueError:
        return 0.5


def evaluate_context_precision(question, contexts, ground_truth, llm):
    """Score 0-1: Are the retrieved contexts relevant to answering the question?"""
    context_str = "\n---\n".join(contexts[:3])
    prompt = f"""Given the question and the expected answer, rate how relevant the retrieved contexts are.

Question: {question}
Expected Answer: {ground_truth}

Retrieved Contexts:
{context_str[:2000]}

Rate context precision from 0.0 to 1.0 where:
- 1.0 = all retrieved contexts are highly relevant
- 0.0 = none of the contexts are relevant

Respond with ONLY a number between 0.0 and 1.0:"""

    response = llm.invoke(prompt)
    try:
        score = float(response.content.strip())
        return min(max(score, 0.0), 1.0)
    except ValueError:
        return 0.5


def evaluate_correctness(answer, ground_truth, llm):
    """Score 0-1: Is the answer factually correct compared to ground truth?"""
    prompt = f"""Compare the generated answer with the ground truth answer.

Ground Truth: {ground_truth}
Generated Answer: {answer}

Rate correctness from 0.0 to 1.0 where:
- 1.0 = generated answer captures all key facts from ground truth
- 0.0 = generated answer is completely wrong

Respond with ONLY a number between 0.0 and 1.0:"""

    response = llm.invoke(prompt)
    try:
        score = float(response.content.strip())
        return min(max(score, 0.0), 1.0)
    except ValueError:
        return 0.5


def main():
    print("=" * 60)
    print("  VideoMind RAG Evaluation")
    print("=" * 60)

    # Step 1: Ingest
    print(f"\n[1/4] Ingesting: {RAG_ARTICLE_SOURCE}")
    text = ingest(RAG_ARTICLE_SOURCE)
    chunks = chunk_text(text, source=RAG_ARTICLE_SOURCE)
    print(f"      Created {len(chunks)} chunks")

    # Step 2: Build retriever
    print("[2/4] Building vectorstore + retriever...")
    vectorstore = create_vectorstore(chunks, save_path="eval_vectorstore")
    retriever = create_hybrid_retriever(vectorstore, chunks)
    chain = build_chain()
    llm = get_llm()

    # Step 3: Run evaluation
    print(f"[3/4] Evaluating {len(RAG_TEST_SET)} questions...\n")

    all_scores = {"faithfulness": [], "relevancy": [], "context_precision": [], "correctness": []}

    for i, test in enumerate(RAG_TEST_SET):
        print(f"  Q{i+1}: {test['question']}")
        answer, contexts, context = run_pipeline(test["question"], retriever, chunks, chain)
        print(f"      A: {answer[:100]}...")

        # Evaluate
        faith = evaluate_faithfulness(test["question"], answer, context, llm)
        relev = evaluate_relevancy(test["question"], answer, llm)
        prec = evaluate_context_precision(test["question"], contexts, test["ground_truth"], llm)
        corr = evaluate_correctness(answer, test["ground_truth"], llm)

        all_scores["faithfulness"].append(faith)
        all_scores["relevancy"].append(relev)
        all_scores["context_precision"].append(prec)
        all_scores["correctness"].append(corr)

        print(f"      Scores: faith={faith:.2f} | relev={relev:.2f} | prec={prec:.2f} | corr={corr:.2f}")
        print()

    # Step 4: Results
    print("\n" + "=" * 60)
    print("  EVALUATION RESULTS")
    print("=" * 60)

    results = {}
    for metric, scores in all_scores.items():
        avg = sum(scores) / len(scores)
        results[metric] = round(avg, 4)
        print(f"\n  {metric.title():25s} {avg:.4f}")

    overall = sum(results.values()) / len(results)
    results["overall"] = round(overall, 4)
    print(f"\n  {'Overall':25s} {overall:.4f}")
    print("=" * 60)

    # Save
    with open("evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n  Results saved to: evaluation_results.json")

    # Cleanup
    import shutil
    if os.path.exists("eval_vectorstore"):
        shutil.rmtree("eval_vectorstore")


if __name__ == "__main__":
    main()
