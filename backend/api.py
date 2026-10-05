from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Header,
    HTTPException,
    Depends
)

from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

import tempfile
import json
import os
import base64
import hashlib
import hmac
import time
import re
from difflib import SequenceMatcher

from langchain_ollama import ChatOllama

from resume_parser import extract_text
from llm_analysis import analyze_resume
from question_generation import generate_question

from backend.database import get_db_connection

from answer_evaluation import (
    evaluate_answer,
    evaluate_topic_interview_answer
)

from backend.assessment_interview_ai import (
    generate_final_interview_analysis
)
from backend.db_operations import (
    save_interview,
    save_interview_question
)

# ============================================================
# ASSESSMENT INTERVIEW DATABASE FUNCTIONS
# ============================================================

from pages.assessment_interview_db import (
    create_interview_assessment,
    save_interview_question_to_attempt,
    save_interview_answer,
    save_question_evaluation,
    finish_interview_attempt
)

# ============================================================
# ASSESSMENT INTERVIEW AI
# ============================================================


from backend.assessment_interview_final_ai import (
    generate_final_interview_analysis
)


# ============================================================
# REQUEST MODELS
# ============================================================

class CreateAssessmentRequest(BaseModel):
    subject: str
    topic: str
    difficulty: str


# ============================================================
# SECURITY
# ============================================================

security = HTTPBearer(
    scheme_name="BearerAuth"
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Adaptive Mock Interview API"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

USERS_FILE = os.path.join(
    BASE_DIR,
    "users.json"
)

INTERVIEWS_FILE = os.path.join(
    BASE_DIR,
    "interviews.json"
)


# ============================================================
# JWT CONFIG
# ============================================================

JWT_SECRET = "9392983478"

JWT_ALGORITHM = "HS256"

JWT_EXPIRATION_SECONDS = 60 * 60 * 24


# ============================================================
# JWT HELPER FUNCTIONS
# ============================================================

def base64url_encode(data: bytes) -> str:

    return base64.urlsafe_b64encode(
        data
    ).rstrip(b"=").decode()


def base64url_decode(data: str) -> bytes:

    padding = "=" * (
        4 - len(data) % 4
    )

    return base64.urlsafe_b64decode(
        data + padding
    )


def create_access_token(
    user_id: str
) -> str:

    header = {
        "alg": JWT_ALGORITHM,
        "typ": "JWT"
    }

    payload = {
        "sub": str(user_id),
        "exp": int(time.time())
        + JWT_EXPIRATION_SECONDS
    }

    header_json = json.dumps(
        header,
        separators=(",", ":")
    ).encode()

    payload_json = json.dumps(
        payload,
        separators=(",", ":")
    ).encode()

    encoded_header = base64url_encode(
        header_json
    )

    encoded_payload = base64url_encode(
        payload_json
    )

    message = (
        encoded_header
        + "."
        + encoded_payload
    )

    signature = hmac.new(
        JWT_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()

    encoded_signature = base64url_encode(
        signature
    )

    return (
        message
        + "."
        + encoded_signature
    )


def verify_access_token(token: str):

    try:

        parts = token.split(".")

        if len(parts) != 3:

            print(
                "JWT ERROR: Invalid token structure"
            )

            return None

        encoded_header = parts[0]
        encoded_payload = parts[1]
        encoded_signature = parts[2]

        message = (
            encoded_header
            + "."
            + encoded_payload
        )

        expected_signature = hmac.new(
            JWT_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()

        actual_signature = base64url_decode(
            encoded_signature
        )

        if not hmac.compare_digest(
            expected_signature,
            actual_signature
        ):

            print(
                "JWT ERROR: Signature mismatch"
            )

            return None

        payload = json.loads(
            base64url_decode(
                encoded_payload
            ).decode("utf-8")
        )

        exp = payload.get("exp")

        if exp is not None:

            if int(exp) < int(time.time()):

                print(
                    "JWT ERROR: Token expired"
                )

                return None

        user_id = (
            payload.get("sub")
            or payload.get("user_id")
            or payload.get("id")
        )

        if not user_id:

            print(
                "JWT ERROR: User ID missing"
            )

            return None

        print(
            "JWT VERIFIED SUCCESSFULLY"
        )

        print(
            "JWT USER ID:",
            user_id
        )

        return payload

    except Exception as e:

        print(
            "JWT VERIFY ERROR:",
            repr(e)
        )

        return None


def get_current_user(
    authorization: str | None = Header(default=None)
):

    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Authorization token required"
        )

    if not authorization.startswith(
        "Bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format"
        )

    token = authorization.split(
        " ",
        1
    )[1].strip()

    if not token:

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token"
        )

    payload = verify_access_token(
        token
    )

    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user_id = (
        payload.get("sub")
        or payload.get("user_id")
        or payload.get("id")
    )

    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="User ID not found in token"
        )

    user_id = str(
        user_id
    ).strip()

    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="Invalid user ID in token"
        )

    current_user = {
        "id": user_id,
        "user_id": user_id,
        "email": payload.get("email"),
        "name": payload.get("name"),
        "role": payload.get("role"),
    }

    print(
        "CURRENT USER VERIFIED"
    )

    print(
        "USER ID:",
        current_user["id"]
    )

    print(
        "EMAIL:",
        current_user["email"]
    )

    return current_user


# ============================================================
# USER HELPER
# ============================================================

def safe_user(user):

    interests = user.get(
        "interests",
        []
    )

    if isinstance(
        interests,
        str
    ):

        try:

            interests = json.loads(
                interests
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            interests = []

    created_at = user.get(
        "createdAt",
        user.get(
            "created_at",
            ""
        )
    )

    if hasattr(
        created_at,
        "isoformat"
    ):

        created_at = created_at.isoformat()

    return {

        "id":
            user.get("id"),

        "fullName":
            user.get(
                "fullName",
                user.get(
                    "name",
                    ""
                )
            ),

        "email":
            user.get(
                "email",
                ""
            ),

        "phone":
            user.get(
                "phone",
                ""
            ),

        "currentRole":
            user.get(
                "currentRole",
                user.get(
                    "current_job_role",
                    ""
                )
            ),

        "experienceYears":
            user.get(
                "experienceYears",
                user.get(
                    "experience_years",
                    0
                )
            ),

        "educationLevel":
            user.get(
                "educationLevel",
                user.get(
                    "education_level",
                    ""
                )
            ),

        "careerGoal":
            user.get(
                "careerGoal",
                user.get(
                    "career_goal",
                    ""
                )
            ),

        "interests":
            interests,

        "learningGoals":
            user.get(
                "learningGoals",
                user.get(
                    "learning_goals",
                    ""
                )
            ),

        "createdAt":
            created_at
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "status": "success",
        "message":
            "Adaptive Mock Interview API is running"
    }


# ============================================================
# ANALYZE RESUME API
# ============================================================

@app.post("/analyze-resume")
async def analyze_resume_api(
    file: UploadFile = File(...)
):

    suffix = os.path.splitext(
        file.filename
    )[1]

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    ) as temp_file:

        temp_file.write(
            await file.read()
        )

        temp_path = temp_file.name

    try:

        resume_text = extract_text(
            temp_path
        )

        result = analyze_resume(
            resume_text
        )

        return {

            "status":
                "success",

            "filename":
                file.filename,

            "skills":
                result.get(
                    "skills",
                    []
                )
        }

    finally:

        if os.path.exists(
            temp_path
        ):

            os.remove(
                temp_path
            )


# ============================================================
# PASSWORD HELPERS
# ============================================================

