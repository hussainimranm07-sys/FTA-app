# ⚠ Fault Tree Analysis Tool — v3 (Visual Tree)

## What's new in v3
- **Interactive D3.js visual tree** — matches your real FTA diagram layout
- Click any node to select and edit it
- Pan (drag), zoom (scroll or buttons), collapse/expand branches
- Color-coded: Purple=Hazard, Blue=SF, Green=FF, Orange=IF
- OR/AND gate badges on every node
- ✓/✗ status colours on calculated values
- Quick-add panel below tree: add SF/FF/IF to selected node

## Run locally
```bash
pip install -r requirements.txt
streamlit run fault_tree.py
```

## Deploy free
1. Push to GitHub
2. https://share.streamlit.io → New app → `fault_tree.py`

## How to use the visual tree
1. **Navigate**: Drag canvas to pan · Scroll to zoom
2. **Select**: Click any node — it highlights and shows info below
3. **Edit**: Go to ✏️ Edit Panel tab — edit selected node properties
4. **Add nodes**: Use Quick Add buttons below tree, or Edit Panel
5. **Collapse**: Click the ▼ button at bottom of any node
6. **Reset view**: Click ⊙ Reset button

## Tabs
- 🌲 Visual Tree — interactive D3 diagram + quick actions
- ✏️ Edit Panel — edit selected node + hazard settings
- 🧮 Audit Trail — full calculation breakdown + export table
