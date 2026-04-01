"""
ai_prompt_engine.py
--------------------
Uses the Claude API to understand ANY natural language assembly prompt
and convert it into structured AssemblyInstruction parameters.

This replaces the regex-based prompt_parser for complex prompts.
Falls back to regex parser if API call fails.

User can say ANYTHING:
  "the shaft should go halfway into the ring"
  "assemble like a knuckle joint with pin through the fork"
  "I want 2mm clearance and the bolt should be flush with the surface"
  "put the bearing inside the housing completely"
  "align the two plates face to face with a 1mm gap between them"
"""

import json
import re
from typing import Optional

# Import fallback parser
from prompt_parser import AssemblyInstruction, parse_prompt


def parse_prompt_with_ai(user_prompt: str,
                          part_a_info: dict,
                          part_b_info: dict) -> AssemblyInstruction:
    """
    Use Claude API to understand the user's assembly intent.

    Args:
        user_prompt:  What the user typed
        part_a_info:  Dict with name, type, cylinders, planes info
        part_b_info:  Same for part b

    Returns:
        AssemblyInstruction with all parameters filled in
    """
    try:
        result = _call_claude_api(user_prompt, part_a_info, part_b_info)
        if result:
            return result
    except Exception as e:
        print(f"[AI] API call failed: {e} — using fallback parser")

    # Fallback to regex parser
    return parse_prompt(user_prompt)


def _call_claude_api(user_prompt: str,
                      part_a_info: dict,
                      part_b_info: dict) -> Optional[AssemblyInstruction]:
    """Call Claude API and parse the structured response."""
    import urllib.request

    system_prompt = """You are a CAD assembly expert. A user will describe how they want two mechanical parts assembled.
Your job is to extract the assembly parameters and return them as JSON.

Return ONLY a JSON object with these exact fields (no explanation, no markdown):
{
  "assembly_type": "shaft_hole" | "plane" | "slot" | "bolt_pattern" | "side_by_side" | "auto",
  "insertion_depth_mm": null or number (how many mm of shaft goes into hole),
  "full_depth": true or false (shaft goes completely through),
  "press_fit": true or false,
  "clearance_mm": null or number (diametral clearance in mm),
  "gap_mm": null or number (gap between faces in mm),
  "prefer_cylinder": true or false,
  "prefer_plane": true or false,
  "flush": true or false (faces touch with no gap),
  "side_by_side": true or false (just place next to each other),
  "notes": "brief explanation of what you understood"
}

Rules:
- "halfway" means insertion_depth = shaft_length / 2 (use full_depth=false, insertion_depth=null, set a note)
- "fully" or "completely" or "through" = full_depth=true
- "press fit" or "force fit" = press_fit=true, assembly_type=shaft_hole
- "clearance fit" = press_fit=false
- "flush" or "face to face" = assembly_type=plane, flush=true
- "side by side" or "next to" = side_by_side=true
- "knuckle joint" or "pin through fork" = assembly_type=shaft_hole, full_depth=true
- if unclear, use assembly_type=auto"""

    context = f"""Parts information:
Part A: {part_a_info.get('name','part_a')} - type: {part_a_info.get('type','unknown')}
  Cylinders: {part_a_info.get('cylinders',[])}
  Planes: {part_a_info.get('n_planes',0)} detected

Part B: {part_b_info.get('name','part_b')} - type: {part_b_info.get('type','unknown')}
  Cylinders: {part_b_info.get('cylinders',[])}
  Planes: {part_b_info.get('n_planes',0)} detected

User wants: {user_prompt}"""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 500,
        "system": system_prompt,
        "messages": [{"role": "user", "content": context}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # Extract text from response
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")

    # Parse JSON from response
    text = text.strip()
    # Remove markdown code blocks if present
    text = re.sub(r"```json\s*|\s*```", "", text).strip()

    parsed = json.loads(text)
    return _json_to_instruction(parsed, user_prompt)


def _json_to_instruction(data: dict, raw_prompt: str) -> AssemblyInstruction:
    """Convert Claude's JSON response to AssemblyInstruction."""
    inst = AssemblyInstruction(raw_prompt=raw_prompt)

    inst.assembly_type = data.get("assembly_type", "auto")

    depth = data.get("insertion_depth_mm")
    inst.insertion_depth = float(depth) if depth is not None else None

    inst.full_depth      = bool(data.get("full_depth", False))
    inst.press_fit       = bool(data.get("press_fit", False))
    inst.prefer_cylinder = bool(data.get("prefer_cylinder", False))
    inst.prefer_plane    = bool(data.get("prefer_plane", False))
    inst.flush           = bool(data.get("flush", False))
    inst.side_by_side    = bool(data.get("side_by_side", False))

    gap = data.get("gap_mm")
    inst.gap = float(gap) if gap is not None else None

    cl = data.get("clearance_mm")
    inst.clearance = float(cl) if cl is not None else None

    if inst.press_fit:
        inst.clearance = inst.clearance or -0.02

    # Set flags based on assembly_type
    if inst.assembly_type == "shaft_hole":
        inst.prefer_cylinder = True
    elif inst.assembly_type in ("plane", "slot"):
        inst.prefer_plane = True
    elif inst.assembly_type == "bolt_pattern":
        inst.prefer_bolt = True
    elif inst.assembly_type == "side_by_side":
        inst.side_by_side = True

    # Default: if full_depth not set and no depth given, default to full
    if not inst.full_depth and inst.insertion_depth is None:
        if inst.assembly_type == "shaft_hole" or inst.prefer_cylinder:
            inst.full_depth = True

    inst.confidence = 0.95  # AI parsing is high confidence
    inst.ai_notes   = data.get("notes", "")

    return inst


def build_part_info(part) -> dict:
    """Build a simple dict describing a part for the AI prompt."""
    cyls = []
    for c in part.cylinders[:4]:  # max 4 cylinders in context
        cyls.append({
            "diameter_mm": round(c.diameter, 2),
            "length_mm":   round(c.length, 2),
            "type":        "hole" if c.is_hole else "shaft"
        })

    return {
        "name":      part.name,
        "type":      part.part_type,
        "cylinders": cyls,
        "n_planes":  len(part.planes),
        "bbox":      [round(d, 1) for d in part.bbox_dims],
    }