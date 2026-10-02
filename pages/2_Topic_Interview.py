import streamlit as st
import requests
import json
import time
import re
from answer_bridge import get_candidate_answer

API_URL = "http://127.0.0.1:8000"
API_TIMEOUT = 300
ADMIN_MAX_QUESTIONS = 15
ADMIN_TOTAL_TIME_SECONDS = 30 * 60
ADMIN_QUESTION_TIME_SECONDS = 2 * 60

def api_post_json(endpoint, payload, token=None):

    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("AUTH HEADER EXISTS:", "Authorization" in headers)

    response = requests.post(
        f"{API_URL}{endpoint}",
        json=payload,
        headers=headers,
        timeout=API_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()

def api_get_json(endpoint, token=None):

    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(
        f"{API_URL}{endpoint}",
        headers=headers,
        timeout=API_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()

def api_start_topic_interview(
    topic,
    level,
):

    token = st.session_state.get("auth_token")
    print("AUTH TOKEN EXISTS:", bool(token))

    return api_post_json(
        "/interview/start",
        {
            "topic": topic,
            "level": level,
        },
        token=token,
    )

def api_get_topic_question(
    session_id,
    candidate_answer="",
):

    return api_post_json(
        "/interview/question",
        {
            "session_id": session_id,
            "candidate_answer": candidate_answer,
        },
    )

def api_evaluate_topic_answer(
    session_id,
    question_id,
    candidate_answer,
):

    return api_post_json(
        "/interview/evaluate",
        {
            "session_id": session_id,
            "question_id": question_id,
            "candidate_answer": candidate_answer,
        },
    )

def api_get_topic_status(
    session_id,
):

    return api_get_json(
        f"/interview/status/{session_id}"
    )

def api_finish_topic_interview(
    session_id,
):

    return api_post_json(
        f"/interview/finish/{session_id}",
        {},
    )

def normalize_topic_key(topic):

    value = str(topic or "").strip().lower()

    value = re.sub(
        r"[^a-z0-9+#.]+",
        "",
        value,
    )

    aliases = {
        "js": "javascript",
        "javascript": "javascript",
        "java": "java",
        "py": "python",
        "python": "python",
        "sql": "sql",
        "figma": "figma",
    }

    return aliases.get(
        value,
        value,
    )

def topic_display_name(topic):

    value = str(topic or "").strip()

    topic_key = normalize_topic_key(value)

    display_names = {
        "javascript": "JavaScript",
        "java": "Java",
        "python": "Python",
        "sql": "SQL",
        "figma": "Figma",
    }

    return display_names.get(
        topic_key,
        value,
    )

def clean_question_text(question):
    """Remove accidental HTML/CSS/code wrappers from backend questions."""
    text = str(question or "").strip()

    # Decode HTML entities first.
    import html
    text = html.unescape(text)

    # Remove fenced code wrappers when the backend accidentally returns
    # HTML/CSS inside a markdown code block.
    text = re.sub(
        r"```(?:html|css|markdown|text)?\\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"```",
        "",
        text,
    )

    # Remove <style>...</style> blocks completely.
    text = re.sub(
        r"<style[^>]*>.*?</style>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove HTML comments.
    text = re.sub(
        r"<!--.*?-->",
        "",
        text,
        flags=re.DOTALL,
    )

    # Remove HTML tags but preserve their visible text.
    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    # Remove CSS declarations that may have been returned as plain text.
    text = re.sub(
        r"\\b(?:background|padding|margin|border|border-radius|box-shadow|"
        r"font-size|font-weight|color|line-height|text-align)\\s*:\\s*[^;{}]+;?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove common leftover CSS punctuation/empty lines.
    text = re.sub(
        r"\\{[^{}]*(?:#[0-9a-fA-F]{3,8}|rgba?\\([^)]*\\)|px|rem|solid|white)[^{}]*\\}",
        "",
        text,
    )

    text = re.sub(r"\\n{3,}", "\\n\\n", text)
    return text.strip()

def is_question_topic_valid(
    topic,
    question,
):

    topic_key = normalize_topic_key(topic)

    question_text = str(
        question or ""
    ).lower()

    if not question_text:
        return False

    # --------------------------------------------------------
    # JavaScript must NOT become Java
    # --------------------------------------------------------

    if topic_key == "javascript":

        java_only_patterns = [
            "synchronized keyword",
            "volatile keyword",
            "synchronized and volatile",
            "jvm",
            "jre",
            "j2ee",
            "spring boot",
            "spring framework",
            "java virtual machine",
            "java bytecode",
            "java thread",
            "java concurrency",
            "java interface",
            "java package",
            "java exception",
        ]

        for pattern in java_only_patterns:

            if pattern in question_text:

                return False

    # --------------------------------------------------------
    # Java must NOT become JavaScript
    # --------------------------------------------------------

    if topic_key == "java":

        javascript_patterns = [
            "javascript dom",
            "javascript event loop",
            "javascript closure",
            "javascript promise",
            "javascript async",
            "javascript await",
            "javascript hoisting",
            "javascript prototype",
            "javascript browser",
        ]

        for pattern in javascript_patterns:

            if pattern in question_text:

                return False

    return True

def clean_api_list(value):

    if not isinstance(value, list):

        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]

def build_topic_report(
    topic,
    level,
    history,
):

    if not isinstance(history, list):

        history = []

    normalized_history = []

    for record in history:

        if not isinstance(record, dict):

            continue

        try:

            score = float(
                record.get(
                    "score",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            score = 0.0

        score = max(
            0.0,
            min(
                10.0,
                score,
            ),
        )

        normalized_history.append(
            {
                **record,
                "score": score,
            }
        )

    # --------------------------------------------------------
    # EXACTLY 15 QUESTIONS ARE PLANNED
    # --------------------------------------------------------

    total_questions = ADMIN_MAX_QUESTIONS

    questions_attempted = len(
        normalized_history
    )

    answered_questions = sum(
        1
        for record in normalized_history
        if str(
            record.get(
                "candidate_answer",
                "",
            )
        ).strip()
        not in (
            "",
            "Skipped",
            "No answer provided",
        )
    )

    skipped_questions = sum(
        1
        for record in normalized_history
        if str(
            record.get(
                "candidate_answer",
                "",
            )
        ).strip()
        in (
            "Skipped",
            "No answer provided",
            "",
        )
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    if normalized_history:

        total_score = sum(
            record["score"]
            for record in normalized_history
        )

        overall_score = round(
            total_score / total_questions,
            1,
        )

    else:

        overall_score = 0.0

    percentage = round(
        (overall_score / 10) * 100,
        1,
    )

    # --------------------------------------------------------
    # CONCEPTS
    # --------------------------------------------------------

    strong_concepts = []
    improvement_concepts = []

    for record in normalized_history:

        score = record.get(
            "score",
            0,
        )

        extracted = clean_api_list(
            record.get(
                "extracted_concepts",
                [],
            )
        )

        missing = clean_api_list(
            record.get(
                "missing_concepts",
                [],
            )
        )

        if score >= 7:

            strong_concepts.extend(
                extracted
            )

        if score < 7:

            improvement_concepts.extend(
                missing
            )

    def unique_values(values):

        result = []

        seen = set()

        for value in values:

            clean_value = str(
                value
            ).strip()

            if not clean_value:

                continue

            key = clean_value.lower()

            if key not in seen:

                seen.add(key)

                result.append(
                    clean_value
                )

        return result

    strong_concepts = unique_values(
        strong_concepts
    )

    improvement_concepts = unique_values(
        improvement_concepts
    )

    return {
        "topic": topic,
        "level": level,
        "total_questions": total_questions,
        "questions_attempted": questions_attempted,
        "answered_questions": answered_questions,
        "skipped_questions": skipped_questions,
        "overall_score": overall_score,
        "percentage": percentage,
        "strong_concepts": strong_concepts,
        "concepts_to_improve": improvement_concepts,
        "history": normalized_history,
    }

def reset_topic_interview():

    st.session_state.topic_interview_active = False

    st.session_state.topic_interview_finished = False

    st.session_state.topic_session_id = ""

    st.session_state.topic_name = ""

    st.session_state.topic_level = "Medium"

    st.session_state.topic_question = ""

    st.session_state.topic_question_id = ""

    st.session_state.topic_question_number = 0

    st.session_state.topic_question_started_at = 0

    st.session_state.topic_total_expires_at = 0

    st.session_state.topic_candidate_answer = ""

    st.session_state.topic_history = []

    st.session_state.topic_result = None

    st.session_state.topic_last_event = None

    st.session_state.topic_result_saved = False

def finish_topic_interview():

    topic = st.session_state.topic_name

    level = st.session_state.topic_level

    session_id = st.session_state.topic_session_id

    history = st.session_state.topic_history

    try:

        api_result = api_finish_topic_interview(
            session_id
        )

    except Exception:

        api_result = {}

    report = build_topic_report(
        topic=topic,
        level=level,
        history=history,
    )

    report["api_result"] = api_result

    st.session_state.topic_result = report

    st.session_state.topic_interview_active = False

    st.session_state.topic_interview_finished = True

# ============================================================
# TOPIC PAGE SESSION DEFAULTS
# ============================================================

TOPIC_DEFAULTS = {
    "auth_token": None,
    "current_user": None,
    "topic_interview_active": False,
    "topic_interview_finished": False,
    "topic_session_id": "",
    "topic_name": "",
    "topic_level": "Medium",
    "topic_question": "",
    "topic_question_id": "",
    "topic_question_number": 0,
    "topic_question_started_at": 0,
    "topic_total_expires_at": 0,
    "topic_candidate_answer": "",
    "topic_history": [],
    "topic_result": None,
    "topic_last_event": None,
    "topic_result_saved": False,
}

for key, value in TOPIC_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if not st.session_state.get("auth_token"):
    st.warning("Please login first.")
    st.switch_page("app.py")

with st.sidebar:
    user = st.session_state.get("current_user") or {}
    st.markdown("### 👤 Account")
    st.write(user.get("name", "User"))
    st.caption(user.get("email", ""))
    st.divider()
    st.page_link("app.py", label="📄 Resume Interview")
    st.page_link("pages/2_Topic_Interview.py", label="🎯 Topic Interview")
    st.divider()
    if st.button("Logout", use_container_width=True):
        for key, value in TOPIC_DEFAULTS.items():
            st.session_state[key] = value
        st.session_state.auth_token = None
        st.session_state.current_user = None
        st.switch_page("app.py")

# ============================================================
# TOPIC INTERVIEW RESULT PAGE
# ============================================================

if st.session_state.topic_interview_finished:

    st.title(
        "🎯 Topic Interview Final Report"
    )

    result = (
        st.session_state.topic_result
        or {}
    )

    topic = result.get(
        "topic",
        st.session_state.topic_name,
    )

    level = result.get(
        "level",
        st.session_state.topic_level,
    )

    history = result.get(
        "history",
        st.session_state.topic_history,
    )

    if not isinstance(history, list):

        history = []

    overall_score = result.get(
        "overall_score",
        0,
    )

    percentage = result.get(
        "percentage",
        0,
    )

    answered_questions = result.get(
        "answered_questions",
        0,
    )

    skipped_questions = result.get(
        "skipped_questions",
        0,
    )

    strong_concepts = clean_api_list(
        result.get(
            "strong_concepts",
            [],
        )
    )

    concepts_to_improve = clean_api_list(
        result.get(
            "concepts_to_improve",
            [],
        )
    )

    st.info(
        f"**Topic:** {topic}  \n"
        f"**Level:** {level}"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Overall Score",
            f"{overall_score}/10",
        )

    with col2:

        st.metric(
            "Percentage",
            f"{percentage}%",
        )

    with col3:

        st.metric(
            "Answered",
            answered_questions,
        )

    with col4:

        st.metric(
            "Skipped",
            skipped_questions,
        )

    st.divider()

    # --------------------------------------------------------
    # STRONG CONCEPTS
    # --------------------------------------------------------

    st.subheader(
        "💪 Strong Concepts"
    )

    if strong_concepts:

        for concept in strong_concepts:

            st.success(
                concept
            )

    else:

        st.write(
            "No strong concepts were identified."
        )

    # --------------------------------------------------------
    # CONCEPTS TO IMPROVE
    # --------------------------------------------------------

    st.subheader(
        "📚 Concepts to Improve"
    )

    if concepts_to_improve:

        for concept in concepts_to_improve:

            st.warning(
                concept
            )

    else:

        st.write(
            "No specific improvement concepts were identified."
        )

    st.divider()

    # --------------------------------------------------------
    # QUESTION-WISE HISTORY
    # --------------------------------------------------------

    st.subheader(
        "📝 Question-wise Performance"
    )

    for index, record in enumerate(
        history,
        start=1,
    ):

        score = record.get(
            "score",
            0,
        )

        st.markdown(
            f"### Question {index} — {score}/10"
        )

        st.write(
            f"**Question:** "
            f"{record.get('question', '')}"
        )

        st.write(
            f"**Your Answer:** "
            f"{record.get('candidate_answer', '')}"
        )

        st.write(
            f"**Feedback:** "
            f"{record.get('feedback', '')}"
        )

        missing = clean_api_list(
            record.get(
                "missing_concepts",
                [],
            )
        )

        if missing:

            st.write(
                "**Missing Concepts:** "
                + ", ".join(
                    missing
                )
            )

        st.divider()

    if st.button(
        "🔄 Start New Topic Interview",
        use_container_width=True,
    ):

        reset_topic_interview()

        st.rerun()

    st.stop()

if not st.session_state.topic_interview_active:

    st.markdown(
        """
        <style>

        .topic-hero {
            text-align: center;
            padding: 45px 20px 25px;
        }

        .topic-hero .icon {
            font-size: 54px;
        }

        .topic-hero h1 {
            font-size: 2.35rem;
            font-weight: 800;
            color: #111827;
            margin: 8px 0;
        }

        .topic-hero p {
            color: #6b7280;
            font-size: 1rem;
        }

        .topic-card {
            max-width: 760px;
            margin: 20px auto;
            padding: 30px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
            box-shadow: 0 12px 30px rgba(15,23,42,.08);
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="topic-hero">
            <div class="icon">🎯</div>
            <h1>Topic Interview</h1>
            <p>
                Questions will stay strictly inside your selected topic
                and difficulty level.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    topic = st.text_input(
        "Interview Topic",
        placeholder="Example: Python, SQL, Figma, JavaScript",
        key="new_topic_input",
    )

    level = st.selectbox(
        "Interview Level",
        [
            "Easy",
            "Medium",
            "Hard",
        ],
        index=1,
        key="new_topic_level",
    )

    st.info(
        "⏱️ 30 minutes total  •  "
        "15 questions  •  "
        "Maximum 2 minutes per question"
    )

    if st.button(
        "🚀 Start Topic Interview",
        use_container_width=True,
    ):

        topic = topic.strip()

        if not topic:

            st.error(
                "Please enter an interview topic."
            )

            st.stop()

        normalized_topic = topic_display_name(
            topic
        )

        try:

            start_result = api_start_topic_interview(
                normalized_topic,
                level,
            )

        except requests.HTTPError as error:

            detail = (
                "Unable to start interview."
            )

            if error.response is not None:

                try:

                    detail = (
                        error.response.json().get(
                            "detail",
                            detail,
                        )
                    )

                except Exception:

                    pass

            st.error(detail)

            st.stop()

        except requests.RequestException as error:

            st.error(
                f"FastAPI connection failed: {error}"
            )

            st.stop()

        session_id = start_result.get(
            "session_id",
            "",
        )

        if not session_id:

            st.error(
                "FastAPI did not return a session ID."
            )

            st.stop()

        st.session_state.topic_session_id = (
            session_id
        )

        st.session_state.topic_name = (
            normalized_topic
        )

        st.session_state.topic_level = (
            level
        )

        st.session_state.topic_total_expires_at = (
            int(
                start_result.get(
                    "expires_at",
                    int(time.time())
                    + ADMIN_TOTAL_TIME_SECONDS,
                )
            )
        )

        st.session_state.topic_question_number = 0

        st.session_state.topic_history = []

        st.session_state.topic_candidate_answer = ""

        st.session_state.topic_question = ""

        st.session_state.topic_question_id = ""

        st.session_state.topic_question_started_at = 0

        st.session_state.topic_last_event = None

        st.session_state.topic_result_saved = False

        st.session_state.topic_interview_finished = False

        st.session_state.topic_interview_active = True

        try:

            question_result = api_get_topic_question(
                session_id
            )

        except requests.RequestException as error:

            st.session_state.topic_interview_active = False

            st.error(
                f"Question generation failed: {error}"
            )

            st.stop()

        question_text = str(
            question_result.get(
                "question",
                "",
            )
        ).strip()

        # ----------------------------------------------------
        # STRICT TOPIC CHECK
        # ----------------------------------------------------

        if not is_question_topic_valid(
            normalized_topic,
            question_text,
        ):

            st.error(
                "The backend generated a question outside the selected topic. "
                "Please restart after fixing the backend topic guard."
            )

            st.session_state.topic_interview_active = False

            st.stop()

        st.session_state.topic_question = (
            question_text
        )

        st.session_state.topic_question_id = (
            question_result.get(
                "question_id",
                "",
            )
        )

        st.session_state.topic_question_number = (
            question_result.get(
                "question_number",
                1,
            )
        )

        st.session_state.topic_question_started_at = (
            int(time.time())
        )

        st.session_state.topic_candidate_answer = ""

        st.rerun()

    st.stop()

if st.session_state.topic_interview_active:

    topic = st.session_state.topic_name
    level = st.session_state.topic_level
    session_id = st.session_state.topic_session_id

    current_question_number = int(
        st.session_state.topic_question_number or 0
    )

    # --------------------------------------------------------
    # EXACT 15 QUESTION LIMIT
    # --------------------------------------------------------

    if current_question_number > ADMIN_MAX_QUESTIONS:
        finish_topic_interview()
        st.rerun()

    st.title("🎤 Topic Interview")

    st.caption(
        f"Topic: **{topic}**  •  Level: **{level}**"
    )

    # --------------------------------------------------------
    # TIMER VALUES
    # --------------------------------------------------------

    now = int(time.time())

    total_expires_at = int(
        st.session_state.topic_total_expires_at
        or (now + ADMIN_TOTAL_TIME_SECONDS)
    )

    question_started_at = int(
        st.session_state.topic_question_started_at
        or now
    )

    total_remaining = max(
        0,
        total_expires_at - now,
    )

    question_remaining = max(
        0,
        ADMIN_QUESTION_TIME_SECONDS
        - (now - question_started_at),
    )

    # --------------------------------------------------------
    # TIMEOUT PROCESSING
    # --------------------------------------------------------

    if total_remaining <= 0 or question_remaining <= 0:

        current_answer = str(
            st.session_state.topic_candidate_answer or ""
        ).strip()

        current_question_id = (
            st.session_state.topic_question_id
        )

        current_question = (
            st.session_state.topic_question
        )

        try:
            evaluation = api_evaluate_topic_answer(
                session_id=session_id,
                question_id=current_question_id,
                candidate_answer=current_answer,
            )
        except Exception:
            evaluation = {}

        try:
            score = float(
                evaluation.get("score", 0)
            )
        except (TypeError, ValueError):
            score = 0.0

        score = max(0.0, min(10.0, score))

        feedback = str(
            evaluation.get(
                "feedback",
                "Question time limit reached.",
            )
        ).strip()

        missing_concepts = clean_api_list(
            evaluation.get("missing_concepts", [])
        )

        extracted_concepts = clean_api_list(
            evaluation.get("extracted_concepts", [])
        )

        # Prevent duplicate history entries if Streamlit reruns
        # around the exact timeout boundary.
        already_recorded = any(
            str(record.get("question_id", "")) == str(current_question_id)
            for record in st.session_state.topic_history
            if isinstance(record, dict)
        )

        if not already_recorded:
            st.session_state.topic_history.append(
                {
                    "question": current_question,
                    "candidate_answer": (
                        current_answer
                        if current_answer
                        else "No answer provided"
                    ),
                    "score": score,
                    "feedback": feedback,
                    "missing_concepts": missing_concepts,
                    "extracted_concepts": extracted_concepts,
                    "question_id": current_question_id,
                }
            )

        # Question 15 or total interview timeout -> final report.
        if (
            current_question_number >= ADMIN_MAX_QUESTIONS
            or int(time.time()) >= total_expires_at
        ):
            finish_topic_interview()
            st.rerun()

        # Otherwise immediately generate the next question.
        try:
            next_question = api_get_topic_question(
                session_id,
                current_answer,
            )
        except requests.RequestException as error:
            st.error(
                f"Next question generation failed: {error}"
            )
            st.stop()

        next_question_text = clean_question_text(
            next_question.get("question", "")
        )

        if not is_question_topic_valid(
            topic,
            next_question_text,
        ):
            st.error(
                "Backend generated a question outside the selected topic. "
                "Fix the backend topic validation before continuing."
            )
            st.stop()

        st.session_state.topic_question = next_question_text

        st.session_state.topic_question_id = (
            next_question.get("question_id", "")
        )

        st.session_state.topic_question_number = (
            next_question.get(
                "question_number",
                current_question_number + 1,
            )
        )

        st.session_state.topic_question_started_at = int(
            time.time()
        )

        st.session_state.topic_candidate_answer = ""

        st.rerun()

    # --------------------------------------------------------
    # LIVE TIMER
    #
    # The timer itself must be INSIDE the 1-second fragment.
    # Otherwise only the fragment reruns while the visible
    # timer outside it remains frozen.
    # --------------------------------------------------------

    @st.fragment(run_every=1)
    def topic_timer_refresh():

        current_time = int(time.time())

        total_remaining_live = max(
            0,
            int(
                st.session_state.topic_total_expires_at
                - current_time
            ),
        )

        question_remaining_live = max(
            0,
            int(
                ADMIN_QUESTION_TIME_SECONDS
                - (
                    current_time
                    - int(
                        st.session_state.topic_question_started_at
                        or current_time
                    )
                )
            ),
        )

        total_minutes = total_remaining_live // 60
        total_seconds = total_remaining_live % 60

        question_minutes = question_remaining_live // 60
        question_seconds = question_remaining_live % 60

        st.progress(
            min(
                1.0,
                total_remaining_live
                / ADMIN_TOTAL_TIME_SECONDS,
            )
        )

        st.info(
            f"⏱️ Total interview time remaining: "
            f"**{total_minutes:02d}:{total_seconds:02d}**"
        )

        if question_remaining_live <= 20:
            st.error(
                f"⏳ Question time: "
                f"**{question_minutes:02d}:{question_seconds:02d}**"
            )
        elif question_remaining_live <= 60:
            st.warning(
                f"⏳ Question time: "
                f"**{question_minutes:02d}:{question_seconds:02d}**"
            )
        else:
            st.success(
                f"⏱️ Question time: "
                f"**{question_minutes:02d}:{question_seconds:02d}**"
            )

        st.progress(
            min(
                1.0,
                question_remaining_live
                / ADMIN_QUESTION_TIME_SECONDS,
            )
        )

        # Full-app rerun is needed only when a timer actually expires.
        # The outer section will then process timeout and move next.
        if (
            total_remaining_live <= 0
            or question_remaining_live <= 0
        ):
            st.rerun()

    topic_timer_refresh()

    # --------------------------------------------------------
    # QUESTION HEADER
    # --------------------------------------------------------

    question_number = int(
        st.session_state.topic_question_number or 1
    )

    st.subheader(
        f"Question {question_number}/{ADMIN_MAX_QUESTIONS}"
    )

    # --------------------------------------------------------
    # QUESTION
    # --------------------------------------------------------

    question_text = clean_question_text(
        st.session_state.topic_question
    )

    if not is_question_topic_valid(
        topic,
        question_text,
    ):
        st.error(
            "This question does not match the selected topic. "
            "Please restart after fixing backend topic validation."
        )
        st.stop()

    # IMPORTANT:
    # Do not inject a custom HTML/CSS card here.
    # Streamlit was showing the backend's HTML/CSS wrapper as text.
    # Render only the clean question text.
    st.markdown(
        f"### {question_text}"
    )

    # --------------------------------------------------------
    # ANSWER
    # --------------------------------------------------------

    # --------------------------------------------------------
    # SAME VOICE COMPONENT USED BY MOCK INTERVIEW
    # --------------------------------------------------------
    # This reuses the existing working answer_bridge component.
    # It automatically speaks the question, provides Start Answer,
    # End Answer, Edit Answer, Next Question and Skip, and sends
    # the final edited answer back to Streamlit.
    voice_event = get_candidate_answer(
        question_text,
        skip_enabled=True,
    )

    answer = st.session_state.topic_candidate_answer
    next_clicked = False
    skip_clicked = False

    if voice_event:
        voice_event = str(voice_event).strip()

        # Skip event from the same mock-interview voice component.
        if voice_event.startswith("__SKIP__:"):
            event_id = voice_event.split(":", 1)[1].strip()

            if event_id != st.session_state.topic_last_event:
                st.session_state.topic_last_event = event_id
                skip_clicked = True

        # Final edited answer from the same mock-interview voice component.
        elif voice_event.startswith("__SUBMIT__:"):
            parts = voice_event.split(":", 2)

            if len(parts) >= 3:
                event_id = parts[1].strip()
                submitted_answer = parts[2].strip()

                if event_id != st.session_state.topic_last_event:
                    st.session_state.topic_last_event = event_id
                    st.session_state.topic_candidate_answer = submitted_answer
                    answer = submitted_answer
                    next_clicked = True

        else:
            # Keep compatibility if the existing bridge returns plain text.
            st.session_state.topic_candidate_answer = voice_event
            answer = voice_event

    # --------------------------------------------------------
    # SKIP
    # --------------------------------------------------------

    if skip_clicked:

        current_question = (
            st.session_state.topic_question
        )

        current_question_id = (
            st.session_state.topic_question_id
        )

        try:
            evaluation = api_evaluate_topic_answer(
                session_id=session_id,
                question_id=current_question_id,
                candidate_answer="",
            )
        except Exception:
            evaluation = {}

        try:
            score = float(
                evaluation.get("score", 0)
            )
        except (TypeError, ValueError):
            score = 0.0

        feedback = str(
            evaluation.get(
                "feedback",
                "Question skipped by candidate.",
            )
        ).strip()

        missing_concepts = clean_api_list(
            evaluation.get("missing_concepts", [])
        )

        extracted_concepts = clean_api_list(
            evaluation.get("extracted_concepts", [])
        )

        already_recorded = any(
            str(record.get("question_id", "")) == str(current_question_id)
            for record in st.session_state.topic_history
            if isinstance(record, dict)
        )

        if not already_recorded:
            st.session_state.topic_history.append(
                {
                    "question": current_question,
                    "candidate_answer": "Skipped",
                    "score": 0.0,
                    "feedback": feedback,
                    "missing_concepts": missing_concepts,
                    "extracted_concepts": extracted_concepts,
                    "question_id": current_question_id,
                }
            )

        # Skip immediately moves to the next question.
        if (
            question_number >= ADMIN_MAX_QUESTIONS
            or int(time.time()) >= total_expires_at
        ):
            finish_topic_interview()
            st.rerun()

        try:
            next_question = api_get_topic_question(
                session_id,
                "",
            )
        except requests.RequestException as error:
            st.error(
                f"Next question generation failed: {error}"
            )
            st.stop()

        next_question_text = clean_question_text(
            next_question.get("question", "")
        )

        if not is_question_topic_valid(
            topic,
            next_question_text,
        ):
            st.error(
                "Backend generated a question outside the selected topic."
            )
            st.stop()

        st.session_state.topic_question = next_question_text

        st.session_state.topic_question_id = (
            next_question.get("question_id", "")
        )

        st.session_state.topic_question_number = (
            next_question.get(
                "question_number",
                question_number + 1,
            )
        )

        st.session_state.topic_question_started_at = int(
            time.time()
        )

        st.session_state.topic_candidate_answer = ""

        st.rerun()

    # --------------------------------------------------------
    # NEXT QUESTION
    # --------------------------------------------------------

    if next_clicked:

        submitted_answer = answer.strip()

        if not submitted_answer:
            st.warning(
                "Please enter an answer or click Skip."
            )
            st.stop()

        try:
            evaluation = api_evaluate_topic_answer(
                session_id=session_id,
                question_id=(
                    st.session_state.topic_question_id
                ),
                candidate_answer=submitted_answer,
            )
        except requests.HTTPError as error:

            detail = "Answer evaluation failed."

            if error.response is not None:
                try:
                    detail = (
                        error.response.json().get(
                            "detail",
                            detail,
                        )
                    )
                except Exception:
                    pass

            st.error(detail)
            st.stop()

        except requests.RequestException as error:
            st.error(
                f"Answer evaluation failed: {error}"
            )
            st.stop()

        try:
            score = float(
                evaluation.get("score", 0)
            )
        except (TypeError, ValueError):
            score = 0.0

        score = max(0.0, min(10.0, score))

        feedback = str(
            evaluation.get("feedback", "")
        ).strip()

        missing_concepts = clean_api_list(
            evaluation.get("missing_concepts", [])
        )

        extracted_concepts = clean_api_list(
            evaluation.get("extracted_concepts", [])
        )

        current_question_id = (
            st.session_state.topic_question_id
        )

        already_recorded = any(
            str(record.get("question_id", "")) == str(current_question_id)
            for record in st.session_state.topic_history
            if isinstance(record, dict)
        )

        if not already_recorded:
            st.session_state.topic_history.append(
                {
                    "question": (
                        st.session_state.topic_question
                    ),
                    "candidate_answer": submitted_answer,
                    "score": score,
                    "feedback": feedback,
                    "missing_concepts": missing_concepts,
                    "extracted_concepts": extracted_concepts,
                    "question_id": current_question_id,
                }
            )

        # Question 15 or total time -> final report.
        if (
            question_number >= ADMIN_MAX_QUESTIONS
            or int(time.time()) >= total_expires_at
        ):
            finish_topic_interview()
            st.rerun()

        try:
            next_question = api_get_topic_question(
                session_id,
                submitted_answer,
            )
        except requests.RequestException as error:
            st.error(
                f"Next question generation failed: {error}"
            )
            st.stop()

        next_question_text = clean_question_text(
            next_question.get("question", "")
        )

        if not is_question_topic_valid(
            topic,
            next_question_text,
        ):
            st.error(
                "Backend generated a question outside the selected topic."
            )
            st.stop()

        st.session_state.topic_question = next_question_text

        st.session_state.topic_question_id = (
            next_question.get("question_id", "")
        )

        st.session_state.topic_question_number = (
            next_question.get(
                "question_number",
                question_number + 1,
            )
        )

        st.session_state.topic_question_started_at = int(
            time.time()
        )

        st.session_state.topic_candidate_answer = ""

        st.rerun()

    st.stop()

st.stop()
