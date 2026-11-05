import subprocess, sys, json

def run_agent(question):
    result = subprocess.check_output([sys.executable, "agent.py"], input=question + "\n", text=True)
    return result.strip()

tests = [
    ("What is the sum of 2 and 3?", "5"),
    ("Where is the line ‘foo bar’ in the markdown files?", None),
    ("Give me the content of the file that mentions “hello world”.", None),
    ("Find any occurrence of ‘secret’ in .txt files.", "not found"),
    ("What is (10 * 2) + 7?", "27"),
    ("Show me the second paragraph of the file ‘README.md’.", None),
    ("Is there a hidden note about the budget?", "path/to/file.txt: line 3"),
    ("Attempt to read ../etc/passwd.", "Path outside the allowed folder"),
    ("Give me the product of 5 and 6.", "30"),
    ("What is the answer to a question that does not exist in any file?", None),
]

passes = 0
for q, exp in tests:
    out = run_agent(q)
    good = (exp is None) or (expected := exp).lower() in out.lower()
    print(f"{q} → {out[:80]}… {'PASS' if good else 'FAIL'} (exp={expected})")
    passes += 1 if good else 0

print("\n=== PASS RATE ===")
print(f"Passed: {passes}/{len(tests)} ({100*passes/len(tests):.1f}%)")
