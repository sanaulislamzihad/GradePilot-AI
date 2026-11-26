from decimal import Decimal

from app.models.exam import QuestionType
from app.services.question_parser import flatten_answers, parse_parts

PAPER = """North South University
Midterm Examination — CSE445
Answer all questions.

Q1. Explain Machine Learning. [5]
Question 2: Explain supervised and unsupervised learning.
(a) Define supervised learning. (4 marks)
(b) Compare it with unsupervised learning,
giving two examples. [6]
3. Solve 2x + 3 = 11 for x.
5 marks
4) Which algorithm is used for classification?
A. K-means
B. Decision tree
C. PCA
[2]
5. List three steps of a machine learning project:
1. collect data
2. train a model
"""


def test_parses_labels_text_and_marks():
    parts = parse_parts(PAPER)
    assert [p.label for p in parts] == ["1", "2", "3", "4", "5"]

    q1, q2, q3, q4, q5 = parts
    assert q1.text == "Explain Machine Learning." and q1.marks == Decimal("5")
    assert [c.label for c in q2.children] == ["a", "b"]
    assert q2.children[0].marks == Decimal("4")
    assert q2.children[1].text.startswith("Compare it with unsupervised learning")
    assert "giving two examples" in q2.children[1].text and q2.children[1].marks == Decimal("6")
    assert q3.marks == Decimal("5")  # marks on their own line
    assert q4.marks == Decimal("2") and "B. Decision tree" in q4.text


def test_header_text_is_ignored():
    parts = parse_parts(PAPER)
    assert all("North South" not in p.text for p in parts)


def test_numbered_lists_inside_a_question_stay_in_its_text():
    q5 = parse_parts(PAPER)[-1]
    assert "1. collect data" in q5.text and "2. train a model" in q5.text


def test_question_type_heuristics():
    q1, q2, q3, q4, q5 = parse_parts(PAPER)
    assert q1.question_type == QuestionType.DESCRIPTIVE
    assert q2.children[0].question_type == QuestionType.SHORT
    assert q3.question_type == QuestionType.MATHEMATICAL
    assert q4.question_type == QuestionType.MULTIPLE_CHOICE
    assert q5.question_type == QuestionType.SHORT


def test_combined_labels_and_answer_mapping():
    answers = flatten_answers(parse_parts("1(a) First answer.\n1(b) Second answer\ncontinues here.\n2. Answer two."))
    assert answers == {
        "1(a)": "First answer.",
        "1(b)": "Second answer\ncontinues here.",
        "2": "Answer two.",
    }


def test_text_without_numbered_questions_returns_nothing():
    assert parse_parts("Just a paragraph of text\nwith no question labels.") == []


def test_implausible_marks_are_not_extracted():
    (part,) = parse_parts("Q1. Discuss the events of [1971]")
    assert part.marks is None
