# app.py — Lingua Layers v3.4 (ИИ-интеграция с replicate.com)
# -------------------------------------------------------------
import os, json, uuid
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

# ==== внешнее ИИ-API (replicate) ============================================
# pip install replicate
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

def get_concept(db, cid):
    for layer, c in iter_concepts(db):
        if c["id"] == cid:
            return layer, c
    return None, None

def all_concepts_list(db):
    return [c for _, c in iter_concepts(db)]

def ensure_layer(db, alias: str, level: int | None = None, description: str = ""):
    """Находит слой по alias (регистронезависимо) или создаёт новый."""
    if not alias:
        alias = "общий"
    alias_norm = alias.strip().lower()
    for l in db["layers"]:
        if l["alias"].strip().lower() == alias_norm:
            return l
    new_id = str(len(db["layers"]) + 1)
    lvl = level if level is not None else 1 + len(db["layers"])
    layer = {
        "id": new_id,
        "alias": alias,
        "level": int(lvl),
        "description": description,
        "library": {"concepts": []}
    }
    db["layers"].append(layer)
    return layer

def create_concept(layer, term, definition, extra=None):
    """Создаёт концепт внутри слоя с новым ID."""
    extra = extra or {}
    next_num = len(layer["library"]["concepts"]) + 1
    cid = f"{layer['id']}.{next_num}"
    concept = {
        "id": cid,
        "term": term,
        "definition": definition,
        "representation_type": extra.get("representation_type"),  # state/event/action/modality/None
        "axes": extra.get("axes", []),          # [{"axis":"масштаб", "role":"A|B", "dual_term":"микро"}]
        "tags": extra.get("tags", []),
        "refs": extra.get("refs", [])           # список id (пока пустые, заполним после)
    }
    layer["library"]["concepts"].append(concept)
    return concept

def upsert_link(db, src_id, dst_id):
    """Двусторонняя связь refs (без дублей)."""
    if not src_id or not dst_id or src_id == dst_id: 
        return
    _, a = get_concept(db, src_id)
    _, b = get_concept(db, dst_id)
    if not a or not b:
        return
    a.setdefault("refs", [])
    b.setdefault("refs", [])
    if dst_id not in a["refs"]:
        a["refs"].append(dst_id)
    if src_id not in b["refs"]:
        b["refs"].append(src_id)

# ================== ОТРИСОВКА ГРАФА =========================================
def draw_subgraph(db, cid):
    G = nx.DiGraph()
    _, center = get_concept(db, cid)
    if not center:
        if os.path.exists(GRAPH):
            os.remove(GRAPH)
        return

    G.add_node(cid, label=center["term"], main=True)
    # исходящие
    for r in center.get("refs", []):
        _, trg = get_concept(db, r)
        if trg:
            G.add_node(r, label=trg["term"], main=False)
            G.add_edge(cid, r)
    # входящие
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

# ================== ИИ: АНАЛИЗ ТЕРМИНА ======================================
SYSTEM_PROMPT = (
    "Ты — редактор семантической дуальной БД для игры. "
    "Получив «термин» и «определение», разложи по дуальным осям и верни СТРОГИЙ JSON "
    "со схемой:\n"
    "{\n"
    "  \"representation_type\": \"state|event|action|modality\",\n"
    "  \"suggested_layers\": [\"строка\" ...],\n"
    "  \"axes\": [\n"
    "    {\"axis\": \"название оси\", \"role\": \"A|B\", \"dual_term\": \"оппонент-слово (если есть)\"}\n"
    "  ],\n"
    "  \"tags\": [\"room:any\", \"scale:macro\", ...],\n"
    "  \"links\": [ {\"kind\":\"related|is_a|contrasts_with|entails\", \"term\":\"существующее_или_новое\"} ]\n"
    "}\n"
    "Только JSON, без комментариев. Если чего-то нет — ставь пустые массивы."
)

