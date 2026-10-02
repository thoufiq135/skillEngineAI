from backend.assessment_interview_db import (
    get_question_evaluations_by_attempt,
    get_final_interview_evaluation_by_attempt,
    save_final_interview_evaluation
)

from backend.assessment_interview_final_ai import (
    generate_final_interview_analysis
)


def evaluate_assessment_interview(
    assessment_id,
    attempt_id,
    student_id
):
    """
    Complete Assessment Interview evaluation flow.

    Flow:
    1. Check whether final evaluation already exists
    2. Get question-level evaluations
    3. Calculate overall score
    4. Calculate max score
    5. Calculate percentage
    6. Generate final AI analysis
    7. Save final interview evaluation
    """

    # --------------------------------------------------
    # 1. Check existing final evaluation
    # --------------------------------------------------

    existing_evaluation = get_final_interview_evaluation_by_attempt(
        attempt_id
    )

    if existing_evaluation:
        print(
            f"Final interview evaluation already exists "
            f"for attempt_id={attempt_id}"
        )

        return existing_evaluation

    # --------------------------------------------------
    # 2. Get question-level evaluations
    # --------------------------------------------------

    evaluations = get_question_evaluations_by_attempt(
        attempt_id
    )

    if not evaluations:
        raise ValueError(
            "No interview question evaluations found "
            "for this attempt."
        )

    # --------------------------------------------------
    # 3. Calculate overall score
    # --------------------------------------------------

    overall_score = sum(
        float(item["score"] or 0)
        for item in evaluations
    )

    # --------------------------------------------------
    # 4. Calculate maximum score
    # --------------------------------------------------

    max_score = sum(
        float(item["max_score"] or 0)
        for item in evaluations
    )

    # --------------------------------------------------
    # 5. Calculate percentage
    # --------------------------------------------------

    if max_score > 0:
        percentage = (
            overall_score / max_score
        ) * 100
    else:
        percentage = 0

    # --------------------------------------------------
    # 6. Generate final AI analysis
    # --------------------------------------------------

    final_analysis = generate_final_interview_analysis(
        evaluations
    )

    # --------------------------------------------------
    # 7. Save final interview evaluation
    # --------------------------------------------------

    evaluation_id = save_final_interview_evaluation(
        assessment_id=assessment_id,
        attempt_id=attempt_id,
        student_id=student_id,
        overall_score=overall_score,
        max_score=max_score,
        percentage=percentage,
        strengths=final_analysis.get(
            "strengths",
            []
        ),
        areas_for_improvement=final_analysis.get(
            "areas_for_improvement",
            []
        ),
        technical_analysis=final_analysis.get(
            "technical_analysis",
            ""
        ),
        communication_analysis=final_analysis.get(
            "communication_analysis",
            ""
        ),
        problem_solving_analysis=final_analysis.get(
            "problem_solving_analysis",
            ""
        ),
        recommended_learning_areas=final_analysis.get(
            "recommended_learning_areas",
            []
        ),
        final_feedback=final_analysis.get(
            "final_feedback",
            ""
        ),
        ai_model="llama3.2:3b"
    )

    # --------------------------------------------------
    # 8. Return complete result
    # --------------------------------------------------

    return {
        "evaluation_id": evaluation_id,
        "assessment_id": assessment_id,
        "attempt_id": attempt_id,
        "student_id": student_id,
        "overall_score": overall_score,
        "max_score": max_score,
        "percentage": percentage,
        "final_analysis": final_analysis
    }