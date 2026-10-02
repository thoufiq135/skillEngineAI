import json
import re
import time

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
# OLLAMA MODEL
# ============================================================

model = ChatOllama(
    model="qwen2.5:1.5b",
    temperature=0.3,
    num_predict=300,
    num_ctx=2048,
    keep_alive="30m",
    format="json"
)


# ============================================================
# PROMPT
# ============================================================

prompt = ChatPromptTemplate.from_template(
    """
You are an adaptive technical interview question generator.

CURRENT INTERVIEW SECTION:
{current_section}

CURRENT ITEM:
{current_skill}

QUESTION TYPE:
{question_type}

TARGET CONCEPT:
{concept}

RESUME EXPERIENCE INFORMATION:
{experience}

RESUME INTERNSHIP INFORMATION:
{internships}

RESUME PROJECT INFORMATION:
{projects}

RESUME TECHNICAL SKILLS:
{skills}

SKILLS / TECHNICAL CONCEPTS EXPLICITLY FOUND IN PREVIOUS ANSWERS:
{answer_skills}

CANDIDATE'S PREVIOUS ANSWER:
{candidate_answer}

PREVIOUS QUESTIONS:
{previous_questions}


============================================================
IMPORTANT INTERVIEW RULES
============================================================

1. Generate exactly ONE interview question.

2. The question MUST be directly related to the CURRENT INTERVIEW
   SECTION and CURRENT ITEM.

3. Do not randomly select another technology or topic.

4. Do not introduce a technology, framework, tool, concept, or skill
   that is not supported by the provided resume information or the
   candidate's answer.

5. Never assume that the candidate knows a technology just because
   it is commonly associated with their role.

6. Do not ask coding questions.

7. Do not ask the candidate to write code.

8. Ask theory, conceptual, experience-based, project-based, or
   technical discussion questions only.


============================================================
LANGUAGE RULE
============================================================

1. The question MUST ALWAYS be written in English.

2. The expected_answer MUST ALWAYS be written in English.

3. NEVER generate the question or expected_answer in Chinese,
   Telugu, Hindi, or any other language.

4. Even if the resume, previous questions, candidate answer,
   or any provided context contains another language, the output
   MUST remain completely in English.

5. Do not translate the candidate's answer or resume content into
   another language. Use it only as context for generating the
   English interview question and expected answer.


============================================================
SECTION RULES
============================================================

If CURRENT INTERVIEW SECTION is "experience":

- Ask about the CURRENT ITEM from the candidate's actual experience.
- Ask about responsibilities, technologies explicitly mentioned,
  technical decisions, challenges, implementation, results,
  architecture, troubleshooting, or lessons learned.
- Do NOT invent responsibilities or technologies.

If CURRENT INTERVIEW SECTION is "internship":

- Ask about the CURRENT ITEM from the candidate's actual internship.
- Ask about work performed, technologies explicitly mentioned,
  challenges, contribution, implementation, or learning.
- Do NOT invent internship details.

If CURRENT INTERVIEW SECTION is "project":

- Ask about the CURRENT PROJECT.
- Ask about its purpose, implementation, architecture, technologies,
  challenges, decisions, results, or limitations.
- Use only information explicitly available in the project data.
- Do NOT invent technologies.

If CURRENT INTERVIEW SECTION is "skill":

- Ask a technical conceptual question about CURRENT ITEM.
- The question must stay within that skill.

If CURRENT INTERVIEW SECTION is "answer_skill":

- Ask a technical question about CURRENT ITEM.
- CURRENT ITEM must come from a technical skill/concept explicitly
  mentioned by the candidate in a previous answer.


============================================================
QUESTION TYPE RULES
============================================================

For "basic":

- Ask a fundamental question about the current item.
- Do not repeat previous questions.

For "skill_deep":

- Ask a deeper conceptual question about the current item.
- Do not repeat or paraphrase previous questions.

For "concept_follow_up":

- Ask specifically about TARGET CONCEPT.
- The question must explore a NEW aspect of that concept.
- Use the candidate's previous answer when useful.
- Do not ask the same definition again.
- If the previous question asked WHAT something is, ask about WHY,
  HOW, ADVANTAGES, LIMITATIONS, DIFFERENCES, USE CASES, BEHAVIOR,
  TRADE-OFFS, or another deeper aspect.
- Do not introduce unrelated concepts.

For experience, internship, or project follow-ups:

- Ask a deeper question about something explicitly mentioned in the
  candidate's previous answer.
- Do not invent details that were not mentioned.


============================================================
PREVIOUS QUESTION RULE
============================================================

Compare the new question against ALL previous questions.

The new question MUST be meaningfully different.

Do not:
- repeat a previous question
- paraphrase a previous question
- change only a few words
- ask the same definition again


============================================================
ANSWER-BASED ADAPTATION
============================================================

The candidate's previous answer may contain technical skills or
concepts that were not present in the resume.

Only use a newly discovered skill/concept if it was explicitly
mentioned by the candidate.

Do not infer hidden skills.

If the current question type is "concept_follow_up", prioritize
the TARGET CONCEPT.

If the current section is "answer_skill", stay focused on the
CURRENT ITEM.


============================================================
EXPECTED ANSWER
============================================================

Generate an actual technically correct expected answer.

The expected answer must directly answer the generated question.

It must NOT be a placeholder.

Do not use phrases such as:
- short verbal answer
- short verbal explanation
- brief explanation
- candidate should explain
- expected answer
- technical explanation
- technical answer
- brief answer

Keep the expected answer to 1-2 sentences only.

Do not write a long explanation.


============================================================
OUTPUT
============================================================

Return ONLY one valid JSON object.

Use exactly these two keys:

question
expected_answer

Both values MUST contain English text only.

No Chinese.
No Telugu.
No Hindi.
No other language.

No markdown.
No explanation outside JSON.
"""
)

