# Deepdive Project Knowledge Transfer (KT) & History

This document serves as the ultimate Knowledge Transfer (KT) for the **Deepdive** project. It outlines the core features, the evolution of the project from the initial fork, the major headaches we encountered during development, and the precise engineering solutions we implemented to solve them.

---

## 1. What We Forked vs. What We Built

**The Starting Point:** 
The project originally started as a fork of a basic RAG (Retrieval-Augmented Generation) application called "Video Mind." The original architecture was a simple linear pipeline: it downloaded a YouTube transcript, chunked it, saved it to a local vector store, and used a basic LangChain retriever to answer questions.

**What We Transformed It Into (Final Delivery):**
We engineered the app into an enterprise-grade, agentic AI platform. It is no longer just a "YouTube summarizer"—it is a full-scale AI operating system that includes:
*   **Multi-Modal Ingestion:** Support for YouTube, Webpages (with Gemini Vision image understanding), and direct PDF uploads.
*   **Agentic Code Execution (E2B):** A self-healing LangGraph agent that can write Python scripts, spin up secure cloud sandboxes via E2B, execute data analysis, and dynamically generate downloadable Excel, CSV, and PDF reports based on user conversations.
*   **Intelligent Routing:** A dual-LLM architecture that uses fast 8B models for background tasks and heavy models for reasoning.
*   **Automated Web Fallback:** If the local document doesn't contain the answer, the LLM autonomously triggers a DuckDuckGo web search to find live information.
*   **Advanced RAG:** Upgraded to a Hybrid Retriever (semantic FAISS + keyword BM25) paired with a Cross-Encoder reranker for maximum precision.

---

## 2. Major Bugs, Headaches, and How We Solved Them

Building an advanced AI agentic application comes with severe edge-cases. Here are the biggest headaches we faced and how we systematically solved them:

### Headache 1: The "Scunthorpe" Guardrail Bug
*   **The Problem:** The user asked a completely innocent question: *"Explain investing in skills and knowledge."* The backend immediately threw a massive security violation and blocked the request. Why? The app's security blocklist had the word `kill` on it. Because the code was doing a simple substring match, it saw `k-i-l-l` inside the word `s-kill-s` and triggered the emergency block!
*   **The Solution:** We hot-patched `backend/generation/guardrail.py` to use Regex Word Boundaries (`\b`). The security system now only blocks the request if the blocked keyword is typed as an exact standalone word, perfectly ignoring false positives like "skills" or "skillet."

### Headache 2: The API Token Rate Limit Nightmare
*   **The Problem:** The massive LLaMA 3.3 70B model was burning through the user's free-tier Groq API limit of 100,000 tokens per day. Once the limit was hit, the entire application hard-crashed with a `429 Rate Limit Exceeded` error for the rest of the day.
*   **The Solution:** 
    1.  **Dual-Model Architecture:** We split the workload. We routed all background tasks (Query Rewriting, Intent Classification, Context Compression) to `llama-3.1-8b-instant`, preserving the precious 70B tokens only for the final answer generation.
    2.  **The Automatic Gemini Failover:** We built an impenetrable safety net. If the Groq API fails or rate-limits, the `chain.py` logic instantly catches the crash and seamlessly routes the user's request to a fallback Google Gemini model. 

### Headache 3: The Gemini Fallback Naming Crash
*   **The Problem:** After building the automatic Gemini failover, we triggered it on purpose. It crashed again. The error revealed that Google had updated their API requirements and rejected the model name `gemini-1.5-flash`.
*   **The Solution:** We dug into the backend logs, caught the `404 NotFound` error, and hot-patched the routing logic in `chain.py` to use the correct Google API spec: `gemini-flash-latest`. The failover now works flawlessly.

### Headache 4: The Chat History Token Explosion
*   **The Problem:** As the user had long, back-and-forth conversations, the chat history array grew massive. Eventually, sending the entire history back to the LLM exceeded the strict token limits of the 8B and 70B models, causing sudden generation failures mid-conversation.
*   **The Solution:** We built a silent, automatic "Memory Compressor" in `api.py`. Once a conversation exceeds 6 messages, the backend secretly fires off a background request to the 8B model to summarize all the old context into a single dense paragraph. It then attaches that summary to the 2 most recent messages, saving thousands of tokens while preserving perfect conversational memory.

### Headache 5: The Hugging Face YouTube Ban
*   **The Problem:** We deployed the Dockerized application flawlessly to Hugging Face Spaces. The web UI loaded perfectly. However, whenever a user pasted a YouTube URL, it crashed.
*   **The Solution:** We discovered that Hugging Face intentionally blocks outbound server connections to YouTube to prevent compute abuse. To solve this, we updated the React frontend to detect if the app was running on the `hf.space` domain. If true, it gracefully renders a UI warning advising users to use PDFs or Webpages instead, while preserving the full YouTube functionality for users running the app locally.

### Headache 6: Agentic Broken Code Loops
*   **The Problem:** When we added the feature to let the AI write Python scripts to generate Excel/PDF files, the LLM would occasionally write code with syntax errors. The E2B Sandbox would crash, and the user would just get an error.
*   **The Solution:** We ripped out the linear logic and replaced it with a **Stateful LangGraph State Machine**. Now, if the AI writes broken code and the sandbox crashes, the LangGraph agent intercepts the error log, feeds it *back* to the LLM, and forces the LLM to fix its own code. It will self-heal and loop up to 3 times before giving up, resulting in a massively higher success rate for report generation.

---

## 3. How to Use the Features You Got

As the owner of this repository, here is how you use the massive power you now hold:

1.  **Ingestion:** Paste a YouTube URL, a Webpage link, or upload a PDF.
2.  **General Chat:** Ask any question. The system will hybrid-search the content and give you a perfectly cited answer.
3.  **File Generation (Agent Mode):** Say something like, *"Extract all the budget advice from this video and generate an Excel spreadsheet for me."* The Intent Classifier will detect you want a file, spin up a LangGraph agent, write a Python script, execute it in an E2B cloud sandbox, and stream a download link back to your chat window.
4.  **Persistent Memory:** Refresh your browser. Your chat history is saved in a local Redis database and your vector embeddings are saved to your hard drive. It will all be there when you get back.

This is no longer a fork; it is a masterclass in resilient, agentic AI engineering.