def call_replicate(term: str, definition: str) -> dict | None:
    """Вызов модели Replicate. Возвращает dict по нашей схеме или None."""
    api_token = os.environ.get("REPLICATE_API_TOKEN") or st.secrets.get("REPLICATE_API_TOKEN", None)
    if replicate is None or not api_token:
        st.warning("Replicate не настроен (нет пакета или токена). Будет сгенерирована заготовка по умолчанию.")
        return None

    os.environ["REPLICATE_API_TOKEN"] = api_token
    # Подходит любой chat-instruct из каталога; возьмём Llama 3.1 70B (пример).
    model = "meta/meta-llama-3.1-70b-instruct"  # укажи свой, если используешь другой в Replicate

    user_prompt = (
        f"Термин: {term}\n"
        f"Определение: {definition}\n"
        "Сформируй JSON по заданной схеме."
    )
    try:
        # replicate.run может возвращать генератор чанков; склеим в строку
        out = replicate.run(
            model,
            input={
                "prompt": user_prompt,
                "system_prompt": SYSTEM_PROMPT,
                "max_tokens": 800,
                "temperature": 0.2
            }
        )
        text = "".join([str(x) for x in out]) if isinstance(out, list) or hasattr(out, "__iter__") else str(out)
        return safe_json(text)
    except Exception as e:
        st.error(f"Ошибка Replicate: {e}")
        return None

def safe_json(s: str) -> dict | None:
    """Пытается достать JSON из строки (строгая и слабая стратегии)."""
    try:
        return json.loads(s)
    except Exception:
        # вырезать первый и последний блок { ... }
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end+1])
            except Exception:
                return None
        return None

def ai_enrich(term: str, definition: str) -> dict:
    """
    Возвращает структуру:
    {
      'representation_type': 'state'|'event'|'action'|'modality'|None,
      'suggested_layers': [..],
      'axes': [{'axis':..., 'role':'A'|'B', 'dual_term':...}, ...],
      'tags': [...],
      'links': [{'kind':..., 'term': ...}]
    }
    """
    data = call_replicate(term, definition)
    if not data:
        # Fallback: простая заготовка
        data = {
            "representation_type": None,
            "suggested_layers": [],
            "axes": [],
            "tags": [],
            "links": []
        }
    # нормализация
    data["representation_type"] = (data.get("representation_type") or "").strip() or None
    data["suggested_layers"] = [str(x).strip() for x in data.get("suggested_layers", []) if str(x).strip()]
    axes = []
    for a in data.get("axes", []):
        axes.append({
            "axis": str(a.get("axis","")).strip(),
            "role": "A" if str(a.get("role","A")).upper().startswith("A") else "B",
            "dual_term": str(a.get("dual_term","")).strip()
        })
    data["axes"] = axes
    data["tags"] = [str(t).strip() for t in data.get("tags", []) if str(t).strip()]
    links = []
    for l in data.get("links", []):
        links.append({"kind": str(l.get("kind","related")).strip(), "term": str(l.get("term","")).strip()})
    data["links"] = links
    return data

# ================== STREAMLIT UI ============================================
st.set_page_config("Lingua Layers", layout="wide")
st.title("Lingua Layers — дуальная БД понятий")

db = load_db()
if "selected_id" not in st.session_state:
    first = next(iter(all_concepts_list(db)), None)
    st.session_state["selected_id"] = first["id"] if first else None
sel_id = st.session_state["selected_id"]

# --- Sidebar: список терминов ------------------------------------------------
st.sidebar.header("Термины")
q = st.sidebar.text_input("Поиск")
concepts = [(c["id"], c["term"]) for c in all_concepts_list(db)]
if q:
    concepts = [c for c in concepts if q.lower() in c[1].lower()]

for idx, (cid, title) in enumerate(concepts):
    c1, c2, c3 = st.sidebar.columns([1, 6, 1])
    with c1:
        st.markdown(
            f"<div style='text-align:center;font-size:18px;color:{'#16a34a' if cid==sel_id else '#9ca3af'}'>●</div>",
            unsafe_allow_html=True
        )
    with c2:
        if st.button(title, key=f"choose_{idx}_{cid}"):
            st.session_state["selected_id"] = cid
            sel_id = cid
    with c3:
        if st.button("🗑️", key=f"del_{idx}_{cid}", help="Удалить термин"):
            # remove concept and references
            for layer in db["layers"]:
                layer["library"]["concepts"] = [c for c in layer["library"]["concepts"] if c["id"] != cid]
            for _, c in iter_concepts(db):
                if cid in c.get("refs", []):
                    c["refs"].remove(cid)
            save_db(db)
            if sel_id == cid:
                st.session_state["selected_id"] = None
            st.experimental_rerun()

