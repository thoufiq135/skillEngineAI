from typing import TypedDict, List


class InterviewState(TypedDict):

    # =========================================================
    # Resume
    # =========================================================

    resume_text: str

    # Resume analysis
    job_role: str
    skills: List[str]

    # =========================================================
    # Resume Sections
    # Interview order:
    # Experience → Internships → Projects → Skills
    # =========================================================

    experience: List[str]
    internships: List[str]
    projects: List[str]

    # =========================================================
    # Skills found from self introduction
    # =========================================================

    self_intro_skills: List[str]

    # Skills discovered from candidate answers
    # Only explicitly mentioned technical skills/concepts
    # should be added here by the evaluation logic.
    answer_skills: List[str]

    # =========================================================
    # Current interview section
    # =========================================================

    current_section: str

    # Possible values:
    # "self_intro"
    # "experience"
    # "internship"
    # "project"
    # "skill"
    # "answer_skill"

    # =========================================================
    # Current item / skill
    # =========================================================

    current_skill: str
    current_question: str
    current_expected_answer: str
    question_type: str

    # =========================================================
    # Candidate answer
    # =========================================================

    candidate_answer: str

    # =========================================================
    # Evaluation
    # =========================================================

    current_score: float

    missing_concepts: List[str]

    # Concepts explicitly extracted from candidate answer
    extracted_concepts: List[str]

    # =========================================================
    # Interview progress
    # =========================================================

    # Index inside the current section
    skill_index: int

    # Total technical questions asked
    question_count: int

    # =========================================================
    # Follow-up tracking
    # =========================================================

    # Whether the current answer qualifies for a follow-up
    follow_up_pending: bool

    # Concepts/items already asked
    asked_concepts: List[str]

    # Questions already asked
    asked_questions: List[str]

    # =========================================================
    # Complete interview records
    # =========================================================

    interview_history: List[dict]

    # =========================================================
    # Skill-wise ratings
    # =========================================================

    skill_ratings: dict