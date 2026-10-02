import psycopg2
import json
from datetime import datetime


DB_CONFIG = {
    "host": "100.117.158.50",
    "port": 5432,
    "user": "admin",
    "password": "admin",
    "dbname": "skill_engine_tho",
}


def get_connection():
    return psycopg2.connect(
        **DB_CONFIG,
        connect_timeout=10
    )


# ============================================================
# EXISTING / RESUME-MOCK INTERVIEW FUNCTIONS
# ============================================================

def save_interview_question(
    question_text,
    expected_key_points=None,
    evaluation_criteria=None,
    max_score=10,
    difficulty=None,
    topic_id=None,
    subject_id=None,
):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        question_query = """
            INSERT INTO questions (
                question_type,
                source,
                subject_id,
                topic_id,
                difficulty,
                is_active
            )
            VALUES (
                'interview',
                'manual',
                %s,
                %s,
                %s,
                TRUE
            )
            RETURNING id;
        """

        cursor.execute(
            question_query,
            (
                subject_id,
                topic_id,
                difficulty.lower() if difficulty else None,
            ),
        )

        question_id = cursor.fetchone()[0]

        interview_query = """
            INSERT INTO interview_questions (
                question_id,
                question_text,
                evaluation_criteria,
                expected_key_points,
                max_score
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """

        cursor.execute(
            interview_query,
            (
                question_id,
                question_text,
                json.dumps(evaluation_criteria or {}),
                json.dumps(expected_key_points or {}),
                max_score,
            ),
        )

        interview_question_id = cursor.fetchone()[0]

        conn.commit()

        return {
            "question_id": question_id,
            "interview_question_id": interview_question_id,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_interview_question(question_id):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        query = """
            SELECT
                q.id,
                iq.id,
                iq.question_text,
                iq.evaluation_criteria,
                iq.expected_key_points,
                iq.max_score,
                q.difficulty,
                q.topic_id,
                q.subject_id
            FROM questions q
            JOIN interview_questions iq
                ON iq.question_id = q.id
            WHERE q.id = %s
              AND q.is_active = TRUE;
        """

        cursor.execute(query, (question_id,))

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "question_id": row[0],
            "interview_question_id": row[1],
            "question_text": row[2],
            "evaluation_criteria": row[3],
            "expected_key_points": row[4],
            "max_score": (
                float(row[5])
                if row[5] is not None
                else 10
            ),
            "difficulty": row[6],
            "topic_id": row[7],
            "subject_id": row[8],
        }

    finally:
        conn.close()


