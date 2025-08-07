import os, json, streamlit as st, networkx as nx, matplotlib.pyplot as plt

DATA  = "data/layers.json"
GRAPH = "graphs/latest.png"


# ---------- работа с базой ----------------------------------
def load_db():
    if not os.path.exists(DATA):
        os.makedirs("data", exist_ok=True)
        json.dump({"meta": {}, "layers": []}, open(DATA, "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    return json.load(open(DATA, encoding="utf-8"))


def save_db(db):
    json.dump(db, open(DATA, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


def all_concepts(db):
    for layer in db["layers"]:
        for c in layer["library"]["concepts"]:
            yield c


# ---------- рисование субграфа ------------------------------
def draw_subgraph(db, concept_id: str):
    """рисует граф с выбранным термином + все его исходящие и входящие связи"""
    G = nx.DiGraph()

    # найдём выбранный концепт и его связи
    for c in all_concepts(db):
        if c["id"] == concept_id:
            G.add_node(c["id"], label=c["term"], color="selected")
            # исходящие
            for ref in c.get("refs", []):
                trg = next(x for x in all_concepts(db) if x["id"] == ref)
                G.add_node(trg["id"], label=trg["term"], color="neighbor")
                G.add_edge(c["id"], ref)
            # входящие
            for c2 in all_concepts(db):
                if concept_id in c2.get("refs", []):
                    G.add_node(c2["id"], label=c2["term"], color="neighbor")
                    G.add_edge(c2["id"], concept_id)
            break

    if G.number_of_nodes() == 0:     # нечего рисовать
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return

    pos    = nx.spring_layout(G, seed=42)
    colors = ["#1976d2" if G.nodes[n]["color"] == "selected" else "#42a5f5"
              for n in G]

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


# ---------- Streamlit UI ------------------------------------
st.set_page_config("Lingua Layers", layout="wide")
db = load_db()

# ===== Sidebar: список терминов + поиск =====================
st.sidebar.header("Термины")
search = st.sidebar.text_input("Поиск")
term_options = [(c["id"], c["term"]) for c in all_concepts(db)]
if search:
    term_options = [t for t in term_options if search.lower() in t[1].lower()]

if term_options:
    default_idx = 0
    selected_id = st.sidebar.radio(
        "Список",
        term_options,
        index=default_idx,
        format_func=lambda x: x[1]
    )[0]
else:
    selected_id = None
    st.sidebar.info("Терминов пока нет")

# ===== Main: форма добавления термина =======================
st.title("Lingua Layers Editor")

with st.form("add_term"):
    layer_names = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    choice = st.selectbox("Слой", layer_names + ["<Создать новый>"])

    if choice == "<Создать новый>":
        alias = st.text_input("Alias слоя")
        level = st.number_input("Уровень", 1, 99, 1)
        desc  = st.text_area("Описание слоя")

    term        = st.text_input("Термин")
    definition  = st.text_area("Определение")
    submit      = st.form_submit_button("Сохранить")

# ====== Обработка сохранения ================================
if submit and term and definition:
    if choice == "<Создать новый>":
        new_id = str(len(db["layers"]) + 1)
        layer  = {"id": new_id, "alias": alias, "level": int(level),
                  "description": desc,
                  "library": {"concepts": []}}
        db["layers"].append(layer)
    else:
        lyr_id = choice.split(" –")[0]
        layer  = next(l for l in db["layers"] if l["id"] == lyr_id)

    cid = f"{layer['id']}.{len(layer['library']['concepts']) + 1}"

    # <—— здесь можно вызвать ИИ-модель, чтобы вычислить refs
    refs = []

    layer["library"]["concepts"].append({
        "id": cid, "term": term, "definition": definition, "refs": refs
    })
    save_db(db)
    st.success(f"Добавлено {cid}")

    # если только что добавили и выбрали его же — обновим граф
    selected_id = cid

# ====== Рисуем граф для выбранного термина ==================
if selected_id:
    draw_subgraph(db, selected_id)
    if os.path.exists(GRAPH):
        st.image(GRAPH, caption=f"Связи термина {selected_id}")
else:
    st.info("Выберите термин в боковой панели, чтобы увидеть связи.")
