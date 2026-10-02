import json

from backend.database import get_db_connection


# ============================================================
# SAVE INTERVIEW
# ============================================================

def save_interview(
    user_id,
    overall_score,
    questions_answered,
    skills,
    strong_skills,
    skills_to_improve,
    best_match_role=None,
    future_roles=None
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO interviews (
                user_id,
                overall_score,
                questions_answered,
                skills,
                strong_skills,
                skills_to_improve,
                best_match_role,
                future_roles
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """

        cursor.execute(
            query,
            (
                user_id,
                overall_score,
                questions_answered,
                json.dumps(skills, ensure_ascii=False),
                json.dumps(strong_skills, ensure_ascii=False),
                json.dumps(skills_to_improve, ensure_ascii=False),
                best_match_role,
                future_roles
            )
        )

        interview_id = cursor.fetchone()[0]

        connection.commit()

        return interview_id

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# ============================================================
# SAVE INTERVIEW QUESTION
# ============================================================

def save_interview_question(
    interview_id,
    skill,
    question,
    question_type,
    candidate_answer,
    score,
    feedback,
    missing_concepts,
    extracted_concepts
):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        # Convert internal question type
        # to PostgreSQL allowed values.

        if question_type == "concept_follow_up":
            db_question_type = "follow-up"

        elif question_type == "skill_deep":
            db_question_type = "deep"

        else:
            db_question_type = "basic"

        query = """
            INSERT INTO interview_questions (
                interview_id,
                skill,
                question,
                question_type,
                candidate_answer,
                score,
                feedback,
                missing_concepts,
                extracted_concepts
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id
        """

        cursor.execute(
            query,
            (
                interview_id,
                skill,
                question,
                db_question_type,
                candidate_answer,
                score,
                feedback,
                json.dumps(
                    missing_concepts,
                    ensure_ascii=False
                ),
                json.dumps(
                    extracted_concepts,
                    ensure_ascii=False
                )
            )
        )

        question_id = cursor.fetchone()[0]

        connection.commit()

        return question_id

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()