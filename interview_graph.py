from langgraph.graph import StateGraph, START, END

from interview_state import InterviewState
from llm_analysis import analyze_resume
from question_generation import generate_question
from answer_evaluation import evaluate_answer


MAX_QUESTIONS = 5


# ============================================================
# ANALYSIS NODE
# ============================================================

def analysis_node(state: InterviewState):

    print("\n========== ANALYSIS NODE ==========")

    resume_text = state.get("resume_text", "")

    print(
        f"Resume characters: {len(resume_text)}"
    )

    if not resume_text.strip():

        print("❌ Resume text is empty.")

        return {
            "skills": [],
            "skill_index": 0,
            "current_skill": "",
            "current_question": "",
            "current_expected_answer": ""
        }

    print(
        "➡️ Calling analyze_resume()..."
    )

    result = analyze_resume(
        resume_text
    )

    # --------------------------------------------------------
    # Extract skills safely
    # --------------------------------------------------------

    if isinstance(result, dict):

        skills = result.get(
            "skills",
            []
        )

    elif isinstance(result, list):

        skills = result

    else:

        skills = []

    # --------------------------------------------------------
    # Clean skills
    # --------------------------------------------------------

    cleaned_skills = []

    for skill in skills:

        if skill is None:
            continue

        skill = str(skill).strip()

        if not skill:
            continue

        if skill not in cleaned_skills:
            cleaned_skills.append(skill)

    skills = cleaned_skills

    print(
        "\n========== SKILLS FROM ANALYSIS =========="
    )

    for skill in skills:
        print(f"- {skill}")

    print(
        f"Total Skills: {len(skills)}"
    )

    # --------------------------------------------------------
    # If no skills
    # --------------------------------------------------------

    if not skills:

        print(
            "❌ No skills extracted."
        )

        return {
            "skills": [],
            "skill_index": 0,
            "current_skill": "",
            "current_question": "",
            "current_expected_answer": ""
        }

    # --------------------------------------------------------
    # FIRST SKILL
    # --------------------------------------------------------

    first_skill = skills[0]

    print(
        f"\n🎯 First Skill: {first_skill}"
    )

    # --------------------------------------------------------
    # Store skills AND current skill together
    # --------------------------------------------------------

    updated_state = {
        "skills": skills,
        "skill_index": 0,
        "current_skill": first_skill,
        "question_type": "basic",
        "extracted_concepts": [],
        "missing_concepts": [],
        "current_question": "",
        "current_expected_answer": ""
    }

    print(
        "✅ Analysis state prepared."
    )

    return updated_state


# ============================================================
# PREPARE COMBINED SKILL POOL
# ============================================================

def prepare_skills_node(state: InterviewState):

    print("\n========== PREPARE SKILLS NODE ==========")

    resume_skills = list(
        state.get(
            "skills",
            []
        )
    )

    self_intro_skills = list(
        state.get(
            "self_intro_skills",
            []
        )
    )

    print(
        f"Resume skills: {resume_skills}"
    )

    print(
        f"Self-intro skills: {self_intro_skills}"
    )

    # --------------------------------------------------------
    # Combine resume skills + self-intro skills
    # --------------------------------------------------------

    combined_skills = []

    # First keep resume skills
    for skill in resume_skills:

        if skill is None:
            continue

        skill_text = str(skill).strip()

        if not skill_text:
            continue

        if skill_text.lower() not in [
            existing.lower()
            for existing in combined_skills
        ]:

            combined_skills.append(
                skill_text
            )

    # Then add new self-intro skills
    for skill in self_intro_skills:

        if skill is None:
            continue

        skill_text = str(skill).strip()

        if not skill_text:
            continue

        if skill_text.lower() not in [
            existing.lower()
            for existing in combined_skills
        ]:

            combined_skills.append(
                skill_text
            )

            print(
                f"➕ Added self-intro skill: {skill_text}"
            )

    print(
        "\n========== COMBINED SKILL POOL =========="
    )

    for skill in combined_skills:
        print(f"- {skill}")

    print(
        f"Total Combined Skills: {len(combined_skills)}"
    )

    # --------------------------------------------------------
    # No skills
    # --------------------------------------------------------

    if not combined_skills:

        print(
            "❌ Combined skill pool is empty."
        )

        return {
            "skills": [],
            "skill_index": 0,
            "current_skill": ""
        }

    # --------------------------------------------------------
    # Preserve current skill if possible
    # --------------------------------------------------------

    current_skill = str(
        state.get(
            "current_skill",
            ""
        )
    ).strip()

    if current_skill:

        matching_index = None

        for index, skill in enumerate(
            combined_skills
        ):

            if skill.lower() == current_skill.lower():

                matching_index = index
                break

        if matching_index is not None:

            skill_index = matching_index
            current_skill = combined_skills[
                matching_index
            ]

        else:

            skill_index = 0
            current_skill = combined_skills[0]

    else:

        skill_index = 0
        current_skill = combined_skills[0]

    print(
        f"🎯 Starting Skill: {current_skill}"
    )

    return {
        "skills": combined_skills,
        "skill_index": skill_index,
        "current_skill": current_skill
    }


