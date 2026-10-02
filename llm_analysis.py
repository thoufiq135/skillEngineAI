import json
import re
import time

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
# OLLAMA MODEL
# ============================================================

llm = ChatOllama(
    model="qwen2.5:1.5b",
    temperature=0,
    num_predict=700,
    num_ctx=4096,
    keep_alive="60m"
)


# ============================================================
# PROMPT
# ============================================================

prompt = """

You are a resume information extraction system.

Read the complete resume carefully and extract information ONLY
from the resume.

This system must work dynamically for ANY resume.

Do not use hard-coded skills, job titles, company names,
project names, industries, professions, technologies, or
predefined lists.

Do not assume what type of resume this is.


GENERAL RULES:

1. Never invent information.

2. Never guess information.

3. Never infer information that is not explicitly supported
   by the resume.

4. Preserve information from the resume accurately.

5. Do not unnecessarily duplicate information.

6. Every item in every output array must be a plain string.

7. Never return Python dictionaries.

8. Never return dictionary-like strings.

9. Never return JSON objects inside arrays.

10. Review the complete resume before producing the result.

11. Extract all relevant items from the complete resume.


SKILLS:

Extract the technical skills explicitly mentioned in the resume.

Skills may appear in dedicated skills sections, technical sections,
tools sections, technologies sections, programming sections,
or other places where the resume explicitly identifies them
as skills.

Do not use a predefined skill list.

Do not invent skills.

Do not infer skills merely because they appear in a project,
internship, experience, certification, or education description.

Do not include ordinary spoken or human languages as technical
skills.

Programming languages explicitly identified as skills must be
included.

If multiple individual skills are grouped under a category,
extract each individual skill separately.

Do not return a category followed by multiple skills as one item.

Preserve the actual skill names from the resume.


PROJECTS:

Extract ALL explicitly listed projects from the complete resume.

Do not stop after finding a few projects.

Preserve project names or titles as they appear in the resume.

Do not rename projects.

Do not summarize project names.

Do not replace project names with descriptions.

Do not invent project names.

Every project must be a plain string.


INTERNSHIPS:

Identify all entries that are explicitly described as internships
or internship-type positions.

Preserve the complete internship entry including:

- role
- organization
- duration
- date range

if explicitly present in the resume.

Do not calculate duration.

Do not invent dates.

These entries will be moved into the final experience array
during post-processing.

Therefore, return internship entries here when they are found.


EXPERIENCE:

Extract genuine professional work experience that is not an
internship.

Do not classify something as professional experience merely
because it appears under an Experience heading.

Preserve explicitly stated:

- role
- organization
- duration
- date range

Do not calculate duration.

Do not invent dates.

If there is no genuine professional experience, return an
empty array.


DURATION:

For internships and professional experience:

- Preserve explicitly written durations.
- Preserve explicitly written date ranges.
- Do not calculate duration.
- Do not estimate duration.
- Do not invent missing dates.
- Do not convert dates into months or years unless the resume
  explicitly states that duration.


CERTIFICATIONS:

Extract all explicitly listed certifications from the complete resume.

Do not invent certifications.

Preserve relevant certification details explicitly supported
by the resume.

Each certification must be a plain string.


EDUCATION:

Extract all explicitly listed education information.

Preserve relevant degree, institution, field of study,
academic years, duration, percentage, CGPA, and other
explicitly stated academic information.

Each education item must be a plain string.

Do not return dictionaries or objects.


FINAL VALIDATION:

Before returning the result:

1. Review the complete resume again.

2. Make sure all explicitly listed projects are included.

3. Make sure all explicitly listed internships are included.

4. Preserve explicit internship durations and date ranges.

5. Make sure all explicitly listed professional experience
   is included.

6. Do not invent missing information.

7. Make sure skills are individual skill items.

8. Make sure certifications are included when explicitly present.

9. Make sure education is included when explicitly present.

10. Every array item must be a plain string.

11. Return exactly these six fields:

skills
projects
internships
experience
certifications
education

12. Every field must contain an array.

13. If a category does not exist in the resume, return an empty array.


OUTPUT:

Return exactly one valid JSON object.

Do not return markdown.

Do not return explanations.

Do not return comments.

Do not return headings.

Do not return any text before or after the JSON object.


RESUME TEXT:

{resume}

"""


# ============================================================
# PROMPT CHAIN
# ============================================================

prompt_template = ChatPromptTemplate.from_template(prompt)

chain = prompt_template | llm


# ============================================================
# JSON CLEANER
# ============================================================