chain = prompt | model


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        item = clean_text(item)

        if item:
            result.append(item)

    return result


def extract_json(text):
    """
    Safely extract a JSON object from model output.
    """

    if not text:
        return None

    text = text.strip()

    # Direct JSON
    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    # Remove markdown fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    # Find first complete JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = text[start:end + 1]

        try:
            data = json.loads(candidate)

            if isinstance(data, dict):
                return data

        except Exception:
            pass

    return None


def is_placeholder_answer(answer):

    if not answer:
        return True

    normalized = answer.lower().strip()

    placeholders = [
        "short verbal answer",
        "short verbal explanation",
        "brief explanation",
        "brief technical explanation",
        "technical explanation",
        "candidate should explain",
        "expected answer",
        "technical answer",
        "short answer",
        "brief answer"
    ]

    return any(
        placeholder in normalized
        for placeholder in placeholders
    )


# ============================================================
# PREVIOUS QUESTIONS
# ============================================================

def get_previous_questions(state):

    history = state.get(
        "interview_history",
        []
    )

    previous_questions = []

    for record in history:

        if not isinstance(record, dict):
            continue

        question = clean_text(
            record.get("question", "")
        )

        if question:
            previous_questions.append(question)

    if not previous_questions:
        return "None"

    return "\n".join(
        f"{index + 1}. {question}"
        for index, question
        in enumerate(previous_questions)
    )


# ============================================================
# CURRENT CONCEPT
# ============================================================

def get_current_concept(state):

    extracted_concepts = normalize_list(
        state.get(
            "extracted_concepts",
            []
        )
    )

    if extracted_concepts:
        return extracted_concepts[-1]

    return ""


# ============================================================
# FALLBACK QUESTION
# ============================================================

def fallback_question(
    current_section,
    current_skill,
    question_type,
    concept
):

    current_section = clean_text(
        current_section
    ).lower()

    current_skill = clean_text(
        current_skill
    )

    concept = clean_text(
        concept
    )

    # --------------------------------------------------------
    # Concept follow-up
    # --------------------------------------------------------

    if (
        question_type == "concept_follow_up"
        and concept
    ):

        return (
            f"How does {concept} affect the way "
            f"{current_skill} is used?"
        )

    # --------------------------------------------------------
    # Experience
    # --------------------------------------------------------

    if current_section == "experience":

        return (
            f"What were the main technical responsibilities "
            f"in {current_skill}?"
        )

    # --------------------------------------------------------
    # Internship
    # --------------------------------------------------------

    if current_section == "internship":

        return (
            f"What technical work did you perform during "
            f"{current_skill}?"
        )

    # --------------------------------------------------------
    # Project
    # --------------------------------------------------------

    if current_section == "project":

        return (
            f"What was the main technical purpose of "
            f"{current_skill}?"
        )

    # --------------------------------------------------------
    # Answer discovered skill
    # --------------------------------------------------------

    if current_section == "answer_skill":

        return (
            f"What is the main purpose of {current_skill}, "
            f"and where is it commonly used?"
        )

    # --------------------------------------------------------
    # Normal skill
    # --------------------------------------------------------

    if current_skill:

        return (
            f"What is {current_skill} and what is its "
            f"main purpose?"
        )

    return (
        "Can you explain the main technical concept "
        "related to this topic?"
    )


