# app.py — Lingua Layers v2.6  (08-08-2025)
# полностью автономный файл
import os, json
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

DATA  = "data/layers.json"
GRAPH = "graphs/latest.png"


# ──────────── helpers ─────────────────────────────────────────
def load_db():
    if not os.path.exists(DATA):
        os.makedirs("data", exist_ok=True)
        json.dump({"meta": {}, "layers": []},
                  open(DATA, "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    return json.load(open(DATA, encoding="utf-8"))


def save_db(db):
    json.dump(db, open(DATA, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


def all_concepts(db):
    for layer in db["layers"]:
        for c in layer["library"]["concepts"]:
            yield c


def draw_subgraph(db, cid):
    """рисуем связи выбранного концепта"""
    G = nx.DiGraph()
    for c in all_concepts(db):
        if c["id"] == cid:
            G.add_node(cid, label=c["term"], main=True)
            # исходящие
            for r in c.get("refs", []):
                trg = next(x for x in all_concepts(db) if x["id"] == r)
                G.add_node(r, label=trg["term"], main=False)
                G.add_edge(cid, r)
            # входящие
            for c2 in all_concepts(db):
                if cid in c2.get("refs", []):
                    G.add_node(c2["id"], label=c2["term"], main=False)
                    G.add_edge(c2["id"], cid)
            break

    if not G:                       # ничего не нашли
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return

    pos    = nx.spring_layout(G, seed=42)
    colors = ["#16a34a" if G.nodes[n]["main"] else "#60d394" for n in G]
    plt.figure(figsize=(7, 5))
    nx.draw(G, pos, node_color=colors, node_size=700,
            arrows=True, with_labels=False)
    nx.draw_networkx_labels(G, pos,
                            nx.get_node_attributes(G, "label"),
                            font_size=8)
    plt.axis("off")
    os.makedirs("graphs", exist_ok=True)
    plt.savefig(GRAPH, dpi=140, bbox_inches="tight")
    plt.close()


# ──────────── Streamlit UI ────────────────────────────────────
st.set_page_config("Lingua Layers", layout="wide")
db = load_db()

# состояние выбора
if "selected_id" not in st.session_state:
    first = next(all_concepts(db), None)
    st.session_state["selected_id"] = first["id"] if first else None
sel_id = st.session_state["selected_id"]


# ═════ sidebar: список терминов ═══════════════════════════════
st.sidebar.header("Термины")
query = st.sidebar.text_input("Поиск")

concepts = [(c["id"], c["term"]) for c in all_concepts(db)]
if query:
    concepts = [c for c in concepts if query.lower() in c[1].lower()]

for idx, (cid, title) in enumerate(concepts):
    selected = cid == sel_id
    dot, txt, bin = st.sidebar.columns([1, 6, 1])

    with dot:
        st.markdown(
            f"<div style='text-align:center;font-size:18px;"
            f"color:{'#16a34a' if selected else '#9ca3af'}'>●</div>",
            unsafe_allow_html=True
        )

    with txt:
        if st.button(title, key=f"choose_{idx}_{cid}"):
            st.session_state["selected_id"] = cid
            sel_id = cid

    with bin:
        if st.button("🗑️", key=f"del_{idx}_{cid}", help="Удалить"):
            # мгновенно удаляем
            for layer in db["layers"]:
                layer["library"]["concepts"] = [
                    c for c in layer["library"]["concepts"] if c["id"] != cid
                ]
            for c in all_concepts(db):
                if cid in c.get("refs", []):
                    c["refs"].remove(cid)
            save_db(db)
            if sel_id == cid:
                st.session_state["selected_id"] = None
                sel_id = None
            st.experimental_rerun()          # перерисовать UI


# ═════ Добавить слой ══════════════════════════════════════════
st.subheader("Добавить слой")
with st.form("add_layer"):
    l_alias = st.text_input("Alias слоя")
    l_level = st.number_input("Уровень", 1, 99, 1)
    l_desc  = st.text_area("Описание")
    if st.form_submit_button("Создать слой") and l_alias:
        new_id = str(len(db["layers"]) + 1)
        db["layers"].append({"id": new_id, "alias": l_alias,
                             "level": int(l_level),
                             "description": l_desc,
                             "library": {"concepts": []}})
        save_db(db)
        st.success(f"Слой {new_id} создан.")


# ═════ Добавить термин ════════════════════════════════════════
st.subheader("Добавить термин")
with st.form("add_term"):
    layer_opts = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    if not layer_opts:
        st.info("Сначала создайте слой выше.")
    else:
        l_sel = st.selectbox("Слой", layer_opts)
        term  = st.text_input("Термин")
        defi  = st.text_area("Определение")
        if st.form_submit_button("Сохранить") and term and defi:
            lid   = l_sel.split(" –")[0]
            layer = next(l for l in db["layers"] if l["id"] == lid)
            cid   = f"{lid}.{len(layer['library']['concepts']) + 1}"
            layer["library"]["concepts"].append(
                {"id": cid, "term": term,
                 "definition": defi, "refs": []}
            )
            save_db(db)
            st.session_state["selected_id"] = cid
            st.success(f"Добавлено {cid}")
            st.experimental_rerun()


# ═════ Граф выбранного термина ════════════════════════════════
if sel_id:
    draw_subgraph(db, sel_id)
    if os.path.exists(GRAPH):
        st.image(GRAPH, caption=f"Связи термина {sel_id}")
else:
    st.info("Выберите термин, чтобы увидеть связи.")
