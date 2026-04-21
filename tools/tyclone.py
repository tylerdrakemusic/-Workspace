"""
$$~~TyClone$$.py - AI-Powered Python File Enhancement & Refactoring Tool
=========================================================================

PURPOSE:
    This script automatically enhances Python files using OpenAI's API. It reads Python
    source files, sends them to an LLM with detailed refactoring instructions, and saves
    the improved versions. Think of it as an automated code reviewer and refactorer.

MAIN FEATURES:
    1. AI Enhancement: Sends Python files to OpenAI with comprehensive prompts requesting:
       - Type hints, docstrings, logging best practices
       - Error handling, cross-platform compatibility
       - Modular/OOP design patterns
       - quantum_rt import corrections (custom random library)

    2. Unittest Detection: Automatically detects test files (test_*.py, *_test.py, or
       files importing unittest) and uses a specialized test-focused prompt instead.

    3. Clone Generation: Saves enhanced files to 'pyClones/' directory as *Clone.py
       before optionally replacing originals.

    4. Batch Processing: After processing N files (default 10), generates a contextually
       relevant new filename suggestion using AI based on the batch.

    5. Exemption System: Skips files based on:
       - Prefix tags: $$, ~, ^, # (configurable via JSON)
       - Explicit file list in tyJson/!exceptional_python.json

    6. Script Execution & Logging: Runs enhanced scripts to verify they work, with:
       - Automatic unittest mode detection
       - AI-suggested argument retry on usage errors
       - Exception logging to exception_log.txt

KEY FUNCTIONS:
    - enhance_python_file(path)      : Core function - sends file to OpenAI, returns enhanced code
    - process_files_in_directory()   : Main loop - iterates files, applies enhancements
    - validate_and_correct_functions(): Fixes misspelled quantum_rt imports
    - run_script(path)               : Executes enhanced script, logs failures
    - generate_new_filename(batch)   : AI generates new filename from batch context

USAGE:
    python "$$~~TyClone$$.py" [-b BATCH_SIZE]

    -b, --batch : Number of files to process before suggesting a new filename (default: 10)

DEPENDENCIES:
    - quantum_rt    : Custom quantum random library (qhoice, qRandom, etc.)
    - ty_py.loader  : JSON config loader
    - ty_py.openai_helper : OpenAI API wrapper
    - colorama      : Colored terminal output

AUTHOR: Tyler James Drake
"""

import os
import re  # Added for regex operations
import signal
import sys
from time import sleep
from quantum_rt import qhoice
from colorama import Fore, Style, init
from ty_py import loader
from ty_py import openai_helper
import concurrent.futures
import subprocess
from datetime import datetime
import argparse
from pathlib import Path  # Added for root/tyPython resolution


# Initialize colorama
init(autoreset=True)

# Kill switch file - create this file to stop the script gracefully
KILL_FILE = Path("STOP_TYCLONE")

# Track state for graceful shutdown
_shutdown_requested = False
_current_file = None
_files_processed = []
_files_created = []  # Track newly created files (AI-suggested filenames)

def _print_session_summary():
    """Print a summary of the session including processed and created files."""
    if _files_processed:
        print(Fore.CYAN + f"\n📋 Files Enhanced ({len(_files_processed)}):" + Style.RESET_ALL)
        for f in _files_processed[-10:]:  # Show last 10
            print(Fore.GREEN + f"  ✓ {f}" + Style.RESET_ALL)
        if len(_files_processed) > 10:
            print(Fore.GREEN + f"  ... and {len(_files_processed) - 10} more" + Style.RESET_ALL)
    
    if _files_created:
        print(Fore.MAGENTA + f"\n🆕 New Files Created ({len(_files_created)}):" + Style.RESET_ALL)
        for f in _files_created:
            print(Fore.MAGENTA + f"  ★ {f}" + Style.RESET_ALL)

def _signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    print(Fore.YELLOW + "\n\n⚠️  Shutdown requested (Ctrl+C)..." + Style.RESET_ALL)
    print(Fore.YELLOW + f"Current file: {_current_file}" + Style.RESET_ALL)
    print(Fore.YELLOW + f"Files processed: {len(_files_processed)}" + Style.RESET_ALL)
    _print_session_summary()
    _shutdown_requested = True
    # Don't exit immediately - let the current file finish

def _check_kill_switch() -> bool:
    """Check if kill switch file exists."""
    if KILL_FILE.exists():
        print(Fore.RED + f"\n🛑 Kill switch detected ({KILL_FILE})" + Style.RESET_ALL)
        print(Fore.YELLOW + "Stopping gracefully after current operation..." + Style.RESET_ALL)
        return True
    return False

# Register signal handler
signal.signal(signal.SIGINT, _signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _signal_handler)

# Create directories to store the enhanced clones
output_dir = "pyClones"
os.makedirs(output_dir, exist_ok=True)

# Initialize a list to hold batches of enhanced filenames
enhanced_batch = []

# Filenames starting with these prefixes are treated as "exempt" by default and will be skipped.
# This can be overridden per-repo via tyJson/exceptional_python.json -> { "exempt_prefixes": ["$$", "~", "^"] }
DEFAULT_EXEMPT_PREFIXES = ("$$", "~", "^", "#")

def _is_prefixed_exempt(name: str, prefixes: tuple | list | None = None) -> bool:
    """Return True if the basename starts with any exempt prefix.

    prefixes: optional override list/tuple (falls back to DEFAULT_EXEMPT_PREFIXES)
    """
    base = os.path.basename(name)
    pfx = tuple(prefixes) if prefixes else DEFAULT_EXEMPT_PREFIXES
    return base.startswith(pfx)

