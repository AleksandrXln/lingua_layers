import os, json, streamlit as st, networkx as nx, matplotlib.pyplot as plt

DATA = "data/layers.json"
GRAPH = "graphs/latest.png"

def load_db():
    if not os.path.exists(DATA):
        os.makedirs("data", exist_ok=True)
        json.dump({"meta":{}, "layers":[]}, open(DATA,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
    return json.load(open(DATA, encoding="utf-8"))

def save_db(db):
    json.dump(db, open(DATA,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

def draw_graph(db):
    G = nx.DiGraph()
    color_map = {}
    for idx, layer in enumerate(db["layers"]):
        color_map[layer["id"]] = idx
    for layer in db["layers"]:
        for c in layer["library"]["concepts"]:
            G.add_node(c["id"], label=f"{c['term']}", color=color_map[layer['id']])
            for ref in c.get("refs", []):
                G.add_edge(c["id"], ref)
    if not G: 
        return
    pos = nx.spring_layout(G, seed=42)
    colors = [G.nodes[n]["color"] for n in G]
    plt.figure(figsize=(12,8))
    nx.draw(G, pos, node_color=colors, cmap=plt.cm.tab20, with_labels=False, node_size=700, arrows=True)
    labels = nx.get_node_attributes(G, 'label')
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    plt.axis("off")
    os.makedirs("graphs", exist_ok=True)
    plt.tight_layout()
    plt.savefig(GRAPH, dpi=140, bbox_inches="tight")
    plt.close()

st.set_page_config("Lingua Layers")
db = load_db()

st.title("Lingua Layers Editor")

# form
with st.form("add_term"):
    layer_names = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    choice = st.selectbox("Слой", layer_names + ["<Создать новый>"])
    if choice == "<Создать новый>":
        alias = st.text_input("Alias слоя")
        level = st.number_input("Уровень", 1, 99, 1)
        desc = st.text_area("Описание слоя")
    term = st.text_input("Термин")
    definition = st.text_area("Определение")
    all_concepts = {c["id"]: c["term"] for l in db["layers"] for c in l["library"]["concepts"]}
    ref_ids = st.multiselect("Ссылки на другие концепты", options=list(all_concepts.keys()), format_func=lambda x: f"{x} – {all_concepts[x]}")
    submit = st.form_submit_button("Сохранить")

if submit:
    if choice == "<Создать новый>":
        new_id = str(len(db["layers"]) + 1)
        layer = {"id": new_id, "alias": alias, "level": int(level), "description": desc, "library": {"concepts":[]}}
        db["layers"].append(layer)
    else:
        lyr_id = choice.split(" –")[0]
        layer = next(l for l in db["layers"] if l["id"] == lyr_id)

    cid = f"{layer['id']}.{len(layer['library']['concepts']) + 1}"
    layer['library']['concepts'].append({"id": cid, "term": term, "definition": definition, "refs": ref_ids})
    save_db(db)
    draw_graph(db)
    st.success(f"Добавлено {cid}")

if os.path.exists(GRAPH):
    st.image(GRAPH, caption="Граф концептов", use_column_width=True)
