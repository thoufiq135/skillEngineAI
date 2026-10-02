from backend.database import get_db_connection


# ============================================================
# 1. INSERT INTERVIEW QUESTION
# ============================================================

def create_interview_question(
    assessment_id,
    question,
    reference_answer=None,
    evaluation_criteria=None,
    marks=0,
    difficulty=None,
    category=None,
    question_order=None
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO assessment_interview_questions (
                assessment_id,
                question,
                reference_answer,
                evaluation_criteria,
                marks,
                difficulty,
                category,
                question_order
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                assessment_id,
                question,
                reference_answer,
                evaluation_criteria,
                marks,
                difficulty,
                category,
                question_order
            )
        )

        question_id = cur.fetchone()[0]
        conn.commit()

        return question_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# ============================================================
# 2. GET ALL INTERVIEW QUESTIONS FOR AN ASSESSMENT
# ============================================================

def get_interview_questions(assessment_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                id,
                assessment_id,
                question,
                reference_answer,
                evaluation_criteria,
                marks,
                difficulty,
                category,
                question_order,
                created_at
            FROM assessment_interview_questions
            WHERE assessment_id = %s
            ORDER BY question_order, id
            """,
            (assessment_id,)
        )

        rows = cur.fetchall()

        questions = []

        for row in rows:
            questions.append({
                "id": row[0],
                "assessment_id": row[1],
                "question": row[2],
                "reference_answer": row[3],
                "evaluation_criteria": row[4],
                "marks": row[5],
                "difficulty": row[6],
                "category": row[7],
                "question_order": row[8],
                "created_at": row[9]
            })

        return questions

    finally:
        cur.close()
        conn.close()


# ============================================================
# 3. INSERT STUDENT INTERVIEW ANSWER
# ============================================================

def save_interview_answer(
    assessment_id,
    attempt_id,
    question_id,
    student_id,
    question,
    student_answer,
    attempt_question_id=None
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO assessment_interview_answers (
                assessment_id,
                attempt_id,
                attempt_question_id,
                question_id,
                student_id,
                question,
                student_answer
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                assessment_id,
                attempt_id,
                attempt_question_id,
                question_id,
                student_id,
                question,
                student_answer
            )
        )

        answer_id = cur.fetchone()[0]
        conn.commit()

        return answer_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# ============================================================
# 4. UPDATE STUDENT INTERVIEW ANSWER
# ============================================================

def update_interview_answer(answer_id, student_answer):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE assessment_interview_answers
            SET
                student_answer = %s,
                submitted_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (student_answer, answer_id)
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


# ============================================================
# 5. GET ALL INTERVIEW ANSWERS FOR AN ATTEMPT
# ============================================================

def get_interview_answers_by_attempt(attempt_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                a.id,
                a.assessment_id,
                a.attempt_id,
                a.attempt_question_id,
                a.question_id,
                a.student_id,
                a.question,
                a.student_answer,
                a.submitted_at,

                q.reference_answer,
                q.evaluation_criteria,
                q.marks,
                q.difficulty,
                q.category

            FROM assessment_interview_answers a

            JOIN assessment_interview_questions q
                ON a.question_id = q.id

            WHERE a.attempt_id = %s

            ORDER BY q.question_order, a.id
            """,
            (attempt_id,)
        )

        rows = cur.fetchall()

        answers = []

        for row in rows:
            answers.append({
                "answer_id": row[0],
                "assessment_id": row[1],
                "attempt_id": row[2],
                "attempt_question_id": row[3],
                "question_id": row[4],
                "student_id": row[5],
                "question": row[6],
                "student_answer": row[7],
                "submitted_at": row[8],
                "reference_answer": row[9],
                "evaluation_criteria": row[10],
                "marks": row[11],
                "difficulty": row[12],
                "category": row[13]
            })

        return answers

    finally:
        cur.close()
        conn.close()
        
        
# ============================================================
# 6. SAVE QUESTION-LEVEL AI EVALUATION
# ============================================================

