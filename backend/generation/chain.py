import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()


def get_llm(purpose="heavy"):
    """
    Returns an LLM depending on the purpose to save tokens and speed up background tasks.
    purpose="heavy": For complex reasoning (Main chat, Agent coding) -> uses LLaMA 3.3 70B
    purpose="fast": For quick classification/routing -> uses LLaMA 3.1 8B
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    # Define fallback model
    gemini_fallback = None
    if gemini_api_key:
        gemini_fallback = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.2, max_output_tokens=8192, google_api_key=gemini_api_key)

    if groq_api_key:
        if purpose == "fast":
            model_name = "llama-3.1-8b-instant"
            temperature = 0.1
        else:
            model_name = "llama-3.1-8b-instant"
            temperature = 0.2
            
        groq_model = ChatGroq(
            model=model_name,
            temperature=temperature,
            max_tokens=1024,
            groq_api_key=groq_api_key
        )
        
        # If Gemini is configured, use it as a safety net for rate limits
        if gemini_fallback:
            return groq_model.with_fallbacks([gemini_fallback])
            
        return groq_model
    else:
        return gemini_fallback


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
