import os
import re
import subprocess
import datetime
import textwrap
from pathlib import Path
import argparse

# Folders and files
DOCS_FOLDER = "docs"         # Folder containing .mdx files
OUTPUT_DIR = "temp_code"     # Folder to output generated code files
REPORT_FILE = "report.txt"   # File to write execution report

# Mapping of languages to file extension and execution command
LANGUAGE_CONFIG = {
    "python": {"ext": ".py", "exec_cmd": ["python"]},
    "javascript": {"ext": ".js", "exec_cmd": ["node"]},
    "bash": {"ext": ".sh", "exec_cmd": ["bash"]},
}

#Identify MDX Files with <Steps> Tags

def find_mdx_files_with_steps(root_folder):
    """
    Recursively search for .mdx files in 'root_folder' that contain a <Steps> block.
    
    Returns:
        List of file paths.
    """
    mdx_files = []
    for dirpath, _, filenames in os.walk(root_folder):
        for fname in filenames:
            if fname.endswith(".mdx"):
                path = os.path.join(dirpath, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "<Steps>" in content and "</Steps>" in content:
                        mdx_files.append(path)
                except Exception as e:
                    print(f"Error reading {path}: {e}")
    return mdx_files

def extract_steps_section(content):
    """
    Extract the content within the first <Steps> ... </Steps> block.
    
    Args:
        content (str): The full MDX file content.
    
    Returns:
        The content inside the <Steps> block (or an empty string if not found).
    """
    match = re.search(r"<Steps>(.*?)</Steps>", content, re.DOTALL)
    return match.group(1) if match else ""

#Parsing Each <Step> Block

def extract_steps(steps_content):
    """
    Parse the <Steps> block into an ordered list of step dictionaries.
    
    Each step dictionary has:
      - "title": The step title.
      - "common_code": dict mapping language to list of code snippets (from code blocks outside <Tabs>).
      - "tabs": dict mapping tab title to dict of language to list of code snippets (from code blocks inside <Tab>).
    
    Returns:
        List of step dictionaries.
    """
    steps = []
    step_pattern = re.compile(r"<Step\b([^>]*)>(.*?)</Step>", re.DOTALL)
    for step_match in step_pattern.finditer(steps_content):
        step_attrs = step_match.group(1)
        step_body = step_match.group(2)
        # Extract step title 
        title_match = re.search(r'title\s*=\s*"([^"]+)"', step_attrs)
        step_title = title_match.group(1) if title_match else "untitled_step"
        
        # Step dictionary
        step_dict = {"title": step_title, "common_code": {}, "tabs": {}}
        
        # Check if step has <Tabs>
        tabs_match = re.search(r"<Tabs>(.*?)</Tabs>", step_body, re.DOTALL)
        if tabs_match:
            tabs_content = tabs_match.group(1)
            # Code outside the <Tabs> block is considered common code.
            outside_body = step_body.replace(tabs_match.group(0), "")
            extract_code_blocks_into(outside_body, step_dict["common_code"])
            # Process each <Tab>
            tab_pattern = re.compile(r"<Tab\b([^>]*)>(.*?)</Tab>", re.DOTALL)
            for tmatch in tab_pattern.finditer(tabs_content):
                tab_attrs = tmatch.group(1)
                tab_body = tmatch.group(2)
                tab_title_match = re.search(r'title\s*=\s*"([^"]+)"', tab_attrs)
                tab_title = tab_title_match.group(1) if tab_title_match else "untitled_tab"
                step_dict["tabs"].setdefault(tab_title, {})
                extract_code_blocks_into(tab_body, step_dict["tabs"][tab_title])
        else:
            # No <Tabs>: all code in the step is common.
            extract_code_blocks_into(step_body, step_dict["common_code"])
        
        steps.append(step_dict)
    return steps

def extract_code_blocks_into(text, code_map):
    """
    Extract code blocks in the given text and add them to code_map.
    
    A code block is defined as:
        ```lang
        code...
        ```
    If no language is specified, the block is skipped.
    
    Args:
        text (str): The text to search.
        code_map (dict): Dictionary mapping language to list of code snippets.
    """
    code_block_pattern = re.compile(r"(?m)^\s*```([\w+-]+)?[^\n]*\n(.*?)^\s*```", re.DOTALL)
    for match in code_block_pattern.finditer(text):
        lang = match.group(1)
        code = textwrap.dedent(match.group(2)).strip()
        if not lang:
            # Skip code blocks without a language label.
            continue
        lang = lang.lower()
        if lang in LANGUAGE_CONFIG:
            code_map.setdefault(lang, []).append(code)

#Build Workflow Branches by Matching Tab Names

def build_branches_for_language(steps, lang):
    """
    Build final workflow branches for a given language.
    
    The workflow is built step-by-step:
      - For a step with no tabs for 'lang', append its common code to every branch.
      - For a step with tabs for 'lang', for each tab:
          * If a branch with that tab name already exists, append the tab's code.
          * Otherwise, create a new branch.
    
    Args:
        steps (list): List of step dictionaries.
        lang (str): The language to build branches for.
    
    Returns:
        Dict mapping branch name (str) to the combined code (str).
        The default branch (no specific tab) is represented by an empty string.
    """
    current = {"": ""}  # Start with a default "common" branch.
    
    for step in steps:
        common_list = step["common_code"].get(lang, [])
        combined_common = "\n\n".join(common_list).strip()
        
        # Collect valid tabs for this step (only those that have code for 'lang')
        valid_tabs = {}
        for ttitle, lang_map in step["tabs"].items():
            if lang in lang_map:
                snippets = lang_map[lang]
                if snippets:
                    valid_tabs[ttitle] = "\n\n".join(snippets).strip()
        
        if not valid_tabs:
            # No tabs for this step: append common code to all current branches.
            if combined_common:
                for branch in current:
                    current[branch] = (current[branch] + "\n\n" + combined_common).strip()
            continue
        
        # Step has valid tabs: first, append common code to all branches.
        if combined_common:
            for branch in current:
                current[branch] = (current[branch] + "\n\n" + combined_common).strip()
        
        # Then process tabs: unify branches by tab name.
        new_branches = {}
        used_tab_titles = set()
        for branch, code_so_far in current.items():
            for ttitle, tcode in valid_tabs.items():
                if ttitle == branch:
                    # Matching branch: append tab code.
                    new_branches[ttitle] = (code_so_far + "\n\n" + tcode).strip()
                    used_tab_titles.add(ttitle)
                elif branch == "":
                    # Default branch: create a new branch with this tab title.
                    new_branches[ttitle] = (code_so_far + ("\n\n" + tcode if tcode else "")).strip()
                    used_tab_titles.add(ttitle)
                else:
                    # Retain existing branch if not overwritten.
                    if branch not in new_branches:
                        new_branches[branch] = code_so_far
        # For any tab not yet represented, create a new branch.
        for ttitle, tcode in valid_tabs.items():
            if ttitle not in used_tab_titles:
                new_branches[ttitle] = (combined_common + "\n\n" + tcode).strip() if combined_common else tcode
        current = new_branches
    
    # Trim whitespace in all branches.
    for key in current:
        current[key] = current[key].strip()
    return current

#Execute Code Files
def execute_code_file(file_path, lang):
    """
    Execute the generated code file for the given language and capture its output.
    
    Args:
        file_path (str): Path to the generated file.
        lang (str): The language (must be in LANGUAGE_CONFIG).
    
    Returns:
        Dict with keys "output", "error", and "exit_code".
    """
    config = LANGUAGE_CONFIG[lang]
    cmd = config["exec_cmd"] + [file_path]
    timeout = None if lang == "bash" else 30
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "output": proc.stdout.strip(),
            "error": proc.stderr.strip(),
            "exit_code": proc.returncode
        }
    except subprocess.TimeoutExpired as e:
        return {
            "output": e.stdout or "",
            "error": f"Command timed out: {e}",
            "exit_code": -1
        }
    except Exception as e:
        return {"output": "", "error": str(e), "exit_code": -1}