def save_question_evaluation(
    answer_id,
    score,
    max_score,
    technical_correctness,
    understanding,
    completeness,
    accuracy,
    relevance,
    communication_quality,
    problem_solving,
    strengths,
    missing_points,
    improvement,
    feedback,
    ai_model="llama3.2:3b"
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO assessment_interview_question_evaluations (
                answer_id,
                score,
                max_score,
                technical_correctness,
                understanding,
                completeness,
                accuracy,
                relevance,
                communication_quality,
                problem_solving,
                strengths,
                missing_points,
                improvement,
                feedback,
                ai_model,
                evaluated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            RETURNING id
            """,
            (
                answer_id,
                score,
                max_score,
                technical_correctness,
                understanding,
                completeness,
                accuracy,
                relevance,
                communication_quality,
                problem_solving,
                "\n".join(str(x) for x in strengths),
                "\n".join(str(x) for x in missing_points),
                improvement,
                feedback,
                ai_model
            )
        )

        evaluation_id = cur.fetchone()[0]

        conn.commit()

        return evaluation_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
        
        
# ============================================================
# 7. GET QUESTION-LEVEL EVALUATIONS FOR AN ATTEMPT
# ============================================================

def get_question_evaluations_by_attempt(attempt_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                e.id,
                e.answer_id,
                a.assessment_id,
                a.attempt_id,
                a.student_id,
                a.question_id,
                a.question,
                a.student_answer,
                q.reference_answer,
                q.evaluation_criteria,
                e.score,
                e.max_score,
                e.technical_correctness,
                e.understanding,
                e.completeness,
                e.accuracy,
                e.relevance,
                e.communication_quality,
                e.problem_solving,
                e.strengths,
                e.missing_points,
                e.improvement,
                e.feedback,
                e.ai_model,
                e.evaluated_at

            FROM assessment_interview_question_evaluations e

            JOIN assessment_interview_answers a
                ON e.answer_id = a.id

            JOIN assessment_interview_questions q
                ON a.question_id = q.id

            WHERE a.attempt_id = %s

            ORDER BY q.question_order, e.id
            """,
            (attempt_id,)
        )

        rows = cur.fetchall()

        evaluations = []

        for row in rows:
            evaluations.append({
                "evaluation_id": row[0],
                "answer_id": row[1],
                "assessment_id": row[2],
                "attempt_id": row[3],
                "student_id": row[4],
                "question_id": row[5],
                "question": row[6],
                "student_answer": row[7],
                "reference_answer": row[8],
                "evaluation_criteria": row[9],
                "score": row[10],
                "max_score": row[11],
                "technical_correctness": row[12],
                "understanding": row[13],
                "completeness": row[14],
                "accuracy": row[15],
                "relevance": row[16],
                "communication_quality": row[17],
                "problem_solving": row[18],
                "strengths": row[19],
                "missing_points": row[20],
                "improvement": row[21],
                "feedback": row[22],
                "ai_model": row[23],
                "evaluated_at": row[24]
            })

        return evaluations

    finally:
        cur.close()
        conn.close()
        
        
# ============================================================
# 8. GET FINAL INTERVIEW EVALUATION BY ATTEMPT
# ============================================================

def get_final_interview_evaluation_by_attempt(attempt_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                id,
                assessment_id,
                attempt_id,
                student_id,
                overall_score,
                max_score,
                percentage,
                strengths,
                areas_for_improvement,
                technical_analysis,
                communication_analysis,
                problem_solving_analysis,
                recommended_learning_areas,
                final_feedback,
                ai_model,
                evaluated_at,
                created_at,
                updated_at
            FROM interview_evaluations
            WHERE attempt_id = %s
            LIMIT 1
            """,
            (attempt_id,)
        )

        row = cur.fetchone()

        if not row:
            return None

        return {
            "evaluation_id": row[0],
            "assessment_id": row[1],
            "attempt_id": row[2],
            "student_id": row[3],
            "overall_score": float(row[4]) if row[4] is not None else 0,
            "max_score": float(row[5]) if row[5] is not None else 0,
            "percentage": float(row[6]) if row[6] is not None else 0,
            "strengths": row[7],
            "areas_for_improvement": row[8],
            "technical_analysis": row[9],
            "communication_analysis": row[10],
            "problem_solving_analysis": row[11],
            "recommended_learning_areas": row[12],
            "final_feedback": row[13],
            "ai_model": row[14],
            "evaluated_at": row[15],
            "created_at": row[16],
            "updated_at": row[17]
        }

    finally:
        cur.close()
        conn.close()
        
        
# ============================================================
# 8. SAVE FINAL INTERVIEW EVALUATION
# ============================================================

def save_final_interview_evaluation(
    assessment_id,
    attempt_id,
    student_id,
    overall_score,
    max_score,
    percentage,
    strengths,
    areas_for_improvement,
    technical_analysis,
    communication_analysis,
    problem_solving_analysis,
    recommended_learning_areas,
    final_feedback,
    ai_model="llama3.2:3b"
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO interview_evaluations (
                assessment_id,
                attempt_id,
                student_id,
                overall_score,
                max_score,
                percentage,
                strengths,
                areas_for_improvement,
                technical_analysis,
                communication_analysis,
                problem_solving_analysis,
                recommended_learning_areas,
                final_feedback,
                ai_model,
                evaluated_at,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id
            """,
            (
                assessment_id,
                attempt_id,
                student_id,
                overall_score,
                max_score,
                percentage,
                "\n".join(str(x) for x in strengths),
                "\n".join(str(x) for x in areas_for_improvement),
                technical_analysis,
                communication_analysis,
                problem_solving_analysis,
                "\n".join(str(x) for x in recommended_learning_areas),
                final_feedback,
                ai_model
            )
        )

        evaluation_id = cur.fetchone()[0]

        conn.commit()

        return evaluation_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()