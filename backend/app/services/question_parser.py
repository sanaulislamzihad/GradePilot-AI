"""Rule-based parsing of question papers and model answers into numbered parts.

Handles the common layouts: "Q1.", "Question 2:", "3)", "1(a)", "(b)", "c)",
marks written as "[5]", "(5 marks)" or "5 marks", and multiple-choice options
"A." to "E.". The output is a starting point the teacher always reviews; it is
never treated as authoritative.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.models.exam import QuestionType

_SUB = r"(?:[a-h]|i{1,3}|iv|v|vi{1,3}|ix|x)"

_Q_PREFIXED = re.compile(r"^\s*(?:q(?:uestion|ues)?)\s*\.?\s*(\d{1,3})\s*[\.\):\-–]?\s*(.*)$", re.IGNORECASE)
_NUMBERED = re.compile(r"^\s*(\d{1,3})\s*[\.\)]\s+(.*)$")
_COMBINED = re.compile(
    rf"^\s*(?:q(?:uestion|ues)?\s*\.?\s*)?(\d{{1,3}})\s*\(\s*({_SUB})\s*\)\s*[\.:\-–]?\s*(.*)$", re.IGNORECASE
)
_SUB_PAREN = re.compile(rf"^\s*\(\s*({_SUB})\s*\)\s*(.*)$", re.IGNORECASE)
_SUB_PLAIN = re.compile(rf"^\s*({_SUB})\s*[\.\)]\s+(.*)$")
_OPTION = re.compile(r"^\s*\(?([A-E])[\.\)]\s+\S")

_MARKS_BRACKET = re.compile(
    r"[\[\(]\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:marks?|mks?|pts?|points?)?\s*[\]\)]\s*$", re.IGNORECASE
)
_MARKS_WORD = re.compile(r"(?:^|\s)(\d{1,3}(?:\.\d{1,2})?)\s*(?:marks?|mks?|points?)\s*\.?\s*$", re.IGNORECASE)

_MATH_WORDS = re.compile(
    r"\b(solve|calculate|compute|evaluate|derive|prove|integrate|differentiate|simplify|factori[sz]e|find the value)\b",
    re.IGNORECASE,
)
_MATH_SYMBOLS = re.compile(r"(\d\s*[\+\-\*/\^=]\s*[\dxyz(])|[∫∑√π≤≥≠]|\b[xyz]\s*=|d[xy]/d[xy]")
_SHORT_START = re.compile(r"^\s*(define|what is|what are|list|name|state|mention|write down|identify)\b", re.IGNORECASE)


@dataclass
class ParsedPart:
    label: str
    text: str
    marks: Decimal | None = None
    question_type: QuestionType = QuestionType.DESCRIPTIVE
    children: list["ParsedPart"] = field(default_factory=list)
    _lines: list[str] = field(default_factory=list, repr=False)
    _has_options: bool = field(default=False, repr=False)


def _split_marks(text: str) -> tuple[str, Decimal | None]:
    for pattern in (_MARKS_BRACKET, _MARKS_WORD):
        match = pattern.search(text)
        if match:
            try:
                value = Decimal(match.group(1))
            except InvalidOperation:
                continue
            if 0 < value <= 500:
                return text[: match.start()].rstrip(" :-–"), value
    return text, None


def classify(text: str, has_options: bool = False) -> QuestionType:
    if has_options:
        return QuestionType.MULTIPLE_CHOICE
    if _MATH_WORDS.search(text) or _MATH_SYMBOLS.search(text):
        return QuestionType.MATHEMATICAL
    if _SHORT_START.match(text) and len(text) < 160:
        return QuestionType.SHORT
    return QuestionType.DESCRIPTIVE


def _finish(part: ParsedPart) -> None:
    text = "\n".join(line for line in part._lines).strip()
    text, marks = _split_marks(text)
    part.text = re.sub(r"[ \t]+", " ", text).strip()
    if part.marks is None:
        part.marks = marks
    for child in part.children:
        _finish(child)
    part.question_type = classify(part.text, part._has_options)


def parse_parts(raw_text: str) -> list[ParsedPart]:
    """Split text into top-level numbered parts with optional lettered sub-parts."""
    parts: list[ParsedPart] = []
    current: ParsedPart | None = None
    current_sub: ParsedPart | None = None

    def start_main(label: str, rest: str) -> ParsedPart:
        nonlocal current, current_sub
        current = ParsedPart(label=label, text="", _lines=[rest] if rest else [])
        current_sub = None
        parts.append(current)
        return current

    def start_sub(label: str, rest: str) -> None:
        nonlocal current_sub
        assert current is not None
        current_sub = ParsedPart(label=label.lower(), text="", _lines=[rest] if rest else [])
        current.children.append(current_sub)

    def main_labels() -> set[str]:
        return {p.label for p in parts}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        target = current_sub or current

        # A line that holds only the marks, e.g. "[5]" printed under the question.
        if target is not None:
            remainder, marks = _split_marks(line)
            if marks is not None and not remainder.strip():
                target.marks = marks
                continue

        combined = _COMBINED.match(line)
        if combined:
            number, sub, rest = combined.group(1), combined.group(2).lower(), combined.group(3)
            if current is None or current.label != number:
                if number in main_labels():
                    current = next(p for p in parts if p.label == number)
                    current_sub = None
                else:
                    start_main(number, "")
            if sub not in {c.label for c in current.children}:  # type: ignore[union-attr]
                start_sub(sub, rest)
                continue

        prefixed = _Q_PREFIXED.match(line)
        if prefixed and prefixed.group(1) not in main_labels():
            start_main(prefixed.group(1), prefixed.group(2))
            continue

        numbered = _NUMBERED.match(line)
        if numbered:
            number = numbered.group(1)
            # Plain "3." only starts a question when it continues the sequence,
            # so numbered lists inside a question stay part of its text.
            expected = str(int(parts[-1].label) + 1) if parts and parts[-1].label.isdigit() else "1"
            if number == expected and number not in main_labels():
                start_main(number, numbered.group(2))
                continue

        if current is not None and not _OPTION.match(line):
            sub_match = _SUB_PAREN.match(line) or _SUB_PLAIN.match(line)
            if sub_match and sub_match.group(1).lower() not in {c.label for c in current.children}:
                start_sub(sub_match.group(1), sub_match.group(2))
                continue

        if target is None:
            continue  # Header text before the first question (title, instructions).
        if _OPTION.match(line):
            target._has_options = True
        target._lines.append(line)

    for part in parts:
        _finish(part)
    return parts


def full_label(parent_label: str | None, label: str) -> str:
    return f"{parent_label}({label})" if parent_label else label


def flatten_answers(parts: list[ParsedPart]) -> dict[str, str]:
    """Map "1", "1(a)" style labels to answer text, for matching model answers to questions."""
    answers: dict[str, str] = {}
    for part in parts:
        if part.text:
            answers[part.label] = part.text
        for child in part.children:
            if child.text:
                answers[full_label(part.label, child.label)] = child.text
    return answers
