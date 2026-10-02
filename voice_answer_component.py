import json
from pathlib import Path

import streamlit.components.v1 as components


# ============================================================
# VOICE COMPONENT FRONTEND
# ============================================================

_COMPONENT_DIR = (
    Path(__file__).resolve().parent
    / "voice_answer_component_frontend"
)


# ============================================================
# STREAMLIT COMPONENT
# ============================================================

_voice_component = components.declare_component(
    name="voice_answer_component_v2",
    path=str(_COMPONENT_DIR),
)


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def voice_answer_component(
    question,
    initial_text="",
    key=None,
):
    result = _voice_component(
        question=question or "",
        initial_text=initial_text or "",
        key=key,
        default={
            "text": initial_text or "",
            "event": "",
        },
    )

    # --------------------------------------------------------
    # Component returned a dictionary
    # --------------------------------------------------------

    if isinstance(result, dict):
        return result

    # --------------------------------------------------------
    # Component returned JSON string
    # --------------------------------------------------------

    if isinstance(result, str):

        try:
            parsed = json.loads(result)

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

        return {
            "text": result,
            "event": "",
        }

    # --------------------------------------------------------
    # Safe fallback
    # --------------------------------------------------------

    return {
        "text": initial_text or "",
        "event": "",
    }