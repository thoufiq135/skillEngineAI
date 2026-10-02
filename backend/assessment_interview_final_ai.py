import json
import re
import time

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
# AI MODEL
# ============================================================

model = ChatOllama(
    model="llama3.2:3b",
    temperature=0.1,
    num_predict=500,
    num_ctx=2048,
    keep_alive="30m",
    format="json"
)


# ============================================================
# FINAL INTERVIEW ANALYSIS PROMPT
# ============================================================

prompt = ChatPromptTemplate.from_template("""
Generate the final interview analysis for a candidate's assessment attempt.

The candidate has answered multiple technical interview questions.

Below are the question-level evaluations.

QUESTION-LEVEL EVALUATIONS:
{evaluations}


IMPORTANT RULES:

1. Base the final analysis ONLY on the provided question-level evaluations.

2. Do not invent skills, strengths, weaknesses, or problems that are not supported
   by the provided evaluations.

3. Consider the candidate's actual demonstrated performance.

4. Technical analysis should summarize technical correctness, understanding,
   completeness, accuracy, and relevant technical strengths or gaps.

5. Communication analysis should be based on the communication quality observed
   in the question-level evaluations.

6. Problem-solving analysis should be based only on problem-solving observations
   that are actually present. If problem-solving was not applicable or not
   evaluated, clearly state that.

7. Identify specific strengths demonstrated across the answers.

8. Identify specific areas for improvement based on missing points and feedback.

9. Recommended learning areas should be directly connected to the identified
   technical gaps.

10. Final feedback should be constructive and specific to this candidate's
    answers.

11. Do not use generic statements that are not supported by the evaluations.

12. Do not perform keyword matching.

13. The overall score and maximum score are calculated outside the AI.
    Do NOT calculate or change them.

14. Return ONLY valid JSON.

Use exactly this structure:

{{
    "strengths": [],
    "areas_for_improvement": [],
    "technical_analysis": "",
    "communication_analysis": "",
    "problem_solving_analysis": "",
    "recommended_learning_areas": [],
    "final_feedback": ""
}}

Additional rules:

- strengths must be a JSON array of strings.
- areas_for_improvement must be a JSON array of strings.
- recommended_learning_areas must be a JSON array of strings.
- technical_analysis must be a concise paragraph.
- communication_analysis must be a concise paragraph.
- problem_solving_analysis must be a concise paragraph.
- final_feedback must be a concise paragraph.
- Do not return markdown.
- Do not return explanations outside JSON.
""")


chain = prompt | model


# ============================================================
# JSON PARSER
# ============================================================

def extract_json(text):

    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)

    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:

        try:
            return json.loads(match.group(0))

        except Exception:
            pass

    return None


# ============================================================
# CLEAN FINAL ANALYSIS
# ============================================================

def clean_final_analysis(result):

    if not isinstance(result, dict):
        result = {}

    strengths = result.get("strengths", [])

    areas_for_improvement = result.get(
        "areas_for_improvement",
        []
    )

    recommended_learning_areas = result.get(
        "recommended_learning_areas",
        []
    )

    if not isinstance(strengths, list):
        strengths = []

    if not isinstance(areas_for_improvement, list):
        areas_for_improvement = []

    if not isinstance(recommended_learning_areas, list):
        recommended_learning_areas = []

    strengths = [
        str(x).strip()
        for x in strengths
        if str(x).strip()
    ]

    areas_for_improvement = [
        str(x).strip()
        for x in areas_for_improvement
        if str(x).strip()
    ]

    recommended_learning_areas = [
        str(x).strip()
        for x in recommended_learning_areas
        if str(x).strip()
    ]

    return {
        "strengths": list(dict.fromkeys(strengths))[:8],

        "areas_for_improvement": list(
            dict.fromkeys(areas_for_improvement)
        )[:8],

        "technical_analysis": str(
            result.get("technical_analysis", "")
        ).strip(),

        "communication_analysis": str(
            result.get("communication_analysis", "")
        ).strip(),

        "problem_solving_analysis": str(
            result.get("problem_solving_analysis", "")
        ).strip(),

        "recommended_learning_areas": list(
            dict.fromkeys(recommended_learning_areas)
        )[:8],

        "final_feedback": str(
            result.get("final_feedback", "")
        ).strip()
    }


# ============================================================
# GENERATE FINAL INTERVIEW ANALYSIS
# ============================================================

def generate_final_interview_analysis(evaluations):

    start_time = time.time()

    if not evaluations:

        return {
            "strengths": [],
            "areas_for_improvement": [],
            "technical_analysis": "",
            "communication_analysis": "",
            "problem_solving_analysis": "",
            "recommended_learning_areas": [],
            "final_feedback": "No interview evaluations were available."
        }

    response = chain.invoke({
        "evaluations": json.dumps(
            evaluations,
            default=str,
            indent=2
        )
    })

    raw_response = response.content

    print(
        "\n========== FINAL INTERVIEW ANALYSIS =========="
    )

    print(raw_response)

    result = extract_json(raw_response)

    if result is None:

        print("JSON parsing failed.")

        result = {
            "strengths": [],
            "areas_for_improvement": [],
            "technical_analysis": "Unable to generate technical analysis.",
            "communication_analysis": "Unable to generate communication analysis.",
            "problem_solving_analysis": "Unable to generate problem-solving analysis.",
            "recommended_learning_areas": [],
            "final_feedback": "Unable to generate final interview analysis."
        }

    result = clean_final_analysis(result)

    elapsed = time.time() - start_time

    print(
        "\nFinal Strengths:",
        result["strengths"]
    )

    print(
        "Areas for Improvement:",
        result["areas_for_improvement"]
    )

    print(
        "Final Feedback:",
        result["final_feedback"]
    )

    print(
        "Analysis Time:",
        f"{elapsed:.2f} seconds"
    )

    print(
        "=============================================="
    )

    return result