import os
from pyexpat.errors import messages
from time import sleep
from quantum_rt import qhoice
from colorama import Fore, Style, init
from ty_py import loader
from ty_py import openai_helper
import concurrent.futures
import subprocess
from datetime import datetime
import re

# Create a directory to store the enhanced clones
output_dir = "pyClones"
os.makedirs(output_dir, exist_ok=True)

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

def enhance_python_file(file_path):
    file_name = os.path.basename(file_path)
    print(Fore.LIGHTMAGENTA_EX + f"enhancing {file_name}" + Style.RESET_ALL)
    with open(file_path, 'r', encoding='utf-8') as file:
        file_content = file.read()

    exception_log = read_exception_log(file_name)
    if exception_log:
        print(f"Found exception log for {file_name}")

    # # Prepare the prompt (optimized and clarified)
    prompt = f"""
You are an expert Python refactoring and bug-fixing assistant.

Task: Enhance and bugfix the file "{file_name}" to the best of your ability.

Requirements:
- Apply clean architecture and OOP where appropriate; keep code modular and maintainable.
- Extract complex logic into small, well-named functions/classes with type hints and docstrings.
- Improve readability, performance, and follow Python best practices (PEP 8/20, context managers, pathlib where suitable).
- Preserve public APIs used by other modules unless a change is essential; document any breaking change in the Change set.
- If the code uses any static lists, externalize them to JSON files:
  - General JSON: save under ./tyJson
  - Physical exercise JSON: save under ./exercises
  - Create JSON files if missing; if present and non-empty, append instead of overwriting.
  - If a JSON file is empty, initialize with sensible defaults before use.
- When reading/writing files, use UTF-8 encoding and handle empty or malformed JSON robustly with clear error handling.
- If you encounter references to quantum random helpers, keep them exactly (do NOT rename):
  from quantum_rt import qRandom, qRax, qsample, qhoice, qpermute, qRandomBool, qRandomBitstring
  - qRandom(n): random integer within 0..n (inclusive or as originally used in code)
  - qRax(min, max): random integer within [min, max]
  - qhoice(list): choose one item from list (note: function name is "qhoice", not "qchoice")
  - qsample(lst, k): choose k unique items from list
  - qpermute(list): return a permutation of the list
  - qRandomBool(), qRandomBitstring(...): retain usage
- Avoid: input()/interactive prompts, time.sleep(), and endless loops (e.g., while(True)). Use event-driven or bounded loops.
- Use logging where appropriate instead of print for reusable libraries; prints are acceptable for scripts.
- Keep Windows compatibility for paths; prefer pathlib for portability when appropriate.
- Images → ./images, Enhanced images → ./enhanced_images, Videos → ./videos, Audio recordings → ./recordings.
- If scope or time limits prevent full completion, add breadcrumbs and actionable TODOs for future models (e.g., "TODO:", "NEXT_MODEL_NOTES:") describing next steps, tests to add, and potential libraries to evaluate.

If an exception log for this file exists, consider it in your fixes and tests.

Output format (STRICT):
- Return exactly ONE fenced code block beginning with:
```python
# Optional: brief analysis as comments or module docstring
# ...
# Full, runnable Python file content follows
```
- Include the brief analysis and a "Change set" as comments INSIDE the code block only.
  - At the TOP, include a short analysis as a commented section or module docstring.
  - At the BOTTOM, include a commented header exactly:
# Change set
  followed by concise bullet points of changes, each starting with "- ".
  - Then include another commented header exactly:
# Future work
  with actionable breadcrumbs/TODOs for future enhancement attempts (e.g., tests to write, areas to refactor next, performance hotspots, API edge cases, data validation hardening, and candidate libs to consider).
- Do NOT include any text before or after the single code block.

File content to improve:
{file_content}
"""
    print(Fore.LIGHTGREEN_EX + f"{file_content}" + Style.RESET_ALL)
    if exception_log:
        prompt += f"\n\nAdditionally, consider the following exception log for this file and incorporate fixes if relevant:\n{exception_log}"
    prompt += "\n\nEnsure the code is self-contained and runnable."

    print(Fore.LIGHTYELLOW_EX + f"{prompt}")

    # Call the OpenAI API Helper with prompt and messages
    messages=[
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
            ]
        }
    ]
    response = openai_helper.get_chat_completion(messages=messages)

    # Get the enhanced content from the API response
    enhanced_content = response.choices.pop().message.content
    # Split the content into sections
    parts = enhanced_content.split('```python')
    pre_code = parts[0]
    python_code_part = parts[1] if len(parts) > 1 else ""
    post_code_part = parts[2] if len(parts) > 2 else ""
    
    python_code = python_code_part.split('```')[0]

    # Extract in-code commented sections for surfacing
    def _extract_section_from_code(code: str, header: str) -> str:
        """
        Extracts a commented section that starts with a line like `# {header}`
        and continues with subsequent comment lines.
        Returns the section text with leading comment markers stripped.
        """
        pattern = rf"(?mi)^\s*#\s*{re.escape(header)}\s*$\n(?P<body>(?:^\s*#.*\n)*)"
        m = re.search(pattern, code)
        if not m:
            return ""
        body = m.group('body')
        # Strip leading comment markers and whitespace
        lines = []
        for line in body.splitlines():
            # Only process lines that are comments
            if line.lstrip().startswith('#'):
                # remove leading spaces then one leading '#'
                stripped = line.lstrip()[1:]
                # remove one leading space after '#'
                if stripped.startswith(' '):
                    stripped = stripped[1:]
                lines.append(stripped)
            else:
                break
        return "\n".join(lines).strip()

    change_set = _extract_section_from_code(python_code, 'Change set')
    future_work = _extract_section_from_code(python_code, 'Future work')

    if change_set:
        print(Fore.CYAN + "\n=== Change set ===\n" + Style.RESET_ALL + change_set + "\n")
    if future_work:
        print(Fore.YELLOW + "\n=== Future work ===\n" + Style.RESET_ALL + future_work + "\n")

    post_code = post_code_part.split('\n\nChange set')[1] if '\n\nChange set' in post_code_part else ""

    # Format the content with comments
    formatted_content = ''
    if pre_code:
        formatted_content += '\n'.join(['# ' + line for line in pre_code.split('\n')]) + '\n'
    if python_code:
        formatted_content += python_code + '\n'
    if post_code:
        formatted_content += '\n'.join(['# ' + line for line in post_code.split('\n')])

    return formatted_content