# ============================================================
# SELECT SKILL NODE
# ============================================================

def select_skill_node(
    state: InterviewState
):

    print(
        "\n========== SELECT SKILL NODE =========="
    )

    skills = state.get(
        "skills",
        []
    )

    skill_index = state.get(
        "skill_index",
        0
    )

    print(
        f"Received skills: {skills}"
    )

    print(
        f"Received skill index: {skill_index}"
    )

    if not skills:

        print(
            "❌ Skills list is empty."
        )

        return {
            "current_skill": ""
        }

    # --------------------------------------------------------
    # Safety
    # --------------------------------------------------------

    if skill_index < 0:
        skill_index = 0

    if skill_index >= len(skills):
        skill_index = 0

    current_skill = skills[
        skill_index
    ]

    print(
        f"🎯 Selected Skill: {current_skill}"
    )

    return {
        "skill_index": skill_index,
        "current_skill": current_skill
    }


# ============================================================
# QUESTION NODE
# ============================================================

def question_node(
    state: InterviewState
):

    print(
        "\n========== QUESTION NODE =========="
    )

    current_skill = state.get(
        "current_skill",
        ""
    )

    print(
        f"Current Skill: {current_skill}"
    )

    if not current_skill:

        print(
            "❌ No current skill."
        )

        return {
            "current_question": "",
            "current_expected_answer": ""
        }

    print(
        "➡️ Calling generate_question()..."
    )

    result = generate_question(
        state
    )

    question = str(
        result.get(
            "question",
            ""
        )
    ).strip()

    expected_answer = str(
        result.get(
            "expected_answer",
            ""
        )
    ).strip()

    print(
        "\n---------- QUESTION ----------"
    )

    print(
        f"Skill: {current_skill}"
    )

    print(
        f"Question: {question}"
    )

    print(
        f"Expected Answer: {expected_answer}"
    )

    return {
        "current_question": question,
        "current_expected_answer": expected_answer
    }


# ============================================================
# EVALUATION NODE
# ============================================================