def _load_exempt_config(exempt_file_path: str) -> tuple[list, list]:
    """Load exemption configuration from JSON.

    Returns (exempt_files, exempt_prefixes). Both are lists. Missing/invalid -> safe defaults.
    Accepts legacy formats: a top-level list (files only), or dict with keys 'exempt_files' and 'exempt_prefixes'.
    Also tolerates alternate keys for prefixes: 'prefixes', 'file_prefixes', 'tags'.
    """
    try:
        data = loader.load_exempt_files(exempt_file_path)
    except Exception:
        return [], list(DEFAULT_EXEMPT_PREFIXES)

    exempt_files: list = []
    exempt_prefixes: list = list(DEFAULT_EXEMPT_PREFIXES)

    if isinstance(data, dict):
        # Files
        v = data.get('exempt_files', [])
        if isinstance(v, list):
            exempt_files = [str(x) for x in v]
        # Prefixes (check a few common keys)
        for key in ('exempt_prefixes', 'prefixes', 'file_prefixes', 'tags'):
            pv = data.get(key)
            if isinstance(pv, list) and pv:
                exempt_prefixes = [str(x) for x in pv]
                break
    elif isinstance(data, list):
        exempt_files = [str(x) for x in data]
        # Keep default prefixes
    else:
        # Unknown format; fall back to defaults
        pass

    return exempt_files, exempt_prefixes

# Helper: resolve repository root (looks for tyPython + .git) and return Path
def _resolve_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / 'tyPython').is_dir() and (p / '.git').exists():
            return p
    # Fallback: directory containing this script
    return here

# Define the set of correct function names
CORRECT_FUNCTION_NAMES = {
    "qRandom",
    "qRax",
    "qhoice",
    "quuffle",
    "qsample",
    "qpermute",
    "qRandomBool",
    "qRandomBitstring"
}

# Define common misspellings and their corrections
MISSPELLED_FUNCTIONS = {
    "qchoice": "qhoice",
    "quffle": "quuffle",
    "quaffle":"quuffle"
    # Add more misspellings as needed
}

# NEW: unified unittest detection helper placed early so both enhancer & runner share it
def _is_unittest_file(file_path: str, file_content: str | None = None) -> bool:  # unified final definition
    """Heuristic to decide if a file is a unittest module.

    Conditions (any true => treat as test):
      - Filename starts with 'test_' or ends with '_test.py'
      - Content imports unittest and references TestCase
    file_content may be provided to avoid re-reading.
    """
    name = os.path.basename(file_path)
    if name.startswith('test_') or name.endswith('_test.py'):
        return True
    try:
        text = file_content
        if text is None:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
                text = fh.read(4000)
        if text and re.search(r'\bimport\s+unittest\b|from\s+unittest\s+import', text) and 'TestCase' in text:
            return True
    except Exception:
        return False
    return False

def read_exception_log(file_name):
    with open('exception_log.txt', 'r') as log_file:
        log_content = log_file.read()
    start_marker = f"Exception in file: {file_name}"
    end_marker = "===================="
    start_index = log_content.find(start_marker)
    if start_index == -1:
        return ""
    end_index = log_content.find(end_marker, start_index + len(start_marker))
    if end_index == -1:
        end_index = len(log_content)
    return log_content[start_index:end_index].strip()

def return_exception_files():
    with open('exception_log.txt', 'r') as log_file:
        log_content = log_file.read()
    exception_files = []
    start_marker = "Exception in file: "
    end_marker = "===================="
    start_index = 0
    while start_index != -1:
        start_index = log_content.find(start_marker, start_index)
        if start_index != -1:
            start_index += len(start_marker)
            end_index = log_content.find('\n', start_index)
            if end_index == -1:
                end_index = len(log_content)
            file_name = log_content[start_index:end_index].strip()
            exception_files.append(file_name)
            start_index = log_content.find(end_marker, start_index) + len(end_marker)
    return exception_files

def get_exception_for_file(file_name):
    with open('exception_log.txt', 'r') as log_file:
        log_content = log_file.read()
    start_marker = f"Exception in file: {file_name}"
    end_marker = "===================="
    start_index = log_content.find(start_marker)
    if start_index == -1:
        return ""
    end_index = log_content.find(end_marker, start_index + len(start_marker))
    if end_index == -1:
        end_index = len(log_content)
    return log_content[start_index:end_index].strip()

def strip_code_fences(content):
    """
    Strips markdown code fences from the content.
    Handles cases where code fences are incomplete or embedded within text.

    Args:
        content (str): The content possibly containing code fences.

    Returns:
        str: Content without code fences.
    """
    # Remove opening code fences with language specifier (e.g., ```python)
    content = re.sub(r'^```python\s*\n', '', content, flags=re.MULTILINE)
    # Remove opening code fences without language specifier (e.g., ```)
    content = re.sub(r'^```\s*\n', '', content, flags=re.MULTILINE)
    # Remove closing code fences
    content = re.sub(r'\n```$', '', content, flags=re.MULTILINE)
    # Remove any remaining backticks
    content = content.replace('```', '')
    return content

def strip_filename_code_fences(filename_content):
    """
    Strips markdown code fences and language specifiers from the filename content.

    Args:
        filename_content (str): The filename content possibly containing code fences.

    Returns:
        str: Cleaned filename.
    """
    # Remove opening code fences with language specifier (e.g., ```python)
    filename_content = re.sub(r'^```python\s*', '', filename_content, flags=re.MULTILINE)
    # Remove opening code fences without language specifier (e.g., ```)
    filename_content = re.sub(r'^```\s*', '', filename_content, flags=re.MULTILINE)
    # Remove closing code fences
    filename_content = re.sub(r'\s*```$', '', filename_content, flags=re.MULTILINE)
    # Remove any remaining backticks
    filename_content = filename_content.replace('```', '').strip()
    return filename_content


