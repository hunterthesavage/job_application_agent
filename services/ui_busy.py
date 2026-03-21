import streamlit as st


def app_is_busy() -> bool:
    return bool(st.session_state.get("_app_busy", False))


def current_busy_label() -> str:
    return str(st.session_state.get("_app_busy_label", "")).strip()


def start_busy(label: str) -> None:
    st.session_state["_app_busy"] = True
    st.session_state["_app_busy_label"] = str(label or "").strip()


def stop_busy() -> None:
    st.session_state["_app_busy"] = False
    st.session_state["_app_busy_label"] = ""


def _pending_key(scope: str) -> str:
    return f"_pending_action_{scope}"


def queue_action(scope: str, action_type: str, payload: dict | None = None, label: str = "") -> None:
    start_busy(label or action_type)
    st.session_state[_pending_key(scope)] = {
        "type": action_type,
        "payload": payload or {},
        "label": label or action_type,
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