def hash_password(
    password: str
) -> str:

    salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return (
        "pbkdf2_sha256$120000$"
        + base64url_encode(salt)
        + "$"
        + base64url_encode(password_hash)
    )


def verify_password(
    password: str,
    stored_hash: str
) -> bool:

    try:

        parts = stored_hash.split("$")

        if len(parts) != 4:
            return False

        algorithm = parts[0]

        iterations = int(
            parts[1]
        )

        salt = base64url_decode(
            parts[2]
        )

        expected_hash = base64url_decode(
            parts[3]
        )

        if algorithm != "pbkdf2_sha256":
            return False

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except Exception:

        return False


# ============================================================
# REGISTER API
# ============================================================

class RegisterRequest(BaseModel):

    fullName: str
    email: str
    password: str
    phone: str = ""
    currentRole: str = ""
    experienceYears: int = 0
    educationLevel: str = ""
    careerGoal: str = ""
    interests: list = []
    learningGoals: str = ""


@app.post("/register")
def register_user(
    request: RegisterRequest
):

    email = request.email.lower().strip()

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(email) = LOWER(%s)
            """,
            (email,)
        )

        if cursor.fetchone():

            return {
                "status":
                    "error",

                "message":
                    "Email already registered"
            }

        password_hash = hash_password(
            request.password
        )

        cursor.execute(
            """
            INSERT INTO users (
                name,
                email,
                password_hash,
                role,
                is_active,
                phone,
                current_job_role,
                experience_years,
                education_level,
                career_goal,
                interests,
                learning_goals
            )
            VALUES (
                %s, %s, %s, 'USER', TRUE,
                %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                request.fullName,
                email,
                password_hash,
                request.phone,
                request.currentRole,
                request.experienceYears,
                request.educationLevel,
                request.careerGoal,
                json.dumps(
                    request.interests,
                    ensure_ascii=False
                ),
                request.learningGoals
            )
        )

        user_id = cursor.fetchone()[0]

        connection.commit()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                phone,
                current_job_role,
                experience_years,
                education_level,
                career_goal,
                interests,
                learning_goals,
                created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        row = cursor.fetchone()

        user = dict(
            zip(
                [
                    "id",
                    "name",
                    "email",
                    "phone",
                    "current_job_role",
                    "experience_years",
                    "education_level",
                    "career_goal",
                    "interests",
                    "learning_goals",
                    "created_at"
                ],
                row
            )
        )

        return {

            "user":
                safe_user(user),

            "token":
                create_access_token(
                    str(user_id)
                )
        }

    except Exception:

        connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# LOGIN API
# ============================================================

class LoginRequest(BaseModel):

    email: str
    password: str