def attempt_ai_error_fix(file_path, file_content, error_message, max_attempts=3):
    """
    Attempts to fix Python code errors by sending the code and error message to OpenAI.
    
    Args:
        file_path (str): Path to the Python file.
        file_content (str): Current content of the file.
        error_message (str): The error message from running the script.
        max_attempts (int): Maximum number of fix attempts.
    
    Returns:
        tuple: (success: bool, fixed_content: str or None, attempts_made: int)
    """
    filename = os.path.basename(file_path)
    
    for attempt in range(1, max_attempts + 1):
        print(Fore.YELLOW + f"🔧 Attempting AI fix #{attempt}/{max_attempts} for {filename}..." + Style.RESET_ALL)
        
        fix_prompt = f"""You are a Python debugging expert. The following Python code produces an error when executed.

Fix the code so it runs without errors. Return ONLY the complete fixed Python code, no explanations.

Error message:
```
{error_message}
```

Python file ({filename}):
```python
{file_content}
```

IMPORTANT:
- Return ONLY the fixed Python code, no markdown fences or explanations
- Preserve all existing functionality
- Fix only the error shown, don't refactor unnecessarily
- Keep the quantum_rt imports exactly as: from quantum_rt import qRandom, qRax, qhoice, quuffle, qsample, qpermute, qRandomBool, qRandomBitstring
- qRandom(n) takes ONE argument (returns 0 to n-1), use qRax(min, max) for ranges
"""
        
        messages = [
            {
                "role": "user",
                "content": fix_prompt
            }
        ]
        
        try:
            fixed_content = openai_helper.get_chat_completion(messages=messages)
            fixed_content = strip_code_fences(fixed_content)
            fixed_content = validate_and_correct_functions(fixed_content)
            
            # Write the fixed content and test it
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            print(Fore.CYAN + f"  → Testing fix #{attempt}..." + Style.RESET_ALL)
            
            # Run and check if it works
            success, new_error = run_script_with_error(file_path)
            
            if success:
                print(Fore.GREEN + f"✓ Fix #{attempt} successful!" + Style.RESET_ALL)
                return True, fixed_content, attempt
            else:
                print(Fore.RED + f"  ✗ Fix #{attempt} still has errors" + Style.RESET_ALL)
                # Update error message for next attempt
                error_message = new_error
                file_content = fixed_content
                
        except Exception as e:
            print(Fore.RED + f"Error during fix attempt: {e}" + Style.RESET_ALL)
            continue
    
    return False, None, max_attempts


def run_script_with_error(file_path):
    """
    Executes a Python script and returns success status and any error message.
    
    Args:
        file_path (str): The path to the Python script to execute.
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if _is_unittest_file(file_path):
        cmd = ["python", "-m", "unittest", file_path]
    else:
        cmd = ["python", file_path]
    
    SCRIPT_TIMEOUT = 30
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SCRIPT_TIMEOUT
        )
        return True, None
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except subprocess.TimeoutExpired:
        return True, None  # Timeout isn't a code error


def validate_and_correct_functions(enhanced_content):
    """
    Validates and corrects the function names imported from quantum_rt and their usages in the code.

    Args:
        enhanced_content (str): The Python code content.

    Returns:
        str: The corrected Python code content.
    """
    # Correct import statements
    import_pattern = re.compile(r"from\s+quantum_rt\s+import\s+([\w,\s]+)")
    matches = import_pattern.findall(enhanced_content)
    
    for match in matches:
        imported_functions = [func.strip() for func in match.split(',')]
        corrected_functions = []
        for func in imported_functions:
            # Check if the function name is correct
            if func in CORRECT_FUNCTION_NAMES:
                corrected_functions.append(func)
            elif func in MISSPELLED_FUNCTIONS:
                # Correct the misspelled function name
                corrected_func = MISSPELLED_FUNCTIONS[func]
                print(Fore.RED + f"Correcting import: '{func}' to '{corrected_func}'." + Style.RESET_ALL)
                corrected_functions.append(corrected_func)
                # Replace the misspelled function in the import statement
                enhanced_content = enhanced_content.replace(func, corrected_func)
            else:
                # Attempt to find the correct function name (case-insensitive)
                corrected_func = next((name for name in CORRECT_FUNCTION_NAMES if name.lower() == func.lower()), None)
                if corrected_func:
                    print(Fore.RED + f"Correcting import: '{func}' to '{corrected_func}'." + Style.RESET_ALL)
                    corrected_functions.append(corrected_func)
                    enhanced_content = enhanced_content.replace(func, corrected_func)
                else:
                    # If function name is unknown, log a warning
                    print(Fore.YELLOW + f"Warning: Unrecognized function '{func}' in import statement." + Style.RESET_ALL)
                    corrected_functions.append(func)
        
        # Reconstruct the import statement with corrected function names
        corrected_import = f"from quantum_rt import {', '.join(corrected_functions)}"
        # Replace the original import statement with the corrected one
        original_import = f"from quantum_rt import {', '.join(imported_functions)}"
        enhanced_content = enhanced_content.replace(original_import, corrected_import)
    
    # Correct function usages in the code
    for incorrect, correct in MISSPELLED_FUNCTIONS.items():
        # Create regex patterns to find function calls and definitions
        # For example: quffle(...) or def quffle(...):
        func_call_pattern = re.compile(rf"(?<!\w){incorrect}\b")
        matches = func_call_pattern.findall(enhanced_content)
        if matches:
            print(Fore.RED + f"Correcting function usage: '{incorrect}' to '{correct}'." + Style.RESET_ALL)
            enhanced_content = func_call_pattern.sub(correct, enhanced_content)
    
    return enhanced_content

def enhance_python_file(file_path, quiet_mode=False):
    file_name = os.path.basename(file_path)
    print(Fore.LIGHTMAGENTA_EX + f"Enhancing {file_name}" + Style.RESET_ALL)
    with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
        file_content = file.read()

    # Detect if this is a unittest file and branch prompt requirements
    is_test_file = _is_unittest_file(file_path, file_content)

    if is_test_file:
        core_requirements = """
You are to enhance and refine the following Python UNIT TEST file. Return ONLY the full, runnable Python test module.

Test-Focused Requirements:
- KEEP this file a unittest-based test module (do NOT convert to pytest unless already using it).
- Improve clarity & coverage; add edge case tests (empty inputs, error paths, boundary values) inferred from current tests.
- Factor repeated setup logic into helper functions / setUp methods where it improves readability without obscuring intent.
- Ensure tests are deterministic: avoid nondeterministic randomness; if quantum_rt randomness is *required*, wrap with a deterministic fallback or seed-like comment.
- Use clear, concise docstrings or Given / When / Then style comments above complex tests.
- Do NOT add production code here; only lightweight test helpers are allowed.
- Avoid network or external side effects. Use temporary directories / in-memory structures.
- Preserve existing test names unless they are misleading; if renamed, explain in a top-of-file comment.
- If flaky patterns detected (sleep calls, broad except), replace with deterministic checks.
- Maintain idempotence: rerunning the suite should yield identical results.
- At top of file include a short commented CHANGE LOG summarizing improvements.
"""
    else:
        core_requirements = """
