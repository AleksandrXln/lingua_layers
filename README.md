# Lingua Layers – Graph Edition
Авто‑редактор терминов + автопостроение PNG‑графа.

## Быстрый старт
```bash
unzip lingua_layers_graph_starter.zip && cd lingua_layers_graph_starter
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
После каждого сохранения термина в интерфейсе перерисовывается PNG‑граф (`graphs/latest.png`).