@app.post("/login")
def login_user(
    request: LoginRequest
):

    email = request.email.lower().strip()

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                password_hash,
                role,
                is_active,
                phone,
                current_job_role,
                experience_years,
                education_level,
                career_goal,
                interests,
                learning_goals,
                created_at
            FROM users
            WHERE LOWER(email) = LOWER(%s)
            """,
            (email,)
        )

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        user = dict(
            zip(
                [
                    "id",
                    "name",
                    "email",
                    "password_hash",
                    "role",
                    "is_active",
                    "phone",
                    "current_job_role",
                    "experience_years",
                    "education_level",
                    "career_goal",
                    "interests",
                    "learning_goals",
                    "created_at"
                ],
                row
            )
        )

        if not user.get(
            "is_active",
            True
        ):

            raise HTTPException(
                status_code=403,
                detail="User account is inactive"
            )

        if not verify_password(
            request.password,
            user.get(
                "password_hash",
                ""
            )
        ):

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        return {

            "user":
                safe_user(user),

            "token":
                create_access_token(
                    str(user["id"])
                )
        }

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# LOGOUT API
# ============================================================

@app.post("/logout")
def logout_user(
    authorization: str | None = Header(
        default=None
    )
):

    get_current_user(
        authorization
    )

    return {
        "message":
            "Logged out successfully"
    }


# ============================================================
# CURRENT USER API
# ============================================================

@app.get("/me")
def get_me(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    )
):

    authorization = (
        f"Bearer {credentials.credentials}"
    )

    user = get_current_user(
        authorization
    )

    return safe_user(
        user
    )


# ============================================================
# UPDATE PROFILE API
# ============================================================

class ProfileUpdateRequest(BaseModel):

    fullName: str = ""
    phone: str = ""
    currentRole: str = ""
    experienceYears: int = 0
    educationLevel: str = ""
    careerGoal: str = ""
    interests: list = []
    learningGoals: str = ""


@app.put("/profile")
def update_profile(
    request: ProfileUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    )
):

    authorization = (
        f"Bearer {credentials.credentials}"
    )

    user = get_current_user(
        authorization
    )

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE users
            SET
                name = %s,
                phone = %s,
                current_job_role = %s,
                experience_years = %s,
                education_level = %s,
                career_goal = %s,
                interests = %s,
                learning_goals = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                request.fullName,
                request.phone,
                request.currentRole,
                request.experienceYears,
                request.educationLevel,
                request.careerGoal,
                json.dumps(
                    request.interests,
                    ensure_ascii=False
                ),
                request.learningGoals,
                user["id"]
            )
        )

        connection.commit()

        updated_user = get_current_user(
            authorization
        )

        return {

            "status":
                "success",

            "message":
                "Profile updated successfully",

            "profile":
                safe_user(updated_user)
        }

    except Exception:

        connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# GENERATE QUESTION API
# ============================================================

class QuestionRequest(BaseModel):

    current_skill: str
    question_type: str = "basic"
    concept: str = ""


HIDDEN_EXPECTED_ANSWERS = {}


def create_question_id():

    return base64.urlsafe_b64encode(
        os.urandom(24)
    ).rstrip(b"=").decode()


@app.post("/generate-question")
def generate_question_api(
    request: QuestionRequest
):

    state = {

        "current_skill":
            request.current_skill,

        "question_type":
            request.question_type,

        "extracted_concepts":
            (
                [request.concept]
                if request.concept
                else []
            )
    }

    result = generate_question(
        state
    )

    question = result.get(
        "question",
        ""
    ).strip()

    expected_answer = result.get(
        "expected_answer",
        ""
    ).strip()

    question_id = create_question_id()

    HIDDEN_EXPECTED_ANSWERS[
        question_id
    ] = {

        "expected_answer":
            expected_answer,

        "question":
            question,

        "current_skill":
            request.current_skill
    }

    return {

        "status":
            "success",

        "question":
            question,

        "question_id":
            question_id
    }


# ============================================================
# SAVE INTERVIEW RESULT REQUEST
# ============================================================

class InterviewResultRequest(BaseModel):

    overallScore: float = 0
    skillRatings: dict = {}
    questionsAnswered: int = 0
    interviewHistory: list = []
    skills: list = []
    strongSkills: list = []
    skillsToImprove: list = []
    bestMatchRole: str = ""
    futureRoles: list = []


# ============================================================
# EVALUATE ANSWER API
# ============================================================

class AnswerEvaluationRequest(BaseModel):

    current_skill: str
    question: str
    candidate_answer: str
    question_id: str = ""


@app.post("/evaluate-answer")
def evaluate_answer_api(
    request: AnswerEvaluationRequest
):

    hidden_data = HIDDEN_EXPECTED_ANSWERS.get(
        request.question_id
    )

    if not hidden_data:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired question_id"
        )

    expected_answer = hidden_data.get(
        "expected_answer",
        ""
    )

    stored_question = hidden_data.get(
        "question",
        request.question
    )

    stored_skill = hidden_data.get(
        "current_skill",
        request.current_skill
    )

    result = evaluate_answer(

        current_skill=stored_skill,

        question=stored_question,

        candidate_answer=request.candidate_answer,

        expected_answer=expected_answer
    )

    HIDDEN_EXPECTED_ANSWERS.pop(
        request.question_id,
        None
    )

    return {

        "status":
            "success",

        "score":
            result.get(
                "score",
                0
            ),

        "feedback":
            result.get(
                "feedback",
                ""
            ),

        "missing_concepts":
            result.get(
                "missing_concepts",
                []
            ),

        "extracted_concepts":
            result.get(
                "extracted_concepts",
                []
            ),

        "next_question_type":
            result.get(
                "next_question_type",
                "basic"
            )
    }


# ============================================================
# PROCESS SELF INTRODUCTION API
# ============================================================

class SelfIntroRequest(BaseModel):

    self_intro: str
    resume_skills: list = []


@app.post("/process-self-intro")
def process_self_intro(
    request: SelfIntroRequest
):

    self_intro = request.self_intro.strip()

    resume_skills = [
        str(skill).strip()
        for skill in request.resume_skills
        if str(skill).strip()
    ]

    if not self_intro:

        return {

            "status":
                "error",

            "message":
                "Self introduction cannot be empty",

            "score":
                0,

            "feedback":
                "Please provide a self introduction.",

            "extracted_concepts":
                [],

            "missing_concepts":
                [],

            "new_skills":
                []
        }

    result = evaluate_answer(

        current_skill=
            "Self Introduction",

        question=
            "Tell me about yourself.",

        candidate_answer=
            self_intro
    )

    extracted_concepts = result.get(
        "extracted_concepts",
        []
    )

    resume_skill_set = {
        skill.lower()
        for skill in resume_skills
    }

    new_skills = []

    for concept in extracted_concepts:

        concept_text = str(
            concept
        ).strip()

        if not concept_text:
            continue

        if concept_text.lower() not in resume_skill_set:

            if concept_text.lower() not in [
                skill.lower()
                for skill in new_skills
            ]:

                new_skills.append(
                    concept_text
                )

    return {

        "status":
            "success",

        "score":
            result.get(
                "score",
                0
            ),

        "feedback":
            result.get(
                "feedback",
                ""
            ),

        "extracted_concepts":
            extracted_concepts,

        "missing_concepts":
            result.get(
                "missing_concepts",
                []
            ),

        "new_skills":
            new_skills
    }


# ============================================================
# TRANSCRIPTION API
# ============================================================

class TranscriptionRequest(BaseModel):

    text: str


@app.post("/transcribe")
def transcribe_text(
    request: TranscriptionRequest
):

    text = request.text.strip()

    if not text:

        return {

            "status":
                "error",

            "message":
                "Transcript cannot be empty",

            "transcript":
                ""
        }

    return {

        "status":
            "success",

        "transcript":
            text
    }


# ============================================================
# SAVE STREAMLIT INTERVIEW RESULT
# ============================================================

@app.post("/streamlit/interviews")
def save_streamlit_interview_result(
    request: InterviewResultRequest
):

    if not os.path.exists(
        INTERVIEWS_FILE
    ):

        data = {
            "interviews": []
        }

    else:

        with open(
            INTERVIEWS_FILE,
            "r"
        ) as file:

            data = json.load(file)

    interview_id = len(
        data.get(
            "interviews",
            []
        )
    ) + 1

    interview_result = {

        "id":
            interview_id,

        "userId":
            0,

        "overallScore":
            request.overallScore,

        "skillRatings":
            request.skillRatings,

        "questionsAnswered":
            request.questionsAnswered,

        "skills":
            request.skills,

        "interviewHistory":
            request.interviewHistory,

        "createdAt":
            time.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
    }

    data["interviews"].append(
        interview_result
    )

    with open(
        INTERVIEWS_FILE,
        "w"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )

    return {

        "status":
            "success",

        "message":
            "Streamlit interview result saved successfully",

        "interview":
            interview_result
    }


# ============================================================
# SAVE INTERVIEW RESULT
# ============================================================

@app.post("/interviews")
def save_interview_result(
    request: InterviewResultRequest,
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    )
):

    authorization = (
        f"Bearer {credentials.credentials}"
    )

    user = get_current_user(
        authorization
    )

    history = request.interviewHistory or []

    interview_id = save_interview(

        user_id=
            user["id"],

        overall_score=
            request.overallScore,

        questions_answered=
            request.questionsAnswered,

        skills=
            request.skills,

        strong_skills=
            request.strongSkills,

        skills_to_improve=
            request.skillsToImprove,

        best_match_role=
            request.bestMatchRole,

        future_roles=
            request.futureRoles
    )

    saved_questions = 0

    for item in history:

        if not isinstance(
            item,
            dict
        ):
            continue

        skill = (
            item.get("skill")
            or item.get("current_skill")
            or ""
        )

        question = (
            item.get("question")
            or ""
        )

        if not skill or not question:
            continue

        question_type = (
            item.get("question_type")
            or item.get("questionType")
            or "basic"
        )

        candidate_answer = (
            item.get("candidate_answer")
            or item.get("candidateAnswer")
            or ""
        )

        score = item.get(
            "score",
            0
        )

        feedback = item.get(
            "feedback",
            ""
        )

        missing_concepts = item.get(
            "missing_concepts",
            item.get(
                "missingConcepts",
                []
            )
        )

        extracted_concepts = item.get(
            "extracted_concepts",
            item.get(
                "extractedConcepts",
                []
            )
        )

        save_interview_question(

            interview_id=
                interview_id,

            skill=
                skill,

            question=
                question,

            question_type=
                question_type,

            candidate_answer=
                candidate_answer,

            score=
                score,

            feedback=
                feedback,

            missing_concepts=
                missing_concepts or [],

            extracted_concepts=
                extracted_concepts or []
        )

        saved_questions += 1

    return {

        "status":
            "success",

        "message":
            "Interview result saved successfully",

        "interview": {

            "id":
                interview_id,

            "userId":
                user["id"],

            "overallScore":
                request.overallScore,

            "skillRatings":
                request.skillRatings,

            "questionsAnswered":
                request.questionsAnswered,

            "skills":
                request.skills,

            "interviewHistory":
                history,

            "createdAt":
                time.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
        },

        "savedQuestions":
            saved_questions
    }


# ============================================================
# GET INTERVIEW HISTORY
# ============================================================

@app.get("/interviews")
def get_interview_history(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    )
):

    authorization = (
        f"Bearer {credentials.credentials}"
    )

    user = get_current_user(
        authorization
    )

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                overall_score,
                questions_answered,
                skills,
                strong_skills,
                skills_to_improve,
                best_match_role,
                future_roles,
                created_at
            FROM interviews
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user["id"],)
        )

        rows = cursor.fetchall()

        interviews = []

        for row in rows:

            (
                interview_id,
                overall_score,
                questions_answered,
                skills,
                strong_skills,
                skills_to_improve,
                best_match_role,
                future_roles,
                created_at
            ) = row

            interviews.append({

                "id":
                    interview_id,

                "userId":
                    user["id"],

                "overallScore":
                    overall_score or 0,

                "questionsAnswered":
                    questions_answered or 0,

                "skills":
                    json.loads(skills)
                    if skills
                    else [],

                "strongSkills":
                    (
                        json.loads(
                            str(strong_skills)
                        )
                        if strong_skills
                        else []
                    ),

                "skillsToImprove":
                    (
                        json.loads(
                            str(skills_to_improve)
                        )
                        if skills_to_improve
                        else []
                    ),

                "bestMatchRole":
                    best_match_role,

                "futureRoles":
                    future_roles,

                "createdAt":
                    (
                        created_at.isoformat()
                        if created_at
                        else ""
                    )
            })

        return {

            "status":
                "success",

            "interviews":
                interviews
        }

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# ASSESSMENT
# ============================================================

@app.post("/assessment/create")
def create_assessment(
    request: CreateAssessmentRequest
):

    subject = request.subject.strip()

    topic = request.topic.strip()

    difficulty = request.difficulty.strip()

    if not subject:

        raise HTTPException(
            status_code=400,
            detail="Subject is required"
        )

    if not topic:

        raise HTTPException(
            status_code=400,
            detail="Topic is required"
        )

    if difficulty not in [
        "Easy",
        "Medium",
        "Hard"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Difficulty must be Easy, Medium, or Hard"
        )

    return {

        "status":
            "success",

        "message":
            "Assessment configuration received",

        "subject":
            subject,

        "topic":
            topic,

        "difficulty":
            difficulty,

        "question_count":
            15,

        "time_per_question_minutes":
            2,

        "maximum_time_minutes":
            30
    }


# ============================================================
# ADMIN-CREATED INTERVIEW MODE
# ============================================================

admin_interview_model = ChatOllama(

    model="qwen2.5:1.5b",

    temperature=0.3,

    num_predict=300,

    num_ctx=2048,

    keep_alive="30m",

    format="json"
)


INTERVIEW_TOTAL_TIME_SECONDS = 30 * 60

INTERVIEW_QUESTION_TIME_SECONDS = 2 * 60

INTERVIEW_SESSIONS = {}

ADMIN_INTERVIEW_QUESTIONS = {}


# ============================================================
# REQUEST MODELS
# ============================================================

class CreateInterviewConfigRequest(BaseModel):

    topic: str
    level: str


class StartInterviewRequest(BaseModel):

    topic: str
    level: str
    previous_questions: list[str] | None = None
    question_number: int = 0
    last_candidate_answer: str = ""
    next_question_type: str = "basic"


class InterviewQuestionRequest(BaseModel):

    session_id: str


class AdminInterviewAnswerRequest(BaseModel):

    session_id: str
    question_id: str
    candidate_answer: str = ""


# ============================================================
# ADMIN INTERVIEW CONFIGURE
# ============================================================

@app.post("/interview/configure")
def configure_interview(
    request: CreateInterviewConfigRequest
):

    topic = request.topic.strip()

    level = request.level.strip()

    if not topic:

        raise HTTPException(
            status_code=400,
            detail="Topic is required"
        )

    if level not in [
        "Easy",
        "Medium",
        "Hard"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Level must be Easy, Medium, or Hard"
        )

    return {

        "status":
            "success",

        "message":
            "Interview configuration received",

        "topic":
            topic,

        "level":
            level,

        "total_time_seconds":
            INTERVIEW_TOTAL_TIME_SECONDS,

        "question_time_seconds":
            INTERVIEW_QUESTION_TIME_SECONDS
    }


# ============================================================
# START ADMIN INTERVIEW
# ============================================================

@app.post("/interview/start")
def start_interview(
    request: StartInterviewRequest,
    current_user: dict = Depends(get_current_user)
):

    topic = request.topic.strip()

    level = request.level.strip()

    if not topic:

        raise HTTPException(
            status_code=400,
            detail="Topic is required"
        )

    if level not in [
        "Easy",
        "Medium",
        "Hard"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Level must be Easy, Medium, or Hard"
        )

    db_data = create_interview_assessment(

        student_id=
            current_user["id"],

        topic=
            topic,

        level=
            level,

        total_questions=
            15,

        total_time_seconds=
            INTERVIEW_TOTAL_TIME_SECONDS,

        question_time_seconds=
            INTERVIEW_QUESTION_TIME_SECONDS
    )

    session_id = create_question_id()

    started_at = int(
        time.time()
    )

    expires_at = (
        started_at
        + INTERVIEW_TOTAL_TIME_SECONDS
    )

    INTERVIEW_SESSIONS[
        session_id
    ] = {

        "session_id":
            session_id,

        "student_id":
            current_user["id"],

        "assessment_id":
            db_data["assessment_id"],

        "assessment_section_id":
            db_data["assessment_section_id"],

        "attempt_id":
            db_data["attempt_id"],

        "attempt_section_id":
            db_data["attempt_section_id"],

        "topic":
            topic,

        "level":
            level,

        "started_at":
            started_at,

        "expires_at":
            expires_at,

        "question_started_at":
            None,

        "current_question_id":
            None,

        "current_question":
            None,

        "current_interview_question_id":
            None,

        "current_attempt_question_id":
            None,

        "status":
            "active",

        "question_number":
            max(
                0,
                min(
                    request.question_number,
                    15
                )
            ),

        "previous_questions": [

            str(question)

            for question in (
                request.previous_questions
                or []
            )

            if str(question).strip()

        ][-15:],

        "history":
            [],

        "last_score":
            None,

        "last_feedback":
            "",

        "last_missing_concepts":
            [],

        "last_extracted_concepts":
            [],

        "next_question_type":
            request.next_question_type,

        "last_candidate_answer":
            request.last_candidate_answer,

        "db_finalized":
            False
    }

    return {

        "status":
            "success",

        "message":
            "Interview started successfully",

        "session_id":
            session_id,

        "topic":
            topic,

        "level":
            level,

        "started_at":
            started_at,

        "expires_at":
            expires_at,

        "total_time_seconds":
            INTERVIEW_TOTAL_TIME_SECONDS,

        "question_time_seconds":
            INTERVIEW_QUESTION_TIME_SECONDS,

        "assessment_id":
            db_data["assessment_id"],

        "assessment_section_id":
            db_data["assessment_section_id"],

        "attempt_id":
            db_data["attempt_id"],

        "attempt_section_id":
            db_data["attempt_section_id"]
    }


# ============================================================
# ADMIN QUESTION GENERATOR
# ============================================================

def _normalize_interview_question(
    text
):

    value = str(
        text or ""
    ).strip().lower()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    return value.strip()


def _question_is_duplicate(
    question,
    previous_questions
):

    candidate = _normalize_interview_question(
        question
    )

    if not candidate:
        return True

    candidate_tokens = set(
        candidate.split()
    )

    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "what",
        "when",
        "why",
        "with",
        "would",
        "you",
    }

    for previous in (
        previous_questions
        or []
    ):

        previous_normalized = (
            _normalize_interview_question(
                previous
            )
        )

        if not previous_normalized:
            continue

        if candidate == previous_normalized:
            return True

        similarity = SequenceMatcher(
            None,
            candidate,
            previous_normalized
        ).ratio()

        if similarity >= 0.88:
            return True

        candidate_filtered = {
            token
            for token in candidate_tokens
            if token not in stop_words
        }

        previous_tokens = set(
            previous_normalized.split()
        )

        previous_filtered = {
            token
            for token in previous_tokens
            if token not in stop_words
        }

        if (
            candidate_filtered
            and previous_filtered
        ):

            overlap = (
                len(
                    candidate_filtered
                    & previous_filtered
                )
                /
                max(
                    1,
                    len(
                        candidate_filtered
                        | previous_filtered
                    )
                )
            )

            if overlap >= 0.82:
                return True

    return False


# ============================================================
# FALLBACK QUESTION
# ============================================================

def _fallback_admin_interview_question(
    topic,
    previous_questions,
    target_concept=""
):

    focus = (
        target_concept.strip()
        or topic.strip()
    )

    question_templates = [

        (
            "What does {focus} do, and what problem is it designed to solve?",
            "A strong answer defines the topic, identifies the problem it addresses, and explains its purpose."
        ),

        (
            "How does {focus} work at a high level?",
            "A strong answer describes the main steps or components and how they work together."
        ),

        (
            "What are the core concepts behind {focus}, and how are they related?",
            "A strong answer identifies the relevant concepts and explains their roles and relationships."
        ),

        (
            "When is {focus} useful, and when might it be a poor fit?",
            "A strong answer gives appropriate use cases and explains situations where the topic is not a good fit."
        ),

        (
            "What are the main benefits and limitations of {focus}?",
            "A strong answer balances the topic's advantages against its practical limitations."
        ),

        (
            "What common problems can arise with {focus}, and how would you investigate them?",
            "A strong answer describes a systematic way to reproduce, isolate, and diagnose a problem involving the topic."
        ),

        (
            "How would you test whether a solution involving {focus} works correctly?",
            "A strong answer describes relevant test cases, expected behavior, and how results would be verified."
        ),

        (
            "What performance factors should be considered when using {focus}?",
            "A strong answer identifies relevant performance constraints and explains how they can be measured or improved."
        ),

        (
            "What security concerns should be considered when working with {focus}?",
            "A strong answer identifies risks relevant to the topic and explains practical ways to reduce them."
        ),

        (
            "How should errors or failure cases be handled in {focus}?",
            "A strong answer explains how failures are detected, handled, and communicated without hiding important errors."
        ),

        (
            "Which design decisions have the greatest impact when applying {focus}?",
            "A strong answer identifies important design choices and explains their effects on the resulting solution."
        ),

        (
            "What limitations of {focus} could affect a real-world implementation?",
            "A strong answer identifies practical constraints and explains how they influence implementation choices."
        ),

        (
            "How would you maintain a solution involving {focus} as requirements change?",
            "A strong answer explains how to keep the solution understandable, testable, and adaptable over time."
        ),

        (
            "How would you apply {focus} to solve a practical problem?",
            "A strong answer connects the topic to a concrete problem and outlines a suitable approach."
        ),

        (
            "What would you explain first to a teammate learning {focus}?",
            "A strong answer introduces the topic's purpose and the foundational ideas needed to use it correctly."
        ),
    ]

    for (
        question_template,
        expected_answer
    ) in question_templates:

        question = question_template.format(
            focus=focus
        )

        if not _question_is_duplicate(
            question,
            previous_questions
        ):

            return {

                "question":
                    question,

                "expected_answer":
                    expected_answer
            }

    return {

        "question":
            f"How would you approach a new challenge involving {focus}?",

        "expected_answer":
            (
                "A strong answer clarifies the problem, explains a suitable "
                "approach, and justifies the relevant trade-offs."
            )
    }


# ============================================================
# GENERATE ADMIN INTERVIEW QUESTION
# ============================================================

def generate_admin_interview_question(
    topic,
    level,
    question_type="basic",
    target_concept="",
    previous_questions=None,
    candidate_answer=""
):

    previous_questions = (
        previous_questions
        or []
    )

    previous_questions_text = "\n".join(

        [
            f"{index + 1}. {question}"

            for index, question
            in enumerate(
                previous_questions
            )
        ]
    )

    if not previous_questions_text:

        previous_questions_text = "None"

    answer_context = (
        candidate_answer.strip()
        if candidate_answer.strip()
        else "None"
    )

    if (
        question_type
        == "concept_follow_up"
        and target_concept
    ):

        question_instruction = f"""