You are to enhance and bugfix the following Python file. Your response must be a single Python file that will compile and run without errors.

Requirements:
- All output (print statements, file writes) must be sanitized for Windows console and file writes to prevent Unicode errors.
- Use type hints for all function signatures and class methods.
- Add clear, concise docstrings for all public functions, classes, and methods.
- Use logging instead of print statements for non-user-facing output, and follow logging best practices (configurable level, no excessive verbosity).
- Ensure code is modular and testable; avoid monolithic functions.
- Write explicit error messages and handle exceptions gracefully.
- Avoid deprecated modules and ensure cross-platform compatibility (Windows, macOS, Linux).
- If the file is empty or contains no Python code, innovate new code based on the file name.
- Follow object-oriented programming principles: make code modular, reusable, and easy to maintain.
- Extract complex logic into independent functions or classes where appropriate.
- Refactor for readability, performance, and Python best practices.
- Handle static lists by appending creatively and storing them in JSON files under the repository root directory 'tyJson'. Resolve the repository ROOT_DIR by walking parent directories from the current file until a 'tyJson' directory is found (or a .git directory), falling back to Path.cwd() if not found.
- Store physical exercise data in JSON files under the repository root 'exercises' directory (use the same ROOT_DIR resolution logic) and create the directory if missing.
- Store images in ROOT_DIR/'images', enhanced images in ROOT_DIR/'enhanced_images', videos in ROOT_DIR/'videos', and audio in ROOT_DIR/'recordings' (create any missing directories). Code may reside in nested folders such as 'tyPython', so never assume relative paths like './tyJson'; always derive absolute paths from ROOT_DIR.
- Always derive ROOT_DIR in enhanced code using something like:
  from pathlib import Path\n  def _resolve_root():\n      here = Path(__file__).resolve()\n      for p in [here] + list(here.parents):\n          if (p/"tyJson").exists() or (p/".git").exists():\n              return p\n      return here.parent\n  ROOT_DIR = _resolve_root()
  Then reference resources as (ROOT_DIR/"tyJson"/"file.json").
- Ensure JSON files are created from scratch if missing, and append to them if they exist. Initialize empty JSON files with defaults before loading.
- Replace 'python random' imports with 'quantum_rt' imports as specified below.
- Replace generic examples with specific, relevant ones.
- Implement known design patterns where applicable.
- Avoid user input, time.sleep, and endless loops like 'while(True)'.
- Address all TODO tags by marking them as DONE (or convert to FUTURE: with rationale if deferral warranted).
- Use concurrent.futures to parallelize processing where beneficial.
- Enhance error handling for API failures and I/O issues.
- Ensure all file and directory paths are handled robustly and portably (use os.path.join, pathlib, etc.).
- If the code is intended to be imported as a module, ensure it does not execute on import (use if __name__ == '__main__').
- If the file is a script, provide a clear entry point and argument parsing if appropriate.
- If the code interacts with external APIs or services, provide clear error messages and retry logic where appropriate.
- All comments in your output must be valid Python comments (no stray markdown).
"""

    quantum_requirements = """
Critical: The following quantum import functions must be preserved exactly as listed below (do not redefine or alter):
```python
from quantum_rt import qRandom, qRax, qhoice, quuffle, qsample, qpermute, qRandomBool, qRandomBitstring
```
If you see any misspellings or incorrect imports/usages, correct them to match the above.
"""

    additional_context = """
