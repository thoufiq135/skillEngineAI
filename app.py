import streamlit as st
import requests
import json
import time
import re

from resume_parser import extract_text
from answer_bridge import get_candidate_answer
from voice_answer_component import voice_answer_component


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Adaptive Mock Interview",
    layout="wide",
)


# ============================================================
# FASTAPI CONNECTION
# ============================================================

API_URL = "http://127.0.0.1:8000"
API_TIMEOUT = 300

# Existing Resume Interview
MAX_QUESTIONS = 5

# Admin / Topic Interview
ADMIN_MAX_QUESTIONS = 15
ADMIN_TOTAL_TIME_SECONDS = 30 * 60
ADMIN_QUESTION_TIME_SECONDS = 2 * 60


# ============================================================
# GENERIC API HELPERS
# ============================================================

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

    print("API STATUS:", response.status_code)

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


# ============================================================
# OLD RESUME INTERVIEW API
# ============================================================

def api_analyze_resume(file_path):

    with open(file_path, "rb") as file:

        response = requests.post(
            f"{API_URL}/analyze-resume",
            files={
                "file": (
                    file_path,
                    file,
                    "application/pdf"
                    if file_path.lower().endswith(".pdf")
                    else (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                )
            },
            timeout=API_TIMEOUT,
        )

    response.raise_for_status()

    return response.json()


def api_generate_question(current_state):

    result = api_post_json(
        "/generate-question",
        {
            "current_skill": current_state.get(
                "current_skill",
                "",
            ),
            "question_type": current_state.get(
                "question_type",
                "basic",
            ),
            "concept": (
                current_state.get(
                    "extracted_concepts",
                    [""],
                )[0]
                if current_state.get(
                    "extracted_concepts"
                )
                else ""
            ),
        },
    )

    current_state["current_question_id"] = result.get(
        "question_id",
        "",
    )

    return result


def api_evaluate_answer(
    current_state,
    candidate_answer,
):

    return api_post_json(
        "/evaluate-answer",
        {
            "current_skill": current_state.get(
                "current_skill",
                "",
            ),
            "question": current_state.get(
                "current_question",
                "",
            ),
            "candidate_answer": candidate_answer,
            "question_id": current_state.get(
                "current_question_id",
                "",
            ),
        },
    )


def api_process_self_intro(
    self_intro,
    resume_skills,
):

    return api_post_json(
        "/process-self-intro",
        {
            "self_intro": self_intro,
            "resume_skills": resume_skills,
        },
    )


def api_save_interview(
    final_result,
    token,
):

    return api_post_json(
        "/interviews",
        final_result,
        token=token,
    )


# ============================================================
# AUTH API
# ============================================================

def api_login(
    email,
    password,
):

    return api_post_json(
        "/login",
        {
            "email": email,
            "password": password,
        },
    )


def api_register(
    full_name,
    email,
    password,
):

    return api_post_json(
        "/register",
        {
            "fullName": full_name,
            "email": email,
            "password": password,
            "phone": "",
            "currentRole": "",
            "experienceYears": 0,
            "educationLevel": "",
            "careerGoal": "",
            "interests": [],
            "learningGoals": "",
        },
    )


# ============================================================
# ADMIN / TOPIC INTERVIEW API
# ============================================================

def api_start_topic_interview(
    topic,
    level,
    previous_questions=None,
    question_number=0,
    last_candidate_answer="",
    next_question_type="basic",
):
    
    token = st.session_state.get("auth_token")
    print("AUTH TOKEN EXISTS:", bool(token))

    return api_post_json(
    "/interview/start",
    {
        "topic": topic,
        "level": level,
        "previous_questions": previous_questions or [],
        "question_number": question_number,
        "last_candidate_answer": last_candidate_answer,
        "next_question_type": next_question_type,
    },
    token=token,
    )


def api_get_topic_question(
    session_id,
    candidate_answer="",
):

    payload = {
        "session_id": session_id,
        "candidate_answer": candidate_answer,
    }

    try:
        return api_post_json(
            "/interview/question",
            payload,
        )
    except requests.HTTPError as error:
        response = error.response
        if response is None or response.status_code != 404:
            raise

        try:
            detail = response.json().get("detail", "")
        except (ValueError, AttributeError):
            detail = ""

        if detail != "Interview session not found":
            raise

        topic = st.session_state.get("topic_name", "")
        level = st.session_state.get("topic_level", "")
        if not topic or not level:
            raise

        previous_questions = [
            str(record.get("question", "")).strip()
            for record in st.session_state.get("topic_history", [])
            if isinstance(record, dict) and record.get("question")
        ]
        current_question_number = int(
            st.session_state.get("topic_question_number", 0) or 0
        )

        recovered_session = api_start_topic_interview(
            topic,
            level,
            previous_questions=previous_questions,
            question_number=current_question_number,
            last_candidate_answer=candidate_answer,
        )
        recovered_session_id = recovered_session.get("session_id", "")
        if not recovered_session_id:
            raise requests.RequestException(
                "Backend did not return a replacement interview session."
            )

        st.session_state.topic_session_id = recovered_session_id
        return api_post_json(
            "/interview/question",
            {
                "session_id": recovered_session_id,
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


# ============================================================
# TOPIC NORMALIZATION
# ============================================================

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


# ============================================================
# QUESTION TEXT CLEANING
# ============================================================

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


# ============================================================
# QUESTION TOPIC SAFETY
# ============================================================

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


# ============================================================
# CLEAN LIST
# ============================================================

def clean_api_list(value):

    if not isinstance(value, list):

        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


# ============================================================
# SKILL-WISE RATING
# ============================================================

def calculate_skill_ratings(history):

    skill_scores = {}

    if not isinstance(history, list):

        return {}

    for record in history:

        if not isinstance(record, dict):

            continue

        skill = str(
            record.get(
                "skill",
                "",
            )
        ).strip()

        if not skill:

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

        if skill not in skill_scores:

            skill_scores[skill] = []

        skill_scores[skill].append(score)

    skill_ratings = {}

    for skill, scores in skill_scores.items():

        if scores:

            skill_ratings[skill] = round(
                sum(scores) / len(scores),
                1,
            )

        else:

            skill_ratings[skill] = 0.0

    return skill_ratings


# ============================================================
# ROLE DETERMINATION
# ============================================================

def determine_roles(
    skills,
    skill_ratings,
    overall_score,
):

    skills = clean_api_list(
        skills
    )

    normalized_skills = [
        skill.lower().strip()
        for skill in skills
    ]

    strong_skills = []

    for skill, rating in skill_ratings.items():

        try:

            numeric_rating = float(
                rating
            )

        except (
            TypeError,
            ValueError,
        ):

            numeric_rating = 0

        if numeric_rating >= 7:

            strong_skills.append(
                skill.lower().strip()
            )

    role_signals = {

        "UI/UX Designer": [
            "figma",
            "framer",
            "canva",
            "sketch",
            "adobe illustrator",
            "illustrator",
            "photoshop",
            "wireframing",
            "prototyping",
            "user research",
            "user flows",
            "information architecture",
            "ui/ux",
            "ui ux",
            "user interface",
            "ux design",
            "ui design",
        ],

        "Data Analyst": [
            "python",
            "sql",
            "pandas",
            "numpy",
            "excel",
            "power bi",
            "tableau",
            "data analysis",
            "data analytics",
            "statistics",
            "eda",
            "exploratory data analysis",
        ],

        "Python Developer": [
            "python",
            "fastapi",
            "flask",
            "django",
            "api",
            "rest api",
            "sql",
            "oop",
            "object oriented programming",
        ],

        "Software Developer": [
            "c",
            "c++",
            "java",
            "python",
            "javascript",
            "html",
            "css",
            "sql",
            "oop",
            "dsa",
            "data structures",
            "algorithms",
        ],

        "QA / Testing Engineer": [
            "testing",
            "manual testing",
            "automation testing",
            "selenium",
            "test cases",
            "test case",
            "debugging",
            "quality assurance",
            "qa",
            "api testing",
        ],

        "Embedded / Firmware Engineer": [
            "embedded",
            "embedded c",
            "firmware",
            "microcontroller",
            "microcontrollers",
            "arduino",
            "stm32",
            "esp32",
            "embedded systems",
            "electronics",
            "iot",
        ],
    }

    role_scores = {}

    for role, signals in role_signals.items():

        resume_matches = 0
        strong_matches = 0

        for signal in signals:

            if any(
                signal == skill
                or signal in skill
                or skill in signal
                for skill in normalized_skills
            ):

                resume_matches += 1

            if any(
                signal == skill
                or signal in skill
                or skill in signal
                for skill in strong_skills
            ):

                strong_matches += 1

        role_score = (
            resume_matches * 2
            + strong_matches * 3
        )

        if (
            overall_score >= 7
            and strong_matches > 0
        ):

            role_score += 1

        role_scores[role] = role_score

    ranked_roles = sorted(
        role_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    roles_with_score = [
        role
        for role, score in ranked_roles
        if score > 0
    ]

    if not roles_with_score:

        return (
            "Entry-Level Technical Role",
            [
                "Associate Software Engineer",
                "Junior QA Engineer",
                "Technical Support Engineer",
            ],
        )

    best_match_role = roles_with_score[0]

    future_roles = []

    for role in roles_with_score[1:]:

        if role != best_match_role:

            future_roles.append(
                role
            )

        if len(future_roles) >= 3:

            break

    return (
        best_match_role,
        future_roles,
    )


# ============================================================
# TOPIC INTERVIEW FINAL REPORT
# ============================================================

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


# ============================================================
# RESET TOPIC INTERVIEW
# ============================================================

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


# ============================================================
# FINISH TOPIC INTERVIEW
# ============================================================

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
# SESSION DEFAULTS
# ============================================================

DEFAULTS = {

    "auth_token": None,

    "current_user": None,

    "browser_state": {},

    "auth_mode": "login",

    # Existing Resume Interview
    "interview_started": False,

    "resume_text": "",

    "question": "",

    "candidate_answer": "",

    "interview_state": None,

    "interview_finished": False,

    "last_processed_skip_event": None,

    "last_processed_answer_event": None,

    "interview_result_saved": False,

    "self_intro_stage": False,

    "self_intro_question": "Tell me about yourself.",

    "self_intro_answer": "",

    "self_intro_completed": False,

    "resume_skills": [],

    "self_intro_skills": [],

    "question_id": "",

    # Admin / Topic Interview
    "interview_mode": "Resume Interview",

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


for key, value in DEFAULTS.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# BROWSER STATE
# ============================================================

def get_browser_state():

    return st.session_state.get(
        "browser_state",
        {},
    )


def set_browser_state(
    key,
    value,
):

    browser_state = st.session_state.get(
        "browser_state",
        {},
    )

    browser_state[key] = value

    st.session_state.browser_state = (
        browser_state
    )


# ============================================================
# AUTHENTICATION
# ============================================================

if not st.session_state.auth_token:

    st.markdown(
        """
        <style>
        .auth-hero {
            text-align: center;
            padding: 55px 20px 20px;
        }

        .auth-hero .icon {
            font-size: 52px;
        }

        .auth-hero h1 {
            font-size: 2.35rem;
            font-weight: 800;
            color: #111827;
            margin: 8px 0 4px;
        }

        .auth-hero p {
            color: #6b7280;
            font-size: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="auth-hero">
            <div class="icon">🎯</div>
            <h1>Adaptive Mock Interview</h1>
            <p>Login to start your interview.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(
        [
            "🔐 Login",
            "📝 Register",
        ]
    )

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with login_tab:

        with st.form(
            "login_form"
        ):

            email = st.text_input(
                "Email"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            login_clicked = (
                st.form_submit_button(
                    "Login",
                    use_container_width=True,
                )
            )

        if login_clicked:

            if (
                not email.strip()
                or not password
            ):

                st.error(
                    "Please enter email and password."
                )

            else:

                try:

                    result = api_login(
                        email.strip(),
                        password,
                    )

                    st.session_state.auth_token = (
                        result.get("token")
                    )

                    st.session_state.current_user = (
                        result.get("user")
                    )

                    st.success(
                        "Login successful."
                    )

                    st.rerun()

                except requests.HTTPError as error:

                    detail = (
                        "Login failed. "
                        "Please check your email and password."
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

                except requests.RequestException as error:

                    st.error(
                        f"FastAPI connection failed: {error}"
                    )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    with register_tab:

        with st.form(
            "register_form"
        ):

            full_name = st.text_input(
                "Full Name"
            )

            register_email = st.text_input(
                "Email"
            )

            register_password = st.text_input(
                "Password",
                type="password",
            )

            register_clicked = (
                st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                )
            )

        if register_clicked:

            if (
                not full_name.strip()
                or not register_email.strip()
                or not register_password
            ):

                st.error(
                    "Please fill all required fields."
                )

            else:

                try:

                    result = api_register(
                        full_name.strip(),
                        register_email.strip(),
                        register_password,
                    )

                    st.session_state.auth_token = (
                        result.get("token")
                    )

                    st.session_state.current_user = (
                        result.get("user")
                    )

                    st.success(
                        "Account created successfully."
                    )

                    st.rerun()

                except requests.HTTPError as error:

                    detail = (
                        "Registration failed."
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

                except requests.RequestException as error:

                    st.error(
                        f"FastAPI connection failed: {error}"
                    )

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    user = (
        st.session_state.current_user
        or {}
    )

    st.markdown(
        "### 👤 Account"
    )

    st.write(
        user.get(
            "name",
            "User",
        )
    )

    st.caption(
        user.get(
            "email",
            "",
        )
    )

    st.divider()

    st.markdown(
        "### 🎤 Interview Type"
    )

    interview_mode = st.radio(
        "Choose interview mode",
        [
            "Resume Interview",
            "Topic Interview",
        ],
        index=(
            0
            if st.session_state.interview_mode
            == "Resume Interview"
            else 1
        ),
        disabled=(
            st.session_state.interview_started
            or st.session_state.topic_interview_active
            or st.session_state.self_intro_stage
        ),
    )

    st.session_state.interview_mode = (
        interview_mode
    )

    st.divider()

    if st.button(
        "Logout",
        use_container_width=True,
    ):

        for key, value in DEFAULTS.items():

            st.session_state[key] = value

        st.rerun()


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


# ============================================================
# TOPIC INTERVIEW SETUP
# ============================================================

if (
    st.session_state.interview_mode
    == "Topic Interview"
    and not st.session_state.topic_interview_active
):

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


# ============================================================
# TOPIC INTERVIEW RUNNING
# ============================================================

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
    # VOICE + EDITABLE ANSWER
    # --------------------------------------------------------
    # The browser reads the question aloud using SpeechSynthesis.
    # The candidate can answer through the microphone using the
    # browser SpeechRecognition API. The transcript appears in an
    # editable textarea, so the candidate can correct it before
    # clicking Next Question.
    voice_result = voice_answer_component(
        question_text,
        st.session_state.topic_candidate_answer,
        key=f"voice_answer_{st.session_state.topic_question_id}",
    )

    if isinstance(voice_result, dict):
        st.session_state.topic_candidate_answer = str(
            voice_result.get(
                "text",
                st.session_state.topic_candidate_answer,
            )
            or ""
        )
    elif voice_result is not None:
        st.session_state.topic_candidate_answer = str(voice_result)

    answer = st.session_state.topic_candidate_answer

    # --------------------------------------------------------
    # BUTTONS
    # --------------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:
        next_clicked = st.button(
            "➡️ Next Question",
            use_container_width=True,
        )

    with col2:
        skip_clicked = st.button(
            "⏭️ Skip",
            use_container_width=True,
        )

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
        except requests.HTTPError as error:
            detail = "Question skip failed."
            if error.response is not None:
                try:
                    detail = error.response.json().get(
                        "detail",
                        detail,
                    )
                except Exception:
                    pass
            st.error(detail)
            st.stop()
        except requests.RequestException as error:
            st.error(f"Question skip failed: {error}")
            st.stop()

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


# ============================================================
# RESUME INTERVIEW RESULT PAGE
# ============================================================

if st.session_state.interview_finished:

    final_state = (
        st.session_state.interview_state
        or {}
    )

    st.title(
        "🎯 Interview Result"
    )

    history = final_state.get(
        "interview_history",
        [],
    )

    if history:

        scores = []

        for record in history:

            try:

                scores.append(
                    float(
                        record.get(
                            "score",
                            0,
                        )
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

        if scores:

            overall_score = round(
                sum(scores) / len(scores),
                1,
            )

        else:

            overall_score = 0

    else:

        overall_score = 0

    st.subheader(
        f"⭐ Overall Score: {overall_score}/10"
    )

    skill_ratings = calculate_skill_ratings(
        history
    )

    final_state["skill_ratings"] = (
        skill_ratings
    )

    strong_skills = []

    improvement_skills = []

    for skill, rating in skill_ratings.items():

        try:

            numeric_rating = float(
                rating
            )

        except (
            TypeError,
            ValueError,
        ):

            numeric_rating = 0

        if numeric_rating >= 7:

            strong_skills.append(
                skill
            )

        else:

            improvement_skills.append(
                skill
            )

    st.subheader(
        "💪 Strong Skills"
    )

    if strong_skills:

        st.write(
            ", ".join(
                strong_skills
            )
        )

    else:

        st.write(
            "No strong skills identified."
        )

    st.subheader(
        "📚 Skills to Improve"
    )

    if improvement_skills:

        st.write(
            ", ".join(
                improvement_skills
            )
        )

    else:

        st.write(
            "No immediate improvement areas identified."
        )

    resume_skills = clean_api_list(
        final_state.get(
            "skills",
            [],
        )
    )

    best_match_role, future_roles = determine_roles(
        resume_skills,
        skill_ratings,
        overall_score,
    )

    final_state["best_match_role"] = (
        best_match_role
    )

    final_state["future_roles"] = (
        future_roles
    )

    st.subheader(
        "💼 Suitable Role"
    )

    st.success(
        f"🎯 **Best Match Role: {best_match_role}**"
    )

    st.subheader(
        "🚀 Other Suitable Roles"
    )

    if future_roles:

        for role in future_roles:

            st.write(
                f"• {role}"
            )

    else:

        st.write(
            "No additional roles identified."
        )

    final_result = {

        "overallScore": overall_score,

        "skillRatings": skill_ratings,

        "questionsAnswered": len(history),

        "skills": resume_skills,

        "strongSkills": clean_api_list(
            strong_skills
        ),

        "skillsToImprove": clean_api_list(
            improvement_skills
        ),

        "bestMatchRole": best_match_role,

        "futureRoles": future_roles,

        "interviewHistory": history,
    }

    if not st.session_state.interview_result_saved:

        try:

            save_result = api_save_interview(
                final_result,
                st.session_state.auth_token,
            )

            if save_result.get(
                "status"
            ) == "success":

                st.session_state.interview_result_saved = (
                    True
                )

                st.success(
                    "✅ Interview result saved successfully."
                )

            else:

                st.warning(
                    "Interview completed, "
                    "but the result was not saved."
                )

        except requests.HTTPError as error:

            if error.response is not None:

                st.error(
                    f"API response: {error.response.text}"
                )

            if (
                error.response is not None
                and error.response.status_code
                in (
                    401,
                    403,
                )
            ):

                st.error(
                    "Your login session expired. "
                    "Please logout and login again."
                )

            else:

                st.error(
                    f"Interview result save failed: {error}"
                )

        except requests.RequestException as error:

            st.error(
                f"Interview result save failed: {error}"
            )

    st.subheader(
        "📊 Skill-wise Ratings"
    )

    if skill_ratings:

        for skill, rating in skill_ratings.items():

            st.write(
                f"**{skill}: {rating}/10**"
            )

    else:

        st.write(
            "No skill ratings available."
        )

    st.subheader(
        "📝 Interview Details"
    )

    for record in history:

        st.markdown(
            f"### Question "
            f"{record.get('question_number', '')}"
        )

        st.write(
            f"**Skill:** "
            f"{record.get('skill', '')}"
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
            f"**Expected Answer:** "
            f"{record.get('expected_answer', '')}"
        )

        st.write(
            f"**Score:** "
            f"{record.get('score', 0)}/10"
        )

        st.write(
            f"**Feedback:** "
            f"{record.get('feedback', '')}"
        )

        if record.get(
            "missing_concepts"
        ):

            st.write(
                "**Missing Concepts:** "
                + ", ".join(
                    record.get(
                        "missing_concepts",
                        [],
                    )
                )
            )

        st.divider()

    if st.button(
        "🔄 Start New Resume Interview"
    ):

        st.session_state.interview_started = False

        st.session_state.interview_finished = False

        st.session_state.resume_text = ""

        st.session_state.question = ""

        st.session_state.candidate_answer = ""

        st.session_state.interview_state = None

        st.session_state.last_processed_skip_event = None

        st.session_state.last_processed_answer_event = None

        st.session_state.interview_result_saved = False

        st.session_state.self_intro_stage = False

        st.session_state.self_intro_completed = False

        st.session_state.resume_skills = []

        st.session_state.self_intro_skills = []

        st.session_state.question_id = ""

        st.rerun()

    st.stop()


# ============================================================
# EXISTING RESUME INTERVIEW
# ============================================================

if (
    st.session_state.interview_mode
    == "Resume Interview"
    and st.session_state.interview_started
):

    st.title(
        "🎤 Adaptive Mock Interview"
    )

    current_state = (
        st.session_state.interview_state
    )

    if current_state is not None:

        st.write(
            f"**Question "
            f"{current_state.get('question_count', 0) + 1}"
            f"/{MAX_QUESTIONS}**"
        )

    candidate_answer = get_candidate_answer(
        st.session_state.question
    )

    if candidate_answer:

        candidate_answer = (
            candidate_answer.strip()
        )

        # ====================================================
        # SKIP
        # ====================================================

        if candidate_answer.startswith(
            "__SKIP__:"
        ):

            skip_event_id = (
                candidate_answer
                .split(
                    ":",
                    1,
                )[1]
                .strip()
            )

            if (
                skip_event_id
                == st.session_state.last_processed_skip_event
            ):

                st.stop()

            st.session_state.last_processed_skip_event = (
                skip_event_id
            )

            current_skill = current_state.get(
                "current_skill",
                "",
            )

            current_question = current_state.get(
                "current_question",
                "",
            )

            question_number = (
                current_state.get(
                    "question_count",
                    0,
                )
                + 1
            )

            interview_history = list(
                current_state.get(
                    "interview_history",
                    [],
                )
            )

            interview_history.append(
                {
                    "question_number": question_number,

                    "skill": current_skill,

                    "question": current_question,

                    "candidate_answer": "Skipped",

                    "score": 0,

                    "feedback": (
                        "Question skipped by candidate."
                    ),

                    "expected_answer": current_state.get(
                        "current_expected_answer",
                        "",
                    ),

                    "missing_concepts": [],

                    "extracted_concepts": [],
                }
            )

            skill_ratings = calculate_skill_ratings(
                interview_history
            )

            current_state["question_count"] = (
                current_state.get(
                    "question_count",
                    0,
                )
                + 1
            )

            current_state["interview_history"] = (
                interview_history
            )

            current_state["skill_ratings"] = (
                skill_ratings
            )

            if (
                current_state["question_count"]
                >= MAX_QUESTIONS
            ):

                st.session_state.interview_state = (
                    dict(current_state)
                )

                st.session_state.question = ""

                st.session_state.candidate_answer = ""

                st.session_state.interview_finished = True

                st.session_state.interview_started = False

                st.rerun()

            skills = current_state.get(
                "skills",
                [],
            )

            if not skills:

                st.error(
                    "No technical skills are available for the next question."
                )

                st.stop()

            next_skill_index = (
                current_state.get(
                    "skill_index",
                    0,
                )
                + 1
            ) % len(skills)

            current_state["skill_index"] = (
                next_skill_index
            )

            current_state["current_skill"] = (
                skills[next_skill_index]
            )

            current_state["question_type"] = (
                "basic"
            )

            current_state["extracted_concepts"] = []

            try:

                next_question_result = (
                    api_generate_question(
                        current_state
                    )
                )

            except requests.RequestException as error:

                st.error(
                    f"FastAPI question generation failed: {error}"
                )

                st.stop()

            current_state["current_question"] = (
                next_question_result.get(
                    "question",
                    "",
                )
            )

            current_state["current_expected_answer"] = ""

            st.session_state.interview_state = (
                current_state
            )

            st.session_state.question = (
                current_state["current_question"]
            )

            st.session_state.candidate_answer = ""

            st.rerun()

        # ====================================================
        # NORMAL ANSWER
        # ====================================================

        if candidate_answer.startswith(
            "__SUBMIT__:"
        ):

            payload = candidate_answer.split(
                ":",
                2,
            )

            if len(payload) < 3:

                st.stop()

            submit_event_id = payload[1].strip()

            submitted_answer = payload[2].strip()

            if (
                submit_event_id
                == st.session_state.last_processed_answer_event
            ):

                st.stop()

            if not submitted_answer:

                st.stop()

            st.session_state.last_processed_answer_event = (
                submit_event_id
            )

            current_state["candidate_answer"] = (
                submitted_answer
            )

            try:

                evaluation = api_evaluate_answer(
                    current_state,
                    submitted_answer,
                )

            except requests.RequestException as error:

                st.error(
                    f"FastAPI answer evaluation failed: {error}"
                )

                st.stop()

            score = evaluation.get(
                "score",
                0,
            )

            try:

                score = float(score)

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

            feedback = str(
                evaluation.get(
                    "feedback",
                    "",
                )
            ).strip()

            missing_concepts = clean_api_list(
                evaluation.get(
                    "missing_concepts",
                    [],
                )
            )

            extracted_concepts = clean_api_list(
                evaluation.get(
                    "extracted_concepts",
                    [],
                )
            )

            current_state["current_score"] = score

            current_state["missing_concepts"] = (
                missing_concepts
            )

            current_state["extracted_concepts"] = (
                extracted_concepts
            )

            history = list(
                current_state.get(
                    "interview_history",
                    [],
                )
            )

            question_number = (
                current_state.get(
                    "question_count",
                    0,
                )
                + 1
            )

            history.append(
                {
                    "question_number": question_number,

                    "skill": current_state.get(
                        "current_skill",
                        "",
                    ),

                    "question": current_state.get(
                        "current_question",
                        "",
                    ),

                    "candidate_answer": submitted_answer,

                    "score": score,

                    "feedback": feedback,

                    "expected_answer": current_state.get(
                        "current_expected_answer",
                        "",
                    ),

                    "missing_concepts": missing_concepts,

                    "extracted_concepts": extracted_concepts,
                }
            )

            current_state["interview_history"] = (
                history
            )

            skill_ratings = calculate_skill_ratings(
                history
            )

            current_state["skill_ratings"] = (
                skill_ratings
            )

            current_state["question_count"] = (
                current_state.get(
                    "question_count",
                    0,
                )
                + 1
            )

            if (
                current_state["question_count"]
                >= MAX_QUESTIONS
            ):

                st.session_state.interview_state = (
                    dict(current_state)
                )

                st.session_state.interview_finished = True

                st.session_state.interview_started = False

                st.session_state.question = ""

                st.session_state.candidate_answer = ""

                st.rerun()

            if score > 6:

                current_state["question_type"] = (
                    "concept_follow_up"
                    if extracted_concepts
                    else "skill_deep"
                )

            else:

                skills = current_state.get(
                    "skills",
                    [],
                )

                if skills:

                    next_skill_index = (
                        current_state.get(
                            "skill_index",
                            0,
                        )
                        + 1
                    ) % len(skills)

                    current_state["skill_index"] = (
                        next_skill_index
                    )

                    current_state["current_skill"] = (
                        skills[next_skill_index]
                    )

                current_state["question_type"] = (
                    "basic"
                )

                current_state["extracted_concepts"] = []

            try:

                next_question_result = (
                    api_generate_question(
                        current_state
                    )
                )

            except requests.RequestException as error:

                st.error(
                    f"FastAPI question generation failed: {error}"
                )

                st.stop()

            current_state["current_question"] = (
                next_question_result.get(
                    "question",
                    "",
                )
            )

            current_state["current_expected_answer"] = ""

            st.session_state.interview_state = (
                current_state
            )

            st.session_state.question = (
                current_state["current_question"]
            )

            st.session_state.candidate_answer = ""

            st.rerun()

    st.stop()


# ============================================================
# RESUME INTERVIEW LANDING PAGE
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background: #f5f7fb;
    }

    .upload-hero {
        text-align: center;
        padding: 42px 20px 24px;
    }

    .upload-hero .icon {
        font-size: 52px;
        margin-bottom: 8px;
    }

    .upload-hero h1 {
        font-size: 2.35rem;
        font-weight: 800;
        margin: 0;
        color: #111827;
    }

    .upload-hero p {
        color: #6b7280;
        font-size: 1.05rem;
        margin-top: 10px;
    }

    .upload-card {
        max-width: 820px;
        margin: 10px auto 24px;
        padding: 30px 34px;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 22px;
        box-shadow: 0 14px 35px rgba(15, 23, 42, .08);
    }

    .upload-card-title {
        text-align: center;
        font-size: 1.2rem;
        font-weight: 750;
        color: #111827;
        margin-bottom: 6px;
    }

    .upload-card-subtitle {
        text-align: center;
        color: #6b7280;
        font-size: .92rem;
        margin-bottom: 20px;
    }

    .upload-features {
        max-width: 820px;
        margin: 0 auto 28px;
        display: flex;
        gap: 14px;
        justify-content: center;
        flex-wrap: wrap;
    }

    .feature {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 13px 18px;
        color: #374151;
        font-size: .9rem;
        box-shadow: 0 5px 15px rgba(15, 23, 42, .04);
    }

    .start-note {
        text-align: center;
        color: #6b7280;
        font-size: .82rem;
        margin-top: 10px;
    }

    div[data-testid="stFileUploader"] {
        border: 2px dashed #cbd5e1;
        border-radius: 16px;
        padding: 8px;
        background: #f8fafc;
    }

    div[data-testid="stFileUploader"]:hover {
        border-color: #2563eb;
        background: #eff6ff;
    }

    div[data-testid="stButton"] > button {
        border-radius: 12px;
        min-height: 46px;
        font-weight: 700;
        transition: all .15s ease;
    }

    div[data-testid="stButton"] > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 20px rgba(15, 23, 42, .12);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SELF INTRODUCTION PAGE
# ============================================================

if (
    st.session_state.self_intro_stage
    and not st.session_state.self_intro_completed
):

    st.title(
        "🎤 Self Introduction"
    )

    st.write(
        "Please introduce yourself briefly before the technical interview."
    )

    self_intro_answer = get_candidate_answer(
        st.session_state.self_intro_question
    )

    if self_intro_answer:

        self_intro_answer = (
            self_intro_answer.strip()
        )

        if self_intro_answer.startswith(
            "__SUBMIT__:"
        ):

            payload = self_intro_answer.split(
                ":",
                2,
            )

            if len(payload) >= 3:

                submit_event_id = (
                    payload[1].strip()
                )

                submitted_intro = (
                    payload[2].strip()
                )

                if (
                    submit_event_id
                    != st.session_state.last_processed_answer_event
                    and submitted_intro
                ):

                    st.session_state.last_processed_answer_event = (
                        submit_event_id
                    )

                    try:

                        intro_result = (
                            api_process_self_intro(
                                submitted_intro,
                                st.session_state.resume_skills,
                            )
                        )

                    except requests.RequestException as error:

                        st.error(
                            "FastAPI self-introduction "
                            f"processing failed: {error}"
                        )

                        st.stop()

                    new_skills = clean_api_list(
                        intro_result.get(
                            "new_skills",
                            [],
                        )
                    )

                    combined_skills = list(
                        st.session_state.resume_skills
                    )

                    for skill in new_skills:

                        if skill.lower() not in [
                            existing.lower()
                            for existing in combined_skills
                        ]:

                            combined_skills.append(
                                skill
                            )

                    st.session_state.self_intro_skills = (
                        new_skills
                    )

                    st.session_state.self_intro_completed = (
                        True
                    )

                    st.session_state.self_intro_stage = (
                        False
                    )

                    initial_state = (
                        st.session_state.interview_state
                    )

                    initial_state["skills"] = (
                        combined_skills
                    )

                    initial_state["current_skill"] = (
                        combined_skills[0]
                    )

                    initial_state["skill_index"] = 0

                    initial_state["question_type"] = (
                        "basic"
                    )

                    initial_state["extracted_concepts"] = []

                    initial_state["question_count"] = 0

                    initial_state["interview_history"] = []

                    initial_state["skill_ratings"] = {}

                    try:

                        question_result = (
                            api_generate_question(
                                initial_state
                            )
                        )

                    except requests.RequestException as error:

                        st.error(
                            "FastAPI question generation "
                            f"failed: {error}"
                        )

                        st.stop()

                    initial_state["current_question"] = (
                        question_result.get(
                            "question",
                            "",
                        )
                    )

                    initial_state["current_expected_answer"] = ""

                    st.session_state.interview_state = (
                        initial_state
                    )

                    st.session_state.question = (
                        initial_state["current_question"]
                    )

                    st.session_state.candidate_answer = ""

                    st.session_state.interview_started = True

                    st.session_state.interview_finished = False

                    st.session_state.interview_result_saved = False

                    st.session_state.last_processed_skip_event = None

                    st.session_state.last_processed_answer_event = None

                    st.rerun()

    st.stop()


# ============================================================
# RESUME UPLOAD PAGE
# ============================================================

st.markdown(
    f"""
    <div class="upload-hero">

        <div class="icon">
            🎯
        </div>

        <h1>
            Adaptive Mock Interview
        </h1>

        <p>
            Practice smarter. Get questions based on your resume
            and receive a performance-based evaluation.
        </p>

    </div>

    <div class="upload-card">

        <div class="upload-card-title">
            📄 Upload your resume
        </div>

        <div class="upload-card-subtitle">
            Upload a PDF or DOCX resume to personalize your interview.
        </div>

    </div>

    <div class="upload-features">

        <div class="feature">
            🧠 Resume-based questions
        </div>

        <div class="feature">
            🎤 Voice interview
        </div>

        <div class="feature">
            📊 Score out of 10
        </div>

        <div class="feature">
            💼 Role assessment
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


with st.container(border=True):
    st.markdown("### 📄 Upload your resume")
    st.caption("Upload a PDF or DOCX resume to personalize your interview.")

    uploaded_file = st.file_uploader(
        "Choose your resume",
        type=["pdf", "docx"],
        label_visibility="visible",
    )

# ============================================================
# START RESUME INTERVIEW
# ============================================================

if uploaded_file:

    st.markdown(
        f"""
        <div class="start-note">
            ✅ <strong>{uploaded_file.name}</strong> selected
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "🚀 Start Resume Interview",
        use_container_width=True,
    ):

        file_path = uploaded_file.name

        with open(
            file_path,
            "wb",
        ) as file:

            file.write(
                uploaded_file.getbuffer()
            )

        try:

            resume_text = extract_text(
                file_path
            )

        except Exception as error:

            st.error(
                f"Resume extraction failed: {error}"
            )

            st.stop()

        initial_state = {

            "resume_text": resume_text,

            "job_role": "",

            "skills": [],

            "current_skill": "",

            "current_question": "",

            "current_expected_answer": "",

            "current_question_id": "",

            "question_type": "basic",

            "candidate_answer": "",

            "current_score": 0.0,

            "missing_concepts": [],

            "extracted_concepts": [],

            "skill_index": 0,

            "question_count": 0,

            "interview_history": [],

            "skill_ratings": {},
        }

        try:

            analysis_result = api_analyze_resume(
                file_path
            )

        except requests.RequestException as error:

            st.error(
                f"FastAPI resume analysis failed: {error}"
            )

            st.stop()

        skills = clean_api_list(
            analysis_result.get(
                "skills",
                [],
            )
        )

        if not skills:

            st.error(
                "No technical skills were extracted from the resume."
            )

            st.stop()

        initial_state["skills"] = skills

        initial_state["current_skill"] = skills[0]

        st.session_state.resume_skills = skills

        st.session_state.self_intro_skills = []

        st.session_state.resume_text = resume_text

        st.session_state.interview_state = initial_state

        st.session_state.self_intro_stage = True

        st.session_state.self_intro_completed = False

        st.session_state.interview_started = False

        st.session_state.interview_finished = False

        st.session_state.interview_result_saved = False

        st.session_state.question = (
            "Tell me about yourself."
        )

        st.session_state.candidate_answer = ""

        st.session_state.last_processed_skip_event = None

        st.session_state.last_processed_answer_event = None

        st.rerun()