Generate ONE adaptive follow-up question about this concept:
{target_concept}

The question must remain inside the ADMIN-SELECTED TOPIC.
Do not ask the same definition again.
Explore WHY, HOW, behavior, use cases, limitations,
trade-offs, comparison, troubleshooting, or another deeper
aspect of the same concept.
"""

    elif question_type == "skill_deep":

        question_instruction = """
Generate ONE deeper question about the ADMIN-SELECTED TOPIC.
Focus on practical scenarios, behavior, troubleshooting,
comparisons, trade-offs, limitations, or deeper concepts.
"""

    else:

        question_instruction = """
Generate ONE question about the ADMIN-SELECTED TOPIC.
This is the first/basic question or a new basic question after
an answer that needs improvement.
Choose a new aspect of the topic that has not been explored in any
previous question.
"""

    prompt = f"""
You are a technical interview question generator.

ADMIN-SELECTED TOPIC:
{topic}

ADMIN-SELECTED LEVEL:
{level}

QUESTION TYPE:
{question_type}

TARGET CONCEPT:
{target_concept if target_concept else "None"}

PREVIOUS QUESTIONS:
{previous_questions_text}

CANDIDATE'S PREVIOUS ANSWER:
{answer_context}

{question_instruction}

IMPORTANT RULES:

