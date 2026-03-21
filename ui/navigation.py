from collections.abc import Sequence

import streamlit as st


def initialize_nav_state(state_key: str, default_value: str) -> None:
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value


def render_button_nav(
    options: Sequence[str],
    state_key: str,
    key_prefix: str,
) -> str:
    if not options:
        raise ValueError("options must not be empty")

    current_value = st.session_state.get(state_key, options[0])
    if current_value not in options:
        current_value = options[0]
        st.session_state[state_key] = current_value

    columns = st.columns(len(options))

    for idx, option in enumerate(options):
        is_selected = option == current_value
        if columns[idx].button(
            option,
            key=f"{key_prefix}_{idx}_{option.lower().replace(' ', '_')}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            if option != current_value:
                st.session_state[state_key] = option
                st.rerun()

    return st.session_state.get(state_key, current_value)
