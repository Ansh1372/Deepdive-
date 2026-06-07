"""
Test dataset for RAGAS evaluation.
Each entry has: question, ground_truth answer, and the source to ingest.
You should customize these for your actual testing.
"""

# Test questions for a Wikipedia article about RAG
RAG_ARTICLE_SOURCE = "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"

RAG_TEST_SET = [
    {
        "question": "What is Retrieval-Augmented Generation?",
        "ground_truth": "Retrieval-augmented generation (RAG) is a technique that combines information retrieval with text generation, allowing language models to access external knowledge sources to generate more accurate and up-to-date responses."
    },
    {
        "question": "Who introduced RAG?",
        "ground_truth": "RAG was introduced by researchers at Facebook AI Research (FAIR) in 2020."
    },
    {
        "question": "What are the main components of a RAG system?",
        "ground_truth": "The main components of a RAG system are a retriever (which finds relevant documents from a knowledge base) and a generator (which produces answers based on the retrieved documents)."
    },
    {
        "question": "What problem does RAG solve compared to standard language models?",
        "ground_truth": "RAG solves the problem of hallucination and outdated knowledge in language models by grounding responses in retrieved factual documents rather than relying solely on parametric knowledge."
    },
    {
        "question": "What is the difference between RAG and fine-tuning?",
        "ground_truth": "RAG retrieves external knowledge at inference time without modifying model weights, while fine-tuning updates the model's parameters on specific data. RAG is more flexible for frequently changing information."
    },
]