def save_interview_answer(
    attempt_question_id,
    answer_text,
    answer_transcript=None,
    audio_url=None,
    video_url=None,
):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        # ----------------------------------------------------
        # 1. Get question, attempt, assessment and student
        #    using attempt_question_id
        # ----------------------------------------------------

        context_query = """
            SELECT
                aq.question_id,
                at.id AS attempt_id,
                at.assessment_id,
                at.student_id
            FROM attempt_questions aq
            JOIN attempt_sections ats
                ON ats.id = aq.attempt_section_id
            JOIN assessment_attempts at
                ON at.id = ats.attempt_id
            WHERE aq.id = %s
            LIMIT 1;
        """

        cursor.execute(
            context_query,
            (attempt_question_id,)
        )

        context = cursor.fetchone()

        if not context:
            raise ValueError(
                f"Attempt question not found: {attempt_question_id}"
            )

        question_id = context[0]
        attempt_id = context[1]
        assessment_id = context[2]
        student_id = context[3]

        # ----------------------------------------------------
        # 2. Check whether answer already exists
        # ----------------------------------------------------

        find_query = """
            SELECT id
            FROM interview_answers
            WHERE attempt_question_id = %s
            ORDER BY created_at DESC
            LIMIT 1;
        """

        cursor.execute(
            find_query,
            (attempt_question_id,)
        )

        existing = cursor.fetchone()

        # ----------------------------------------------------
        # 3. Update existing answer
        # ----------------------------------------------------

        if existing:

            answer_id = existing[0]

            query = """
                UPDATE interview_answers
                SET
                    assessment_id = %s,
                    question_id = %s,
                    student_id = %s,
                    answer_text = %s,
                    answer_transcript = %s,
                    audio_url = %s,
                    video_url = %s,
                    evaluation_status = 'pending',
                    answered_at = NOW(),
                    submitted_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """

            cursor.execute(
                query,
                (
                    assessment_id,
                    question_id,
                    student_id,
                    answer_text,
                    answer_transcript,
                    audio_url,
                    video_url,
                    answer_id,
                ),
            )

        # ----------------------------------------------------
        # 4. Insert new answer
        # ----------------------------------------------------

        else:

            query = """
                INSERT INTO interview_answers (
                    attempt_question_id,
                    assessment_id,
                    question_id,
                    student_id,
                    answer_text,
                    answer_transcript,
                    audio_url,
                    video_url,
                    evaluation_status,
                    answered_at,
                    submitted_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'pending',
                    NOW(),
                    NOW()
                )
                RETURNING id;
            """

            cursor.execute(
                query,
                (
                    attempt_question_id,
                    assessment_id,
                    question_id,
                    student_id,
                    answer_text,
                    answer_transcript,
                    audio_url,
                    video_url,
                ),
            )

        answer_id = cursor.fetchone()[0]

        conn.commit()

        return answer_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def save_question_evaluation(
    answer_id,
    score,
    feedback,
    evaluation_details,
):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        query = """
            UPDATE interview_answers
            SET
                score = %s,
                feedback = %s,
                evaluation_details = %s,
                evaluation_status = 'evaluated',
                evaluated_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING id;
        """

        cursor.execute(
            query,
            (
                score,
                feedback,
                json.dumps(evaluation_details or {}),
                answer_id,
            ),
        )

        row = cursor.fetchone()

        if not row:
            raise ValueError(
                f"Interview answer not found: {answer_id}"
            )

        conn.commit()

        return row[0]

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def save_final_interview_evaluation(
    assessment_id,
    attempt_id,
    student_id,
    overall_score,
    strengths,
    areas_for_improvement,
    technical_analysis,
    communication_analysis,
    problem_solving_analysis,
    final_feedback,
    ai_model,
):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        check_query = """
            SELECT id
            FROM interview_evaluations
            WHERE attempt_id = %s
            LIMIT 1;
        """

        cursor.execute(
            check_query,
            (attempt_id,)
        )

        existing = cursor.fetchone()

        if existing:
            evaluation_id = existing[0]

            query = """
                UPDATE interview_evaluations
                SET
                    assessment_id = %s,
                    student_id = %s,
                    overall_score = %s,
                    strengths = %s,
                    areas_for_improvement = %s,
                    technical_analysis = %s,
                    communication_analysis = %s,
                    problem_solving_analysis = %s,
                    final_feedback = %s,
                    ai_model = %s,
                    evaluated_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """

            cursor.execute(
                query,
                (
                    assessment_id,
                    student_id,
                    overall_score,
                    strengths,
                    areas_for_improvement,
                    technical_analysis,
                    communication_analysis,
                    problem_solving_analysis,
                    final_feedback,
                    ai_model,
                    evaluation_id,
                ),
            )

        else:
            query = """
                INSERT INTO interview_evaluations (
                    assessment_id,
                    attempt_id,
                    student_id,
                    overall_score,
                    strengths,
                    areas_for_improvement,
                    technical_analysis,
                    communication_analysis,
                    problem_solving_analysis,
                    final_feedback,
                    ai_model,
                    evaluated_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW(),
                    NOW(),
                    NOW()
                )
                RETURNING id;
            """

            cursor.execute(
                query,
                (
                    assessment_id,
                    attempt_id,
                    student_id,
                    overall_score,
                    strengths,
                    areas_for_improvement,
                    technical_analysis,
                    communication_analysis,
                    problem_solving_analysis,
                    final_feedback,
                    ai_model,
                ),
            )

        evaluation_id = cursor.fetchone()[0]

        conn.commit()

        return evaluation_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# TOPIC / ASSESSMENT INTERVIEW DB FUNCTIONS
