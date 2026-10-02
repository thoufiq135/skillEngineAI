from backend.database import get_db_connection


def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1. Assessment Interview Questions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assessment_interview_questions (
                id BIGSERIAL PRIMARY KEY,
                assessment_id BIGINT NOT NULL,
                question TEXT NOT NULL,
                reference_answer TEXT,
                evaluation_criteria TEXT,
                marks NUMERIC NOT NULL DEFAULT 0,
                difficulty VARCHAR(50),
                category TEXT,
                question_order INTEGER,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Student Assessment Interview Answers
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assessment_interview_answers (
                id BIGSERIAL PRIMARY KEY,
                assessment_id BIGINT NOT NULL,
                attempt_id BIGINT NOT NULL,
                attempt_question_id BIGINT,
                question_id BIGINT NOT NULL,
                student_id BIGINT NOT NULL,
                question TEXT NOT NULL,
                student_answer TEXT,
                submitted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Question-level AI Evaluation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assessment_interview_question_evaluations (
                id BIGSERIAL PRIMARY KEY,
                answer_id BIGINT NOT NULL,
                score NUMERIC NOT NULL DEFAULT 0,
                max_score NUMERIC NOT NULL DEFAULT 0,
                technical_correctness TEXT,
                understanding TEXT,
                completeness TEXT,
                accuracy TEXT,
                relevance TEXT,
                communication_quality TEXT,
                problem_solving TEXT,
                strengths TEXT,
                missing_points TEXT,
                improvement TEXT,
                feedback TEXT,
                ai_model VARCHAR(255),
                evaluated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Final Interview Evaluation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS interview_evaluations (
                id BIGSERIAL PRIMARY KEY,
                assessment_id BIGINT NOT NULL,
                attempt_id BIGINT NOT NULL,
                student_id BIGINT NOT NULL,

                overall_score NUMERIC NOT NULL DEFAULT 0,
                max_score NUMERIC NOT NULL DEFAULT 0,
                percentage NUMERIC NOT NULL DEFAULT 0,

                strengths TEXT,
                areas_for_improvement TEXT,
                technical_analysis TEXT,
                communication_analysis TEXT,
                problem_solving_analysis TEXT,
                recommended_learning_areas TEXT,
                final_feedback TEXT,

                ai_model VARCHAR(255),

                evaluated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT unique_interview_evaluation_per_attempt
                    UNIQUE (attempt_id)
            );
        """)

        conn.commit()

        print("Assessment Interview tables created successfully.")

    except Exception as e:
        conn.rollback()
        print("Error creating tables:")
        print(e)

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_tables()