# --- Управление слоями -------------------------------------------------------
with st.expander("➕ Управление слоями", expanded=False):
    st.subheader("Создать слой")
    with st.form("add_layer"):
        l_alias = st.text_input("Alias слоя")
        l_level = st.number_input("Уровень", 1, 99, 1)
        l_desc  = st.text_area("Описание")
        if st.form_submit_button("Создать слой") and l_alias:
            ensure_layer(db, l_alias, int(l_level), l_desc)
            save_db(db)
            st.success(f"Создан слой «{l_alias}».")
            st.experimental_rerun()

    st.subheader("Удалить слой")
    if db["layers"]:
        del_choice = st.selectbox("Выберите слой", [f"{l['id']} – {l['alias']}" for l in db["layers"]])
        if st.button("Удалить выбранный слой"):
            did = del_choice.split(" –")[0]
            db["layers"] = [l for l in db["layers"] if l["id"] != did]
            # чистим ссылки внутри
            for _, c in iter_concepts(db):
                c["refs"] = [r for r in c.get("refs", []) if not r.startswith(f"{did}.")]
            save_db(db)
            st.success(f"Слой {did} удалён.")
            if sel_id and sel_id.startswith(f"{did}."):
                st.session_state["selected_id"] = None
            st.experimental_rerun()
    else:
        st.info("Пока нет слоёв.")

# --- Добавить термин вручную -------------------------------------------------
st.subheader("Добавить термин (вручную)")
with st.form("add_term_manual"):
    layer_opts = [f"{l['id']} – {l['alias']}" for l in db["layers"]]
    if not layer_opts:
        st.info("Сначала создайте слой во вкладке выше.")
        submitted = False
    else:
        l_sel = st.selectbox("Слой", layer_opts, key="manual_layer")
        term  = st.text_input("Термин", key="manual_term")
        defi  = st.text_area("Определение", key="manual_def")
        submitted = st.form_submit_button("Сохранить")
    if submitted and term and defi:
        lid = l_sel.split(" –")[0]
        layer = next(l for l in db["layers"] if l["id"] == lid)
        c = create_concept(layer, term, defi)
        save_db(db)
        st.session_state["selected_id"] = c["id"]
        st.success(f"Добавлено {c['id']}")
        st.experimental_rerun()

# --- Добавить термин с ИИ ----------------------------------------------------
st.subheader("Добавить термин с ИИ (replicate.com)")
with st.form("add_term_ai"):
    term_ai = st.text_input("Термин", key="ai_term")
    defi_ai = st.text_area("Определение", key="ai_def")
    run_ai  = st.form_submit_button("Проанализировать ИИ")
if run_ai and term_ai and defi_ai:
    enrich = ai_enrich(term_ai, defi_ai)
    st.session_state["ai_enrich"] = enrich
    st.session_state["ai_term"] = term_ai
    st.session_state["ai_def"] = defi_ai
    st.experimental_rerun()