1. Generate exactly ONE interview question.
2. The question MUST be directly related to the topic: {topic}
3. The difficulty MUST match the level: {level}
4. The interview must stay completely inside the same topic.
5. Do NOT use resume information.
6. Do NOT use projects, internships, education, employment,
   resume skills, or candidate profile information.
7. Do NOT introduce unrelated technologies.
8. Do NOT assume knowledge of another technology that was not
   selected by the admin.
9. Do NOT ask coding questions.
10. Do NOT ask the candidate to write code.
11. Ask conceptual, theoretical, practical, comparison,
    troubleshooting, scenario, advantages/disadvantages,
    behavior, architecture, design-decision, or trade-off
    questions as appropriate for the level.
12. The question MUST be written in English.
13. The expected answer MUST be written in English.
14. Do NOT repeat or paraphrase any previous question.
15. The new question must be meaningfully different from every
    previous question listed above.
16. Choose a new aspect of the topic.
17. Easy = fundamentals and simple practical understanding.
18. Medium = deeper concepts, practical scenarios,
    comparisons, behavior and troubleshooting.
19. Hard = advanced concepts, architecture, complex scenarios,
    deep troubleshooting, design decisions, limitations and trade-offs.
20. Return valid JSON only.

Return exactly:
{{
    "question": "one interview question",
    "expected_answer": "technically correct expected answer"
}}
"""

    rejected_questions = []

    for _ in range(3):

        try:

            attempt_prompt = prompt

            if rejected_questions:

                rejected_text = "\n".join(

                    f"- {question}"

                    for question
                    in rejected_questions
                )

                attempt_prompt += f"""

RETRY REQUIREMENT:

The following candidate question was rejected as a repeat.
Generate a different question with a genuinely different angle.
Do not reuse or paraphrase it:

{rejected_text}
"""

            response = admin_interview_model.invoke(
                attempt_prompt
            )

            content = response.content

            if isinstance(
                content,
                list
            ):

                content = "".join(
                    str(item)
                    for item in content
                )

            result = json.loads(
                str(content).strip()
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

            if not question:

                raise ValueError(
                    "LLM returned an empty question"
                )

            if not _question_is_duplicate(
                question,
                previous_questions
            ):

                return {

                    "question":
                        question,

                    "expected_answer":
                        expected_answer
                }

            rejected_questions.append(
                question
            )

        except Exception:

            continue

    return _fallback_admin_interview_question(

        topic=
            topic,

        previous_questions=
            previous_questions
            + rejected_questions,

        target_concept=
            target_concept
    )


# ============================================================
# GENERATE NEXT ADMIN INTERVIEW QUESTION
# ============================================================

@app.post("/interview/question")
def generate_admin_interview_question_api(
    request: InterviewQuestionRequest
):

    session = INTERVIEW_SESSIONS.get(
        request.session_id
    )

    if not session:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    current_time = int(
        time.time()
    )

    if session["status"] != "active":

        raise HTTPException(
            status_code=400,
            detail="Interview is not active"
        )

    if current_time >= session["expires_at"]:

        session["status"] = "ended"

        _finish_topic_interview_in_db(
            session
        )

        raise HTTPException(
            status_code=400,
            detail="Interview time has ended"
        )

    result = generate_admin_interview_question(

        topic=
            session["topic"],

        level=
            session["level"],

        question_type=
            "basic",

        target_concept=
            "",

        previous_questions=
            session.get(
                "previous_questions",
                []
            ),

        candidate_answer=
            ""
    )

    question = result["question"]

    expected_answer = result[
        "expected_answer"
    ]

    question_id = create_question_id()

    question_started_at = current_time

    db_question = save_interview_question_to_attempt(

        section_id=
            session["assessment_section_id"],

        attempt_section_id=
            session["attempt_section_id"],

        question_text=
            question,

        expected_answer=
            expected_answer,

        expected_key_points=[
            expected_answer
        ],

        evaluation_criteria={
            "topic":
                session["topic"],

            "level":
                session["level"],

            "max_score":
                10
        },

        max_score=
            10,

        difficulty=
            session["level"].lower(),

        display_order=
            session["question_number"] + 1
    )

    # IMPORTANT:
    # Keep the evaluation criteria in memory because the new
    # assessment AI evaluator needs them.

    ADMIN_INTERVIEW_QUESTIONS[
        question_id
    ] = {

        "session_id":
            request.session_id,

        "topic":
            session["topic"],

        "level":
            session["level"],

        "question":
            question,

        "expected_answer":
            expected_answer,

        "evaluation_criteria": {
            "topic":
                session["topic"],

            "level":
                session["level"],

            "max_score":
                10
        },

        "max_score":
            10,

        "started_at":
            question_started_at,

        "evaluated":
            False,

        "db_question_id":
            db_question.get(
                "question_id"
            ),

        "db_interview_question_id":
            db_question.get(
                "interview_question_id"
            ),

        "db_assessment_section_question_id":
            db_question.get(
                "assessment_section_question_id"
            ),

        "db_attempt_question_id":
            db_question.get(
                "attempt_question_id"
            )
    }

    session[
        "question_started_at"
    ] = question_started_at

    session[
        "current_question_id"
    ] = question_id

    session[
        "current_question"
    ] = question

    session[
        "current_interview_question_id"
    ] = db_question.get(
        "interview_question_id"
    )

    session[
        "current_attempt_question_id"
    ] = db_question.get(
        "attempt_question_id"
    )

    session[
        "previous_questions"
    ].append(
        question
    )

    session[
        "question_number"
    ] += 1

    remaining_time = max(

        0,

        session["expires_at"]
        - current_time
    )

    return {

        "status":
            "success",

        "session_id":
            request.session_id,

        "topic":
            session["topic"],

        "level":
            session["level"],

        "question":
            question,

        "question_id":
            question_id,

        "question_number":
            session["question_number"],

        "question_time_seconds":
            INTERVIEW_QUESTION_TIME_SECONDS,

        "remaining_time_seconds":
            remaining_time
    }


# ============================================================
# EXTRACT SKIPPED QUESTION CONCEPTS
# ============================================================

def _extract_skipped_question_concepts(
    topic,
    question,
    expected_answer=""
):

    prompt = f"""
You are extracting concepts for an interview report.

Topic: {topic}
Question: {question}
Expected answer: {expected_answer}

Return JSON only in this exact format:
{{"concepts": ["concept 1", "concept 2"]}}

Rules:
- Return 1 to 3 concise technical concept names.
- Use the actual concept/topic being tested, not the full question.
- Do not write explanations.
- Do not introduce concepts outside the selected topic.
- If one concept is enough, return one concept.
"""

    try:

        response = admin_interview_model.invoke(
            prompt
        )

        content = response.content

        if isinstance(
            content,
            list
        ):

            content = "".join(
                str(item)
                for item in content
            )

        result = json.loads(
            str(content).strip()
        )

        concepts = result.get(
            "concepts",
            []
        )

        if not isinstance(
            concepts,
            list
        ):

            return []

        return [

            str(item).strip()

            for item in concepts

            if str(item).strip()

        ][:3]

    except Exception:

        return []


# ============================================================
# GET INTERVIEW EVALUATIONS FOR ATTEMPT
# ============================================================

def get_interview_evaluations_for_attempt(
    attempt_id
):

    # IMPORTANT:
    # get_connection() was NOT defined in your previous code.
    # We use the already-existing project DB connection instead.

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        query = """
            SELECT
                aq.display_order,
                iq.question_text,
                iq.expected_answer,
                iq.evaluation_criteria,
                iq.max_score,
                ia.answer_text,
                ia.score,
                ia.feedback,
                ia.evaluation_details
            FROM attempt_questions aq

            JOIN interview_questions iq
                ON iq.question_id = aq.question_id

            LEFT JOIN interview_answers ia
                ON ia.attempt_question_id = aq.id

            WHERE aq.attempt_section_id = (
                SELECT id
                FROM attempt_sections
                WHERE attempt_id = %s
                LIMIT 1
            )

            ORDER BY aq.display_order ASC
        """

        cursor.execute(
            query,
            (attempt_id,)
        )

        rows = cursor.fetchall()

        evaluations = []

        for row in rows:

            evaluation_details = row[8]

            if isinstance(
                evaluation_details,
                str
            ):

                try:

                    evaluation_details = json.loads(
                        evaluation_details
                    )

                except Exception:

                    evaluation_details = {}

            evaluations.append({

                "question_number":
                    row[0],

                "question":
                    row[1] or "",

                "expected_answer":
                    row[2] or "",

                "evaluation_criteria":
                    row[3] or {},

                "max_score":
                    float(row[4])
                    if row[4] is not None
                    else 10,

                "candidate_answer":
                    row[5] or "",

                "score":
                    float(row[6])
                    if row[6] is not None
                    else 0,

                "feedback":
                    row[7] or "",

                "evaluation_details":
                    evaluation_details or {}
            })

        return evaluations

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# GET ATTEMPT MAX SCORE
# ============================================================

def get_attempt_max_score(
    attempt_id
):

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT max_score
            FROM assessment_attempts
            WHERE id = %s
            """,
            (attempt_id,)
        )

        row = cursor.fetchone()

        if row and row[0] is not None:

            return float(
                row[0]
            )

        return 150.0

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# SAVE RECOMMENDED LEARNING AREAS
# ============================================================

def save_recommended_learning_areas(
    attempt_id,
    recommended_learning_areas
):

    connection = get_db_connection()

    cursor = None

    try:

        cursor = connection.cursor()

        if isinstance(
            recommended_learning_areas,
            (dict, list)
        ):

            recommended_learning_areas = json.dumps(
                recommended_learning_areas,
                ensure_ascii=False
            )

        elif recommended_learning_areas is None:

            recommended_learning_areas = ""

        else:

            recommended_learning_areas = str(
                recommended_learning_areas
            )

        cursor.execute(
            """
            UPDATE interview_evaluations
            SET
                recommended_learning_areas = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE attempt_id = %s
            """,
            (
                recommended_learning_areas,
                attempt_id
            )
        )

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    finally:

        if cursor:
            cursor.close()

        connection.close()


# ============================================================
# FINISH TOPIC INTERVIEW IN DATABASE
# ============================================================

