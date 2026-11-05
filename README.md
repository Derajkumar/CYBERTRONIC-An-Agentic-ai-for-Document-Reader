# Cybertornic — AI Document Reader

A small command-line agent for asking questions about local `.txt` and `.md` files. It can search document text, read a file, and evaluate arithmetic using a restricted parser.

## Features

- **Local document search:** searches `.txt` and `.md` files under the selected folder.
- **File reads constrained to that folder:** attempts to read paths outside it are rejected.
- **Restricted calculator:** supports arithmetic without Python `eval()`.
- **Bounded tool loop:** the agent stops after at most eight tool steps.
- **JSONL logging:** tool calls and errors are recorded in `agent_log.jsonl` by default.
- **Offline by default:** uses a deterministic local planner unless API mode is explicitly enabled.

> **Privacy note:** In default offline mode, the planner does not make an API request. With `--api`, the agent sends prompts and tool results to the configured OpenAI-compatible API. Do not enable API mode for sensitive documents unless that service is approved for the data.

## Requirements

- Python 3. No third-party packages are required for offline mode.
- API mode requires an API key and a compatible chat-completions endpoint.

## Setup

From the repository root, create and activate a virtual environment if desired:

```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Place the documents you want to query in `documents/` (create the folder if needed). The agent searches `.txt` and `.md` files recursively.

## Usage

Ask a one-off question:

```bash
python agent.py "What is the sum of 2 and 3?"
```

Ask about documents in the default `documents/` folder:

```bash
python agent.py "What does the deployment guide say?"
```

Choose a different document folder:

```bash
python agent.py --folder ./my-documents "Find the maintenance schedule"
```

Start interactive mode:

```bash
python agent.py
```

In interactive mode, enter questions at the `Question>` prompt. Use `/folder <path>` to switch folders, or type `exit` to quit.

### Optional API mode

Set `OPENAI_API_KEY` and, if needed, configure `OPENAI_MODEL` and `OPENAI_BASE_URL`, then run:

```bash
python agent.py --api "Summarize the maintenance notes"
```

The default API base URL is `https://api.openai.com/v1`. API mode sends prompts and tool outputs to that endpoint.

## Tools and safeguards

- `search_files(query)` searches lines in `.txt` and `.md` files. Use `*` to list matching file names.
- `read_file(path)` reads a `.txt` or `.md` file inside the selected folder and rejects paths that resolve outside it.
- `calculate(expression)` evaluates numeric arithmetic using an allowlist of operators.
- Tool execution has a five-second timeout, and the planner has a maximum of eight steps.

These safeguards limit what the agent's tools can do; they are not a substitute for reviewing code or protecting sensitive data.

## Tests

The repository includes `test.py`. Run it from the repository root with:

```bash
python test.py
```

The script currently has a known issue: it references an unset `expected` variable for test cases whose expected value is `None`, so it may stop before completing the suite. No pass-rate claim is made here.

## Project layout

```text
.
├── agent.py          # CLI, planner, tool orchestration, and logging
├── tools.py          # Document search/read and restricted calculator
├── test.py           # Basic test script
├── documents/        # Add your .txt and .md files here
├── agent_log.jsonl   # Runtime log (created/appended when the agent runs)
└── README.md
```