if "ai_enrich" in st.session_state:
    st.markdown("### Предпросмотр (можно поправить перед сохранением)")
    enrich = st.session_state["ai_enrich"]

    # editable preview
    colA, colB = st.columns([1,1])
    with colA:
        rt = st.selectbox("Тип представления",
                          options=[None, "state", "event", "action", "modality"],
                          index=[None, "state", "event", "action", "modality"].index(enrich.get("representation_type")),
                          format_func=lambda x: x if x else "—")
        tags = st.text_input("Теги (через запятую)", value=", ".join(enrich.get("tags", [])))
        sug_layers = st.text_input("Предложенные слои (через запятую)", value=", ".join(enrich.get("suggested_layers", [])))
    with colB:
        st.write("Оси/дуальности:")
        axes_edit = []
        for i, a in enumerate(enrich.get("axes", [])):
            c1,c2,c3 = st.columns([2,1,2])
            with c1:
                axis = st.text_input(f"Ось #{i+1}", value=a["axis"], key=f"axis_{i}")
            with c2:
                role = st.selectbox(f"Роль #{i+1}", options=["A","B"], index=0 if a["role"]=="A" else 1, key=f"role_{i}")
            with c3:
                dual = st.text_input(f"Дуал-термин #{i+1}", value=a.get("dual_term",""), key=f"dual_{i}")
            axes_edit.append({"axis": axis, "role": role, "dual_term": dual})

    st.write("Связи (links):")
    links_edit = []
    for i, lnk in enumerate(enrich.get("links", [])):
        d1,d2 = st.columns([1,3])
        with d1:
            kind = st.selectbox(f"Вид связи #{i+1}", ["related","is_a","contrasts_with","entails"],
                                index=["related","is_a","contrasts_with","entails"].index(lnk.get("kind","related")),
                                key=f"link_kind_{i}")
        with d2:
            t = st.text_input(f"Термин/узел #{i+1}", value=lnk.get("term",""), key=f"link_term_{i}")
        links_edit.append({"kind":kind, "term":t})

    # save button
    if st.button("Сохранить в БД"):
        # 1) определить слой: берем первый из предложенных, иначе «общий»
        sugg = [s.strip() for s in (sug_layers or "").split(",") if s.strip()]
        layer_alias = sugg[0] if sugg else (axes_edit[0]["axis"] if axes_edit and axes_edit[0]["axis"] else "общий")
        layer = ensure_layer(db, layer_alias)

        # 2) создать основной концепт
        concept = create_concept(layer, st.session_state["ai_term"], st.session_state["ai_def"], {
            "representation_type": rt,
            "axes": axes_edit,
            "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
            "refs": []
        })

        # 3) обработать дуалы: если dual_term указан и ещё не существует — создаём заглушку
        known_terms = {c["term"].strip().lower(): c["id"] for _, c in iter_concepts(db)}
        for ax in axes_edit:
            dual_term = ax.get("dual_term","").strip()
            if not dual_term:
                continue
            if dual_term.strip().lower() in known_terms:
                dual_id = known_terms[dual_term.strip().lower()]
            else:
                # создаём в слое по названию оси
                dual_layer = ensure_layer(db, ax["axis"])
                dual_c = create_concept(
                    dual_layer,
                    dual_term,
                    f"Автосозданный дуальный полюс для оси «{ax['axis']}».",
                    {"representation_type": rt, "axes": [], "tags": ["auto:dual"]}
                )
                dual_id = dual_c["id"]
                known_terms[dual_term.strip().lower()] = dual_id
            upsert_link(db, concept["id"], dual_id)

        # 4) обработать links: если ссылка на несуществующий термин — создаём stub
        for lnk in links_edit:
            t = lnk.get("term","").strip()
            if not t:
                continue
            if t.strip().lower() in known_terms:
                tid = known_terms[t.strip().lower()]
            else:
                stub_layer = ensure_layer(db, "связи")
                stub = create_concept(stub_layer, t, "Автосозданный узел по ссылке.", {"tags":["auto:stub"]})
                tid = stub["id"]
                known_terms[t.strip().lower()] = tid
            upsert_link(db, concept["id"], tid)

        save_db(db)
        st.success(f"Добавлено: {concept['id']} ({concept['term']}) в слой «{layer['alias']}».")
        st.session_state.pop("ai_enrich", None)
        st.session_state["selected_id"] = concept["id"]
        st.experimental_rerun()

# --- Визуализация выбранного термина ----------------------------------------
st.markdown("---")
if sel_id:
    draw_subgraph(db, sel_id)
    if os.path.exists(GRAPH):
        st.image(GRAPH, caption=f"Связи термина {sel_id}")
    # карточка термина
    _, c = get_concept(db, sel_id)
    if c:
        st.markdown(f"### {c['term']}")
        st.write(c["definition"])
        colx, coly = st.columns([1,1])
        with colx:
            st.write("Тип:", c.get("representation_type") or "—")
            st.write("Теги:", ", ".join(c.get("tags", [])) or "—")
        with coly:
            st.write("Оси:", c.get("axes", []) or "—")
        st.write("Связи:", c.get("refs", []) or "—")
else:
    st.info("Выберите термин в сайдбаре, чтобы увидеть связи.")