def main():
    parser = argparse.ArgumentParser(
        description="Build code workflows from MDX <Steps> with tab-based branch unification."
    )
    parser.add_argument("--extract_only", action="store_true",
                        help="Only generate code files; do not execute them.")
    args = parser.parse_args()

    mdx_files = find_mdx_files_with_steps(DOCS_FOLDER)
    report_lines = ["Code Execution Report", "=" * 80, ""]
    
    if not mdx_files:
        msg = "No MDX files with <Steps> found."
        print(msg)
        report_lines.append(msg)
    
    for mdx_file in mdx_files:
        msg = f"Processing: {mdx_file}"
        print(msg)
        report_lines.append(msg)
        
        try:
            with open(mdx_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            err_msg = f"  Could not read file: {e}"
            print(err_msg)
            report_lines.append(err_msg)
            continue
        
        steps_block = extract_steps_section(content)
        if not steps_block:
            err_msg = "  No <Steps> section found; skipping."
            print(err_msg)
            report_lines.append(err_msg)
            continue
        
        steps = extract_steps(steps_block)
        if not steps:
            err_msg = "  No steps found after parsing."
            print(err_msg)
            report_lines.append(err_msg)
            continue
        
        # Determine all languages used in the steps.
        all_langs = set()
        for step in steps:
            all_langs.update(step["common_code"].keys())
            for tab_langs in step["tabs"].values():
                all_langs.update(tab_langs.keys())
        
        # For each language, build the workflow branches.
        for lang in all_langs:
            branch_map = build_branches_for_language(steps, lang)
            # branch_map is a dict { branch_name: final_code }
            for branch_name, final_code in branch_map.items():
                base_name = Path(mdx_file).stem
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                ext = LANGUAGE_CONFIG[lang]["ext"]
                if branch_name:
                    out_file = f"{base_name}_{branch_name}_{timestamp}{ext}"
                else:
                    out_file = f"{base_name}_{timestamp}{ext}"
                out_path = os.path.join(OUTPUT_DIR, out_file)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                
                with open(out_path, "w", encoding="utf-8") as wf:
                    wf.write(final_code)
                
                gen_msg = f"File generated: {out_path} (lang={lang}, branch={branch_name or 'common'})"
                print(gen_msg)
                report_lines.append(gen_msg)
                
                if not args.extract_only:
                    exec_res = execute_code_file(out_path, lang)
                    emoji = "✅" if exec_res["exit_code"] == 0 else "❌"
                    status_line = f"File tested: {'successful' if exec_res['exit_code'] == 0 else 'unsuccessful'} {emoji}"
                    print(status_line)
                    report_lines.append(status_line)
                    print("Output:")
                    report_lines.append("Output:")
                    if exec_res["output"]:
                        for line in exec_res["output"].splitlines():
                            l = "  " + line
                            print(l)
                            report_lines.append(l)
                    else:
                        no_out = "  (No output)"
                        print(no_out)
                        report_lines.append(no_out)
                    if exec_res["error"]:
                        print("Errors:")
                        report_lines.append("Errors:")
                        for line in exec_res["error"].splitlines():
                            er = "  " + line
                            print(er)
                            report_lines.append(er)
                else:
                    skip_msg = "  (Execution skipped via --extract_only)"
                    print(skip_msg)
                    report_lines.append(skip_msg)
            
            divider = "-" * 80
            print(divider)
            report_lines.append(divider)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as rf:
        rf.write("\n".join(report_lines))
    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    main()