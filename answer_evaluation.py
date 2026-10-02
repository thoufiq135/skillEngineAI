
import json
import re
import time

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
# EVALUATION CONFIGURATION
# ============================================================

model = ChatOllama(
    model="llama3.2:3b",
    temperature=0.1,
    num_predict=300,
    num_ctx=2048,
    keep_alive="30m",
    format="json"
)


# ============================================================
# EVALUATION PROMPT
# ============================================================

prompt = ChatPromptTemplate.from_template("""
Evaluate this technical interview answer.

Skill: {current_skill}

Question:
{question}

Reference / Expected Answer:
{expected_answer}

Candidate Answer:
{candidate_answer}


IMPORTANT EVALUATION RULES:

1. Evaluate ONLY the candidate's actual answer.

2. Use the expected answer only as a hidden reference for comparison.

3. Do NOT give credit for information that appears only in the expected answer.

4. Do NOT assume the candidate knows something they did not say.

5. Do NOT extract concepts from the question.

6. Do NOT extract concepts from the expected answer.

7. Extracted concepts MUST come ONLY from the candidate's answer.

8. Do NOT invent concepts that the candidate did not mention or clearly demonstrate.

9. Concepts can be technical terms, technologies, tools, methods, features,
   programming concepts, design concepts, frameworks, or important technical ideas.

10. If the candidate gives a technically meaningful answer, carefully identify
    the technical concepts actually present in that answer.

11. Do not return [] for extracted_concepts merely because the answer is not
    worded exactly like the expected answer.

12. If the candidate explicitly mentions a technology or technical concept,
    include it in extracted_concepts.

13. Keep extracted_concepts short and relevant. Usually 1 to 5 concepts.

14. Do not include generic words such as:
    "project", "answer", "work", "thing", "good", "experience"
    unless they are technically meaningful in context.


EXTRACTED CONCEPTS:

Extract the important technical concepts that are explicitly present
or clearly demonstrated in the candidate answer.

Examples:

Candidate:
"I used React components and state management to build the interface."

Extracted concepts:
["React", "components", "state management"]

Candidate:
"I created wireframes and an interactive prototype in Figma."

Extracted concepts:
["wireframes", "interactive prototyping", "Figma"]

Candidate:
"I used reusable components, spacing, visual hierarchy, and auto layout."

Extracted concepts:
["reusable components", "spacing", "visual hierarchy", "auto layout"]

Candidate:
"Yes, I worked on the project and learned a lot."

Extracted concepts:
[]


MISSING CONCEPTS:

Compare the candidate's actual answer against the expected answer.

Identify the important technical concepts that the candidate failed
to mention or explain sufficiently.

Follow these steps:

1. Identify the important technical concepts required by the expected answer.

2. Check whether each concept is actually present in the candidate's answer.

3. If a concept is clearly present in the candidate's answer,
   DO NOT include it in missing_concepts.

4. If an important concept from the expected answer is absent from
   the candidate's answer, include it in missing_concepts.

5. If the candidate mentions a concept only partially, include the
   missing specific part when it is technically important.

6. Do NOT copy complete sentences from the expected answer.

7. Return short concept names or short technical phrases only.

8. Do NOT invent unrelated concepts.

9. Do NOT use the candidate's score to decide missing concepts.

10. Do NOT use the question text alone to create missing concepts.

11. Missing concepts must mainly come from comparing the expected answer
    with the candidate answer.

12. Return at most 5 missing concepts.

13. If the candidate covered all important concepts sufficiently, return [].

Example 1:

Expected Answer:
"Framer.js integrates with React through reusable React components.
Framer Motion provides animations, transitions, and gestures.
React manages component structure and state."

Candidate Answer:
"Framer.js works with React to create interactive interfaces.
It provides animations and transitions."

Missing concepts:
["reusable React components", "gestures", "component structure", "state management"]


Example 2:

Expected Answer:
"Figma supports real-time collaboration, comments, shared components,
version history, and team-based design editing."

Candidate Answer:
"I used Figma to create wireframes and shared the file with my team.
We used comments to discuss changes."

Missing concepts:
["real-time collaboration", "shared components", "version history"]


Example 3:

Expected Answer:
"React Native provides native mobile components and platform-specific
capabilities for Android and iOS."

Candidate Answer:
"React Native is used for mobile applications on Android and iOS."

Missing concepts:
["native mobile components", "platform-specific capabilities"]


Example 4:

Expected Answer:
"Figma is a browser-based collaborative design tool with real-time
editing, comments, shared components, and version history."

Candidate Answer:
"Figma allows team members to work remotely, use comments, and share
designs."

Missing concepts:
["real-time editing", "shared components", "version history"]


SCORING:

Give a score from 0 to 10 based ONLY on the candidate's actual answer.

0 = wrong, irrelevant, skipped, or no answer
1-2 = very poor
3-4 = weak
5-6 = partially correct
7-8 = good
9 = very strong
10 = excellent and complete


FEEDBACK:

Give exactly ONE short sentence explaining the main reason for the score.


ROUTING:

score > 6 + extracted_concepts found
    -> concept_follow_up

score > 6 + no extracted_concepts
    -> skill_deep

score <= 6
    -> basic

Do NOT generate the next question.


OUTPUT:

Return ONLY valid JSON.

Use exactly this structure:

{{
    "score": 0,
    "feedback": "",
    "missing_concepts": [],
    "extracted_concepts": [],
    "next_question_type": "basic"
}}

The values above are placeholders.

Calculate the REAL result from the candidate answer.

IMPORTANT:

- score must be a number between 0 and 10
- feedback must be one short sentence
- missing_concepts must be a JSON array of strings
- extracted_concepts must be a JSON array of strings
- next_question_type must be one of:
  "basic"
  "concept_follow_up"
  "skill_deep"
- Do not return markdown
- Do not return explanations outside JSON
- Do not return empty concepts when technical concepts are clearly present
""")


