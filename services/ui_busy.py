from __future__ import annotations

import streamlit as st


ACTION_LABELS = {
    "discover_and_ingest": "Run Jobs",
    "save_run_inputs": "Save Run Inputs",
    "discover_only": "Find Job Links Only",
    "ingest_saved": "Add Saved Job Links",
    "ingest_pasted": "Add Pasted Job Links",
    "rescore_existing_jobs": "Rescore Existing Jobs",
    "refresh_source_registry": "Refresh Source Registry",
    "health_check": "Run Health Check",
}


def _humanize_action_label(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    if raw in ACTION_LABELS:
        return ACTION_LABELS[raw]

    return raw.replace("_", " ").strip().title()


def app_is_busy() -> bool:
    return bool(st.session_state.get("_app_busy", False))


def current_busy_label() -> str:
    raw = str(st.session_state.get("_app_busy_label", "")).strip()
    return _humanize_action_label(raw)


def start_busy(label: str) -> None:
    st.session_state["_app_busy"] = True
    st.session_state["_app_busy_label"] = str(label or "").strip()


def stop_busy() -> None:
    st.session_state["_app_busy"] = False
    st.session_state["_app_busy_label"] = ""


def _pending_key(scope: str) -> str:
    return f"_pending_action_{scope}"


def queue_action(scope: str, action_type: str, payload: dict | None = None, label: str = "") -> None:
    resolved_label = str(label or "").strip() or _humanize_action_label(action_type)

    start_busy(resolved_label)
    st.session_state[_pending_key(scope)] = {
        "type": action_type,
        "payload": payload or {},
        "label": resolved_label,
        "phase": "prepare",
    }


def get_action(scope: str) -> dict | None:
    return st.session_state.get(_pending_key(scope))


def move_action_to_execute(scope: str) -> None:
    action = get_action(scope)
    if not action:
        return
    action["phase"] = "execute"
    st.session_state[_pending_key(scope)] = action


def clear_action(scope: str) -> None:
    st.session_state.pop(_pending_key(scope), None)