def evaluate_answer_node(
    state: InterviewState
):

    print(
        "\n========== EVALUATION NODE =========="
    )

    current_skill = state.get(
        "current_skill",
        ""
    )

    current_question = state.get(
        "current_question",
        ""
    )

    candidate_answer = state.get(
        "candidate_answer",
        ""
    )

    skills = list(
        state.get(
            "skills",
            []
        )
    )

    skill_index = state.get(
        "skill_index",
        0
    )

    question_count = state.get(
        "question_count",
        0
    )

    print(
        f"Current Skill: {current_skill}"
    )

    print(
        f"Question Count: {question_count}"
    )

    # --------------------------------------------------------
    # Evaluate answer
    # --------------------------------------------------------

    result = evaluate_answer(
        current_skill=current_skill,
        question=current_question,
        candidate_answer=candidate_answer,
        skill_index=skill_index,
        skills=skills
    )

    if not isinstance(result, dict):
        result = {}

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    try:

        score = float(
            result.get(
                "score",
                0
            )
        )

    except Exception:

        score = 0

    score = max(
        0,
        min(10, score)
    )

    # --------------------------------------------------------
    # Concepts extracted from answer
    # --------------------------------------------------------

    extracted_concepts = result.get(
        "extracted_concepts",
        []
    )

    if not isinstance(
        extracted_concepts,
        list
    ):

        extracted_concepts = []

    extracted_concepts = [
        str(x).strip()
        for x in extracted_concepts
        if str(x).strip()
    ]

    # --------------------------------------------------------
    # Missing concepts
    # --------------------------------------------------------

    missing_concepts = result.get(
        "missing_concepts",
        []
    )

    if not isinstance(
        missing_concepts,
        list
    ):

        missing_concepts = []

    missing_concepts = [
        str(x).strip()
        for x in missing_concepts
        if str(x).strip()
    ]

    feedback = str(
        result.get(
            "feedback",
            ""
        )
    ).strip()

    print(
        f"\n⭐ Score: {score}/10"
    )

    print(
        f"🧠 Extracted Concepts: {extracted_concepts}"
    )

    print(
        f"📌 Missing Concepts: {missing_concepts}"
    )

    # ========================================================
    # UPDATE HISTORY
    # ========================================================

    history = list(
        state.get(
            "interview_history",
            []
        )
    )

    history.append({

        "question_number":
            question_count + 1,

        "skill":
            current_skill,

        "question":
            current_question,

        "candidate_answer":
            candidate_answer,

        "score":
            score,

        "feedback":
            feedback,

        "expected_answer":
            state.get(
                "current_expected_answer",
                ""
            ),

        "missing_concepts":
            missing_concepts

    })

    # ========================================================
    # UPDATE SKILL RATING
    # ========================================================

    skill_ratings = dict(
        state.get(
            "skill_ratings",
            {}
        )
    )

    # Keep the strongest score obtained
    # for the skill.

    previous_score = skill_ratings.get(
        current_skill,
        0
    )

    try:

        previous_score = float(
            previous_score
        )

    except Exception:

        previous_score = 0

    skill_ratings[
        current_skill
    ] = max(
        previous_score,
        score
    )

    # ========================================================
    # QUESTION COUNT
    # ========================================================

    new_question_count = (
        question_count + 1
    )

    # ========================================================
    # INTERVIEW COMPLETE
    # ========================================================

    if new_question_count >= MAX_QUESTIONS:

        print(
            "\n🏁 MAX QUESTIONS REACHED"
        )

        return {

            "current_score":
                score,

            "missing_concepts":
                missing_concepts,

            "extracted_concepts":
                extracted_concepts,

            "interview_history":
                history,

            "skill_ratings":
                skill_ratings,

            "question_count":
                new_question_count,

            "current_question":
                "",

            "current_expected_answer":
                ""

        }

    # ========================================================
    # ADAPTIVE ROUTING
    # ========================================================

    next_skill_index = skill_index

    next_skill = current_skill

    next_question_type = "basic"

    next_concepts = []

    # --------------------------------------------------------
    # SCORE > 6
    # --------------------------------------------------------

    if score > 6:

        print(
            "\n🔥 Strong answer detected."
        )

        # Remove concepts that were
        # already used in previous questions.

        previously_used = set()

        for item in history:

            for concept in item.get(
                "extracted_concepts",
                []
            ):

                previously_used.add(
                    str(concept).strip().lower()
                )

        available_concepts = []

        for concept in extracted_concepts:

            normalized = (
                str(concept)
                .strip()
                .lower()
            )

            if normalized not in previously_used:

                available_concepts.append(
                    str(concept).strip()
                )

        # ----------------------------------------------------
        # Concept found
        # ----------------------------------------------------

        if available_concepts:

            next_concepts = [
                available_concepts[0]
            ]

            next_skill = current_skill

            next_skill_index = skill_index

            next_question_type = (
                "concept_follow_up"
            )

            print(
                f"🧠 Next concept: {next_concepts[0]}"
            )

        # ----------------------------------------------------
        # No new concept
        # ----------------------------------------------------

        else:

            next_skill = current_skill

            next_skill_index = skill_index

            next_question_type = (
                "skill_deep"
            )

            print(
                "➡️ No new concept found."
            )

            print(
                "➡️ Going deeper into current skill."
            )

    # --------------------------------------------------------
    # SCORE <= 6
    # --------------------------------------------------------

    else:

        print(
            "\n➡️ Answer score <= 6."
        )

        # Move to next combined skill.

        if skills:

            next_skill_index = (
                skill_index + 1
            )

            # Wrap around safely.

            if (
                next_skill_index
                >= len(skills)
            ):

                next_skill_index = 0

            next_skill = skills[
                next_skill_index
            ]

        else:

            next_skill = current_skill

        next_question_type = "basic"

        next_concepts = []

        print(
            f"➡️ Next Skill: {next_skill}"
        )

    # ========================================================
    # RETURN UPDATED STATE
    # ========================================================

    return {

        "current_score":
            score,

        "missing_concepts":
            missing_concepts,

        "extracted_concepts":
            next_concepts,

        "interview_history":
            history,

        "skill_ratings":
            skill_ratings,

        "question_count":
            new_question_count,

        "skill_index":
            next_skill_index,

        "current_skill":
            next_skill,

        "question_type":
            next_question_type,

        "current_question":
            "",

        "current_expected_answer":
            ""

    }


