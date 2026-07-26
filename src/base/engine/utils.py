
"""
@Time    : 2025-06-06
@Author  : didi & Zhaoyang
"""
import os
import re
import json
import types
import inspect
from pathlib import Path

from typing import Any, Awaitable, Callable, Dict, Optional, List
from base.engine.logs import logger

def parse_xml_content(content: str, tag: str) -> dict:
    """
    Parse the given content string and extract all occurrences of the specified XML tag.

    Args:
        content (str): The string containing XML-like data.
        tag (str): The tag name to search for.

    Returns:
        dict: A dictionary with the tag as key and a list of extracted values as value.
    """
    pattern = rf"<{tag}>(.*?)</{tag}>"
    matches = re.findall(pattern, content, re.DOTALL)
    # If only one match, return as string, else as list
    if not matches:
        return {tag: None}
    elif len(matches) == 1:
        return {tag: matches[0].strip()}
    else:
        return {tag: [m.strip() for m in matches]}

def read_file_content(file_path):
    """
    Read the entire content of a Python or YAML file.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The content of the file as a string.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()
    

def write_file_content(file_path, content):
    """
    Write the given content to a file, overwriting if it exists.

    Args:
        file_path (str): The path to the file.
        content (str): The content to write to the file.

    Returns:
        None
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def get_env_paths(base_path: str) -> List[str]:
    env_paths = []
    if os.path.exists(base_path):
        for item in os.listdir(base_path):
            if item.startswith("env_") and os.path.isdir(os.path.join(base_path, item)):
                env_paths.append(os.path.join(base_path, item))
    return env_paths


