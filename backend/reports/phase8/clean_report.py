import re

with open("backend/reports/phase8/PHASE8_FINAL_REPORT.md", "r") as f:
    text = f.read()

# Remove the two empty Decision Benchmark blocks (lines containing "0.00 m")
while True:
    match = re.search(r"## Phase 8 Decision Benchmark\n\n\| Combination.*?Interaction Result.*?\n\n", text, re.DOTALL)
    if not match:
        break
    if "0.00 m" in match.group(0):
        text = text.replace(match.group(0), "")
    else:
        break

with open("backend/reports/phase8/PHASE8_FINAL_REPORT.md", "w") as f:
    f.write(text)
