# app.py – Lingua Layers v2 (Python 3.7 friendly)
import os, json, streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

DATA   = "data/layers.json"
GRAPH  = "graphs/latest.png"


# ───────────────────────── БАЗА ДАННЫХ ──────────────────────────
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


# ───────────────────────── РИСОВАНИЕ ГРАФА ──────────────────────
def draw_subgraph(db, concept_id: str):
    """Строит граф: выбранный термин + все входящие/исходящие связи"""
    G = nx.DiGraph()
    # найдём узел и связи
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

    if G.number_of_nodes() == 0:       # нечего рисовать
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return

    pos = nx.spring_layout(G, seed=42)
    colors = ["#1976d2" if G.nodes[n]["main"] else "#42a5f5" for n in G]
    plt.figure(figsize=(7, 5))
    nx.draw(G, pos, node_color=colors, with_labels=False,
            node_size=700, arrows=True)
    labels = nx.get_node_attributes(G, "label")
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    plt.axis("off")
    os.makedirs("graphs", exist_ok=True)
    plt.tight_layout()
    plt.savefig(GRAPH, dpi=140, bbox_inches="tight")
    plt.close()


# ───────────────────────── UI / STREAMLIT ───────────────────────
st.set_page_config("Lingua Layers", layout="wide")
db = load_db()

# ===== Сайдбар: поиск + список + корзина ========================
st.sidebar.header("Термины")
search = st.sidebar.text_input("Поиск")

concepts = [(c["id"], c["term"]) for c in all_concepts(db)]
if search:
    concepts = [c for c in concepts if search.lower() in c[1].lower()]

selected_id = None
for cid, title in concepts:
    col_text, col_bin = st.sidebar.columns([8, 1])
    with col_text:
        if st.radio(" ", [cid], format_func=lambda _: title,
                    key=f"sel_{cid}"):
            selected_id = cid
    with col_bin:
        if st.button("🗑️", key=f"del_{cid}", help="Удалить термин"):
            st.session_state["delete_request"] = cid

# ===== Форма добавления термина =================================
st.title("Lingua Layers Editor")

with st.form("add_term"):
    layer_opts = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    layer_sel  = st.selectbox("Слой", layer_opts + ["<Создать новый>"])

    if layer_sel == "<Создать новый>":
        new_alias = st.text_input("Alias слоя")
        new_level = st.number_input("Уровень", 1, 99, 1)
        new_desc  = st.text_area("Описание слоя")

    term        = st.text_input("Термин")
    definition  = st.text_area("Определение")
    submitted   = st.form_submit_button("Сохранить")

# ----- обработка сохранения ------------------------------------
if submitted and term and definition:
    if layer_sel == "<Создать новый>":
        lid   = str(len(db["layers"]) + 1)
        layer = {"id": lid, "alias": new_alias, "level": int(new_level),
                 "description": new_desc,
                 "library": {"concepts": []}}
        db["layers"].append(layer)
    else:
        lid   = layer_sel.split(" –")[0]
        layer = next(l for l in db["layers"] if l["id"] == lid)

    cid = f"{layer['id']}.{len(layer['library']['concepts']) + 1}"

    # 👇 здесь можно подключить ИИ для автоматического определения refs
    refs = []

    layer["library"]["concepts"].append({
        "id": cid,
        "term": term,
        "definition": definition,
        "refs": refs
    })
    save_db(db)
    st.success(f"Добавлено {cid}")
    selected_id = cid        # сразу показываем свежий термин

# ----- обработка удаления --------------------------------------
if "delete_request" in st.session_state:
    del_id = st.session_state.pop("delete_request")

    # удаляем сам термин
    for layer in db["layers"]:
        before = len(layer["library"]["concepts"])
        layer["library"]["concepts"] = [
            c for c in layer["library"]["concepts"] if c["id"] != del_id
        ]
        if len(layer["library"]["concepts"]) < before:
            # убираем ссылки на него из других концептов
            for c in all_concepts(db):
                if del_id in c.get("refs", []):
                    c["refs"].remove(del_id)
            save_db(db)
            st.sidebar.success(f"Удалён {del_id}")
            if selected_id == del_id:
                selected_id = None
            break

# ====== Граф выбранного термина =================================
if selected_id:
    draw_subgraph(db, selected_id)
    if os.path.exists(GRAPH):
        st.image(GRAPH, caption=f"Связи термина {selected_id}")
else:
    st.info("Выберите термин в сайдбаре, чтобы увидеть связи.")