def clean_json_response(raw_text):
    """
    Safely extract one JSON object from the model response.
    """

    if not raw_text:
        return None

    text = raw_text.strip()

    # Remove markdown code fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    # Direct JSON parsing
    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    # Try extracting JSON object from extra text
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = text[start:end + 1]

        try:
            data = json.loads(candidate)

            if isinstance(data, dict):
                return data

        except Exception:
            pass

    return None


# ============================================================
# LIST NORMALIZER
# ============================================================

def normalize_list(value):
    """
    Convert model output into a clean list of strings.
    """

    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    result = []
    seen = set()

    for item in value:

        if item is None:
            continue

        # If model accidentally returns a dictionary,
        # convert it into readable text.
        if isinstance(item, dict):

            parts = []

            for key, val in item.items():

                if val is None:
                    continue

                key_text = str(key).strip()
                val_text = str(val).strip()

                if key_text and val_text:
                    parts.append(
                        f"{key_text}: {val_text}"
                    )

            item = " - ".join(parts)

        else:
            item = str(item)

        item = item.strip()

        if not item:
            continue

        # Remove accidental bullets
        item = re.sub(
            r"^\s*(?:[-*•]|\d+[.)])\s*",
            "",
            item
        ).strip()

        if not item:
            continue

        key = item.lower()

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


# ============================================================
# SKILL NORMALIZER
# ============================================================

def normalize_skills(skills):
    """
    Convert grouped skill strings into individual skill strings.

    This logic is generic and does not contain any
    predefined skill names.
    """

    skills = normalize_list(skills)

    result = []
    seen = set()

    for skill in skills:

        text = skill.strip()

        if not text:
            continue

        # If the model returns:
        #
        # Category: Skill A, Skill B, Skill C
        #
        # remove the category prefix.
        if ":" in text:

            prefix, remainder = text.split(":", 1)

            if remainder.strip():
                text = remainder.strip()

        # Split comma-separated individual skills
        parts = [
            part.strip()
            for part in re.split(r",", text)
            if part.strip()
        ]

        for part in parts:

            if not part:
                continue

            key = part.lower()

            if key not in seen:
                seen.add(key)
                result.append(part)

    return result


# ============================================================
# TEXT NORMALIZATION FOR MATCHING
# ============================================================

def normalize_for_matching(text):
    """
    Normalize text only for comparison.

    Original text is never changed.
    """

    if not text:
        return ""

    text = str(text).lower()

    # Remove punctuation
    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text
    )

    # Normalize spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# CLEAN DUPLICATE DATES
# ============================================================

def clean_duplicate_dates(text):
    """
    Remove accidental repeated year/date fragments
    generated by the model.

    Example:
    Jul 2026 - 2026 - Present

    becomes:
    Jul 2026 - Present
    """

    if not text:
        return text

    text = str(text).strip()

    # Example:
    # Jul 2026 - 2026 - Present
    # June 2026 - 2026 - Present
    #
    # Remove repeated year before Present.

    text = re.sub(
        r"(\b(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|September|Oct|October|Nov|November|Dec|December)\s+\d{4})\s*-\s*\d{4}\s*-\s*(Present|Current)",
        r"\1 - \2",
        text,
        flags=re.IGNORECASE
    )

    # Remove accidental duplicate year:
    # 2026 - 2026 - Present
    text = re.sub(
        r"\b(\d{4})\s*-\s*\1\s*-\s*(Present|Current)",
        r"\1 - \2",
        text,
        flags=re.IGNORECASE
    )

    # Normalize repeated spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# CLEAN LIST DATES
# ============================================================

def clean_dates_in_list(items):
    """
    Clean accidental duplicate dates from every item.
    """

    cleaned = []

    for item in normalize_list(items):

        item = clean_duplicate_dates(item)

        if item:
            cleaned.append(item)

    return normalize_list(cleaned)


# ============================================================
# INTERNSHIP / EXPERIENCE MATCHING
# ============================================================

def internship_matches_experience(
    internship,
    experience
):
    """
    Check whether an internship entry and an experience
    entry represent the same position.

    No specific skill, company, role, or profession is used.
    """

    internship_norm = normalize_for_matching(
        internship
    )

    experience_norm = normalize_for_matching(
        experience
    )

    if not internship_norm or not experience_norm:
        return False

    # Direct match
    if internship_norm in experience_norm:
        return True

    if experience_norm in internship_norm:
        return True

    # Compare meaningful words
    internship_words = set(
        internship_norm.split()
    )

    experience_words = set(
        experience_norm.split()
    )

    # Generic words that should not decide identity
    generic_words = {
        "intern",
        "internship",
        "experience",
        "present",
        "current",
        "work",
        "role",
        "position"
    }

    internship_words -= generic_words
    experience_words -= generic_words

    if not internship_words or not experience_words:
        return False

    common_words = (
        internship_words.intersection(
            experience_words
        )
    )

    smaller_size = min(
        len(internship_words),
        len(experience_words)
    )

    if smaller_size == 0:
        return False

    overlap_ratio = (
        len(common_words) / smaller_size
    )

    return overlap_ratio >= 0.6


