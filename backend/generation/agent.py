import os
import re
import uuid
from backend.utils.logger import get_logger
from backend.generation.chain import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    Sandbox = None

logger = get_logger("agent")

# Ensure the downloads directory exists
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def generate_and_run_script(prompt: str, context: str, chat_history: str) -> str:
    """Uses LLM to write a Python script, runs it in E2B, and returns a download link."""
    
    e2b_api_key = os.getenv("E2B_API_KEY")
    if not Sandbox or not e2b_api_key:
        logger.error("E2B Sandbox is not configured properly.")
        return "Sorry, the secure code execution environment is not configured (missing E2B_API_KEY)."

    llm = get_llm()
    
    # 1. Ask LLM to write the Python script
    system_prompt = """You are an expert Python data analyst and developer.
Your task is to write a Python script that generates a highly-formatted file (e.g. Excel, CSV, PDF, Word docx, Markdown) based on the user's explicit request.

Requirements:
1. Pay close attention to the EXACT file format the user requests (e.g., if they ask for a PDF, generate a .pdf; if Word, generate .docx; if Excel, generate .xlsx).
2. If you need third-party libraries (like `python-docx` for Word, `fpdf2` or `reportlab` for PDF, `openpyxl` for Excel), you MUST install them at the very top of your script using `import subprocess; subprocess.run(['pip', 'install', 'python-docx', 'fpdf2', 'openpyxl', 'reportlab'])`.
3. If making a PDF with fpdf2, handle Unicode text safely and DO NOT use custom header/footer methods that reference uninitialized variables (e.g. `self.title`). Call `add_page()` only AFTER setting necessary titles, or just keep the script extremely simple without custom headers.
3. You MUST save the final generated file in the current working directory.
4. Output ONLY the raw Python code enclosed in ```python ... ``` tags. Do not include any other explanations.
5. DO NOT hardcode the entire raw context text into your script. Instead, analyze the text yourself and hardcode ONLY the final extracted key points, summaries, or insights as small Python data structures (like lists of dictionaries) inside the script.

Here is the entire Chat History up to this point:
{chat_history}

Here is the Source Document Context:
{context}
"""

    user_prompt = f"User Request: {prompt}\n\nPlease write the complete Python script to generate this file."

    logger.info("[AGENT] Generating Python script...")
    response = llm.invoke([
        SystemMessage(content=system_prompt.format(chat_history=chat_history, context=context)),
        HumanMessage(content=user_prompt)
    ])
    logger.info(f"[AGENT] Raw LLM Response:\n{response.content}\n-----------------------")
    
    # 2. Extract code
    code_match = re.search(r'```python\n(.*?)\n```', response.content, re.DOTALL)
    if not code_match:
        # Fallback if no markdown block
        code = response.content.replace('```python', '').replace('```', '').strip()
    else:
        code = code_match.group(1).strip()
        
    logger.info(f"[AGENT] Extracted script ({len(code)} bytes):\n{code}\nRunning in E2B Sandbox...")

    # 3. Run in E2B Sandbox
    try:
        with Sandbox.create() as sandbox:
            execution = sandbox.run_code(code)
            
            if execution.error:
                logger.error(f"[AGENT] E2B Execution Error: {execution.error.name} - {execution.error.value}")
                return f"Sorry, there was an error generating the report: {execution.error.value}"
                
            # 4. Find the generated file
            files = sandbox.files.list("/home/user")
            
            # Filter out hidden files or standard python files
            generated_files = [f for f in files if not f.name.startswith('.') and not f.name.endswith('.py')]
            
            if not generated_files:
                logger.warning("[AGENT] Script executed but no file was generated.")
                return "The report generation completed, but no file was created."
                
            # Grab the most recently modified or just the first generated file
            target_file = generated_files[0]
            
            # Download it to our local backend/downloads folder
            file_bytes = sandbox.files.read(target_file.path, format="bytes")
            
            # Give it a unique name to prevent collisions
            unique_filename = f"{uuid.uuid4().hex[:8]}_{target_file.name}"
            local_path = os.path.join(DOWNLOADS_DIR, unique_filename)
            
            with open(local_path, "wb") as f:
                f.write(file_bytes)
                
            logger.info(f"[AGENT] File downloaded successfully: {unique_filename}")
            
            # Return the markdown link
            return f"Your report has been generated successfully! \n\n[Download {target_file.name} here](http://localhost:8001/downloads/{unique_filename})"
            
    except Exception as e:
        logger.error(f"[AGENT] Sandbox connection/execution failed: {e}")
        return "An error occurred while connecting to the secure sandbox environment."
