import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import time
from urllib import request

import tools as tool_module


MAX_STEPS = 8
TOOL_TIMEOUT = 5.0
LOG_FILE = "agent_log.jsonl"

TOOL_SCHEMAS = [
    {"name": "search_files", "description": "Keyword search over .txt and .md files.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "read_file", "description": "Read one file inside the allowed folder.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "calculate", "description": "Safely evaluate arithmetic without code execution.",
     "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}},
]


class OfflinePlanner:
    """Small deterministic planner used when no API credentials are configured."""
    def __init__(self, question):
        self.question = question
        self.calls = 0
        self.last_search = None
        stop_words = {
            "what", "which", "where", "when", "who", "why", "how", "is", "are", "the",
            "a", "an", "of", "in", "on", "at", "to", "for", "and", "does", "do", "tell",
            "me", "about", "give", "please", "my", "your", "file", "files", "document", "documents",
            "search", "keyword", "contains", "find",
        }
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*|\d+(?:\.\d+)?", question)
        unique = []
        for word in words:
            if word.lower() not in stop_words and word.lower() not in {item.lower() for item in unique}:
                unique.append(word)
        self.search_terms = unique or ["project"]

    def __call__(self, messages, schemas):
        latest_tool_result = None
        for message in reversed(messages):
            if message.get("role") == "tool":
                latest_tool_result = message["content"]
                break

        self.calls += 1
        if self.calls == 1:
            q = self.question.lower()
            if re.search(r"\b(all|every)\s+(files?|documents?)\b|\b(list|names)\s+(of\s+)?(files?|documents?)\b", q):
                return {"tool": "search_files", "args": {"query": "*"}}
            read_match = re.search(r"(?:read|open|show)\s+(?:the\s+)?(?:content(?:s)?\s+(?:of\s+)?|file\s+)?([^\s]+\.(?:txt|md))", self.question, re.IGNORECASE)
            if read_match:
                return {"tool": "read_file", "args": {"path": read_match.group(1).replace("\\", "/")}}
            filename_match = re.search(r"([^\s]+\.(?:txt|md))", self.question, re.IGNORECASE)
            if filename_match and re.search(
                r"\b(content|contents|read|open|show|inside)\b",
                q,
            ):
                return {"tool": "read_file", "args": {"path": filename_match.group(1).replace("\\", "/")}}
            if filename_match and q.strip() == filename_match.group(1).lower():
                return {"tool": "read_file", "args": {"path": filename_match.group(1).replace("\\", "/")}}
            quoted = re.search(r"['\"]([^'\"]+)['\"]", self.question)
            if quoted:
                return {"tool": "search_files", "args": {"query": quoted.group(1)}}
            keyword_match = re.search(
                r"\bkeyword(?:\s+is)?\s+([^\s]+(?:\s+[^\s]+)*)",
                self.question,
                re.IGNORECASE,
            )
            if not keyword_match:
                keyword_match = re.search(
                    r"\b(?:search\s+for|contains?|find)\s+(?:the\s+)?(?:keyword\s+)?(.+)",
                    self.question,
                    re.IGNORECASE,
                )
            if keyword_match:
                query_text = keyword_match.group(1).strip().rstrip("?!. ")
                if query_text:
                    return {"tool": "search_files", "args": {"query": query_text}}
            if any(word in q for word in ("sum", "total", "minus", "plus", "calculate", "costs")):
                match = re.search(r"(\d+(?:\.\d+)?)\s*(plus|\+|minus|-|times|\*|divided by|/)\s*(\d+(?:\.\d+)?)", q)
                if match:
                    left, op, right = match.groups()
                    symbols = {"plus": "+", "minus": "-", "times": "*", "divided by": "/", "+": "+", "-": "-", "*": "*", "/": "/"}
                    return {"tool": "calculate", "args": {"expression": f"{left}{symbols[op]}{right}"}}
            query = self.search_terms[0]
            self.last_search = query
            return {"tool": "search_files", "args": {"query": query}}

        if isinstance(latest_tool_result, str):
            try:
                payload = json.loads(latest_tool_result)
            except json.JSONDecodeError:
                payload = {"error": latest_tool_result}
        else:
            payload = latest_tool_result

        if isinstance(payload, dict) and payload.get("error"):
            return {"final_answer": payload["error"]}
        if isinstance(payload, str) and payload:
            return {"final_answer": payload}
        if isinstance(payload, list):
            if not payload:
                term_index = min(self.calls - 1, len(self.search_terms) - 1)
                if term_index + 1 < len(self.search_terms):
                    next_term = self.search_terms[term_index + 1]
                    self.last_search = next_term
                    return {"tool": "search_files", "args": {"query": next_term}}
                return {"final_answer": "not found"}
            if re.search(r"\b(all|every)\s+(files?|documents?)\b|\b(list|names)\s+(of\s+)?(files?|documents?)\b", self.question.lower()):
                names = sorted({match["file"] for match in payload if match.get("line") == "[FILE]"})
                return {"final_answer": "\n".join(names) if names else "not found"}
            if any(word in self.question.lower() for word in ("guide", "details", "read")):
                return {"tool": "read_file", "args": {"path": payload[0]["file"]}}
            question_terms = {term.lower() for term in self.search_terms}
            ranked_payload = sorted(
                payload,
                key=lambda match: sum(
                    1 for term in question_terms
                    if term in match.get("line", "").lower()
                ),
                reverse=True,
            )
            if self.calls == 2:
                covered_text = " ".join(match.get("line", "") for match in payload).lower()
                for term in self.search_terms[1:]:
                    if term.lower() not in covered_text:
                        return {"tool": "search_files", "args": {"query": term}}
            lines = []
            for match in ranked_payload[:8]:
                line = match.get("line", "").strip()
                if line and line != "[FILE]" and line not in lines:
                    lines.append(line)
            return {"final_answer": "\n".join(lines) if lines else "not found"}
        if isinstance(payload, dict) and "value" in payload:
            return {"final_answer": str(payload["value"])}
        return {"final_answer": "not found"}


class OpenAICompatiblePlanner:
    def __init__(self, model=None, api_key=None, base_url=None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")

    def __call__(self, messages, schemas):
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        tool_specs = [{"type": "function", "function": {
            "name": s["name"], "description": s["description"], "parameters": s["parameters"]
        }} for s in schemas]
        body = json.dumps({"model": self.model, "messages": messages, "tools": tool_specs, "tool_choice": "auto"})
        req = request.Request(
            self.base_url + "/chat/completions",
            data=body.encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        message = result["choices"][0]["message"]
        if message.get("tool_calls"):
            call = message["tool_calls"][0]
            return {"tool": call["function"]["name"], "args": json.loads(call["function"]["arguments"])}
        return {"final_answer": message.get("content", "").strip() or "not found"}


def _log(log_file, entry):
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def execute_tool(name, args, folder):
    if name == "search_files":
        return tool_module.search_files(args["query"], folder=folder)
    if name == "read_file":
        return tool_module.read_file(args["path"], folder=folder)
    if name == "calculate":
        value = tool_module.calculate(args["expression"])
        return {"value": value}
    raise ValueError(f"unknown tool: {name}")


def run_agent(question, folder="documents", log_file=LOG_FILE, planner=None):
    folder = pathlib.Path(folder).resolve()
    tool_module.set_allowed_folder(folder)
    log_path = pathlib.Path(log_file)
    planner = planner or OfflinePlanner(question)
    messages = [
        {"role": "system", "content": "Answer questions using only local documents and tools. Use tool results. Return 'not found' when evidence is absent. Keep path arguments relative to the allowed folder."},
        {"role": "user", "content": question},
    ]

    for step in range(1, MAX_STEPS + 1):
        llm_response = planner(messages, TOOL_SCHEMAS)
        if "final_answer" in llm_response:
            return llm_response["final_answer"]

        name = llm_response.get("tool")
        args = llm_response.get("args", {})
        if name not in allowed_names():
            result, error = None, f"unknown tool: {name}"
            elapsed_ms = 0
        else:
            started = time.perf_counter()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(execute_tool, name, args, folder)
                    try:
                        result = future.result(timeout=TOOL_TIMEOUT)
                        error = None
                    except concurrent.futures.TimeoutError:
                        result, error = None, f"tool timeout after {TOOL_TIMEOUT:.1f} seconds"
            except (KeyError, TypeError, ValueError, FileNotFoundError, OSError) as exc:
                result, error = None, str(exc)
            except Exception as exc:
                result, error = None, f"{type(exc).__name__}: {exc}"
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        tool_result = {"error": error} if error else result
        _log(log_path, {"step": step, "tool": name, "args": args, "result": result,
                        "error": error, "latency_ms": elapsed_ms})
        messages.append({"role": "assistant", "content": None})
        messages.append({"role": "tool", "name": name, "content": json.dumps(tool_result, ensure_ascii=False)})

    return "not found (maximum tool steps reached)"


def allowed_names():
    return {"search_files", "read_file", "calculate"}


def main():
    parser = argparse.ArgumentParser(description="Answer questions from local documents.")
    parser.add_argument("question", nargs="*", help="Question to answer")
    parser.add_argument("--folder", default=os.getenv("DOCUMENT_FOLDER", "documents"))
    parser.add_argument("--log", default=os.getenv("AGENT_LOG", LOG_FILE))
    parser.add_argument("--api", action="store_true", help="Use OPENAI_API_KEY/OpenAI-compatible chat completions")
    args = parser.parse_args()
    planner = OpenAICompatiblePlanner() if args.api else None

    if args.question:
        print(run_agent(" ".join(args.question), folder=args.folder, log_file=args.log, planner=planner))
        return

    folder = pathlib.Path(args.folder)
    if not folder.is_dir():
        print(f"Folder not found: {folder.resolve()}")
        return

    print(f"Local document agent ready. Folder: {folder.resolve()}")
    print("Ask a question, use /folder <path> to switch folders, or type exit/quit.")
    while True:
        try:
            question = input("\nQuestion> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            break
        if question.startswith("/folder "):
            new_folder = pathlib.Path(question[len("/folder "):].strip()).resolve()
            if new_folder.is_dir():
                args.folder = str(new_folder)
                print(f"Folder changed to: {new_folder}")
            else:
                print(f"Folder not found: {new_folder}")
            continue
        print(run_agent(question, folder=args.folder, log_file=args.log, planner=planner))


if __name__ == "__main__":
    main()
