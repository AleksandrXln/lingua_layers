# ===== САЙДБАР =================================================
st.sidebar.header("Термины")
search = st.sidebar.text_input("Поиск")

concepts = [(c["id"], c["term"]) for c in all_concepts(db)]
if search:
    concepts = [c for c in concepts if search.lower() in c[1].lower()]

# инициализация выбранного id
if "selected_id" not in st.session_state and concepts:
    st.session_state["selected_id"] = concepts[0][0]

for idx, (cid, title) in enumerate(concepts):
    sel = (st.session_state["selected_id"] == cid)
    dot = "●" if sel else "○"

    col_dot, col_lbl, col_bin = st.sidebar.columns([1, 7, 1])

    with col_dot:
        st.markdown(
            f"<div style='text-align:center;font-size:18px;color:#16a34a;'>{dot}</div>",
            unsafe_allow_html=True
        )

    with col_lbl:
        if st.button(
            title,
            key=f"choose_{idx}_{cid}",
            help="Выбрать термин",
            use_container_width=True,
        ):
            st.session_state["selected_id"] = cid

    with col_bin:
        if st.button(
            "🗑️",
            key=f"del_{idx}_{cid}",
            help="Удалить термин",
        ):
            st.session_state["delete_request"] = cid

selected_id = st.session_state.get("selected_id")
