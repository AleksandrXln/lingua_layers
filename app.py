# app.py — Lingua Layers v3.4 (совместимость Py3.7 / Streamlit 1.17)
# -------------------------------------------------------------
import os, json, uuid
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from typing import Optional, Dict, Any, List, Tuple

# ==== внешнее ИИ-API (replicate) ============================================
try:
    import replicate
except Exception:
    replicate = None

DATA, GRAPH = "data/layers.json", "graphs/latest.png"

# ================== БАЗА ДАННЫХ =============================================
def load_db():
    if not os.path.exists(DATA):
        os.makedirs("data", exist_ok=True)
        json.dump({"meta": {}, "layers": []}, open(DATA, "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    return json.load(open(DATA, encoding="utf-8"))

def save_db(db):
    json.dump(db, open(DATA, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

def iter_concepts(db):
    for layer in db["layers"]:
        for c in layer.get("library", {}).get("concepts", []):
            yield layer, c

def get_concept(db, cid: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    for layer, c in iter_concepts(db):
        if c["id"] == cid:
            return layer, c
    return None, None

def all_concepts_list(db) -> List[Dict[str, Any]]:
    return [c for _, c in iter_concepts(db)]

def ensure_layer(db: Dict[str, Any], alias: str,
                 level: Optional[int] = None,
                 description: str = "") -> Dict[str, Any]:
    if not alias:
        alias = "общий"
    alias_norm = alias.strip().lower()
    for l in db["layers"]:
        if l["alias"].strip().lower() == alias_norm:
            return l
    new_id = str(len(db["layers"]) + 1)
    lvl = level if level is not None else 1 + len(db["layers"])
    layer: Dict[str, Any] = {
        "id": new_id,
        "alias": alias,
        "level": int(lvl),
        "description": description,
        "library": {"concepts": []}
    }
    db["layers"].append(layer)
    return layer

def create_concept(layer: Dict[str, Any], term: str, definition: str,
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    extra = extra or {}
    next_num = len(layer["library"]["concepts"]) + 1
    cid = f"{layer['id']}.{next_num}"
    concept: Dict[str, Any] = {
        "id": cid,
        "term": term,
        "definition": definition,
        "representation_type": extra.get("representation_type"),
        "axes": extra.get("axes", []),
        "tags": extra.get("tags", []),
        "refs": extra.get("refs", [])
    }
    layer["library"]["concepts"].append(concept)
    return concept

def upsert_link(db, src_id: str, dst_id: str):
    if not src_id or not dst_id or src_id == dst_id:
        return
    _, a = get_concept(db, src_id)
    _, b = get_concept(db, dst_id)
    if not a or not b:
        return
    if dst_id not in a.get("refs", []):
        a.setdefault("refs", []).append(dst_id)
    if src_id not in b.get("refs", []):
        b.setdefault("refs", []).append(src_id)

# ================== ОТРИСОВКА ГРАФА =========================================
def draw_subgraph(db, cid: str):
    G = nx.DiGraph()
    _, center = get_concept(db, cid)
    if not center:
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return

    G.add_node(cid, label=center["term"], main=True)
    for r in center.get("refs", []):
        _, trg = get_concept(db, r)
        if trg:
            G.add_node(r, label=trg["term"], main=False)
            G.add_edge(cid, r)
    for _, c2 in iter_concepts(db):
        if cid in c2.get("refs", []):
            G.add_node(c2["id"], label=c2["term"], main=False)
            G.add_edge(c2["id"], cid)

    pos = nx.spring_layout(G, seed=42)
    colors = ["#16a34a" if G.nodes[n].get("main") else "#60d394" for n in G.nodes()]
    plt.figure(figsize=(7, 5))
    nx.draw(G, pos, node_color=colors, node_size=700, arrows=True, with_labels=False)
    nx.draw_networkx_labels(G, pos, nx.get_node_attributes(G, "label"), font_size=8)
    plt.axis("off")
    os.makedirs("graphs", exist_ok=True)
    plt.savefig(GRAPH, dpi=140, bbox_inches="tight")
    plt.close()

# ================== ИИ Replicate =============================================
SYSTEM_PROMPT = (
    "Ты — редактор семантической дуальной БД для игры. "
    "Получив «термин» и «определение», разложи по дуальным осям и верни СТРОГИЙ JSON."
)

def call_replicate(term: str, definition: str) -> Optional[Dict[str, Any]]:
    api_token = (
        os.environ.get("REPLICATE_API_TOKEN") or
        (st.secrets.get("REPLICATE_API_TOKEN") if hasattr(st, "secrets") else None)
    )
    if replicate is None or not api_token:
        st.warning("Replicate не настроен.")
        return None
    os.environ["REPLICATE_API_TOKEN"] = api_token
    model = "meta/meta-llama-3.1-70b-instruct"
    user_prompt = "Термин: {}\nОпределение: {}\nСформируй JSON.".format(term, definition)
    try:
        out = replicate.run(model, input={
            "prompt": user_prompt,
            "system_prompt": SYSTEM_PROMPT,
            "max_tokens": 800,
            "temperature": 0.2
        })
        text = "".join([str(x) for x in out]) if hasattr(out, "__iter__") else str(out)
        return safe_json(text)
    except Exception as e:
        st.error("Ошибка Replicate: {}".format(e))
        return None

def safe_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end+1])
            except Exception:
                return None
        return None

def ai_enrich(term: str, definition: str) -> Dict[str, Any]:
    data = call_replicate(term, definition)
    if not data:
        return {"representation_type": None, "suggested_layers": [], "axes": [], "tags": [], "links": []}
    return data

# ================== STREAMLIT UI ============================================
st.set_page_config("Lingua Layers", layout="wide")
st.title("Lingua Layers — дуальная БД понятий")

db = load_db()
if "selected_id" not in st.session_state:
    lst = all_concepts_list(db)
    first = lst[0] if lst else None
    st.session_state["selected_id"] = first["id"] if first else None
sel_id = st.session_state["selected_id"]

# Sidebar
st.sidebar.header("Термины")
q = st.sidebar.text_input("Поиск")
concepts = [(c["id"], c["term"]) for c in all_concepts_list(db)]
if q:
    concepts = [c for c in concepts if q.lower() in c[1].lower()]
for idx, (cid, title) in enumerate(concepts):
    if st.sidebar.button(title, key="choose_{}".format(cid)):
        st.session_state["selected_id"] = cid
        sel_id = cid
    if st.sidebar.button("🗑️", key="del_{}".format(cid)):
        for layer in db["layers"]:
            layer["library"]["concepts"] = [c for c in layer["library"]["concepts"] if c["id"] != cid]
        for _, c in iter_concepts(db):
            if cid in c.get("refs", []):
                c["refs"].remove(cid)
        save_db(db)
        if sel_id == cid:
            st.session_state["selected_id"] = None
        st.experimental_rerun()

# Add term manually
st.subheader("Добавить термин (вручную)")
with st.form("add_term_manual"):
    layer_opts = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    if layer_opts:
        l_sel = st.selectbox("Слой", layer_opts)
        term = st.text_input("Термин")
        defi = st.text_area("Определение")
        if st.form_submit_button("Сохранить") and term and defi:
            lid = l_sel.split(" –")[0]
            layer = next(l for l in db["layers"] if l["id"] == lid)
            c = create_concept(layer, term, defi)
            save_db(db)
            st.session_state["selected_id"] = c["id"]
            st.success("Добавлено {}".format(c["id"]))
            st.experimental_rerun()

# Add with AI
st.subheader("Добавить термин с ИИ (replicate.com)")
with st.form("add_term_ai"):
    term_ai = st.text_input("Термин", key="ai_term")
    defi_ai = st.text_area("Определение", key="ai_def")
    run_ai = st.form_submit_button("Анализировать")
if run_ai and term_ai and defi_ai:
    enrich = ai_enrich(term_ai, defi_ai)
    st.write("Результат анализа:", enrich)
    # тут можно сразу вызывать create_concept + ensure_layer

# Graph
if sel_id:
    draw_subgraph(db, sel_id)
    if os.path.exists(GRAPH):
        st.image(GRAPH, caption="Связи {}".format(sel_id))
    _, c = get_concept(db, sel_id)
    if c:
        st.write("### {}".format(c["term"]))
        st.write(c["definition"])
else:
    st.info("Выберите термин")