def archive_files(env_folder_path: str, env_id: str = None) -> bool:
    """
    Clean up environment directory by archiving auxiliary files.
    Keeps only core environment files in the root directory.
    
    Args:
        env_folder_path (str): Path to the environment folder
        env_id (str, optional): Environment ID for logging
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not env_folder_path:
        raise ValueError("env_folder_path cannot be empty")
    
    import subprocess
    import sys
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Resolve repo root robustly for both legacy layout and src/ layout.
    this_file = Path(__file__).resolve()
    src_root = this_file.parents[2]
    project_root = src_root.parent if src_root.name == "src" else src_root
    archive_script = os.path.join(str(project_root), "scripts", "run_archive_files.py")
    
    if env_id:
        logger.info(f"Archiving auxiliary files for environment: {env_id}")
    logger.info(f"Environment folder: {env_folder_path}")
    
    try:
        # Run the archive script
        result = subprocess.run(
            [sys.executable, archive_script, env_folder_path],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        
        if result.returncode == 0:
            logger.info("Directory cleanup completed successfully")
            logger.info(f"Archive output: {result.stdout}")
            
            # Create done.txt file to mark completion
            done_file_path = os.path.join(env_folder_path, "done.txt")
            write_file_content(done_file_path, "")
            logger.info(f"Created done.txt file: {done_file_path}")
            
            return True
        else:
            logger.error(f"Archive script failed with return code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error running archive script: {e}")
        return False

def parse_llm_output(resp: str, key: str) -> Dict[str, Any]:
    """
    Extract a value for `key` from an LLM response.

    Heuristics (in order):
    1) Try JSON inside ```json ... ``` block
    2) Try JSON inside ``` ... ``` block
    3) Try JSON from whole string or the first {...} blob
    4) Fallback to simple `key: value` line extraction
    """
    result: Dict[str, Any] = {key: None}

    if not resp:
        result["_parse_error"] = "empty_response"
        return result

    candidates: List[str] = []

    def _extract_block(marker: str) -> Optional[str]:
        start = resp.find(marker)
        if start == -1:
            return None
        start += len(marker)
        end = resp.find("```", start)
        return resp[start:end if end != -1 else None].strip()

    # ```json ... ```
    block = _extract_block("```json")
    if block:
        candidates.append(block)

    # ``` ... ```
    if not candidates:
        block = _extract_block("```")
        if block:
            candidates.append(block)

    # Raw whole string
    candidates.append(resp.strip())

    # First JSON-looking blob
    if "{" in resp and "}" in resp:
        blob = re.search(r"\{[\s\S]*\}", resp)
        if blob:
            candidates.append(blob.group(0))

    # Try to parse candidates as JSON and fetch key
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if isinstance(obj, dict) and key in obj:
            return {key: obj[key]}
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and key in item:
                    return {key: item[key]}

    # Fallback: simple key: value pattern
    m = re.search(rf"{re.escape(key)}\s*[:=]\s*(.+)", resp)
    if m:
        return {key: m.group(1).strip()}

    result["_parse_error"] = "key_not_found"
    logger.warning(f"Failed to parse key '{key}' from LLM output.")
    return result

def parse_llm_action_response(resp: str) -> Dict[str, Any]:
    """Parse LLM response to extract action data.
    
    This function handles various LLM response formats:
    - JSON wrapped in ```json``` blocks
    - JSON wrapped in ``` blocks  
    - Raw JSON strings
    - List responses (takes first action)
    - Malformed responses (returns default action)
    
    Args:
        resp: Raw LLM response string
        
    Returns:
        Dict containing action data with 'action' and 'params' keys
    """
    try:
        # Check if response is None or empty
        if not resp:
            logger.warning("Received None or empty response from LLM")
            return {"action": "no_action", "params": {}, "_parse_error": "Empty LLM response"}

        def _strip_think_blocks(text: str) -> str:
            return re.sub(r"<think\b[^>]*>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

        parse_source = _strip_think_blocks(resp) or resp

        def _extract_block(text: str, marker: str) -> Optional[str]:
            start = text.find(marker)
            if start == -1:
                return None
            start += len(marker)
            end = text.find("```", start)
            return text[start:end if end != -1 else None].strip()

        def _extract_code_blocks(text: str) -> List[str]:
            blocks: List[str] = []
            for match in re.finditer(r"```(?:json|JSON)?\s*([\s\S]*?)```", text):
                block = match.group(1).strip()
                if block:
                    blocks.append(block)
            return blocks

        def _extract_balanced_blocks(text: str, open_char: str, close_char: str) -> List[str]:
            """Return all balanced {...} or [...] blocks, not just the first one."""
            blocks: List[str] = []
            start: Optional[int] = None
            depth = 0
            in_string = False
            quote_char = ""
            escape = False
            for idx, ch in enumerate(text):
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch in ("'", '"'):
                    if in_string and ch == quote_char:
                        in_string = False
                        quote_char = ""
                    elif not in_string:
                        in_string = True
                        quote_char = ch
                    continue
                if in_string:
                    continue
                if ch == open_char:
                    if depth == 0:
                        start = idx
                    depth += 1
                elif ch == close_char and depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        blocks.append(text[start:idx + 1].strip())
                        start = None
            return blocks

        def _try_json_loads(text: str) -> (Optional[Any], Optional[str]):
            try:
                return json.loads(text), None
            except Exception as e:
                return None, f"{type(e).__name__}: {e}"

        def _try_yaml_loads(text: str) -> (Optional[Any], Optional[str]):
            try:
                import yaml

                value = yaml.safe_load(text)
                if isinstance(value, (dict, list)):
                    return value, None
                return None, f"YAML returned {type(value).__name__}, not dict/list"
            except Exception as e:
                return None, f"{type(e).__name__}: {e}"

        def _escape_unescaped_inner_quotes(text: str) -> str:
            """Heuristic: escape quotes that appear inside strings but are not closing delimiters."""
            out: List[str] = []
            in_string = False
            escape = False
            length = len(text)

            for i, ch in enumerate(text):
                if escape:
                    out.append(ch)
                    escape = False
                    continue
                if ch == "\\":
                    out.append(ch)
                    escape = True
                    continue
                if ch == '"':
                    if not in_string:
                        in_string = True
                        out.append(ch)
                        continue

                    # We are inside a string; decide whether this is an end quote or needs escaping.
                    j = i + 1
                    next_nonspace = None
                    while j < length and text[j].isspace():
                        j += 1
                    if j < length:
                        next_nonspace = text[j]

                    if next_nonspace in (",", "}", "]", None):
                        in_string = False
                        out.append(ch)
                    else:
                        out.append("\\\"")
                    continue

                out.append(ch)

            return "".join(out)

        candidates: List[str] = []

        def _add_candidate(text: Optional[str]) -> None:
            if text:
                stripped_text = text.strip()
                if stripped_text and stripped_text not in candidates:
                    candidates.append(stripped_text)

        for source in (parse_source, resp):
            block = _extract_block(source, "```json")
            _add_candidate(block)

        for source in (parse_source, resp):
            for block in _extract_code_blocks(source):
                _add_candidate(block)

        block = _extract_block(parse_source, "```")
        _add_candidate(block)

        _add_candidate(parse_source)
        _add_candidate(resp)

        for source in (parse_source, resp):
            for extra in [*_extract_balanced_blocks(source, "{", "}"), *_extract_balanced_blocks(source, "[", "]")]:
                _add_candidate(extra)

        parse_errors: List[str] = []

        for cand in candidates:
            action_data, err = _try_json_loads(cand)
            if action_data is None:
                sanitized = _escape_unescaped_inner_quotes(cand)
                if sanitized != cand:
                    action_data, err2 = _try_json_loads(sanitized)
                    if action_data is None:
                        yaml_data, yaml_err = _try_yaml_loads(cand)
                        if yaml_data is None:
                            parse_errors.append(f"{err}; after sanitizing quotes -> {err2}; yaml -> {yaml_err}")
                            continue
                        action_data = yaml_data
                    else:
                        logger.warning("Recovered action JSON by escaping inner quotes inside strings.")
                else:
                    action_data, yaml_err = _try_yaml_loads(cand)
                    if action_data is None:
                        parse_errors.append(f"{err}; yaml -> {yaml_err}")
                        continue
                    logger.warning("Recovered action JSON with YAML-compatible parsing.")
            elif not isinstance(action_data, (dict, list)):
                parse_errors.append(f"JSON returned {type(action_data).__name__}, not dict/list")
                continue

            # Handle case where LLM returns a list instead of single action
            if isinstance(action_data, list):
                first_action = next((item for item in action_data if isinstance(item, dict) and "action" in item), None)
                if first_action is not None:
                    logger.warning("LLM returned a list of actions; taking the first action entry")
                    action_data = first_action
                elif not action_data:
                    parse_errors.append("Empty list returned by LLM")
                    continue
                else:
                    parse_errors.append("List returned by LLM contains no action entry")
                    continue

            # Ensure action_data has required structure
            if not isinstance(action_data, dict) or "action" not in action_data:
                parse_errors.append("Missing 'action' key or invalid dict")
                continue

            return action_data

        error_detail = "; ".join(parse_errors) if parse_errors else "Unknown parse failure"
        logger.warning(f"Failed to parse action JSON. Tried {len(candidates)} candidates. Errors: {error_detail}. Using default action. Raw response: {resp}")
        return {"action": "Invalid", "params": {}, "_parse_error": error_detail}
    except Exception as e:
        logger.warning(f"Unexpected error while parsing action: {e}. Using default action.")
        return {"action": "Invalid", "params": {}, "_parse_error": f"{type(e).__name__}: {e}"}