# ============================================================
# ROUTING AFTER EVALUATION
# ============================================================

def route_after_evaluation(
    state: InterviewState
):

    question_count = state.get(
        "question_count",
        0
    )

    print(
        "\n========== POST-EVALUATION ROUTING =========="
    )

    print(
        f"Question Count: {question_count}"
    )

    if question_count >= MAX_QUESTIONS:

        print(
            "→ INTERVIEW COMPLETE"
        )

        return "complete"

    print(
        "→ GENERATE NEXT QUESTION"
    )

    return "next_question"


# ============================================================
# START ROUTING
# ============================================================

def route_from_start(
    state: InterviewState
):

    print(
        "\n========== START ROUTING =========="
    )

    skills = state.get(
        "skills",
        []
    )

    self_intro_skills = state.get(
        "self_intro_skills",
        []
    )

    current_question = state.get(
        "current_question",
        ""
    )

    candidate_answer = state.get(
        "candidate_answer",
        ""
    )

    # --------------------------------------------------------
    # Existing answer
    # --------------------------------------------------------

    if candidate_answer.strip():

        print(
            "→ Candidate answer available"
        )

        return "evaluate"

    # --------------------------------------------------------
    # Existing question
    # --------------------------------------------------------

    if current_question.strip():

        print(
            "→ Existing question available"
        )

        return "question_ready"

    # --------------------------------------------------------
    # Self-intro skills need to be merged
    # --------------------------------------------------------

    if self_intro_skills:

        print(
            "→ Self-intro skills available"
        )

        print(
            "→ Preparing combined skill pool"
        )

        return "prepare_skills"

    # --------------------------------------------------------
    # Skills available
    # --------------------------------------------------------

    if skills:

        print(
            "→ Skills available"
        )

        return "question"

    # --------------------------------------------------------
    # Otherwise analyze
    # --------------------------------------------------------

    print(
        "→ No skills available"
    )

    return "analysis"


# ============================================================
# BUILD GRAPH
# ============================================================

builder = StateGraph(
    InterviewState
)


# ------------------------------------------------------------
# Nodes
# ------------------------------------------------------------

builder.add_node(
    "analysis",
    analysis_node
)

builder.add_node(
    "prepare_skills",
    prepare_skills_node
)

builder.add_node(
    "select_skill",
    select_skill_node
)

builder.add_node(
    "question",
    question_node
)

builder.add_node(
    "evaluate",
    evaluate_answer_node
)


# ------------------------------------------------------------
# START ROUTING
# ------------------------------------------------------------

builder.add_conditional_edges(

    START,

    route_from_start,

    {

        "analysis":
            "analysis",

        "prepare_skills":
            "prepare_skills",

        "question":
            "question",

        "question_ready":
            END,

        "evaluate":
            "evaluate"

    }

)


# ------------------------------------------------------------
# ANALYSIS → SELECT SKILL
# ------------------------------------------------------------

builder.add_edge(
    "analysis",
    "select_skill"
)


# ------------------------------------------------------------
# PREPARE SKILLS → SELECT SKILL
# ------------------------------------------------------------

builder.add_edge(
    "prepare_skills",
    "select_skill"
)


# ------------------------------------------------------------
# SELECT SKILL → QUESTION
# ------------------------------------------------------------

builder.add_edge(
    "select_skill",
    "question"
)


# ------------------------------------------------------------
# QUESTION → END
# ------------------------------------------------------------

builder.add_edge(
    "question",
    END
)


# ------------------------------------------------------------
# EVALUATION ROUTING
# ------------------------------------------------------------

builder.add_conditional_edges(

    "evaluate",

    route_after_evaluation,

    {

        "complete":
            END,

        "next_question":
            "question"

    }

)


# ============================================================
# COMPILE
# ============================================================

app = builder.compile()