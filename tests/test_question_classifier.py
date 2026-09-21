import pytest
from backend.services.question_classifier import classify_question
from backend.schemas import QuestionType

def test_classify_deterministic():
    q_type, requires_review = classify_question("Please enter your current cumulative CGPA.")
    assert q_type == QuestionType.TYPE_A
    assert requires_review is False

def test_classify_skills():
    q_type, requires_review = classify_question("Which programming languages and frameworks do you know?")
    assert q_type == QuestionType.TYPE_B
    assert requires_review is False

def test_classify_experience():
    q_type, requires_review = classify_question("Detail an impactful technical project you built during college.")
    assert q_type == QuestionType.TYPE_C
    assert requires_review is False

def test_classify_sensitive():
    # Sensitive questions must trigger review gating
    q_type, requires_review = classify_question("Are you willing to relocate to Gurgaon or Hyderabad?")
    assert q_type == QuestionType.TYPE_E
    assert requires_review is True

    q_type2, requires_review2 = classify_question("Do you have any existing employment bond with another entity?")
    assert q_type2 == QuestionType.TYPE_E
    assert requires_review2 is True