Additional instructions:
- Include comments explaining your changes and important design decisions.
- At the top of your response, provide a brief analysis of the file and a summary of the changes you made as comments.
- If you add or change any requirements, explain why in your comments.
"""

    prompt = f"{core_requirements}\n{quantum_requirements}\n{additional_context}\nFile to improve: {file_name}\nFile content to improve:\n{file_content}\n"
    if is_test_file:
        prompt += "\nNOTE: This is a TEST MODULE. Do NOT embed application logic."

    if not quiet_mode:
        print(Fore.LIGHTGREEN_EX + f"{file_content}" + Style.RESET_ALL)
    else:
        print(Fore.GREEN + f"  → Original: {len(file_content.splitlines())} lines, {len(file_content)} chars" + Style.RESET_ALL)
    prompt += "\n\nPlease include a detailed analysis of the file and the change set as comments in the code returned."

    # Call the OpenAI API Helper with prompt and messages
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
            ]
        }
    ]
    enhanced_content = openai_helper.get_chat_completion(messages=messages)

    # Strip code fences from the response
    enhanced_content = strip_code_fences(enhanced_content)

    # Validate and correct function names
    enhanced_content = validate_and_correct_functions(enhanced_content)

    formatted_content = enhanced_content
    return formatted_content

def generate_new_filename(batch_filenames):
    """
    Generates a new Python filename based on the context of the batch_filenames using OpenAI.

    Args:
        batch_filenames (list of str): List of 13 Python filenames.

    Returns:
        str: The generated new Python filename.
    """
    # Prepare the prompt for generating a new filename
    prompt = (
        "Based on the following Python filenames, suggest a meaningful and contextually relevant name for a new Python script that complements these files. "
        "Ensure the name follows Python naming conventions and clearly indicates its purpose. "
        "Provide only the filename without any Markdown formatting, backticks, or additional text.\n\n"
        "Here are the filenames:\n"
    )
    prompt += "\n".join(batch_filenames)
    prompt += "\n\nPlease provide only the suggested filename (e.g., practice_scheduler.py) without any explanations or additional formatting."

    # Call the OpenAI API to generate the new filename
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    
    response = openai_helper.get_chat_completion(messages=messages)

    # Clean the filename by stripping code fences and any unwanted text
    clean_filename = strip_filename_code_fences(response)

    # Ensure the filename ends with .py
    if not clean_filename.endswith(".py"):
        clean_filename += ".py"

    # Validate that the filename is a valid Python filename
    if not re.match(r'^[\w\-]+\.py$', clean_filename):
        print(Fore.RED + f"Invalid filename generated: '{clean_filename}'. Using default naming convention." + Style.RESET_ALL)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_filename = f"generated_script_{timestamp}.py"

    # Check if the filename already exists in the current directory
    original_clean_filename = clean_filename
    counter = 1
    while os.path.exists(clean_filename):
        # Append a numerical suffix to create a unique filename
        name, ext = os.path.splitext(original_clean_filename)
        clean_filename = f"{name}_{counter}{ext}"
        counter += 1
        print(Fore.YELLOW + f"Filename '{original_clean_filename}' already exists. Trying '{clean_filename}'." + Style.RESET_ALL)

    if clean_filename != original_clean_filename:
        print(Fore.GREEN + f"New unique filename generated: '{clean_filename}'." + Style.RESET_ALL)
    else:
        print(Fore.GREEN + f"Suggested filename accepted: '{clean_filename}'." + Style.RESET_ALL)

    return clean_filename

def process_files_in_directory(directory, exempt_file_path, batch_size=10, 
                                auto_mode=False, quiet_mode=False, no_sleep=False, dry_run=False,
                                stop_on_error=False, no_replace_on_error=False, fix_errors=False):
    """Process Python files within the given directory (non-recursive).

    Parameters
    ----------
    directory: str
        Directory to search for Python files (no recursion).
    exempt_file_path: str
        Path to a JSON file containing filenames to skip.
    batch_size: int, optional
        Number of processed files before generating a new filename.
    auto_mode: bool, optional
        If True, auto-approve all prompts without user input.
    quiet_mode: bool, optional
        If True, suppress full file content output.
    no_sleep: bool, optional
        If True, skip sleep delays between files.
    dry_run: bool, optional
        If True, don't replace original files, only create clones.
    stop_on_error: bool, optional
        If True, stop processing if an enhanced file fails to run.
    no_replace_on_error: bool, optional
        If True, don't replace original if enhanced version fails to run.
    fix_errors: bool, optional
        If True, attempt AI fix before rollback on errors.
    """
    global _current_file, _files_processed, _shutdown_requested

    exempt_files, exempt_prefixes = _load_exempt_config(exempt_file_path)

    files = []
    for fname in os.listdir(directory):
        # Skip JSON-exempt files and any file with an exempt prefix tag
        if (
            fname.endswith('.py')
            and fname not in exempt_files
            and not _is_prefixed_exempt(fname, exempt_prefixes)
        ):
            fpath = os.path.join(directory, fname)
            if os.path.isfile(fpath):
                files.append(fpath)
    
    total_files = len(files)
    processed_count = 0
    error_count = 0
    start_time = datetime.now()
    
    print(Fore.CYAN + f"\n{'='*60}" + Style.RESET_ALL)
    print(Fore.CYAN + f"TyClone Starting - {total_files} files to process" + Style.RESET_ALL)
    print(Fore.CYAN + f"Mode: auto={auto_mode}, quiet={quiet_mode}, no_sleep={no_sleep}, dry_run={dry_run}" + Style.RESET_ALL)
    print(Fore.CYAN + f"Error handling: stop_on_error={stop_on_error}, no_replace_on_error={no_replace_on_error}, fix_errors={fix_errors}" + Style.RESET_ALL)
    print(Fore.YELLOW + f"Kill switch: Create '{KILL_FILE}' file to stop gracefully" + Style.RESET_ALL)
    print(Fore.CYAN + f"{'='*60}\n" + Style.RESET_ALL)
    
    while files:
        # Check kill switch and shutdown flag
        if _shutdown_requested or _check_kill_switch():
            print(Fore.RED + f"\n🛑 Stopping... Processed {processed_count} files, {error_count} errors" + Style.RESET_ALL)
            print(Fore.YELLOW + f"Remaining files: {len(files)}" + Style.RESET_ALL)
            _print_session_summary()
            # Clean up kill file if it exists
            if KILL_FILE.exists():
                KILL_FILE.unlink()
                print(Fore.GREEN + f"Removed kill switch file" + Style.RESET_ALL)
            break
            
        file_path = qhoice(files)
        files.remove(file_path)
        filename = os.path.basename(file_path)
        _current_file = filename
        processed_count += 1
        
        # Progress indicator
        elapsed = datetime.now() - start_time
        print(Fore.CYAN + f"\n[{processed_count}/{total_files}] Processing: {filename}" + Style.RESET_ALL)
        print(Fore.CYAN + f"Elapsed: {elapsed} | Remaining: {len(files)} files | Errors: {error_count}" + Style.RESET_ALL)
        
        enhanced_content = enhance_python_file(file_path, quiet_mode=quiet_mode)
        
        if not quiet_mode:
            print(Fore.LIGHTRED_EX + f"{enhanced_content}" + Style.RESET_ALL)
        else:
            # In quiet mode, just show a summary
            lines = enhanced_content.count('\n') if enhanced_content else 0
            print(Fore.GREEN + f"✓ Enhanced: {lines} lines generated" + Style.RESET_ALL)

        # Save the enhanced content to the pyClones directory
        if enhanced_content:  # Only if there is any enhanced content
            clone_filename = os.path.splitext(filename)[0] + "Clone.py"
            clone_file_path = os.path.join(output_dir, clone_filename)

            with open(clone_file_path, 'w', encoding='utf-8') as clone_file:
                clone_file.write(enhanced_content)

            print(f"Enhanced clone created for {filename} as {clone_filename}")

            # Add the enhanced filename (full path) to the batch for richer context
            enhanced_batch.append(file_path)  # Store full path instead of just basename
            # Check if the batch size reached BATCH_SIZE
            if not quiet_mode:
                print(enhanced_batch)
            if len(enhanced_batch) == batch_size:
                print(
                    Fore.CYAN
                    + f"Batch of {batch_size} files reached. Generating a new filename based on this batch."
                    + Style.RESET_ALL
                )
                remaining_names = [os.path.basename(f) for f in files]
                new_filename = generate_new_filename(remaining_names)
                
                # Define the path for the new file in the current directory
                new_file_path = os.path.join(directory, new_filename)

                # Auto-approve in auto_mode, otherwise prompt
                if auto_mode:
                    approval = 'y'
                    print(Fore.YELLOW + f"[AUTO] Creating new file: '{new_filename}'" + Style.RESET_ALL)
                else:
                    approval = input(Fore.YELLOW + f"Do you want to create a new file named '{new_filename}' in the current directory? (y/n): " + Style.RESET_ALL)
                
                if approval.lower() == 'y':
                    # Create an empty new Python file
                    with open(new_file_path, 'w') as new_file:
                        pass  # Creates an empty file
                    print(Fore.GREEN + f"New file '{new_filename}' created successfully in the current directory." + Style.RESET_ALL)
                    _files_created.append(new_filename)  # Track new file
                else:
                    print(Fore.RED + "New file creation skipped." + Style.RESET_ALL)

                # Clear the batch
                enhanced_batch.clear()

            # Approval step for replacing original files (skip in dry_run mode)
            success = user_input(filename, file_path, enhanced_content, auto_mode=auto_mode, 
                                 no_sleep=no_sleep, dry_run=dry_run, no_replace_on_error=no_replace_on_error,
                                 fix_errors=fix_errors)
            if not success:
                error_count += 1
                if stop_on_error:
                    print(Fore.RED + f"\n🛑 Stopping due to error (--stop-on-error flag)" + Style.RESET_ALL)
                    print(Fore.YELLOW + f"Processed {processed_count} files, {error_count} errors" + Style.RESET_ALL)
                    _print_session_summary()
                    break

    # After processing all files, check if there's any remaining content in the batch
    if enhanced_batch and not _shutdown_requested:
        # **Enhanced Part: Display the list of input filenames**
        print(Fore.LIGHTMAGENTA_EX + "Current batch of files contributing to the new filename:" + Style.RESET_ALL)
        for idx, f in enumerate(enhanced_batch, start=1):
            print(Fore.BLUE + f"  {idx}. {f}" + Style.RESET_ALL)

        print(Fore.CYAN + f"Processing remaining {len(enhanced_batch)} files in the batch. Generating a new filename based on this batch." + Style.RESET_ALL)
        # Pass only basenames to generator
        new_filename = generate_new_filename([os.path.basename(p) for p in enhanced_batch])
        
        # Define the path for the new file in the current directory
        new_file_path = os.path.join(directory, new_filename)

        # Auto-approve in auto_mode, otherwise prompt
        if auto_mode:
            approval = 'y'
            print(Fore.YELLOW + f"[AUTO] Creating new file: '{new_filename}'" + Style.RESET_ALL)
        else:
            approval = input(Fore.YELLOW + f"Do you want to create a new file named '{new_filename}' in the current directory? (y/n): " + Style.RESET_ALL)
        
        if approval.lower() == 'y':
            # Create an empty new Python file
            with open(new_file_path, 'w') as new_file:
                pass  # Creates an empty file
            print(Fore.GREEN + f"New file '{new_filename}' created successfully in the current directory." + Style.RESET_ALL)
            _files_created.append(new_filename)  # Track new file
        else:
            print(Fore.RED + "New file creation skipped." + Style.RESET_ALL)

        # Clear the batch
        enhanced_batch.clear()
    
    # Final summary
    total_time = datetime.now() - start_time
    _print_session_summary()
    print(Fore.CYAN + f"\n{'='*60}" + Style.RESET_ALL)
    if _shutdown_requested or KILL_FILE.exists():
        print(Fore.YELLOW + f"TyClone Stopped! Processed {processed_count} files, {error_count} errors in {total_time}" + Style.RESET_ALL)
    else:
        print(Fore.GREEN + f"TyClone Complete! Processed {processed_count} files, {error_count} errors in {total_time}" + Style.RESET_ALL)
    print(Fore.CYAN + f"{'='*60}\n" + Style.RESET_ALL)

def user_input(filename, file_path, enhanced_content, auto_mode=False, no_sleep=False, dry_run=False, 
               no_replace_on_error=False, fix_errors=False):
    """
    Handles user input for approving and replacing original files or skipping/quitting.

    Args:
        filename (str): Name of the file being processed.
        file_path (str): Path to the original file.
        enhanced_content (str): Enhanced content to potentially replace the original.
        auto_mode (bool): If True, auto-approve without prompting.
        no_sleep (bool): If True, skip sleep delays.
        dry_run (bool): If True, don't replace original files.
        no_replace_on_error (bool): If True, restore original if run fails.
        fix_errors (bool): If True, attempt AI fix before rollback.
    
    Returns:
        bool: True if successful, False if the enhanced file failed to run.
    """
    global _files_processed
    
    # In dry_run mode, skip replacement entirely
    if dry_run:
        print(Fore.YELLOW + f"[DRY-RUN] Would replace {filename} (skipped)" + Style.RESET_ALL)
        return True

    # Save original content in case we need to rollback
    original_content = None
    if no_replace_on_error or fix_errors:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                original_content = f.read()
        except Exception as e:
            print(Fore.RED + f"Warning: Could not backup original {filename}: {e}" + Style.RESET_ALL)

    # For automation/testing, auto-approve
    user_input_choice = 't'

    if user_input_choice.lower() == 't':
        with open(file_path, 'w', encoding='utf-8') as original_file:
            original_file.write(enhanced_content)
        print(Fore.LIGHTRED_EX + f"Original file {filename} replaced with the enhanced clone." + Style.RESET_ALL)
        
        success, error_msg = run_script_with_error(file_path)
        
        # If failed and fix_errors is enabled, try AI fix
        if not success and fix_errors:
            print(Fore.YELLOW + f"⚠️  Enhanced version has errors. Attempting AI fix..." + Style.RESET_ALL)
            fix_success, fixed_content, attempts = attempt_ai_error_fix(
                file_path, enhanced_content, error_msg, max_attempts=3
            )
            if fix_success:
                success = True
                enhanced_content = fixed_content
                print(Fore.GREEN + f"✓ Fixed {filename} after {attempts} attempt(s)" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"✗ Could not fix {filename} after {attempts} attempts" + Style.RESET_ALL)
        
        # If still failed and rollback is enabled
        if not success and no_replace_on_error and original_content is not None:
            print(Fore.RED + f"⚠️  Enhanced version failed! Rolling back {filename}..." + Style.RESET_ALL)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                print(Fore.GREEN + f"✓ Restored original {filename}" + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"Error restoring original: {e}" + Style.RESET_ALL)
            return False
        
        _files_processed.append(filename)
        
        if not no_sleep:
            sleep(10)
        return success
        
    elif user_input_choice.lower() == 's':
        with open(file_path, 'w', encoding='utf-8') as original_file:
            original_file.write(enhanced_content)
        print(Fore.LIGHTRED_EX + f"Original file {filename} replaced with the enhanced clone." + Style.RESET_ALL)
        print("Exiting the script.")
        exit(0)  # Exit the script with status 0 (success)
    elif user_input_choice.lower() == 'q':
        print("Exiting the script.")
        exit(0)  # Exit the script with status 0 (success)
    
    return True

def process_files_with_exceptions(directory, batch_size=10):
    # Load configurable exemptions from the same default location as __main__ uses
    repo_root = _resolve_repo_root()
    exempt_path = repo_root / 'tyJson' / '!exceptional_python.json'
    if not exempt_path.exists():
        exempt_path = repo_root / 'tyJson' / 'exceptional_python.json'
    _, exempt_prefixes = _load_exempt_config(str(exempt_path))

    exception_files = return_exception_files()
    for filename in exception_files:
        # Respect exempt prefixes even for exception-driven processing
        if _is_prefixed_exempt(filename, exempt_prefixes):
            continue
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            enhanced_content = enhance_python_file(file_path)
            print(Fore.LIGHTRED_EX + f"{enhanced_content}" + Style.RESET_ALL)

            # Save the enhanced content to the pyClones directory
            if enhanced_content:  # Only if there is any enhanced content
                clone_filename = os.path.splitext(filename)[0] + "Clone.py"
                clone_file_path = os.path.join(output_dir, clone_filename)

                with open(clone_file_path, 'w') as clone_file:
                    clone_file.write(enhanced_content)

                print(f"Enhanced clone created for {filename} as {clone_filename}")

                # Add the enhanced filename (full path) to the batch for context
                enhanced_batch.append(file_path)  # Store full path

                # Check if the batch size reached BATCH_SIZE
                if len(enhanced_batch) == batch_size:
                    # **Enhanced Part: Display the list of input filenames**
                    print(Fore.BLUE + "Current batch of files contributing to the new filename:" + Style.RESET_ALL)
                    for idx, f in enumerate(enhanced_batch, start=1):
                        print(Fore.BLUE + f"  {idx}. {f}" + Style.RESET_ALL)

                    print(Fore.CYAN + f"Batch of {batch_size} files reached. Generating a new filename based on this batch." + Style.RESET_ALL)
                    # Use basenames when generating suggestion
                    new_filename = generate_new_filename([os.path.basename(p) for p in enhanced_batch])
                    
                    # Define the path for the new file in the current directory
                    new_file_path = os.path.join(directory, new_filename)

                    # Prompt for manual approval before creating the new file
                    approval = input(Fore.YELLOW + f"Do you want to create a new file named '{new_filename}' in the current directory? (y/n): " + Style.RESET_ALL)
                    if approval.lower() == 'y':
                        # Create an empty new Python file
                        with open(new_file_path, 'w') as new_file:
                            pass  # Creates an empty file
                        print(Fore.GREEN + f"New file '{new_filename}' created successfully in the current directory." + Style.RESET_ALL)
                    else:
                        print(Fore.RED + "New file creation skipped." + Style.RESET_ALL)

                    # Clear the batch
                    enhanced_batch.clear()

                # Manual approval step for replacing original files
                user_input(filename, file_path, enhanced_content)

    # After processing all exception files, check if there's any remaining content in the batch
    if enhanced_batch:
        # **Enhanced Part: Display the list of input filenames**
        print(Fore.BLUE + "Current batch of files contributing to the new filename:" + Style.RESET_ALL)
        for idx, f in enumerate(enhanced_batch, start=1):
            print(Fore.BLUE + f"  {idx}. {f}" + Style.RESET_ALL)

        print(Fore.CYAN + f"Processing remaining {len(enhanced_batch)} files in the batch. Generating a new filename based on this batch." + Style.RESET_ALL)
        # Use basenames for generation
        new_filename = generate_new_filename([os.path.basename(p) for p in enhanced_batch])
        
        # Define the path for the new file in the current directory
        new_file_path = os.path.join(directory, new_filename)

        # Prompt for manual approval before creating the new file
        approval = input(Fore.YELLOW + f"Do you want to create a new file named '{new_filename}' in the current directory? (y/n): " + Style.RESET_ALL)
        if approval.lower() == 'y':
            # Create an empty new Python file
            with open(new_file_path, 'w') as new_file:
                pass  # Creates an empty file
            print(Fore.GREEN + f"New file '{new_filename}' created successfully in the current directory." + Style.RESET_ALL)
        else:
            print(Fore.RED + "New file creation skipped." + Style.RESET_ALL)

        # Clear the batch
        enhanced_batch.clear()

def run_script(file_path):
    """
    Executes a Python script located at file_path using subprocess.
    If the target appears to be a unittest file, runs via 'python -m unittest'.
    Logs any exceptions that occur during execution to exception_log.txt
    in the same directory as the main script.

    Args:
        file_path (str): The path to the Python script to execute.
    
    Returns:
        bool: True if script executed successfully, False otherwise.
    """
    print(f"Running {file_path}")
    # Decide command based on detection
    if _is_unittest_file(file_path):
        cmd = ["python", "-m", "unittest", file_path]
    else:
        cmd = ["python", file_path]
    
    # Timeout to prevent hanging on scripts that don't terminate
    SCRIPT_TIMEOUT = 30  # seconds
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SCRIPT_TIMEOUT
        )
        print(Fore.LIGHTGREEN_EX + f"{file_path} executed successfully." + Style.RESET_ALL)
        print("Output:")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"Error executing {file_path}:" + Style.RESET_ALL)
        print(e.stderr)

        logged_exception = True  # Only log if both attempts fail
    except subprocess.TimeoutExpired:
        print(Fore.YELLOW + f"Script {file_path} timed out after {SCRIPT_TIMEOUT}s - skipping execution test." + Style.RESET_ALL)
        return True  # Don't count timeout as failure, just skip

        # If we did not already use unittest and error hints at unittest usage, retry
        if cmd[:3] != ["python", "-m", "unittest"] and (
            'unittest' in e.stderr.lower() or 'testcase' in e.stderr.lower()
        ) and _is_unittest_file(file_path):
            retry_cmd = ["python", "-m", "unittest", file_path]
            print(Fore.YELLOW + f"Retrying as unittest: {' '.join(retry_cmd)}" + Style.RESET_ALL)
            try:
                result2 = subprocess.run(
                    retry_cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                print(Fore.LIGHTGREEN_EX + f"{file_path} executed successfully (unittest mode)." + Style.RESET_ALL)
                print("Output:")
                print(result2.stdout)
                logged_exception = False
            except subprocess.CalledProcessError as e2:
                print(Fore.RED + f"Retry failed: {e2.stderr}" + Style.RESET_ALL)

        # If the error message contains 'usage:' or 'arguments', try to get suggested arguments from OpenAI
        if logged_exception and ("usage:" in e.stderr or "arguments" in e.stderr):
            print(Fore.YELLOW + "Detected usage/arguments error. Attempting to fetch correct command from OpenAI..." + Style.RESET_ALL)
            suggested_command = get_suggested_command(file_path, e.stderr)
            if suggested_command:
                print(Fore.CYAN + f"Retrying with suggested command: {suggested_command}" + Style.RESET_ALL)
                try:
                    cmd_args = suggested_command.split()
                    result2 = subprocess.run(cmd_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    print(Fore.LIGHTGREEN_EX + f"{file_path} executed successfully with arguments." + Style.RESET_ALL)
                    print("Output:")
                    print(result2.stdout)
                    logged_exception = False  # Success, do not log
                except subprocess.CalledProcessError as e2:
                    print(Fore.RED + f"Error executing with suggested arguments: {e2.stderr}" + Style.RESET_ALL)
        if logged_exception:
            # Prepare the log entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = (
                "====================\n"
                f"Timestamp: {timestamp}\n"
                f"Exception in file: {os.path.basename(file_path)}\n"
                f"{e.stderr.strip()}\n"
                "====================\n\n"
            )

            log_file_path = os.path.join(os.getcwd(), "exception_log.txt")

            try:
                os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
                MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB

                if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > MAX_LOG_SIZE:
                    new_log_name = f"exception_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    os.rename(log_file_path, os.path.join(os.path.dirname(log_file_path), new_log_name))
                    existing_logs = ""

                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r', encoding='utf-8') as log_file:
                        existing_logs = log_file.read()
                else:
                    existing_logs = ""

                with open(log_file_path, 'w', encoding='utf-8') as log_file:
                    log_file.write(log_entry + existing_logs)

                print(Fore.YELLOW + f"Logged exception to '{log_file_path}'." + Style.RESET_ALL)
            except Exception as log_error:
                print(Fore.RED + f"Failed to write to log file '{log_file_path}': {log_error}" + Style.RESET_ALL)
        
        return not logged_exception  # Return False if we logged an exception

def get_suggested_command(file_path, error_message):
    """
    Uses OpenAI to suggest the correct python command with arguments for a script, given the error message.
    Returns the command as a string, or None if not found.
    """
    script_name = os.path.basename(file_path)
    prompt = (
        f"Given the following error message when running a Python script, suggest the correct python command including any required arguments. "
        f"Only return the command, no explanation or formatting.\n\n"
        f"Script: {script_name}\n"
        f"Error message:\n{error_message}\n"
    )
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]
    response = openai_helper.get_chat_completion(messages=messages)
    # Clean up response: remove code fences, extra whitespace
    command = response.strip().replace('```', '').replace('python3', 'python')
    # Only return if it starts with 'python'
    if command.lower().startswith('python'):
        return command
    return None

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="AI-Powered Python File Enhancement Tool")
    parser.add_argument("-b", "--batch", type=int, default=10, help="Batch size for processing files (default: 10)")
    parser.add_argument("--auto", action="store_true", help="Fully automated mode: auto-approve all prompts (no user input needed)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode: suppress full file content output, show only summaries")
    parser.add_argument("--no-sleep", action="store_true", help="Skip sleep delays between files (faster processing)")
    parser.add_argument("--dry-run", action="store_true", help="Don't replace original files, only create clones")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop processing if an enhanced file fails to run")
    parser.add_argument("--no-replace-on-error", action="store_true", help="Don't replace original if enhanced version fails to run")
    parser.add_argument("--fix-errors", action="store_true", help="Attempt AI fix from error messages before rollback (up to 3 attempts)")
    args = parser.parse_args()

    # Resolve repo root and target tyPython directory
    repo_root = _resolve_repo_root()

    ty_dir = repo_root
    if not ty_dir.exists():
        print(Fore.RED + f"tyPython directory not found under {repo_root}. Aborting." + Style.RESET_ALL)
        raise SystemExit(1)

    # Exempt file path now resolved relative to repo root tyJson folder (prefer new name '!exceptional_python.json')
    exempt_path = repo_root / 'tyJson' / '!exceptional_python.json'
    if not exempt_path.exists():
        exempt_path = repo_root / 'tyJson' / 'exceptional_python.json'

    # Only process Python files under tyPython and create any new generated files in tyPython
    process_files_in_directory(
        str(ty_dir), 
        str(exempt_path), 
        args.batch,
        auto_mode=args.auto,
        quiet_mode=args.quiet,
        no_sleep=args.no_sleep,
        dry_run=args.dry_run,
        stop_on_error=args.stop_on_error,
        no_replace_on_error=args.no_replace_on_error,
        fix_errors=args.fix_errors
    )
    # process_files_with_exceptions(str(ty_dir), args.batch)