# ============================================================

def create_interview_assessment(
    student_id,
    topic,
    level,
    total_questions=15,
    total_time_seconds=1800,
    question_time_seconds=120,
):
    """
    Creates:

        assessments
        assessment_sections
        assessment_attempts
        attempt_sections

    Returns all IDs needed by the interview session.
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # ----------------------------------------------------
        # 1. Create assessment
        # ----------------------------------------------------

        assessment_query = """
            INSERT INTO assessments (
                title,
                description,
                source,
                status,
                created_by,
                schedule_type,
                duration_seconds,
                instructions,
                result_status,
                timing_mode
            )
            VALUES (
                %s,
                %s,
                'manual',
                'draft',
                %s,
                'instant',
                %s,
                %s,
                'pending',
                'overall'
            )
            RETURNING id;
        """

        cursor.execute(
            assessment_query,
            (
                f"Topic Interview - {topic} - {level}",
                f"Topic Interview assessment for {topic} at {level} difficulty.",
                student_id,
                total_time_seconds,
                (
                    f"{total_questions} interview questions. "
                    f"Maximum {question_time_seconds} seconds per question."
                ),
            ),
        )

        assessment_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 2. Create interview section
        # ----------------------------------------------------

        section_query = """

            INSERT INTO assessment_sections (
                assessment_id,
                name,
                description,
                sequence,
                duration_seconds,
                question_count,
                total_marks,
                negative_marks,
                section_type,
                unlock_rule,
                difficulty,
                interview_mode,
                configuration

            )

            VALUES (
                %s,
                'Topic Interview',
                %s,
                1,
                %s,
                %s,
                %s,
                0,
                'interview',
                'previous_completed',
                %s,
                'manual',
                %s

            )

            RETURNING id;


        """

        configuration = json.dumps({
            "topic": topic,
            "level": level,
            "total_questions": total_questions,
            "total_time_seconds": total_time_seconds,
            "question_time_seconds": question_time_seconds,
        })

        cursor.execute(
            section_query,
            (
                assessment_id,
                f"Interview questions for {topic}",
                total_time_seconds,
                total_questions,
                total_questions * 10,
                level.lower(),
                configuration,
            ),
        )

        section_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 3. Create assessment attempt
        # ----------------------------------------------------

        attempt_query = """
            INSERT INTO assessment_attempts (
                assessment_id,
                student_id,
                attempt_number,
                status,
                started_at,
                total_score,
                max_score
            )
            VALUES (
                %s,
                %s,
                1,
                'in_progress',
                NOW(),
                0,
                %s
            )
            RETURNING id;
        """

        cursor.execute(
            attempt_query,
            (
                assessment_id,
                student_id,
                total_questions * 10,
            ),
        )

        attempt_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 4. Create attempt section
        # ----------------------------------------------------

        attempt_section_query = """
            INSERT INTO attempt_sections (
                attempt_id,
                section_id,
                status,
                started_at,
                score,
                max_score
            )
            VALUES (
                %s,
                %s,
                'in_progress',
                NOW(),
                0,
                %s
            )
            RETURNING id;
        """

        cursor.execute(
            attempt_section_query,
            (
                attempt_id,
                section_id,
                total_questions * 10,
            ),
        )

        attempt_section_id = cursor.fetchone()[0]

        conn.commit()

        
        return {
            "assessment_id": assessment_id,
            "section_id": section_id,
            "assessment_section_id": section_id,
            "attempt_id": attempt_id,
            "attempt_section_id": attempt_section_id,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def save_interview_question_to_attempt(
    section_id,
    attempt_section_id,
    question_text,
    expected_answer=None,
    expected_key_points=None,
    evaluation_criteria=None,
    max_score=10,
    difficulty=None,
    topic_id=None,
    subject_id=None,
    display_order=1,
):
    """
    Creates an interview question and links it to:

        assessment section
        student attempt

    Stores:
        - question text
        - expected/reference answer
        - expected key points
        - evaluation criteria
        - maximum score
        - difficulty/topic information
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # ----------------------------------------------------
        # 1. Create base question
        # ----------------------------------------------------

        question_query = """
            INSERT INTO questions (
                question_type,
                source,
                subject_id,
                topic_id,
                difficulty,
                is_active
            )
            VALUES (
                'interview',
                'ai',
                %s,
                %s,
                %s,
                TRUE
            )
            RETURNING id;
        """

        cursor.execute(
            question_query,
            (
                subject_id,
                topic_id,
                difficulty.lower() if difficulty else None,
            ),
        )

        question_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 2. Create interview question
        # ----------------------------------------------------

        interview_query = """
            INSERT INTO interview_questions (
                question_id,
                question_text,
                expected_answer,
                evaluation_criteria,
                expected_key_points,
                max_score
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id;
        """

        cursor.execute(
            interview_query,
            (
                question_id,
                question_text,
                expected_answer,
                json.dumps(evaluation_criteria or {}),
                json.dumps(expected_key_points or {}),
                max_score,
            ),
        )

        interview_question_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 3. Link question to assessment section
        # ----------------------------------------------------

        section_question_query = """
            INSERT INTO assessment_section_questions (
                section_id,
                question_id,
                marks,
                negative_marks
            )
            VALUES (
                %s,
                %s,
                %s,
                0
            )
            RETURNING id;
        """

        cursor.execute(
            section_question_query,
            (
                section_id,
                question_id,
                max_score,
            ),
        )

        assessment_section_question_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 4. Create attempt question
        # ----------------------------------------------------

        attempt_question_query = """
            INSERT INTO attempt_questions (
                attempt_section_id,
                question_id,
                display_order,
                marks,
                negative_marks
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                0
            )
            RETURNING id;
        """

        cursor.execute(
            attempt_question_query,
            (
                attempt_section_id,
                question_id,
                display_order,
                max_score,
            ),
        )

        attempt_question_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 5. Commit everything
        # ----------------------------------------------------

        conn.commit()

        return {
            "question_id": question_id,
            "interview_question_id": interview_question_id,
            "assessment_section_question_id": (
                assessment_section_question_id
            ),
            "attempt_question_id": attempt_question_id,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
             


def finish_interview_attempt(
    attempt_id,
    assessment_id,
    attempt_section_id,
    overall_score,
    max_score,
    student_id,
    strengths=None,
    areas_for_improvement=None,
    technical_analysis=None,
    communication_analysis=None,
    problem_solving_analysis=None,
    final_feedback=None,
    ai_model=None,
):
    """
    Finalizes a Topic Interview attempt.

    Updates:
        - assessment_attempts
        - attempt_sections
        - interview_evaluations

    Returns:
        evaluation_id
        attempt_id
        overall_score
        max_score
        percentage
    """

    def _db_text(value):
        """
        PostgreSQL text-safe conversion.

        AI output can sometimes be dict/list.
        Convert dict/list to JSON string before saving
        into text/varchar columns.
        """
        if value is None:
            return None

        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)

        return str(value)

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # ---------------------------------------------------------
        # 1. Calculate percentage
        # ---------------------------------------------------------

        if max_score and float(max_score) > 0:
            percentage = (
                float(overall_score) / float(max_score)
            ) * 100
        else:
            percentage = 0.0

        # ---------------------------------------------------------
        # 2. Finish assessment attempt
        # ---------------------------------------------------------

        attempt_query = """
            UPDATE assessment_attempts
            SET
                status = 'completed',
                submitted_at = NOW(),
                completed_at = NOW(),
                total_score = %s,
                max_score = %s,
                percentage = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id;
        """

        cursor.execute(
            attempt_query,
            (
                overall_score,
                max_score,
                round(percentage, 2),
                attempt_id,
            ),
        )

        attempt_result = cursor.fetchone()

        if not attempt_result:
            raise ValueError(
                f"Assessment attempt not found: {attempt_id}"
            )

        # ---------------------------------------------------------
        # 3. Finish attempt section
        # ---------------------------------------------------------

        attempt_section_query = """
            UPDATE attempt_sections
            SET
                status = 'completed',
                completed_at = NOW(),
                score = %s,
                max_score = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id;
        """

        cursor.execute(
            attempt_section_query,
            (
                overall_score,
                max_score,
                attempt_section_id,
            ),
        )

        attempt_section_result = cursor.fetchone()

        if not attempt_section_result:
            raise ValueError(
                f"Attempt section not found: {attempt_section_id}"
            )

        # ---------------------------------------------------------
        # 4. Check whether final evaluation already exists
        # ---------------------------------------------------------

        existing_evaluation_query = """
            SELECT id
            FROM interview_evaluations
            WHERE attempt_id = %s
            LIMIT 1;
        """

        cursor.execute(
            existing_evaluation_query,
            (attempt_id,),
        )

        existing_evaluation = cursor.fetchone()

        # ---------------------------------------------------------
        # 5. Convert AI output to DB-safe text
        # ---------------------------------------------------------

        strengths_db = _db_text(strengths)
        areas_for_improvement_db = _db_text(
            areas_for_improvement
        )
        technical_analysis_db = _db_text(
            technical_analysis
        )
        communication_analysis_db = _db_text(
            communication_analysis
        )
        problem_solving_analysis_db = _db_text(
            problem_solving_analysis
        )
        final_feedback_db = _db_text(
            final_feedback
        )
        ai_model_db = _db_text(ai_model)

        # ---------------------------------------------------------
        # 6. Update existing evaluation
        # ---------------------------------------------------------

        if existing_evaluation:

            evaluation_id = existing_evaluation[0]

            evaluation_update_query = """
                UPDATE interview_evaluations
                SET
                    assessment_id = %s,
                    student_id = %s,
                    overall_score = %s,
                    strengths = %s,
                    areas_for_improvement = %s,
                    technical_analysis = %s,
                    communication_analysis = %s,
                    problem_solving_analysis = %s,
                    final_feedback = %s,
                    ai_model = %s,
                    evaluated_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """

            cursor.execute(
                evaluation_update_query,
                (
                    assessment_id,
                    student_id,
                    overall_score,
                    strengths_db,
                    areas_for_improvement_db,
                    technical_analysis_db,
                    communication_analysis_db,
                    problem_solving_analysis_db,
                    final_feedback_db,
                    ai_model_db,
                    evaluation_id,
                ),
            )

            evaluation_result = cursor.fetchone()

            if not evaluation_result:
                raise ValueError(
                    "Failed to update interview evaluation."
                )

            evaluation_id = evaluation_result[0]

        # ---------------------------------------------------------
        # 7. Create new final evaluation
        # ---------------------------------------------------------

        else:

            evaluation_insert_query = """
                INSERT INTO interview_evaluations (
                    assessment_id,
                    attempt_id,
                    student_id,
                    overall_score,
                    strengths,
                    areas_for_improvement,
                    technical_analysis,
                    communication_analysis,
                    problem_solving_analysis,
                    final_feedback,
                    ai_model,
                    evaluated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                RETURNING id;
            """

            cursor.execute(
                evaluation_insert_query,
                (
                    assessment_id,
                    attempt_id,
                    student_id,
                    overall_score,
                    strengths_db,
                    areas_for_improvement_db,
                    technical_analysis_db,
                    communication_analysis_db,
                    problem_solving_analysis_db,
                    final_feedback_db,
                    ai_model_db,
                ),
            )

            evaluation_result = cursor.fetchone()

            if not evaluation_result:
                raise ValueError(
                    "Failed to create interview evaluation."
                )

            evaluation_id = evaluation_result[0]

        # ---------------------------------------------------------
        # 8. Commit everything
        # ---------------------------------------------------------

        conn.commit()

        # ---------------------------------------------------------
        # 9. Return final result
        # ---------------------------------------------------------

        return {
            "evaluation_id": evaluation_id,
            "attempt_id": attempt_id,
            "overall_score": float(overall_score),
            "max_score": float(max_score),
            "percentage": round(percentage, 2),
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()