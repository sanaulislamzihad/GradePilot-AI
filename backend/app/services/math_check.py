"""Stage 4: symbolic checking of mathematical answers with SymPy.

Compares the student's final answer with the model answer's (equivalent forms
count as equal) and checks each equation in the student's working against the
expected solution, so an error can be located in the working, not only at the
end. Anything that cannot be parsed reliably is reported as uncertain and left
for the teacher.

SymPy's parser evaluates Python, so student text is filtered through a strict
whitelist (digits, single-letter variables, a few functions, operators) before
it is ever parsed.
"""

import re
from dataclasses import asdict, dataclass, field

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_FUNCTIONS = {
    "sqrt": sympy.sqrt, "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
    "log": sympy.log, "ln": sympy.log, "exp": sympy.exp, "pi": sympy.pi,
}
_ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z\s+\-*/^().]*$")
_WORD = re.compile(r"[A-Za-z]+")
_MAX_LENGTH = 120
# A lone variable being assigned: "x = 4", not the "x" of "2x = 8".
_ASSIGNMENT = re.compile(r"(?<![A-Za-z0-9*)^])([a-zA-Z])\s*=\s*([^=,;]+)$")


@dataclass
class MathResult:
    status: str  # match | mismatch | uncertain
    expected: str | None = None
    student: str | None = None
    step_errors: list[dict] = field(default_factory=list)
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    replacements = {"×": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "²": "^2", "³": "^3", "√": "sqrt"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip().rstrip(".")


def safe_parse(text: str):
    """Parse a short expression, or return None if it is not plainly mathematical."""
    text = _clean(text)
    if not text or len(text) > _MAX_LENGTH or not _ALLOWED_CHARS.match(text) or "__" in text:
        return None
    for word in _WORD.findall(text):
        if len(word) > 1 and word not in _FUNCTIONS:
            return None
    symbols = {ch: sympy.Symbol(ch) for ch in set(re.findall(r"[A-Za-z]", text)) if ch not in ("e", "E")}
    local = {**symbols, **_FUNCTIONS, "e": sympy.E}
    try:
        return parse_expr(text, local_dict=local, global_dict={"__builtins__": {}, **_sympy_globals()},
                          transformations=_TRANSFORMS, evaluate=True)
    except Exception:  # noqa: BLE001 - malformed maths is simply "not parseable"
        return None


def _sympy_globals() -> dict:
    # Names parse_expr's generated code needs; nothing else is reachable.
    return {"Integer": sympy.Integer, "Float": sympy.Float, "Rational": sympy.Rational,
            "Symbol": sympy.Symbol, "Function": sympy.Function}


def equivalent(a, b) -> bool | None:
    try:
        difference = sympy.simplify(a - b)
        if difference == 0:
            return True
        if difference.free_symbols:
            return False
        return abs(complex(sympy.N(difference))) < 1e-9
    except Exception:  # noqa: BLE001
        return None


def _final_values(text: str) -> dict[str, object]:
    """Last value assigned to each variable, e.g. 'x = 4' -> {'x': 4}."""
    values: dict[str, object] = {}
    for line in text.splitlines():
        for piece in re.split(r"[,;]|\.\s| and ", line):
            match = _ASSIGNMENT.search(piece.strip())
            if match:
                parsed = safe_parse(match.group(2))
                if parsed is not None and not getattr(parsed, "free_symbols", set()):
                    values[match.group(1)] = parsed
    return values


def _final_expression(text: str):
    """The right-hand side of the last '=' (or the last line), for answers without a variable."""
    lines = [line for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        candidate = line.split("=")[-1] if "=" in line else re.sub(r"(?i)^\s*(answer|ans)\s*[:\-]\s*", "", line)
        parsed = safe_parse(candidate)
        if parsed is not None:
            return parsed
    return None


def _step_errors(student: str, expected: dict[str, object]) -> list[dict]:
    errors = []
    substitutions = {sympy.Symbol(k): v for k, v in expected.items()}
    for number, line in enumerate(student.splitlines(), start=1):
        text = _clean(line)
        if text.count("=") != 1:
            continue
        left, right = (safe_parse(side) for side in text.split("="))
        if left is None or right is None:
            continue
        free = (left - right).free_symbols
        if not free or not free <= set(substitutions):
            continue
        holds = equivalent((left - right).subs(substitutions), sympy.Integer(0))
        if holds is False:
            errors.append({"line": number, "text": line.strip()[:200]})
    return errors


def check(model_answer: str, student_answer: str) -> MathResult:
    expected_values = _final_values(model_answer)
    if expected_values:
        student_values = _final_values(student_answer)
        if not student_values:
            return MathResult("uncertain", detail="No final value could be read from the student's answer.",
                              expected=_describe(expected_values))
        compared = []
        for name, value in expected_values.items():
            if name not in student_values:
                return MathResult("uncertain", expected=_describe(expected_values), student=_describe(student_values),
                                  detail=f"The student gave no final value for {name}.")
            compared.append(equivalent(value, student_values[name]))
        steps = _step_errors(student_answer, expected_values)
        if None in compared:
            return MathResult("uncertain", _describe(expected_values), _describe(student_values), steps,
                              "The answers could not be compared symbolically.")
        status = "match" if all(compared) else "mismatch"
        detail = "Final answer is equivalent to the model answer." if status == "match" else "Final answer differs from the model answer."
        if steps:
            detail += f" {len(steps)} step(s) in the working do not hold for the expected solution."
        return MathResult(status, _describe(expected_values), _describe(student_values), steps, detail)

    expected = _final_expression(model_answer)
    student = _final_expression(student_answer)
    if expected is None or student is None:
        return MathResult("uncertain", detail="The final answer could not be read as an expression.")
    same = equivalent(expected, student)
    if same is None:
        return MathResult("uncertain", str(expected), str(student), detail="The answers could not be compared symbolically.")
    return MathResult("match" if same else "mismatch", str(expected), str(student),
                      detail="Final answer is equivalent to the model answer." if same else "Final answer differs from the model answer.")


def _describe(values: dict[str, object]) -> str:
    return ", ".join(f"{k} = {v}" for k, v in sorted(values.items()))