def process_files_in_directory(directory, exempt_file_path):
    files = [f for f in os.listdir(directory) if (f.endswith(".py") and f not in loader.load_exempt_files(exempt_file_path))]
    while files:
        filename = qhoice(files)
        files.remove(filename)
        file_path = os.path.join(directory, filename)
        enhanced_content = enhance_python_file(file_path)
        print(Fore.LIGHTRED_EX + f"{enhanced_content}" + Style.RESET_ALL)

        # Save the enhanced content to the pyClones directory
        if enhanced_content:  # Only if there is any enhanced content
            clone_filename = os.path.splitext(filename)[0] + "Clone.py"
            clone_file_path = os.path.join(output_dir, clone_filename)

            with open(clone_file_path, 'w') as clone_file:
                clone_file.write(enhanced_content)

            print(f"Enhanced clone created for {filename} as {clone_filename}")

            # Manual break for evaluation
            user_input(filename,file_path,enhanced_content)
            

def user_input(filename, file_path, enhanced_content):
    user_input = 't'
    # user_input = input("Press 'T' to approve and replace the original file, 'S' to approve and Quit, or Enter to continue to the next file: ")

    if user_input.lower() == 't':
                with open(file_path, 'w') as original_file:
                    original_file.write(enhanced_content)
                print(f"Original file {filename} replaced with the enhanced clone.")
                run_script(file_path)
                sleep(10)
                #input("Press anything to continue")
    elif user_input == 's':
        with open(file_path, 'w') as original_file:
            original_file.write(enhanced_content)
        print(f"Original file {filename} replaced with the enhanced clone.")
        print("Exiting the script.")
        exit(0)  # Exit the script with status 0 (success)
    elif user_input == 'q':
        print("Exiting the script.")
        exit(0)  # Exit the script with status 0 (success)

def process_files_with_exceptions(directory):
    exception_files = return_exception_files()
    for filename in exception_files:
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            enhanced_content = enhance_python_file(file_path)
            print(Fore.LIGHTRED_EX + f"{enhanced_content}" + Style.RESET_ALL)

            # Save the enhanced content to the pyClones directory
            if enhanced_content:  # Only if there is any enhanced content
                clone_filename = os.path.splitext(filename)[0] + "Clone.py"
                clone_file_path = os.path.join(output_dir, clone_filename)

                with open(clone_file_path, 'w',encoding='utf-8') as clone_file:
                    clone_file.write(enhanced_content)

                print(f"Enhanced clone created for {filename} as {clone_filename}")

                # Manual break for evaluation
                user_input(filename,file_path,enhanced_content)

def run_script(file_path):
    """
    Executes a Python script located at file_path using subprocess.
    Logs any exceptions that occur during execution to exception_log.txt
    in the same directory as the main script.

    Args:
        file_path (str): The path to the Python script to execute.
    """
    print(f"Running {file_path}")
    try:
        # Execute the script using the same Python interpreter
        result = subprocess.run(
            ["python", file_path],
            check=True,                   # Raises CalledProcessError for non-zero exit codes
            stdout=subprocess.PIPE,       # Captures standard output
            stderr=subprocess.PIPE,       # Captures standard error
            text=True                     # Returns output as strings
        )
        print(f"{file_path} executed successfully.")
        print("Output:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing {file_path}:")
        print(e.stderr)
        
        # Prepare the log entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (
            "====================\n"
            f"Timestamp: {timestamp}\n"
            f"Exception in file: {os.path.basename(file_path)}\n"
            f"{e.stderr.strip()}\n"
            "====================\n\n"
        )
        
        # Define the path to exception_log.txt in the current working directory
        log_file_path = os.path.join(os.getcwd(), "exception_log.txt")
        
        try:
            # Ensure the directory exists (os.getcwd() should always exist, but included for completeness)
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB

            if os.path.getsize(log_file_path) > MAX_LOG_SIZE:
                # Rename the current log file with a timestamp
                new_log_name = f"exception_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                os.rename(log_file_path, os.path.join(os.path.dirname(log_file_path), new_log_name))
                existing_logs = ""
            
            # Read existing logs if any
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r', encoding='utf-8') as log_file:
                    existing_logs = log_file.read()
            else:
                existing_logs = ""
            
            # Prepend the new log entry
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                log_file.write(log_entry + existing_logs)
            
            print(f"Logged exception to '{log_file_path}'.")
        except Exception as log_error:
            print(f"Failed to write to log file '{log_file_path}': {log_error}")

if __name__ == "__main__":
    current_directory = os.getcwd()
    #process_files_in_directory(current_directory, 'tyJson/exceptional_python.json')
    process_files_in_directory(current_directory,'tyJson/exceptional_python.json')