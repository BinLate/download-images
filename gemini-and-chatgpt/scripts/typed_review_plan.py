import re

def build_plan(text: str) -> dict:
    prompt_id_match = re.search(r"^PROMPT_ID:\s*([^\s]+)", text, re.MULTILINE)
    target_head_sha_match = re.search(r"^TARGET_HEAD_SHA:\s*([^\s]+)", text, re.MULTILINE)
    
    prompt_id = prompt_id_match.group(1) if prompt_id_match else None
    target_head_sha = target_head_sha_match.group(1) if target_head_sha_match else None
    
    actions = []
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.replace('\r', '')
        if line:
            actions.append({"action": "TYPE_TEXT", "text": line})
        if i < len(lines) - 1:
            actions.append({"action": "SHIFT_ENTER"})
            
    return {
        "transport": "TYPED_FALLBACK_LINE_SAFE",
        "actions": actions,
        "prompt_id": prompt_id,
        "target_head_sha": target_head_sha
    }
