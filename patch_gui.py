"""
patch_gui.py
Run this ONCE in Anaconda to fix gui_app.py:
  python patch_gui.py
"""
import os, re

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_app.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Change operation=ops[-1] to operation=ops
content = re.sub(
    r'operation\s*=\s*ops\[-1\]',
    'operation = ops  # all ops as list',
    content
)

# Fix 2: Remove the rotation-copy block that follows
content = re.sub(
    r'# If first op has rotation.*?operation\.pre_rotate_degrees=ops\[0\]\.pre_rotate_degrees\s*\n',
    '',
    content, flags=re.DOTALL
)

# Fix 3: Remove the broken "Using:" log line that accesses operation.hole_description
content = re.sub(
    r'root\.after\(0,lambda:_log\(\s*\n?\s*f"  Using: hole=\{operation\.hole_description.*?\}\s*\n?\s*f"depth=\{operation\.insertion_depth.*?\}\s*\n?\s*f"strategy=\{operation\.strategy\}","dim"\)\)',
    '',
    content, flags=re.DOTALL
)

# Fix 4: Also remove simpler single-line version
content = re.sub(
    r'root\.after\(0,lambda:_log\(f"  Using: hole=\{operation\.hole_description[^)]*\)\)',
    '',
    content
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# Verify
with open(path, "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if "hole_description" in line and "op.hole_description" not in line:
        print(f"WARNING still has issue at line {i}: {line.rstrip()}")

print("Done! gui_app.py patched.")
print("Now run: python gui_app.py")