chain = prompt | model



# ============================================================
# TOPIC INTERVIEW AI EVALUATION
# ============================================================

topic_interview_prompt = ChatPromptTemplate.from_template("""
Evaluate the candidate's technical interview answer.

Topic:
{topic}

Question:
{question}

Reference / Expected Answer:
{expected_answer}

Evaluation Criteria:
{evaluation_criteria}

Candidate Answer:
{candidate_answer}


IMPORTANT RULES:

1. Evaluate ONLY what the candidate actually said.

2. Use the expected answer and evaluation criteria only as references
   for judging correctness and completeness.

3. Do NOT give credit for information that appears only in the
   expected answer.

4. Do NOT assume knowledge that the candidate did not demonstrate.

5. Evaluate the meaning and technical correctness of the answer,
   not exact keyword matching.

6. Consider:
   - technical correctness
   - understanding
   - completeness
   - accuracy
   - relevance
   - communication
   - problem solving when applicable

7. Identify strengths that are actually demonstrated by the candidate.

8. Identify important points from the expected answer that the candidate
   missed or explained insufficiently.

9. Do not invent strengths or missing points.

10. Keep strengths and missing_points concise and specific.

11. Give a score from 0 to 10.

SCORING:

0 = wrong, irrelevant, skipped, or no answer
1-2 = very poor
3-4 = weak
5-6 = partially correct
7-8 = good
9 = very strong
10 = excellent and complete


OUTPUT:

Return ONLY valid JSON.

Use exactly this structure:

{{
    "score": 0,
    "max_score": 10,
    "technical_correctness": "",
    "understanding": "",
    "strengths": [],
    "missing_points": [],
    "improvement": "",
    "feedback": ""
}}

IMPORTANT:

- score must be a number from 0 to 10
- max_score must be 10
- technical_correctness must be a short assessment
- understanding must be a short assessment
- strengths must be a JSON array of short strings
- missing_points must be a JSON array of short strings
- improvement must be one concise improvement suggestion
- feedback must be one short explanation of the score
- Do not return markdown
- Do not return explanations outside JSON
""")


topic_interview_chain = (
    topic_interview_prompt
    | model
)


def evaluate_topic_interview_answer(
    topic,
    question,
    candidate_answer,
    expected_answer="",
    evaluation_criteria=None
):

    if evaluation_criteria is None:
        evaluation_criteria = {}

    response = topic_interview_chain.invoke({

        "topic":
            topic,

        "question":
            question,

        "expected_answer":
            expected_answer,

        "evaluation_criteria":
            json.dumps(
                evaluation_criteria,
                ensure_ascii=False
            ),

        "candidate_answer":
            candidate_answer
    })

    raw_response = response.content

    print("\n========== TOPIC INTERVIEW EVALUATION ==========")
    print(raw_response)

    result = extract_json(raw_response)

    if result is None:

        print(
            "\n⚠️ Topic Interview JSON parsing failed."
        )

        result = {
            "score": 0,
            "max_score": 10,
            "technical_correctness": "Unable to evaluate",
            "understanding": "Unable to evaluate",
            "strengths": [],
            "missing_points": [],
            "improvement": "Please provide a clearer technical answer.",
            "feedback": "The answer could not be evaluated correctly."
        }

    return result


# ============================================================
# JSON PARSER
# ============================================================

def extract_json(text):
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find a JSON object inside the response
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return None


# ============================================================
# PLAIN TEXT FALLBACK PARSER
# ============================================================

