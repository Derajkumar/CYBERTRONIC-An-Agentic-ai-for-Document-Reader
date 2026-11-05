import ast
import pathlib
import threading


_allowed_folder = pathlib.Path("documents").resolve()
_folder_lock = threading.Lock()


def set_allowed_folder(folder):
    global _allowed_folder
    with _folder_lock:
        _allowed_folder = pathlib.Path(folder).resolve()


def get_allowed_folder():
    with _folder_lock:
        return _allowed_folder


def search_files(query, folder=None):
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    if folder is None:
        root = get_allowed_folder()
    else:
        root = pathlib.Path(folder).resolve()
    if not root.is_dir():
        raise ValueError(f"folder does not exist: {root}")

    matches = []
    if query.strip() == "*":
        for suffix in ("*.txt", "*.md"):
            for path in sorted(root.rglob(suffix)):
                if path.is_file():
                    matches.append({
                        "file": str(path.relative_to(root)).replace("\\", "/"),
                        "line_number": 0,
                        "line": "[FILE]",
                    })
        return matches
    if not query.strip():
        raise ValueError("query must be a non-empty string")

    needle = query.lower()
    for suffix in ("*.txt", "*.md"):
        for path in sorted(root.rglob(suffix)):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"cannot decode text file: {path}") from exc
            for number, line in enumerate(text.splitlines(), 1):
                if needle in line.lower():
                    matches.append({
                        "file": str(path.relative_to(root)).replace("\\", "/"),
                        "line_number": number,
                        "line": line,
                    })
    return matches


def read_file(path, folder=None):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    root = get_allowed_folder() if folder is None else pathlib.Path(folder).resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("path traversal rejected: path is outside the allowed folder") from exc

    if not candidate.is_file():
        requested_name = pathlib.PureWindowsPath(path).name
        matches = [
            item for item in root.rglob(requested_name)
            if item.is_file() and item.suffix.lower() in (".txt", ".md")
        ]
        if len(matches) == 1:
            candidate = matches[0].resolve()
        else:
            raise ValueError(f"file not found: {path}")
    if candidate.suffix.lower() not in (".txt", ".md"):
        raise ValueError("only .txt and .md files may be read")
    return candidate.read_text(encoding="utf-8")


_ALLOWED_OPERATORS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}


def calculate(expression):
    if not isinstance(expression, str) or len(expression) > 500:
        raise ValueError("expression must be a string of at most 500 characters")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent is too large")
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                raise ZeroDivisionError("division by zero")
            return _ALLOWED_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](evaluate(node.operand))
        raise ValueError("unsupported expression; use numbers and arithmetic operators")

    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("invalid arithmetic expression") from exc
    return evaluate(parsed)
