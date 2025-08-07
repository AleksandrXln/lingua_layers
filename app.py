# app.py — Lingua Layers v2.4 (фильтр + ровная строка)
import os, json
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

DATA, GRAPH = "data/layers.json", "graphs/latest.png"

# ──────── DB ──────────────────────────────────────────
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

# ──────── GRAPH ───────────────────────────────────────
def draw_subgraph(db, cid):
    G = nx.DiGraph()
    for c in all_concepts(db):
        if c["id"] == cid:
            G.add_node(cid, label=c["term"], main=True)
            for r in c.get("refs", []):
                trg = next(x for x in all_concepts(db) if x["id"] == r)
                G.add_node(r, label=trg["term"], main=False)
                G.add_edge(cid, r)
            for c2 in all_concepts(db):
                if cid in c2.get("refs", []):
                    G.add_node(c2["id"], label=c2["term"], main=False)
                    G.add_edge(c2["id"], cid)
            break
    if not G:                          # нет узлов
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return
    pos = nx.spring_layout(G, seed=42)
    colors = ["#16a34a" if G.nodes[n]["main"] else "#60d394" for n in G]
    plt.figure(figsize=(7, 5))
    nx.draw(G, pos, node_color=colors, node_size=700, arrows=True,
            with_labels=False)
    nx.draw_networkx_labels(G, pos,
                            nx.get_node_attributes(G, "label"), font_size=8)
    plt.axis("off"); os.makedirs("graphs", exist_ok=True)
    plt.tight_layout(); plt.savefig(GRAPH, dpi=140); plt.close()

# ──────── UI ───────────────────────────────────────────
st.set_page_config("Lingua Layers", layout="wide")
db = load_db()

if "selected_id" not in st.session_state:
    first = next(all_concepts(db), None)
    st.session_state["selected_id"] = first["id"] if first else None
sel_id = st.session_state["selected_id"]

# ----- SIDEBAR ---------------------------------------
st.sidebar.header("Термины")
query = st.sidebar.text_input("Поиск")

concepts = [(c["id"], c["term"]) for c in all_concepts(db)]
filtered = [item for item in concepts if query.lower() in item[1].lower()]

# гарантируем, что выбранный термин остаётся видимым
if sel_id and sel_id not in [c[0] for c in filtered]:
    sel_concept = next((c for c in concepts if c[0] == sel_id), None)
    if sel_concept:
        filtered.insert(0, sel_concept)

for idx, (cid, title) in enumerate(filtered):
    sel = (cid == sel_id)
    line = (
        f"<span style='font-size:18px;color:{'#16a34a' if sel else '#9ca3af'}'>●</span> "
        f"<button style='border:none;background:none;color:#111;font-size:15px;"
        f"text-align:left;cursor:pointer;' "
        f"onclick=\"window.parent.postMessage({{'type':'select','id':'{cid}'}},'*');\">"
        f"{title}</button> "
        f"<button style='border:none;background:none;cursor:pointer;color:#e11d48;' "
        f"onclick=\"window.parent.postMessage({{'type':'del','id':'{cid}'}},'*');\">🗑️</button>"
    )
    st.sidebar.markdown(line, unsafe_allow_html=True)

# JS-bridge: ловим клики из html-кнопок
components = st.components.v1
components.html("""
<script>
window.addEventListener("message", (ev)=>{
  const d = ev.data;
  if(d.type==="select"){parent.postMessage(d,"*")}
  if(d.type==="del"){parent.postMessage(d,"*")}
});
</script>""", height=0)

# сообщения от iFrame -> Streamlit
evt = st.experimental_get_query_params().get("streamlit_message")
if evt:
    import json, urllib.parse
    msg = json.loads(urllib.parse.unquote(evt[0]))
    if msg["type"] == "select":
        st.session_state["selected_id"] = msg["id"]
        sel_id = msg["id"]
    elif msg["type"] == "del":
        st.session_state["delete_request"] = msg["id"]

# ----- FORM: добавить термин --------------------------
st.title("Lingua Layers Editor")
with st.form("add"):
    lopts = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    lsel  = st.selectbox("Слой", lopts + ["<Создать новый>"])
    if lsel == "<Создать новый>":
        nalias = st.text_input("Alias слоя")
        nlevel = st.number_input("Уровень", 1, 99, 1)
        ndesc  = st.text_area("Описание слоя")
    term = st.text_input("Термин")
    defi = st.text_area("Определение")
    ok   = st.form_submit_button("Сохранить")

if ok and term and defi:
    if lsel == "<Создать новый>":
        lid = str(len(db["layers"]) + 1)
        db["layers"].append({"id": lid, "alias": nalias, "level": int(nlevel),
                             "description": ndesc,
                             "library": {"concepts": []}})
    else:
        lid = lsel.split(" –")[0]
    layer = next(l for l in db["layers"] if l["id"] == lid)
    cid = f"{lid}.{len(layer['library']['concepts']) + 1}"
    layer["library"]["concepts"].append(
        {"id": cid, "term": term, "definition": defi, "refs": []}
    )
    save_db(db); st.session_state["selected_id"] = cid; sel_id = cid
    st.success(f"Добавлено {cid}")

# ----- Удаление ---------------------------------------
if "delete_request" in st.session_state:
    did = st.session_state.pop("delete_request")
    for layer in db["layers"]:
        layer["library"]["concepts"] = [c for c in layer["library"]["concepts"]
                                        if c["id"] != did]
        for c in layer["library"]["concepts"]:
            if did in c.get("refs", []): c["refs"].remove(did)
    save_db(db)
    if sel_id == did:
        st.session_state["selected_id"] = None
        sel_id = None
    st.sidebar.success(f"Удалён {did}")

# ----- ГРАФ -------------------------------------------
if sel_id:
    draw_subgraph(db, sel_id)
    if os.path.exists(GRAPH):
        st.image(GRAPH, caption=f"Связи термина {sel_id}")
else:
    st.info("Выберите термин в сайдбаре, чтобы увидеть связи.")