def parse_plain_text_response(text):
    result = {
        "score": 0,
        "feedback": "",
        "missing_concepts": [],
        "extracted_concepts": [],
        "next_question_type": "basic"
    }

    # ---------------- SCORE ----------------

    score_match = re.search(
        r"(?:score|Score)\s*[:\-]?\s*(\d+(?:\.\d+)?)",
        text
    )

    if score_match:
        try:
            result["score"] = float(score_match.group(1))
        except Exception:
            result["score"] = 0

    # ---------------- FEEDBACK ----------------

    feedback_match = re.search(
        r"(?:feedback|Feedback)\s*[:\-]?\s*(.*?)(?=\n"
        r"(?:missing|Missing|extracted|Extracted|next|Next)|$)",
        text,
        re.DOTALL
    )

    if feedback_match:
        result["feedback"] = feedback_match.group(1).strip()

    # ---------------- MISSING CONCEPTS ----------------

    missing_match = re.search(
        r"(?:missing concepts|Missing Concepts)\s*[:\-]?\s*(.*?)(?=\n"
        r"(?:extracted|Extracted|next|Next)|$)",
        text,
        re.DOTALL
    )

    if missing_match:
        value = missing_match.group(1).strip()

        if value.lower() not in ["", "none", "none.", "[]"]:
            try:
                parsed = json.loads(value)

                if isinstance(parsed, list):
                    result["missing_concepts"] = [
                        str(x).strip()
                        for x in parsed
                        if str(x).strip()
                    ]

            except Exception:
                result["missing_concepts"] = [
                    x.strip()
                    for x in re.split(r",|\band\b", value)
                    if x.strip()
                ]

    # ---------------- EXTRACTED CONCEPTS ----------------

    extracted_match = re.search(
        r"(?:extracted concepts|Extracted Concepts)\s*[:\-]?\s*(.*?)(?=\n"
        r"(?:next|Next)|$)",
        text,
        re.DOTALL
    )

    if extracted_match:
        value = extracted_match.group(1).strip()

        if value.lower() not in ["", "none", "none.", "[]"]:
            try:
                parsed = json.loads(value)

                if isinstance(parsed, list):
                    result["extracted_concepts"] = [
                        str(x).strip()
                        for x in parsed
                        if str(x).strip()
                    ]

            except Exception:
                result["extracted_concepts"] = [
                    x.strip()
                    for x in re.split(r",|\band\b", value)
                    if x.strip()
                ]

    # ---------------- QUESTION TYPE ----------------

    type_match = re.search(
        r"(?:next_question_type|Next Question Type)\s*[:\-]?\s*"
        r"([A-Za-z_]+)",
        text
    )

    if type_match:
        result["next_question_type"] = (
            type_match.group(1).strip()
        )

    return result


# ============================================================
# CLEAN RESULT
# ============================================================

def clean_result(result):

    if not isinstance(result, dict):
        result = {}

    # ---------------- SCORE ----------------

    raw_score = result.get("score", 0)

    try:
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)

        else:
            score_text = str(raw_score).strip()

            score_match = re.search(
                r"(\d+(?:\.\d+)?)",
                score_text
            )

            if score_match:
                score = float(score_match.group(1))
            else:
                score = 0

    except Exception:
        score = 0

    score = max(0, min(10, score))

    # ---------------- CONCEPTS ----------------

    missing_concepts = result.get(
        "missing_concepts",
        []
    )

    extracted_concepts = result.get(
        "extracted_concepts",
        []
    )

    if not isinstance(missing_concepts, list):
        missing_concepts = []

    if not isinstance(extracted_concepts, list):
        extracted_concepts = []

    missing_concepts = [
        str(x).strip()
        for x in missing_concepts
        if str(x).strip()
    ]

    extracted_concepts = [
        str(x).strip()
        for x in extracted_concepts
        if str(x).strip()
    ]

    # Remove duplicates while preserving order

    missing_concepts = list(
        dict.fromkeys(missing_concepts)
    )

    extracted_concepts = list(
        dict.fromkeys(extracted_concepts)
    )

    # ---------------- ROUTING ----------------

    if score > 6:

        if extracted_concepts:
            next_question_type = "concept_follow_up"

        else:
            next_question_type = "skill_deep"

    else:
        next_question_type = "basic"

    return {
        "score": score,

        "feedback": str(
            result.get("feedback", "")
        ).strip(),

        "missing_concepts": missing_concepts[:5],

        "extracted_concepts": extracted_concepts[:5],

        "next_question_type": next_question_type
    }


# ============================================================
# EVALUATE ANSWER
# ============================================================

def evaluate_answer(
    current_skill,
    question,
    candidate_answer,
    expected_answer="",
    skill_index=0,
    skills=None,
    next_skill=""
):

    start_time = time.time()

    if skills is None:
        skills = []

    response = chain.invoke({
        "current_skill": current_skill,
        "question": question,
        "expected_answer": expected_answer,
        "candidate_answer": candidate_answer
    })

    raw_response = response.content

    print("\n========== EVALUATION ==========")
    print(raw_response)

    result = extract_json(raw_response)

    if result is None:

        print("\n⚠️ JSON parsing failed.")
        print("Trying plain-text fallback parser...")

        result = parse_plain_text_response(
            raw_response
        )

    result = clean_result(result)

    print(
        f"\n⭐ Score: {result['score']}/10"
    )

    print(
        f"🧠 Extracted Concepts: "
        f"{result['extracted_concepts']}"
    )

    print(
        f"📌 Missing Concepts: "
        f"{result['missing_concepts']}"
    )

    print(
        f"💬 Feedback: "
        f"{result['feedback']}"
    )

    print(
        f"➡️ Next Question Type: "
        f"{result['next_question_type']}"
    )

    elapsed = time.time() - start_time

    print(
        f"\n⏱️ Evaluation Time: "
        f"{elapsed:.2f} seconds"
    )

    print("================================")

    return result
