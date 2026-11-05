# 🤖 Cybertornic  
## AI Agent for Secure Document Reader  

### What it does  
Cybertornic is a **bounded reasoning agent** that answers questions about local documents *without* leaving your folder. It uses 3 safe tools:  
- ✅ `search_files()` – Finds keywords in `.txt/.md` files  
- ✅ `read_file()` – Reads content (blocks path traversal)  
- ✅ `calculate()` – Safe math evaluation (no `eval`!)  

### Why it’s different  
| Feature | Benefit |
|---------|---------|
| **Folder-scoped only** | Never accesses files outside `./documents/` |
| **No hallucinations** | Returns `"not found"` if no match exists |
| **8-step max** | Prevents infinite loops (tested 10/10 cases pass) |
| **Error-safe** | Logs all errors as JSON (`agent_log.jsonl`) |

### How to use  
```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate

# 2. Place docs in ./documents/
cp sample.txt documents/

# 3. Run a question
python agent.py "What is the sum of 2 and 3?"
# → Output: 5

# 4. Full test suite (100% pass rate!)
python run_tests.py
```

### Project Structure 
### CYBERTRO-An-Agentic-ai-for-Document-Reader
|
|-- documents/
|   |-- docs/
|   |   |-- deployment.txt
|   |   |-- maintenance.txt
|   |   `-- sample1.txt
|
|-- agent.py
|-- tools.py
|-- test.py
|-- agent_log.jsonl
`-- README.md
```

### Test Results ✅  
| Question | Expected Answer | Status |
|----------|-----------------|--------|
| "What is the sum of 2 and 3?" | `5` | PASS |
| "Where is 'foo bar' in markdown files?" | `./docs/faq.md: foo bar` | PASS |
| Path-traversal attempt (`../etc/passwd`) | `"Path outside allowed folder"` | PASS |

### Question> what is the server error
Server error: file not found

### Question> service status
Transport service status: maintenance
Billing service owner: Noah Patel
 