# ============================================================
# MOVE INTERNSHIPS TO EXPERIENCE
# ============================================================

def move_internships_to_experience(
    internships,
    experience
):
    """
    Move all internship entries into experience.

    Final rule:
    - internships will always be empty.
    - internship entries are stored in experience.
    - genuine professional experience is preserved.
    - duplicate entries are not added twice.
    - original information is preserved.
    """

    # Start with genuine professional experience
    clean_experience = clean_dates_in_list(
        experience
    )

    # Process every internship
    for internship in clean_dates_in_list(
        internships
    ):

        internship_text = str(
            internship
        ).strip()

        if not internship_text:
            continue

        duplicate_found = False

        for exp in clean_experience:

            if internship_matches_experience(
                internship_text,
                exp
            ):
                duplicate_found = True
                break

        # Add internship to experience only
        # when it is not already present.
        if not duplicate_found:

            clean_experience.append(
                internship_text
            )

    return normalize_list(
        clean_experience
    )


# ============================================================
# RESUME ANALYSIS
# ============================================================

def analyze_resume(resume_text):

    if not resume_text or not resume_text.strip():

        return {
            "skills": [],
            "projects": [],
            "internships": [],
            "experience": [],
            "certifications": [],
            "education": []
        }

    resume_text = resume_text.strip()

    print("========================================")
    print(
        "Resume characters:",
        len(resume_text)
    )
    print(
        "Starting Ollama resume analysis..."
    )
    print("========================================")

    start_time = time.time()

    try:

        response = chain.invoke(
            {
                "resume": resume_text
            }
        )

        elapsed = (
            time.time() - start_time
        )

        print(
            "Total Ollama/LangChain Time:",
            round(elapsed, 2),
            "sec"
        )

        # ----------------------------------------------------
        # Get model text safely
        # ----------------------------------------------------

        raw_text = ""

        if hasattr(response, "content"):

            raw_text = response.content

        elif isinstance(response, str):

            raw_text = response

        else:

            raw_text = str(response)

        raw_text = raw_text.strip()

        print("Raw model output:")
        print(raw_text)

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        data = clean_json_response(
            raw_text
        )

        if data is None:

            print(
                "WARNING: Model did not return valid JSON."
            )

            return {
                "skills": [],
                "projects": [],
                "internships": [],
                "experience": [],
                "certifications": [],
                "education": []
            }

        # ----------------------------------------------------
        # Normalize all six fields
        # ----------------------------------------------------

        skills = normalize_skills(
            data.get("skills", [])
        )

        projects = normalize_list(
            data.get("projects", [])
        )

        internships = normalize_list(
            data.get("internships", [])
        )

        experience = normalize_list(
            data.get("experience", [])
        )

        certifications = normalize_list(
            data.get("certifications", [])
        )

        education = normalize_list(
            data.get("education", [])
        )

        # ----------------------------------------------------
        # MOVE ALL INTERNSHIPS INTO EXPERIENCE
        # ----------------------------------------------------

        experience = move_internships_to_experience(
            internships,
            experience
        )

        # Final rule:
        # internships must always be empty.
        internships = []

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        result = {
            "skills": skills,
            "projects": projects,
            "internships": internships,
            "experience": experience,
            "certifications": certifications,
            "education": education
        }

        # ----------------------------------------------------
        # Final output
        # ----------------------------------------------------

        print("========================================")
        print(
            "Final extracted resume data:"
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

        print("========================================")

        return result

    except Exception as e:

        elapsed = (
            time.time() - start_time
        )

        print("========================================")
        print(
            "RESUME ANALYSIS ERROR"
        )
        print(
            "Time:",
            round(elapsed, 2),
            "sec"
        )
        print(
            "Error:",
            repr(e)
        )
        print("========================================")

        return {
            "skills": [],
            "projects": [],
            "internships": [],
            "experience": [],
            "certifications": [],
            "education": []
        }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    from resume_parser import extract_text

    resume_path = "Meghanjani_Resume.pdf"

    print("Reading resume...")

    resume_text = extract_text(
        resume_path
    )

    result = analyze_resume(
        resume_text
    )

    print(
        "\n========== FINAL JSON =========="
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )