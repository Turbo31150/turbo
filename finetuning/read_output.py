"""Read the training output file and extract content after loading bars."""
import sys

filepath = sys.argv[1] if len(sys.argv) > 1 else (
    r"C:\Users\franc\AppData\Local\Temp\claude\C--Users-franc\tasks\b61f00b.output"
)

try:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
except PermissionError:
    # Try with file sharing
    import io
    with open(filepath, "rb") as f:
        raw = f.read()
    content = raw.decode("utf-8", errors="replace")

# Split on newlines and carriage returns
lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

# Filter out progress bar lines and empty lines
meaningful = []
for line in lines:
    stripped = line.strip()
    if not stripped:
        continue
    if stripped.startswith("Loading weights:"):
        continue
    meaningful.append(stripped)

print(f"Total lines: {len(lines)}")
print(f"Meaningful lines: {len(meaningful)}")
print("\n=== MEANINGFUL OUTPUT ===")
for line in meaningful:
    safe = line.encode("ascii", errors="replace").decode("ascii")
    print(safe)
