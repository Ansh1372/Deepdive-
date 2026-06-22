import os
import re
import uuid
from typing import TypedDict, Optional
from backend.utils.logger import get_logger
from backend.generation.chain import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    Sandbox = None

logger = get_logger("agent")

# Ensure the downloads directory exists
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

class AgentState(TypedDict):
    prompt: str
    context: str
    chat_history: str
    code: Optional[str]
    error: Optional[str]
    iterations: int
    final_response: Optional[str]

def generate_code_node(state: AgentState):
    llm = get_llm()
    logger.info(f"[AGENT] Generating code (Iteration {state['iterations'] + 1})")
    
    system_prompt = """You are an expert Python developer specializing in creating beautiful, professional, colorful documents.
Your task is to write a Python script that generates a stunning, well-designed file based on the user's request.

=== LIBRARY RULES (CRITICAL — follow exactly) ===
- For PDF files: ALWAYS use `reportlab`. NEVER use fpdf2. Install with: subprocess.run(['pip', 'install', 'reportlab'], check=True)
- For Excel files: use `openpyxl`. Install with: subprocess.run(['pip', 'install', 'openpyxl'], check=True)
- For Word files: use `python-docx`. Install with: subprocess.run(['pip', 'install', 'python-docx'], check=True)
- ALWAYS run the install at the very top of the script before any other imports.

=== DESIGN RULES (CRITICAL — you MUST follow these) ===
1. If the user asks for colors, bold text, or formatting — you MUST implement rich visual design. A plain black-and-white document is UNACCEPTABLE.
2. For PDFs using reportlab, you MUST use:
   - `colors.HexColor('#XXXXXX')` for background fills and text colors
   - Bold fonts like "Helvetica-Bold" for headings
   - Colored rectangles as section backgrounds using `canvas.setFillColor()` + `canvas.rect()`
   - Tables with colored headers using `TableStyle` with `BACKGROUND`, `TEXTCOLOR`, `FONTNAME`, `GRID`
   - A styled title section with a colored banner at the top
   - Alternating row colors in tables
3. Color palette suggestion for professional look: Dark navy (#1a237e), bright teal (#00bcd4), white text on dark headers, light gray (#f5f5f5) for alternating rows.
4. You MUST save the file in the current working directory.
5. Output ONLY raw Python code in ```python ... ``` tags. No other text.

=== DATA RULES ===
6. DO NOT dump raw context text into the script. Extract key insights, structure them into Python lists/dicts, and use that structured data to build the document.
7. CRITICAL: If the user asks for content NOT found in the Source Document Context, output EXACTLY "REJECT: OUT_OF_CONTEXT" and nothing else.

Here is the entire Chat History up to this point:
{chat_history}

Here is the Source Document Context:
{context}
"""
    user_prompt = f"User Request: {state['prompt']}\n\nPlease write the complete Python script to generate this file."
    
    if state.get("error"):
        user_prompt += f"\n\nCRITICAL: Your previous code execution FAILED with the following error:\n{state['error']}\n\nPlease analyze the error, fix your code, and try again. Output the full corrected code."
        
    response = llm.invoke([
        SystemMessage(content=system_prompt.format(chat_history=state["chat_history"], context=state["context"])),
        HumanMessage(content=user_prompt)
    ])
    
    if "REJECT: OUT_OF_CONTEXT" in response.content.upper():
        logger.warning("[AGENT] Rejected out of context request.")
        return {"final_response": "I can only generate files and reports based on the content you uploaded. Please ask a question related to the source document."}

    code_match = re.search(r'```python\n(.*?)\n```', response.content, re.DOTALL)
    if not code_match:
        code = response.content.replace('```python', '').replace('```', '').strip()
    else:
        code = code_match.group(1).strip()
        
    return {"code": code}

def execute_code_node(state: AgentState):
    logger.info("[AGENT] Executing code in Sandbox...")
    e2b_api_key = os.getenv("E2B_API_KEY")
    if not Sandbox or not e2b_api_key:
        return {"error": "E2B Sandbox is not configured properly.", "iterations": state["iterations"] + 1}
        
    try:
        with Sandbox(api_key=e2b_api_key) as sandbox:
            # Pre-install common document libraries so the generated code can import them
            logger.info("[AGENT] Installing packages in sandbox...")
            sandbox.commands.run(
                "pip install reportlab openpyxl python-docx -q",
                timeout=120
            )
            logger.info("[AGENT] Packages installed. Running code...")
            execution = sandbox.run_code(state["code"])
            
            if execution.error:
                error_msg = f"{execution.error.name}: {execution.error.value}"
                logger.warning(f"[AGENT] E2B Error: {error_msg}")
                return {"error": error_msg, "iterations": state["iterations"] + 1}
                
            files = sandbox.files.list("/home/user")
            generated_files = [f for f in files if not f.name.startswith('.') and not f.name.endswith('.py')]
            
            if not generated_files:
                error_msg = "Script executed but no file was generated in the current working directory."
                logger.warning(f"[AGENT] {error_msg}")
                return {"error": error_msg, "iterations": state["iterations"] + 1}
                
            target_file = generated_files[0]
            file_bytes = sandbox.files.read(target_file.path, format="bytes")
            
            unique_filename = f"{uuid.uuid4().hex[:8]}_{target_file.name}"
            local_path = os.path.join(DOWNLOADS_DIR, unique_filename)
            
            with open(local_path, "wb") as f:
                f.write(file_bytes)
                
            # Build correct download URL — HF sets SPACE_HOST automatically
            space_host = os.getenv("SPACE_HOST")
            if space_host:
                base_url = f"https://{space_host}"
            else:
                base_url = "http://localhost:8001"
            
            final_response = f"Your report has been generated successfully! \n\n[Download {target_file.name} here]({base_url}/downloads/{unique_filename})"
            return {"final_response": final_response, "error": None}
            
    except Exception as e:
        logger.error(f"[AGENT] Sandbox exception: {e}")
        return {"error": str(e), "iterations": state["iterations"] + 1}

def should_continue(state: AgentState):
    if state.get("final_response"):
        return END
    if state["iterations"] >= 3:
        return END
    return "generate_code"

# Compile graph
workflow = StateGraph(AgentState)
workflow.add_node("generate_code", generate_code_node)
workflow.add_node("execute_code", execute_code_node)

workflow.set_entry_point("generate_code")
workflow.add_conditional_edges("generate_code", lambda x: "execute_code" if not x.get("final_response") else END)
workflow.add_conditional_edges("execute_code", should_continue)

agent_app = workflow.compile()

def generate_and_run_script(prompt: str, context: str, chat_history: str) -> str:
    """Invokes the LangGraph state machine to generate and run a script."""
    initial_state = {
        "prompt": prompt,
        "context": context,
        "chat_history": chat_history,
        "code": None,
        "error": None,
        "iterations": 0,
        "final_response": None
    }
    
    logger.info("[AGENT] Starting LangGraph Agent")
    final_state = agent_app.invoke(initial_state)
    
    if final_state.get("final_response"):
        return final_state["final_response"]
    elif final_state.get("error"):
        return f"Sorry, there was an error generating the report after {final_state['iterations']} attempts: {final_state['error']}"
    else:
        return "Unknown error occurred during generation."
