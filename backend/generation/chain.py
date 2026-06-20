import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()


def get_llm():
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0.2, max_tokens=8192)


def build_chain():
    """Build the generation chain with conversation memory support."""
    prompt = PromptTemplate(
        template="""You are a helpful assistant. Answer STRICTLY from the provided context only.
Do NOT use your training data or prior knowledge to fill in gaps.
Provide detailed, thorough explanations with examples where possible.
Structure your answer clearly with key points.

If the context contains a section marked "[Additional context from web search]":
- You may use that web-sourced information to answer.
- Clearly state: "Based on web search results:" before presenting that information.

If the context does NOT contain enough information to answer and there is no web search section, say: "The ingested document doesn't contain this information."

Previous conversation:
{chat_history}

Context from source:
{context}

Question: {question}""",
        input_variables=["chat_history", "context", "question"],
    )

    chain = prompt | get_llm() | StrOutputParser()
    return chain