# ============================================================
# GENERATE QUESTION
# ============================================================

def generate_question(state):

    start_time = time.time()

    # --------------------------------------------------------
    # Current section
    # --------------------------------------------------------

    current_section = clean_text(
        state.get(
            "current_section",
            "skill"
        )
    )

    # --------------------------------------------------------
    # Current item / skill
    # --------------------------------------------------------

    current_skill = clean_text(
        state.get(
            "current_skill",
            ""
        )
    )

    # --------------------------------------------------------
    # Question type
    # --------------------------------------------------------

    question_type = clean_text(
        state.get(
            "question_type",
            "basic"
        )
    )

    # --------------------------------------------------------
    # Concept
    # --------------------------------------------------------

    concept = get_current_concept(state)

    # --------------------------------------------------------
    # Candidate answer
    # --------------------------------------------------------

    candidate_answer = clean_text(
        state.get(
            "candidate_answer",
            ""
        )
    )

    # --------------------------------------------------------
    # Resume sections
    # --------------------------------------------------------

    experience = normalize_list(
        state.get(
            "experience",
            []
        )
    )

    internships = normalize_list(
        state.get(
            "internships",
            []
        )
    )

    projects = normalize_list(
        state.get(
            "projects",
            []
        )
    )

    skills = normalize_list(
        state.get(
            "skills",
            []
        )
    )

    # --------------------------------------------------------
    # Answer-discovered skills
    # --------------------------------------------------------

    answer_skills = normalize_list(
        state.get(
            "answer_skills",
            []
        )
    )

    # --------------------------------------------------------
    # Previous questions
    # --------------------------------------------------------

    previous_questions = get_previous_questions(
        state
    )

    # --------------------------------------------------------
    # Log
    # --------------------------------------------------------

    print(
        "\n========== QUESTION GENERATION =========="
    )

    print(
        "Current Section:",
        current_section
    )

    print(
        "Current Item:",
        current_skill
    )

    print(
        "Question Type:",
        question_type
    )

    print(
        "Target Concept:",
        concept
    )

    # --------------------------------------------------------
    # Invoke model
    # --------------------------------------------------------

    try:

        response = chain.invoke(
            {
                "current_section": current_section,

                "current_skill": current_skill,

                "question_type": question_type,

                "concept": concept,

                "experience": json.dumps(
                    experience,
                    ensure_ascii=False
                ),

                "internships": json.dumps(
                    internships,
                    ensure_ascii=False
                ),

                "projects": json.dumps(
                    projects,
                    ensure_ascii=False
                ),

                "skills": json.dumps(
                    skills,
                    ensure_ascii=False
                ),

                "answer_skills": json.dumps(
                    answer_skills,
                    ensure_ascii=False
                ),

                "candidate_answer": candidate_answer,

                "previous_questions":
                    previous_questions
            }
        )

        raw_response = clean_text(
            getattr(
                response,
                "content",
                ""
            )
        )

    except Exception as e:

        print(
            "⚠️ Question generation model error:",
            repr(e)
        )

        raw_response = ""

    print(
        "Raw model output:"
    )

    print(raw_response)

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    result = extract_json(
        raw_response
    )

    if result is None:

        print(
            "⚠️ JSON parsing failed."
        )

        result = {}

    # --------------------------------------------------------
    # Question
    # --------------------------------------------------------

    question = clean_text(
        result.get(
            "question",
            ""
        )
    )

    # --------------------------------------------------------
    # Expected answer
    # --------------------------------------------------------

    expected_answer = clean_text(
        result.get(
            "expected_answer",
            ""
        )
    )

    # --------------------------------------------------------
    # Question fallback
    # --------------------------------------------------------

    if not question:

        question = fallback_question(
            current_section,
            current_skill,
            question_type,
            concept
        )

    # --------------------------------------------------------
    # Expected answer validation
    # --------------------------------------------------------

    if is_placeholder_answer(
        expected_answer
    ):

        print(
            "⚠️ Invalid placeholder expected answer detected."
        )

        expected_answer = ""

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    elapsed = time.time() - start_time

    print(
        f"\n❓ Question: {question}"
    )

    # IMPORTANT:
    # Expected answer remains backend-side.
    # It is not returned to frontend by backend/api.py.

    print(
        f"⏱️ Question Generation Time: "
        f"{elapsed:.2f} seconds"
    )

    print(
        "=========================================="
    )

    return {
        "question": question,
        "expected_answer": expected_answer
    }