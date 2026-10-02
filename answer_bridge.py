import os
import streamlit.components.v1 as components


answer_component = components.declare_component(
    "answer_bridge",
    path=os.path.join(
        os.path.dirname(__file__),
        "answer_bridge"
    )
)


def get_candidate_answer(question="", skip_enabled=True):

    # Use a question-specific component key.
    # This forces Streamlit to create a fresh component
    # whenever the question changes, preventing the previous
    # __SUBMIT__ / __SKIP__ event from being reused.
    question_key = str(question).strip()

    safe_key = (
        "candidate_answer_bridge_"
        + str(abs(hash(question_key)))
    )

    return answer_component(
        question=question,
        skip_enabled=skip_enabled,
        default="",
        key=safe_key
    )

