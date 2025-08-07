# app.py — Lingua Layers v2.3 (2025-08-07)
# ----------------------------------------
import os, json
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt


DATA  = "data/layers.json"
GRAPH = "graphs/latest.png"


# ──────────── helpers: работа с JSON-базой ────────────
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


# ──────────── helpers: рисование графа ───────────────
def draw_subgraph(db, concept_id):
    """строит PNG-граф выбранного узла + его связей"""
    G = nx.DiGraph()

    # добавляем выбранный узел и связи
    for c in all_concepts(db):
        if c["id"] == concept_id:
            G.add_node(c["id"], label=c["term"], main=True)

            # исходящие
            for trg_id in c.get("refs", []):
                trg = next(x for x in all_concepts(db) if x["id"] == trg_id)
                G.add_node(trg["id"], label=trg["term"], main=False)
                G.add_edge(c["id"], trg_id)

            # входящие
            for c2 in all_concepts(db):
                if concept_id in c2.get("refs", []):
                    G.add_node(c2["id"], label=c2["term"], main=False)
                    G.add_edge(c2["id"], concept_id)
            break

    if G.number_of_nodes() == 0:           # нечего рисовать
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return

    pos    = nx.spring_layout(G, seed=42)
    colors = ["#16a34a" if G.nodes[n]["main"] else "#60d394" for n in G]
    plt.figure(figsize=(7, 5))
    nx.draw(G, pos, node_color=colors, with_labels=False,
            node_size=700, arrows=True)
    nx.draw_networkx_labels(G, pos,
                            labels=nx.get_node_attributes(G, "label"),
                            font_size=8)
    plt.axis("off")
    os.makedirs("graphs", exist_ok=True)
    plt.tight_layout()
    plt.savefig(GRAPH, dpi=140, bbox_inches="tight")
    plt.close()


# ──────────────── Streamlit UI ────────────────────────
st.set_page_config("Lingua Layers", layout="wide")
db = load_db()

# --- сохранить выбранный id между рендерами
if "selected_id" not in st.session_state:
    first = next(all_concepts(db), None)
    st.session_state["selected_id"] = first["id"] if first else None


# ======= САЙДБАР: список терминов =====================
st.sidebar.header("Термины")
search = st.sidebar.text_input("Поиск")

concepts = [(c["id"], c["term"]) for c in all_concepts(db)]
if search:
    concepts = [c for c in concepts if search.lower() in c[1].lower()]

for idx, (cid, title) in enumerate(concepts):
    sel = (st.session_state["selected_id"] == cid)
    dot = "●" if sel else "○"

    col_dot, col_txt, col_bin = st.sidebar.columns([1, 7, 1])

    with col_dot:
        st.markdown(
            f"<div style='text-align:center;font-size:18px;"
            f"color:{'#16a34a' if sel else '#6b7280'}'>{dot}</div>",
            unsafe_allow_html=True
        )

   