def _load_basic_info(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def summarize_candidates(workspace_path: str) -> Dict[str, Any]:
    """
    Summarize candidates under <workspace_path>/candidates.

    For each candidate, compute deltas vs parent and a success flag:
      success := (acc_child > acc_parent) or (acc_child == acc_parent and cost_child < cost_parent)

    Returns a dict and also writes:
      - <workspace_path>/summary.json
      - <workspace_path>/candidates/candidate_<n>/optimization_result.json
    """
    cdir = os.path.join(workspace_path, "candidates")
    result: Dict[str, Any] = {
        "workspace_path": workspace_path,
        "candidates": [],
        "edges": [],
        "best": None,
    }

    if not os.path.isdir(cdir):
        with open(os.path.join(workspace_path, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    # Load basics
    basics_by_round: Dict[int, Dict[str, Any]] = {}
    for name in sorted(os.listdir(cdir)):
        if not name.startswith("candidate_"):
            continue
        try:
            r = int(name.split("_")[-1])
        except Exception:
            continue
        info = _load_basic_info(os.path.join(cdir, name, "basic_info.json")) or {}
        info["folder_name"] = name
        basics_by_round[r] = info

    # Build summaries
    def _m(info: Dict[str, Any], key: str) -> Optional[float]:
        try:
            val = (info.get("metrics") or {}).get(key)
            return None if val is None else float(val)
        except Exception:
            return None

    best = {"round": None, "accuracy": -1.0, "cost": None}
    for r in sorted(basics_by_round.keys()):
        info = basics_by_round[r]
        parent = info.get("parent")
        acc = _m(info, "accuracy")
        cost = _m(info, "cost")
        parent_acc = None
        parent_cost = None
        acc_delta = None
        cost_delta = None
        success = None

        if parent is not None and parent in basics_by_round:
            pinfo = basics_by_round[parent]
            parent_acc = _m(pinfo, "accuracy")
            parent_cost = _m(pinfo, "cost")
            if parent_acc is not None and acc is not None:
                acc_delta = acc - parent_acc
            if parent_cost is not None and cost is not None:
                cost_delta = cost - parent_cost
            # Success rule
            if acc is not None and parent_acc is not None:
                if acc > parent_acc:
                    success = True
                elif acc == parent_acc and (cost is not None and parent_cost is not None) and cost < parent_cost:
                    success = True
                else:
                    success = False
            else:
                success = False

            result["edges"].append([parent, r])

        # Update best
        if acc is not None and acc > best["accuracy"]:
            best = {"round": r, "accuracy": acc, "cost": cost}

        item = {
            "round": r,
            "parent": parent,
            "accuracy": acc,
            "cost": cost,
            "parent_accuracy": parent_acc,
            "parent_cost": parent_cost,
            "acc_delta": acc_delta,
            "cost_delta": cost_delta,
            "success": success,
            "trajectory_path": info.get("trajectory_path"),
        }
        result["candidates"].append(item)

        # Write per-candidate summary
        try:
            with open(os.path.join(cdir, info.get("folder_name"), "optimization_result.json"), "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    result["best"] = best if best["round"] is not None else None

    # Write root summary
    try:
        with open(os.path.join(workspace_path, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result