def _finish_topic_interview_in_db(
    session
):

    if not session:
        return

    if session.get(
        "db_finalized",
        False
    ):

        return

    attempt_id = session.get(
        "attempt_id"
    )

    if not attempt_id:
        return

    # --------------------------------------------------------
    # GET ALL SAVED ANSWERS/EVALUATIONS FROM DATABASE
    # --------------------------------------------------------

    evaluations_from_db = (
        get_interview_evaluations_for_attempt(
            attempt_id
        )
    )

    # --------------------------------------------------------
    # GET THE FULL ATTEMPT MAX SCORE
    # --------------------------------------------------------

    max_score = get_attempt_max_score(
        attempt_id
    )

    # --------------------------------------------------------
    # CALCULATE OVERALL SCORE FROM QUESTION EVALUATIONS
    # --------------------------------------------------------

    overall_score = 0.0

    for item in evaluations_from_db:

        try:

            overall_score += float(
                item.get(
                    "score",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            pass

    # --------------------------------------------------------
    # PREPARE DATA FOR FINAL AI
    # --------------------------------------------------------

    final_ai_input = []

    for item in evaluations_from_db:

        final_ai_input.append({

            "question_number":
                item.get(
                    "question_number"
                ),

            "question":
                item.get(
                    "question",
                    ""
                ),

            "candidate_answer":
                item.get(
                    "candidate_answer",
                    ""
                ),

            "expected_answer":
                item.get(
                    "expected_answer",
                    ""
                ),

            "evaluation_criteria":
                item.get(
                    "evaluation_criteria",
                    {}
                ),

            "max_score":
                item.get(
                    "max_score",
                    10
                ),

            "evaluation":
                item.get(
                    "evaluation_details",
                    {}
                ),

            "score":
                item.get(
                    "score",
                    0
                ),

            "feedback":
                item.get(
                    "feedback",
                    ""
                )
        })

    # --------------------------------------------------------
    # GENERATE FINAL AI ANALYSIS
    # --------------------------------------------------------

    if final_ai_input:

        try:

            final_analysis = (
                generate_final_interview_analysis(
                    final_ai_input
                )
            )

            if not isinstance(
                final_analysis,
                dict
            ):

                final_analysis = {}

        except Exception as e:

            print(
                "FINAL INTERVIEW AI ERROR:",
                repr(e)
            )

            final_analysis = {}

    else:

        final_analysis = {}

    # --------------------------------------------------------
    # READ FINAL ANALYSIS FIELDS
    # --------------------------------------------------------

    strengths = final_analysis.get(
        "strengths",
        []
    )

    areas_for_improvement = (
        final_analysis.get(
            "areas_for_improvement",
            []
        )
    )

    technical_analysis = (
        final_analysis.get(
            "technical_analysis",
            ""
        )
    )

    communication_analysis = (
        final_analysis.get(
            "communication_analysis",
            ""
        )
    )

    problem_solving_analysis = (
        final_analysis.get(
            "problem_solving_analysis",
            ""
        )
    )

    recommended_learning_areas = (
        final_analysis.get(
            "recommended_learning_areas",
            []
        )
    )

    final_feedback = (
        final_analysis.get(
            "final_feedback",
            ""
        )
    )

    # --------------------------------------------------------
    # FALLBACKS
    # --------------------------------------------------------

    if not final_feedback:

        final_feedback = (
            "The interview was completed. "
            "Review the question-level feedback "
            "to identify areas for improvement."
        )

    # --------------------------------------------------------
    # SAVE FINAL INTERVIEW EVALUATION
    # --------------------------------------------------------

    finish_interview_attempt(

        attempt_id=
            attempt_id,

        assessment_id=
            session["assessment_id"],

        attempt_section_id=
            session["attempt_section_id"],

        overall_score=
            overall_score,

        max_score=
            max_score,

        student_id=
            session["student_id"],

        strengths=
            strengths,

        areas_for_improvement=
            areas_for_improvement,

        technical_analysis=
            technical_analysis,

        communication_analysis=
            communication_analysis,

        problem_solving_analysis=
            problem_solving_analysis,

        final_feedback=
            final_feedback,

        ai_model=
            "llama3.2:3b"
    )

    # --------------------------------------------------------
    # SAVE RECOMMENDED LEARNING AREAS
    # --------------------------------------------------------

    try:

        save_recommended_learning_areas(

            attempt_id=
                attempt_id,

            recommended_learning_areas=
                recommended_learning_areas
        )

    except Exception as e:

        print(
            "RECOMMENDED LEARNING SAVE ERROR:",
            repr(e)
        )

    # --------------------------------------------------------
    # MARK SESSION AS FINALIZED
    # --------------------------------------------------------

    session[
        "db_finalized"
    ] = True

    # Keep final analysis available in memory
    # for the /interview/end response.

    session[
        "final_analysis"
    ] = {

        "overall_score":
            overall_score,

        "max_score":
            max_score,

        "percentage":
            (
                round(
                    (
                        overall_score
                        / max_score
                    )
                    * 100,
                    2
                )
                if max_score > 0
                else 0
            ),

        "strengths":
            strengths,

        "areas_for_improvement":
            areas_for_improvement,

        "technical_analysis":
            technical_analysis,

        "communication_analysis":
            communication_analysis,

        "problem_solving_analysis":
            problem_solving_analysis,

        "recommended_learning_areas":
            recommended_learning_areas,

        "final_feedback":
            final_feedback
    }


# ============================================================
# EVALUATE ADMIN INTERVIEW ANSWER
# ============================================================

@app.post("/interview/evaluate")
def evaluate_admin_interview_answer(
    request: AdminInterviewAnswerRequest
):

    session = INTERVIEW_SESSIONS.get(
        request.session_id
    )

    if not session:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    question_data = ADMIN_INTERVIEW_QUESTIONS.get(
        request.question_id
    )

    if not question_data:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired question_id"
        )

    if (
        question_data["session_id"]
        != request.session_id
    ):

        raise HTTPException(
            status_code=400,
            detail="Question does not belong to this interview session"
        )

    # --------------------------------------------------------
    # DUPLICATE SUBMIT PROTECTION
    # --------------------------------------------------------

    if question_data.get(
        "evaluated"
    ):

        return question_data.get(

            "evaluation_result",

            {

                "status":
                    "success",

                "interview_ended":
                    session.get(
                        "status"
                    ) == "ended",

                "score":
                    0,

                "feedback":
                    "Question already evaluated.",

                "missing_concepts":
                    [],

                "extracted_concepts":
                    [],

                "next_question_type":
                    "basic",

                "remaining_time_seconds":
                    max(
                        0,
                        session["expires_at"]
                        - int(time.time())
                    )
            }
        )

    current_time = int(
        time.time()
    )

    # --------------------------------------------------------
    # TOTAL INTERVIEW TIME CHECK
    # --------------------------------------------------------

    if current_time >= session[
        "expires_at"
    ]:

        session["status"] = "ended"

        result = {

            "status":
                "success",

            "interview_ended":
                True,

            "reason":
                "total_time_expired",

            "score":
                0,

            "feedback":
                "Interview time has ended.",

            "missing_concepts":
                [],

            "extracted_concepts":
                [],

            "next_question_type":
                "basic",

            "remaining_time_seconds":
                0
        }

        question_data[
            "evaluated"
        ] = True

        question_data[
            "evaluation_result"
        ] = result

        _finish_topic_interview_in_db(
            session
        )

        return result

    # --------------------------------------------------------
    # QUESTION TIMER
    # --------------------------------------------------------

    question_started_at = question_data.get(

        "started_at",

        session.get(
            "question_started_at",
            current_time
        )
    )

    question_time_expired = (

        current_time
        - question_started_at

        >= INTERVIEW_QUESTION_TIME_SECONDS
    )

    candidate_answer = (
        request.candidate_answer.strip()
    )

    # --------------------------------------------------------
    # EMPTY / SKIPPED ANSWER
    # --------------------------------------------------------

    if not candidate_answer:

        skipped_concepts = (
            _extract_skipped_question_concepts(

                topic=
                    session["topic"],

                question=
                    question_data["question"],

                expected_answer=
                    question_data.get(
                        "expected_answer",
                        ""
                    )
            )
        )

        result = {

            "score":
                0,

            "max_score":
                question_data.get(
                    "max_score",
                    10
                ),

            "technical_correctness":
                "Not evaluated because no answer was provided.",

            "understanding":
                "No answer was provided.",

            "completeness":
                "No answer was provided.",

            "accuracy":
                "No answer was provided.",

            "relevance":
                "No answer was provided.",

            "communication_quality":
                "No answer was provided.",

            "problem_solving":
                "No answer was provided.",

            "strengths":
                [],

            "missing_points":
                skipped_concepts,

            "improvement":
                (
                    "Provide an answer addressing the main concepts "
                    "asked in the question."
                ),

            "feedback":
                "No answer was provided for this question.",

            "missing_concepts":
                skipped_concepts,

            "extracted_concepts":
                [],

            "next_question_type":
                "basic"
        }

    else:

        # ----------------------------------------------------
        # NEW MEANING-BASED ASSESSMENT AI
        # ----------------------------------------------------

        result = evaluate_topic_interview_answer(
            topic=session["topic"],
            question=question_data["question"],
            candidate_answer=candidate_answer,
            expected_answer=question_data.get(
                "expected_answer",
                ""
            ),
            evaluation_criteria=question_data.get(
            "evaluation_criteria",
            {}
            )
        )

        if not isinstance(
            result,
            dict
        ):

            result = {}

        # Keep old frontend-compatible fields.

        result.setdefault(
            "missing_concepts",
            result.get(
                "missing_points",
                []
            )
        )

        result.setdefault(
            "extracted_concepts",
            []
        )

        result.setdefault(
            "next_question_type",
            "basic"
        )

        result.setdefault(
            "max_score",
            question_data.get(
                "max_score",
                10
            )
        )

    # --------------------------------------------------------
    # READ RESULT
    # --------------------------------------------------------

    score = result.get(
        "score",
        0
    )

    feedback = result.get(
        "feedback",
        ""
    )

    missing_concepts = result.get(
        "missing_concepts",
        result.get(
            "missing_points",
            []
        )
    )

    extracted_concepts = result.get(
        "extracted_concepts",
        []
    )

    next_question_type = result.get(
        "next_question_type",
        "basic"
    )

    # --------------------------------------------------------
    # UPDATE SESSION
    # --------------------------------------------------------

    session[
        "last_candidate_answer"
    ] = candidate_answer

    session[
        "last_score"
    ] = score

    session[
        "last_feedback"
    ] = feedback

    session[
        "last_missing_concepts"
    ] = missing_concepts

    session[
        "last_extracted_concepts"
    ] = extracted_concepts

    session[
        "next_question_type"
    ] = next_question_type

    # --------------------------------------------------------
    # SAVE QUESTION HISTORY
    # --------------------------------------------------------

    session[
        "history"
    ].append({

        "question_number":
            session[
                "question_number"
            ],

        "topic":
            session["topic"],

        "level":
            session["level"],

        "question":
            question_data["question"],

        "candidate_answer":
            candidate_answer,

        "score":
            score,

        "max_score":
            result.get(
                "max_score",
                10
            ),

        "feedback":
            feedback,

        "missing_concepts":
            missing_concepts,

        "extracted_concepts":
            extracted_concepts,

        "question_time_expired":
            question_time_expired
    })

    # --------------------------------------------------------
    # SAVE ANSWER TO DATABASE
    # --------------------------------------------------------

    attempt_question_id = question_data.get(
        "db_attempt_question_id"
    )

    answer_id = None

    if attempt_question_id:

        answer_id = save_interview_answer(

            attempt_question_id=
                attempt_question_id,

            answer_text=
                candidate_answer,

            answer_transcript=
                candidate_answer
        )

        # ----------------------------------------------------
        # SAVE COMPLETE QUESTION-LEVEL AI EVALUATION
        # ----------------------------------------------------

        evaluation_details = dict(
            result
        )

        evaluation_details[
            "question_time_expired"
        ] = question_time_expired

        evaluation_details[
            "next_question_type"
        ] = next_question_type

        save_question_evaluation(

            answer_id=
                answer_id,

            score=
                score,

            feedback=
                feedback,

            evaluation_details=
                evaluation_details
        )

    # --------------------------------------------------------
    # REMAINING TOTAL TIME
    # --------------------------------------------------------

    remaining_time = max(

        0,

        session["expires_at"]
        - current_time
    )

    if remaining_time <= 0:

        session["status"] = "ended"

    response = {

        "status":
            "success",

        "interview_ended":
            session["status"] == "ended",

        "score":
            score,

        "max_score":
            result.get(
                "max_score",
                10
            ),

        "feedback":
            feedback,

        "missing_concepts":
            missing_concepts,

        "extracted_concepts":
            extracted_concepts,

        "next_question_type":
            next_question_type,

        "remaining_time_seconds":
            remaining_time
    }

    # --------------------------------------------------------
    # CACHE EVALUATION
    # --------------------------------------------------------

    question_data[
        "evaluated"
    ] = True

    question_data[
        "evaluation_result"
    ] = response

    # --------------------------------------------------------
    # FINALIZE IF TOTAL TIME ENDED
    # --------------------------------------------------------

    if session["status"] == "ended":

        _finish_topic_interview_in_db(
            session
        )

    return response


# ============================================================
# ADMIN INTERVIEW STATUS
# ============================================================

@app.get("/interview/status/{session_id}")
def get_admin_interview_status(
    session_id: str
):

    session = INTERVIEW_SESSIONS.get(
        session_id
    )

    if not session:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    current_time = int(
        time.time()
    )

    remaining_time = max(

        0,

        session["expires_at"]
        - current_time
    )

    if remaining_time <= 0:

        session["status"] = "ended"

        _finish_topic_interview_in_db(
            session
        )

    return {

        "status":
            "success",

        "session_id":
            session_id,

        "topic":
            session["topic"],

        "level":
            session["level"],

        "interview_status":
            session["status"],

        "question_number":
            session["question_number"],

        "remaining_time_seconds":
            remaining_time,

        "question_time_seconds":
            INTERVIEW_QUESTION_TIME_SECONDS,

        "history":
            session["history"],

        "final_analysis":
            session.get(
                "final_analysis"
            )
    }


# ============================================================
# END ADMIN INTERVIEW
# ============================================================

@app.post("/interview/end/{session_id}")
def end_admin_interview(
    session_id: str
):

    session = INTERVIEW_SESSIONS.get(
        session_id
    )

    if not session:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    session["status"] = "ended"

    # --------------------------------------------------------
    # FINAL DATABASE EVALUATION
    # --------------------------------------------------------

    _finish_topic_interview_in_db(
        session
    )

    return {

        "status":
            "success",

        "message":
            "Interview ended successfully",

        "session_id":
            session_id,

        "topic":
            session["topic"],

        "level":
            session["level"],

        "questions_answered":
            len(
                session["history"]
            ),

        "history":
            session["history"],

        "final_analysis":
            session.get(
                "final_analysis"
            ),

        "assessment_id":
            session.get(
                "assessment_id"
            ),

        "attempt_id":
            session.get(
                "attempt_id"
            )
    }