"""
Fault Tree Analysis Tool v3
============================
Full interactive visual tree built with D3.js inside Streamlit via st.components.
Click any node in the tree to select and edit it in the sidebar panel.
"""

import streamlit as st
import json, uuid, math, copy
from datetime import datetime
import pandas as pd
import streamlit.components.v1 as components

st.set_page_config(page_title="FTA Tool v3", page_icon="⚠", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'IBM Plex Sans',sans-serif;background:#08080f;color:#c8c8d8;}
.stApp{background:#08080f;}
[data-testid="stSidebar"]{background:#0d0d1a;border-right:1px solid #1e1e3a;}
.stButton>button{border-radius:7px;font-weight:600;font-size:12px;}
.stTextInput>div>div>input,.stNumberInput>div>div>input{background:#0a0a18!important;color:#e2e8f0!important;font-family:'IBM Plex Mono',monospace!important;border-color:#1e1e3a!important;}
.stSelectbox>div>div{background:#0a0a18!important;color:#e2e8f0!important;}
.stTextArea>div>div>textarea{background:#0a0a18!important;color:#e2e8f0!important;}
.stTabs [data-baseweb="tab-list"]{background:#0d0d1a;border-bottom:1px solid #1e1e3a;}
.stTabs [data-baseweb="tab"]{color:#64748b;font-weight:600;}
.stTabs [aria-selected="true"]{color:#e2e8f0!important;border-bottom:2px solid #7c3aed!important;}
.node-edit-card{background:#0f0f20;border:1px solid #1e1e3a;border-radius:12px;padding:16px;margin-bottom:12px;}
.stat-chip{background:#0d0d1a;border:1px solid #1e1e3a;border-radius:8px;padding:6px 12px;display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:12px;}
.ok-color{color:#4ade80;} .over-color{color:#f87171;} .muted{color:#64748b;}
#MainMenu{visibility:hidden;}footer{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ─── engine ───────────────────────────────────────────────────────────────────
def new_id(): return str(uuid.uuid4())[:8]

def fmt(v, d=2):
    if v is None or (isinstance(v,float) and (math.isnan(v) or math.isinf(v))): return "–"
    if v == 0: return "0"
    return f"{v:.{d}e}"

def calc_node(node):
    ch = node.get("children",[])
    if not ch: return node.get("value")
    vals = [v for v in (calc_node(c) for c in ch) if v is not None and math.isfinite(v)]
    if not vals: return node.get("value")
    if node.get("gate","OR")=="OR": return sum(vals)
    r=1.0
    for v in vals: r*=v
    return r

def propagate_targets(node, target):
    node=copy.deepcopy(node); node["_target"]=target
    ch=node.get("children",[])
    if not ch: return node
    n=len(ch); gate=node.get("gate","OR")
    ct = target/n if gate=="OR" else max(target,1e-300)**(1.0/n)
    node["children"]=[propagate_targets(c,ct) for c in ch]
    return node

def redistribute(tree, mode="equal"):
    tree=copy.deepcopy(tree); sfs=tree.get("children",[])
    if not sfs: return tree
    ht=tree.get("value",1e-7)
    if mode=="equal":
        sft=ht/len(sfs)
        for sf in tree["children"]:
            sf["weight"]=1; sf["_target"]=sft
            ffs=sf.get("children",[]); fft=sft/max(len(ffs),1)
            sf["children"]=[propagate_targets(ff,fft) for ff in ffs]
    else:
        tw=sum(sf.get("weight",1) for sf in sfs) or 1
        for sf in tree["children"]:
            sft=ht*(sf.get("weight",1)/tw); sf["_target"]=sft
            ffs=sf.get("children",[]); fft=sft/max(len(ffs),1)
            sf["children"]=[propagate_targets(ff,fft) for ff in ffs]
    return tree

def find_node(tree, node_id):
    if tree.get("id")==node_id: return tree
    for c in tree.get("children",[]):
        r=find_node(c,node_id)
        if r: return r
    return None

def update_node_in_tree(tree, node_id, patch):
    if tree.get("id")==node_id:
        tree=copy.deepcopy(tree); tree.update(patch); return tree
    if not tree.get("children"): return tree
    tree=copy.deepcopy(tree)
    tree["children"]=[update_node_in_tree(c,node_id,patch) for c in tree["children"]]
    return tree

def delete_node_from_tree(tree, node_id):
    if not tree.get("children"): return tree
    tree=copy.deepcopy(tree)
    tree["children"]=[delete_node_from_tree(c,node_id) for c in tree["children"] if c.get("id")!=node_id]
    return tree

def add_child(tree, parent_id, child):
    if tree.get("id")==parent_id:
        tree=copy.deepcopy(tree); tree.setdefault("children",[]).append(child); return tree
    if not tree.get("children"): return tree
    tree=copy.deepcopy(tree)
    tree["children"]=[add_child(c,parent_id,child) for c in tree["children"]]
    return tree

# ─── factories ────────────────────────────────────────────────────────────────
def make_if(nid="IF-001",label="Initial Failure",value=1e-5):
    return {"id":new_id(),"type":"IF","node_id":nid,"label":label,"value":value,
            "children":[],"gate":"OR","note":"","flag":"none"}
def make_ff(nid="FF-01",label="Following Failure"):
    return {"id":new_id(),"type":"FF","node_id":nid,"label":label,"gate":"OR",
            "children":[make_if("IF-001","Initial Failure A"),make_if("IF-002","Initial Failure B")],
            "value":None,"note":"","flag":"none"}
def make_sf(nid="SF-01",label="System Failure"):
    return {"id":new_id(),"type":"SF","node_id":nid,"label":label,"gate":"OR","weight":1,
            "children":[make_ff("FF-01","Following Failure 1"),make_ff("FF-02","Following Failure 2")],
            "value":None,"note":"","flag":"none"}
def build_default(hid="H-01",hlabel="Toxic Hazard"):
    tree={"id":new_id(),"type":"HAZARD","node_id":hid,"label":hlabel,
          "value":1e-7,"gate":"OR","children":[make_sf("SF-01","System Failure 1"),
           make_sf("SF-02","System Failure 2"),make_sf("SF-03","System Failure 3")],
          "note":"","flag":"none"}
    return redistribute(tree,"equal")

# ─── session state ────────────────────────────────────────────────────────────
if "project_name" not in st.session_state: st.session_state.project_name="My FTA Project"
if "hazards" not in st.session_state: st.session_state.hazards=[build_default()]
if "dist_mode" not in st.session_state: st.session_state.dist_mode="equal"
if "active_h" not in st.session_state: st.session_state.active_h=0
if "selected_node_id" not in st.session_state: st.session_state.selected_node_id=None

FLAG_OPTIONS={"none":"—","ok":"✓ Confirmed","tbc":"TBC","reword":"Reword Required"}

def get_tree(): return st.session_state.hazards[st.session_state.active_h]
def set_tree(t):
    st.session_state.hazards[st.session_state.active_h]=t

# ─── D3 VISUAL TREE HTML ──────────────────────────────────────────────────────
def build_tree_html(tree_data, selected_id=None):
    tree_json = json.dumps(tree_data)
    selected_json = json.dumps(selected_id)
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:#08080f; font-family:'IBM Plex Mono',monospace; overflow:hidden; }}
  #tree-container {{ width:100%; height:100%; position:relative; overflow:hidden; cursor:grab; }}
  #tree-container.dragging {{ cursor:grabbing; }}
  svg {{ width:100%; height:100%; }}

  .node-hazard rect  {{ fill:#1a0a35; stroke:#7c3aed; stroke-width:2; rx:10; }}
  .node-SF rect      {{ fill:#071525; stroke:#0ea5e9; stroke-width:1.5; }}
  .node-FF rect      {{ fill:#081a0e; stroke:#16a34a; stroke-width:1; }}
  .node-IF rect      {{ fill:#1c1000; stroke:#d97706; stroke-width:1; }}

  .node-hazard rect.selected {{ stroke:#c084fc; stroke-width:3; filter:drop-shadow(0 0 8px #7c3aed); }}
  .node-SF rect.selected     {{ stroke:#38bdf8; stroke-width:2.5; filter:drop-shadow(0 0 6px #0ea5e9); }}
  .node-FF rect.selected     {{ stroke:#4ade80; stroke-width:2; filter:drop-shadow(0 0 5px #16a34a); }}
  .node-IF rect.selected     {{ stroke:#fbbf24; stroke-width:2; filter:drop-shadow(0 0 5px #d97706); }}

  .node-hazard rect:hover    {{ filter:drop-shadow(0 0 10px #7c3aed88); cursor:pointer; }}
  .node-SF rect:hover        {{ filter:drop-shadow(0 0 8px #0ea5e988); cursor:pointer; }}
  .node-FF rect:hover        {{ filter:drop-shadow(0 0 6px #16a34a88); cursor:pointer; }}
  .node-IF rect:hover        {{ filter:drop-shadow(0 0 5px #d9770688); cursor:pointer; }}

  .node-id   {{ font-size:9px; font-weight:700; letter-spacing:1px; fill:#94a3b8; }}
  .node-label {{ font-size:10px; fill:#e2e8f0; font-weight:500; }}
  .node-prob  {{ font-size:10px; font-weight:700; font-family:'IBM Plex Mono',monospace; }}
  .node-target {{ font-size:8px; fill:#64748b; }}
  .node-gate  {{ font-size:8px; font-weight:800; letter-spacing:1px; }}
  .node-flag  {{ font-size:8px; font-weight:700; }}

  .link {{ fill:none; stroke:#334155; stroke-width:1.2; }}

  .gate-or  {{ fill:#f87171; }}
  .gate-and {{ fill:#60a5fa; }}
  .prob-ok   {{ fill:#4ade80; }}
  .prob-over {{ fill:#f87171; }}
  .prob-na   {{ fill:#64748b; }}

  .controls {{ position:absolute; bottom:12px; right:12px; display:flex; gap:6px; z-index:10; }}
  .ctrl-btn {{
    background:#0d0d1a; border:1px solid #334155; color:#94a3b8;
    border-radius:6px; padding:5px 10px; font-size:11px;
    cursor:pointer; font-family:'IBM Plex Mono',monospace;
    transition:all 0.15s;
  }}
  .ctrl-btn:hover {{ border-color:#7c3aed; color:#c084fc; }}

  .legend {{ position:absolute; top:10px; left:10px; display:flex; gap:10px; z-index:10; }}
  .leg-item {{ display:flex; align-items:center; gap:5px; font-size:9px; color:#64748b; }}
  .leg-dot {{ width:8px; height:8px; border-radius:2px; }}
</style>
</head>
<body>
<div id="tree-container">
  <svg id="svg"></svg>
  <div class="legend">
    <div class="leg-item"><div class="leg-dot" style="background:#7c3aed"></div>Hazard</div>
    <div class="leg-item"><div class="leg-dot" style="background:#0ea5e9"></div>SF</div>
    <div class="leg-item"><div class="leg-dot" style="background:#16a34a"></div>FF</div>
    <div class="leg-item"><div class="leg-dot" style="background:#d97706"></div>IF</div>
    <div class="leg-item"><div class="leg-dot" style="background:#f87171;border-radius:10px"></div>OR gate</div>
    <div class="leg-item"><div class="leg-dot" style="background:#60a5fa;border-radius:10px"></div>AND gate</div>
  </div>
  <div class="controls">
    <button class="ctrl-btn" onclick="zoomIn()">＋ Zoom</button>
    <button class="ctrl-btn" onclick="zoomOut()">－ Zoom</button>
    <button class="ctrl-btn" onclick="resetView()">⊙ Reset</button>
    <button class="ctrl-btn" onclick="expandAll()">▼ Expand</button>
    <button class="ctrl-btn" onclick="collapseAll()">▶ Collapse</button>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
const RAW_TREE = {tree_json};
const SELECTED_ID = {selected_json};

// ── node dimensions by type ──
const NODE_W = {{ HAZARD:200, SF:180, FF:170, IF:155 }};
const NODE_H = {{ HAZARD:70,  SF:65,  FF:60,  IF:55  }};
const V_GAP = 60;
const H_GAP = 20;

// ── calc engine (mirrors Python) ──
function calcNode(node) {{
  const ch = (node.children||[]).filter(c=>!c._collapsed);
  const allCh = node.children||[];
  if (!allCh.length) return node.value ?? null;
  const src = node._collapsed ? [] : allCh;
  const vals = src.map(calcNode).filter(v=>v!==null&&isFinite(v));
  if (!vals.length) return node.value ?? null;
  if ((node.gate||"OR")==="OR") return vals.reduce((a,b)=>a+b,0);
  return vals.reduce((a,b)=>a*b,1);
}}

function fmtP(v) {{
  if (v===null||v===undefined||!isFinite(v)) return "–";
  if (v===0) return "0";
  return v.toExponential(2);
}}

// ── tree layout ──
let treeData = JSON.parse(JSON.stringify(RAW_TREE));
let collapsed = new Set();
let svgEl, gMain, zoom;
let transform = {{ x:40, y:40, k:1 }};

function getVisible(node) {{
  const n = {{...node, _collapsed: collapsed.has(node.id)}};
  if (!n._collapsed && node.children) {{
    n.children = node.children.map(getVisible);
  }} else {{
    n._hiddenChildren = node.children;
    n.children = [];
  }}
  return n;
}}

function computeLayout(root) {{
  // assign positions using simple recursive layout
  function measure(node) {{
    const w = NODE_W[node.type]||160;
    const h = NODE_H[node.type]||55;
    node._w = w; node._h = h;
    if (!node.children||!node.children.length) {{
      node._subtreeW = w;
      return;
    }}
    node.children.forEach(measure);
    const totalChildW = node.children.reduce((s,c)=>s+c._subtreeW,0)
                      + H_GAP*(node.children.length-1);
    node._subtreeW = Math.max(w, totalChildW);
  }}

  function place(node, x, y) {{
    node._x = x; node._y = y;
    if (!node.children||!node.children.length) return;
    const totalChildW = node.children.reduce((s,c)=>s+c._subtreeW,0)
                      + H_GAP*(node.children.length-1);
    let cx = x - totalChildW/2;
    for (const ch of node.children) {{
      place(ch, cx + ch._subtreeW/2, y + node._h + V_GAP);
      cx += ch._subtreeW + H_GAP;
    }}
  }}

  measure(root);
  place(root, root._subtreeW/2, 0);
  return root;
}}

function allNodes(node, arr=[]) {{
  arr.push(node);
  (node.children||[]).forEach(c=>allNodes(c,arr));
  return arr;
}}
function allLinks(node, arr=[]) {{
  (node.children||[]).forEach(c=>{{
    arr.push({{source:node, target:c}});
    allLinks(c,arr);
  }});
  return arr;
}}

// ── render ──
function render() {{
  const visible = getVisible(treeData);
  computeLayout(visible);

  const nodes = allNodes(visible);
  const links = allLinks(visible);

  // bounds
  const minX = d3.min(nodes, d=>d._x - d._w/2) - 20;
  const minY = d3.min(nodes, d=>d._y) - 20;

  const svg = d3.select("#svg");
  const g = svg.select("g.main");

  // ── links ──
  g.selectAll(".link").data(links, d=>d.source.id+"-"+d.target.id)
    .join(
      enter => enter.append("path").attr("class","link").attr("opacity",0)
        .call(e=>e.transition().duration(300).attr("opacity",1)),
      update => update,
      exit => exit.transition().duration(200).attr("opacity",0).remove()
    )
    .attr("d", d=>{{
      const sx=d.source._x, sy=d.source._y+d.source._h;
      const tx=d.target._x, ty=d.target._y;
      const my=(sy+ty)/2;
      return `M${{sx}},${{sy}} C${{sx}},${{my}} ${{tx}},${{my}} ${{tx}},${{ty}}`;
    }});

  // ── nodes ──
  const nodeGs = g.selectAll("g.node-group")
    .data(nodes, d=>d.id)
    .join(
      enter => {{
        const ng = enter.append("g").attr("class", d=>`node-group node-${{d.type}}`)
          .attr("transform", d=>`translate(${{d._x - d._w/2}},${{d._y}})`)
          .attr("opacity",0)
          .on("click", (event, d) => {{
            event.stopPropagation();
            nodeClicked(d.id);
          }});
        ng.transition().duration(300).attr("opacity",1);
        ng.append("rect");
        ng.append("text").attr("class","node-id");
        ng.append("text").attr("class","node-label");
        ng.append("text").attr("class","node-prob");
        ng.append("text").attr("class","node-target");
        ng.append("text").attr("class","node-gate");
        ng.append("text").attr("class","node-flag");
        ng.append("circle").attr("class","collapse-btn");
        ng.append("text").attr("class","collapse-icon");
        return ng;
      }},
      update => update.transition().duration(300)
        .attr("transform", d=>`translate(${{d._x - d._w/2}},${{d._y}})`),
      exit => exit.transition().duration(200).attr("opacity",0).remove()
    );

  // rect
  nodeGs.select("rect")
    .attr("width", d=>d._w).attr("height", d=>d._h)
    .attr("rx",8)
    .attr("class", d=> d.id===SELECTED_ID ? "selected" : "");

  // node_id text
  nodeGs.select("text.node-id")
    .attr("x",8).attr("y",14)
    .text(d=>d.node_id||"");

  // label — wrap long text
  nodeGs.select("text.node-label")
    .attr("x",8).attr("y",27)
    .text(d=>{{
      const max = Math.floor(d._w/6.5);
      const lbl = d.label||"";
      return lbl.length>max ? lbl.slice(0,max-1)+"…" : lbl;
    }});

  // probability
  nodeGs.select("text.node-prob")
    .attr("x",8).attr("y",40)
    .attr("class", d=>{{
      const calc=calcNode(d), tgt=d._target;
      const ok = calc!==null && tgt && calc<=tgt*1.001;
      return "node-prob " + (calc===null?"prob-na": ok?"prob-ok":"prob-over");
    }})
    .text(d=>{{
      const calc=calcNode(d);
      return `P=${fmtP(calc)}`;
    }});

  // target
  nodeGs.select("text.node-target")
    .attr("x",8).attr("y",51)
    .text(d=> d._target ? `tgt:${{fmtP(d._target)}}` : (d.type==="IF"?`P=${{fmtP(d.value)}}`:""));

  // gate badge
  nodeGs.select("text.node-gate")
    .attr("x", d=>d._w-30).attr("y",14)
    .attr("class", d=>"node-gate " + ((d.gate||"OR")==="OR"?"gate-or":"gate-and"))
    .text(d=>d.gate||"OR");

  // flag
  nodeGs.select("text.node-flag")
    .attr("x", d=>d._w-30).attr("y",27)
    .attr("fill", d=>d.flag==="tbc"?"#fde68a":d.flag==="reword"?"#fed7aa":d.flag==="ok"?"#86efac":"transparent")
    .text(d=>d.flag==="tbc"?"TBC":d.flag==="reword"?"RWD":d.flag==="ok"?"✓":"");

  // collapse button (circle at bottom center)
  nodeGs.select("circle.collapse-btn")
    .attr("cx", d=>d._w/2).attr("cy", d=>d._h)
    .attr("r",7)
    .attr("fill", d=>(d._hiddenChildren||[]).length||(d.children||[]).length ? "#1e1e3a":"transparent")
    .attr("stroke", d=>(d._hiddenChildren||[]).length||(d.children||[]).length ? "#334155":"transparent")
    .style("cursor","pointer")
    .on("click", (event,d)=>{{ event.stopPropagation(); toggleCollapse(d.id); }});

  nodeGs.select("text.collapse-icon")
    .attr("x", d=>d._w/2).attr("y", d=>d._h+4)
    .attr("text-anchor","middle").attr("font-size","8px").attr("fill","#94a3b8")
    .style("pointer-events","none")
    .text(d=>{{
      const hasKids=(d._hiddenChildren||[]).length||(d.children||[]).length;
      if (!hasKids) return "";
      return collapsed.has(d.id) ? "▶" : "▼";
    }});
}}

function toggleCollapse(id) {{
  if (collapsed.has(id)) collapsed.delete(id);
  else collapsed.add(id);
  render();
}}

function expandAll() {{ collapsed.clear(); render(); }}
function collapseAll() {{
  function addCollapsible(node) {{
    if ((node.children||[]).length) {{ collapsed.add(node.id); node.children.forEach(addCollapsible); }}
  }}
  addCollapsible(treeData);
  render();
}}

function nodeClicked(id) {{
  window.parent.postMessage({{type:"node_selected", nodeId:id}}, "*");
}}

function zoomIn()  {{ transform.k=Math.min(transform.k*1.3,4); applyTransform(); }}
function zoomOut() {{ transform.k=Math.max(transform.k/1.3,0.15); applyTransform(); }}

function applyTransform() {{
  d3.select("g.main").attr("transform",`translate(${{transform.x}},${{transform.y}}) scale(${{transform.k}})`);
}}

function resetView() {{
  const visible=getVisible(treeData);
  computeLayout(visible);
  const nodes=allNodes(visible);
  const svgW=document.getElementById("svg").clientWidth||1200;
  const svgH=document.getElementById("svg").clientHeight||700;
  const minX=d3.min(nodes,d=>d._x-d._w/2);
  const maxX=d3.max(nodes,d=>d._x+d._w/2);
  const minY=d3.min(nodes,d=>d._y);
  const maxY=d3.max(nodes,d=>d._y+d._h);
  const tw=maxX-minX, th=maxY-minY;
  const k=Math.min((svgW-80)/tw, (svgH-80)/th, 1.2);
  transform.k=k;
  transform.x=(svgW-tw*k)/2 - minX*k;
  transform.y=40;
  applyTransform();
}}

// ── init ──
window.addEventListener("load", ()=>{{
  const svg=d3.select("#svg");
  svgEl=svg.node();

  svg.append("g").attr("class","main");

  // pan + zoom
  const zoomBehavior = d3.zoom()
    .scaleExtent([0.1,4])
    .on("zoom", (event)=>{{
      transform={{x:event.transform.x, y:event.transform.y, k:event.transform.k}};
      d3.select("g.main").attr("transform", event.transform);
    }});
  svg.call(zoomBehavior);

  render();
  setTimeout(resetView, 100);
}});

// live update from streamlit
window.addEventListener("message", (e)=>{{
  if (e.data && e.data.type==="update_tree") {{
    treeData=e.data.tree;
    render();
  }}
}});
</script>
</body>
</html>
"""

# ─── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚠ FTA Tool v3")
    st.divider()
    st.session_state.project_name = st.text_input("Project", value=st.session_state.project_name)

    # hazard nav
    st.markdown("**Hazards**")
    for i,h in enumerate(st.session_state.hazards):
        hc=calc_node(h); hok=hc is not None and hc<=h["value"]*1.001
        ind="🟢" if hok else "🔴"
        if st.button(f"{ind} {h['node_id']} {h['label']}", key=f"hnav_{i}", use_container_width=True):
            st.session_state.active_h=i; st.session_state.selected_node_id=None; st.rerun()

    c1,c2=st.columns(2)
    with c1:
        if st.button("➕ Hazard", use_container_width=True):
            n=len(st.session_state.hazards)+1
            st.session_state.hazards.append(build_default(f"H-{n:02d}",f"Hazard {n}"))
            st.session_state.active_h=len(st.session_state.hazards)-1
            st.session_state.selected_node_id=None; st.rerun()
    with c2:
        if st.button("🗑 Hazard", use_container_width=True):
            if len(st.session_state.hazards)>1:
                st.session_state.hazards.pop(st.session_state.active_h)
                st.session_state.active_h=max(0,st.session_state.active_h-1)
                st.session_state.selected_node_id=None; st.rerun()

    st.divider()

    # dist mode
    st.markdown("**Distribution**")
    nm=st.radio("",["equal","weighted"], index=0 if st.session_state.dist_mode=="equal" else 1,
                horizontal=True, key="dist_radio")
    if nm!=st.session_state.dist_mode:
        st.session_state.dist_mode=nm
        set_tree(redistribute(get_tree(),nm)); st.rerun()

    st.divider()

    # save/load
    save_data=json.dumps({"project":st.session_state.project_name,
        "saved_at":datetime.now().isoformat(),
        "dist_mode":st.session_state.dist_mode,
        "hazards":st.session_state.hazards},indent=2)
    st.download_button("💾 Save JSON", data=save_data,
        file_name=f"{st.session_state.project_name.replace(' ','_')}.json",
        mime="application/json", use_container_width=True)

    uploaded=st.file_uploader("📂 Load JSON", type="json", label_visibility="collapsed")
    if uploaded:
        try:
            d=json.load(uploaded)
            st.session_state.hazards=d["hazards"]
            st.session_state.dist_mode=d.get("dist_mode","equal")
            st.session_state.project_name=d.get("project","Project")
            st.session_state.active_h=0; st.session_state.selected_node_id=None
            st.success("Loaded!"); st.rerun()
        except Exception as e: st.error(str(e))

    st.divider()

    # CSV export
    if st.button("📊 Export CSV", use_container_width=True):
        rows=[]
        for h in st.session_state.hazards:
            hc2=calc_node(h)
            for sf in h.get("children",[]):
                sfc=calc_node(sf)
                for ff in sf.get("children",[]):
                    ffc=calc_node(ff)
                    for ifn in ff.get("children",[]):
                        rows.append({"Hazard":h["node_id"],"H_Label":h["label"],"H_Target":h["value"],"H_Calc":hc2,
                            "SF":sf["node_id"],"SF_Label":sf["label"],"SF_Gate":sf["gate"],"SF_Calc":sfc,"SF_Tgt":sf.get("_target"),
                            "FF":ff["node_id"],"FF_Label":ff["label"],"FF_Gate":ff["gate"],"FF_Calc":ffc,"FF_Tgt":ff.get("_target"),
                            "IF":ifn["node_id"],"IF_Label":ifn["label"],"IF_Val":ifn.get("value"),"IF_Tgt":ifn.get("_target"),
                            "Flag":ifn.get("flag",""),"Note":ifn.get("note","")})
        if rows:
            df=pd.DataFrame(rows)
            st.download_button("⬇ Download",df.to_csv(index=False),
                file_name=f"{st.session_state.project_name}_export.csv",mime="text/csv",use_container_width=True)

# ─── main area ────────────────────────────────────────────────────────────────
tree=get_tree()
hcalc=calc_node(tree); hok=hcalc is not None and hcalc<=tree["value"]*1.001

st.markdown(f"## ⚠ {st.session_state.project_name} — {tree.get('node_id','')} {tree.get('label','')}")

# top stats
sc1,sc2,sc3,sc4,sc5=st.columns(5)
sc1.metric("Hazard Target", fmt(tree["value"]))
color="✅" if hok else "❌"
sc2.metric("Calculated", f"{color} {fmt(hcalc)}")
pct=f"{hcalc/tree['value']*100:.1f}%" if hcalc and tree["value"] else "–"
sc3.metric("Budget Used", pct)
sc4.metric("System Failures", len(tree.get("children",[])))
ff_t=sum(len(sf.get("children",[])) for sf in tree.get("children",[]))
sc5.metric("Following Failures", ff_t)

st.divider()

tab_tree, tab_edit, tab_audit = st.tabs(["🌲 Visual Tree", "✏️ Edit Panel", "🧮 Audit Trail"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: VISUAL TREE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_tree:
    st.caption("Click any node to select it · Drag to pan · Scroll to zoom · Use buttons for zoom/collapse")

    # Render the D3 tree
    tree_html = build_tree_html(tree, st.session_state.selected_node_id)
    components.html(tree_html, height=680, scrolling=False)

    st.divider()

    # Add nodes panel below tree
    st.markdown("**Quick Add Nodes**")
    qa1,qa2,qa3,qa4,qa5 = st.columns(5)
    with qa1:
        if st.button("➕ Add SF", use_container_width=True, type="primary"):
            n=len(tree.get("children",[]))+1
            tree=add_child(tree, tree["id"], make_sf(f"SF-{n:02d}",f"System Failure {n}"))
            st.session_state.dist_mode="equal"
            tree=redistribute(tree,"equal"); set_tree(tree); st.rerun()
    with qa2:
        sel=st.session_state.selected_node_id
        sel_node=find_node(tree,sel) if sel else None
        can_add_ff = sel_node and sel_node["type"]=="SF"
        if st.button("➕ Add FF to selected SF", use_container_width=True, disabled=not can_add_ff):
            n=len(sel_node.get("children",[]))+1
            new_ff=make_ff(f"FF-{n:02d}",f"Following Failure {n}")
            tree=add_child(tree, sel, new_ff)
            tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()
    with qa3:
        can_add_if = sel_node and sel_node["type"]=="FF"
        if st.button("➕ Add IF to selected FF", use_container_width=True, disabled=not can_add_if):
            n=len(sel_node.get("children",[]))+1
            new_if=make_if(f"IF-{n:03d}",f"Initial Failure {n}")
            tree=add_child(tree, sel, new_if)
            tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()
    with qa4:
        can_del = sel_node and sel_node["type"] in ("SF","FF","IF")
        if st.button("🗑 Delete selected", use_container_width=True, disabled=not can_del):
            tree=delete_node_from_tree(tree, sel)
            tree=redistribute(tree,st.session_state.dist_mode)
            st.session_state.selected_node_id=None; set_tree(tree); st.rerun()
    with qa5:
        if st.button("🔄 Recalculate", use_container_width=True):
            tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()

    # Show selected node info
    if sel_node:
        sc=calc_node(sel_node)
        sok=sc is not None and sel_node.get("_target") and sc<=sel_node["_target"]*1.001
        st.markdown(f"""
        <div style="background:#0f0f20;border:1px solid #334155;border-radius:10px;padding:12px;margin-top:8px;font-family:'IBM Plex Mono',monospace;font-size:12px;">
        <strong style="color:#e2e8f0">{sel_node.get('node_id','')} — {sel_node.get('label','')}</strong><br>
        <span style="color:#64748b">Type: {sel_node['type']} · Gate: {sel_node.get('gate','OR')}</span><br>
        <span style="color:{'#4ade80' if sok else '#f87171'}">Calc: {fmt(sc)}</span>
        <span style="color:#64748b"> · Target: {fmt(sel_node.get('_target'))}</span>
        {"<br><span style='color:#fbbf24'>⚠ " + FLAG_OPTIONS.get(sel_node.get('flag','none'),'') + "</span>" if sel_node.get('flag','none')!='none' else ""}
        </div>
        """, unsafe_allow_html=True)
        st.info("👉 Go to **Edit Panel** tab to edit this node's values")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: EDIT PANEL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_edit:
    sel_id=st.session_state.selected_node_id
    sel_node=find_node(tree,sel_id) if sel_id else None

    col_tree_edit, col_node_edit = st.columns([1,1])

    with col_tree_edit:
        st.markdown("#### 🌲 Tree Structure")
        st.caption("Click a node in the Visual Tree tab first, then edit here")

        # Hazard settings
        with st.expander(f"⚠ {tree.get('node_id','')} — {tree.get('label','')} (HAZARD)", expanded=True):
            e1,e2=st.columns(2)
            with e1:
                nid=st.text_input("Hazard ID", value=tree.get("node_id",""), key="edit_h_nid")
                if nid!=tree.get("node_id"): tree=update_node_in_tree(tree,tree["id"],{"node_id":nid}); set_tree(tree); st.rerun()
            with e2:
                lbl=st.text_input("Label", value=tree.get("label",""), key="edit_h_lbl")
                if lbl!=tree.get("label"): tree=update_node_in_tree(tree,tree["id"],{"label":lbl}); set_tree(tree); st.rerun()
            e3,e4=st.columns(2)
            with e3:
                tval=st.number_input("Target P", value=float(tree.get("value",1e-7)), format="%.2e", step=1e-8, key="edit_h_val")
                if abs(tval-tree.get("value",1e-7))>1e-20:
                    tree=update_node_in_tree(tree,tree["id"],{"value":tval})
                    tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()
            with e4:
                hg=st.selectbox("Gate",["OR","AND"],index=0 if tree.get("gate","OR")=="OR" else 1, key="edit_h_gate")
                if hg!=tree.get("gate"):
                    tree=update_node_in_tree(tree,tree["id"],{"gate":hg})
                    tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()
            hn=st.text_input("Notes", value=tree.get("note",""), key="edit_h_note")
            if hn!=tree.get("note"): tree=update_node_in_tree(tree,tree["id"],{"note":hn}); set_tree(tree); st.rerun()

    with col_node_edit:
        st.markdown("#### ✏️ Selected Node Editor")
        if not sel_node:
            st.info("Click any node in the **Visual Tree** tab to select it, then edit its properties here.")
            st.markdown("""
            **How to select a node:**
            1. Go to 🌲 Visual Tree tab
            2. Click on any SF / FF / IF node
            3. Come back here to edit
            """)
        else:
            t=sel_node["type"]
            color_map={"SF":"#0ea5e9","FF":"#16a34a","IF":"#d97706","HAZARD":"#7c3aed"}
            st.markdown(f'<div style="background:#0f0f20;border-left:3px solid {color_map.get(t,"#666")};border-radius:8px;padding:12px;margin-bottom:12px;">', unsafe_allow_html=True)
            st.markdown(f"**Editing: `{sel_node.get('node_id','')}` — {t}**")

            n1,n2=st.columns(2)
            with n1:
                new_nid=st.text_input("Node ID", value=sel_node.get("node_id",""), key=f"sel_nid")
            with n2:
                new_lbl=st.text_input("Label", value=sel_node.get("label",""), key=f"sel_lbl")

            n3,n4=st.columns(2)
            with n3:
                new_gate=st.selectbox("Gate",["OR","AND"], index=0 if sel_node.get("gate","OR")=="OR" else 1, key="sel_gate")
            with n4:
                new_flag=st.selectbox("Flag", list(FLAG_OPTIONS.keys()),
                    format_func=lambda x:FLAG_OPTIONS[x],
                    index=list(FLAG_OPTIONS.keys()).index(sel_node.get("flag","none")),
                    key="sel_flag")

            if t=="IF":
                new_val=st.number_input("Probability P =", value=float(sel_node.get("value") or 1e-5),
                    format="%.2e", step=1e-6, key="sel_val")
            elif t=="SF" and st.session_state.dist_mode=="weighted":
                new_weight=st.number_input("Weight", value=float(sel_node.get("weight",1)),
                    min_value=0.01, step=0.1, key="sel_weight")

            new_note=st.text_area("Notes", value=sel_node.get("note",""), key="sel_note", height=60)

            # calc display
            sc=calc_node(sel_node); tgt=sel_node.get("_target")
            sok=sc is not None and tgt and sc<=tgt*1.001
            st.markdown(f"""
            <div style="display:flex;gap:16px;margin-top:8px;font-family:'IBM Plex Mono',monospace;font-size:11px;">
              <span style="color:{'#4ade80' if sok else '#f87171'}">Calc: <strong>{fmt(sc)}</strong></span>
              <span style="color:#64748b">Target: {fmt(tgt)}</span>
              <span>{"✓ OK" if sok else "✗ OVER"}</span>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💾 Apply Changes", type="primary", use_container_width=True, key="apply_node"):
                patch={"node_id":new_nid,"label":new_lbl,"gate":new_gate,"flag":new_flag,"note":new_note}
                if t=="IF": patch["value"]=new_val
                if t=="SF" and st.session_state.dist_mode=="weighted": patch["weight"]=new_weight
                tree=update_node_in_tree(tree,sel_id,patch)
                tree=redistribute(tree,st.session_state.dist_mode)
                set_tree(tree); st.rerun()

            if t in ("SF","FF","IF"):
                st.markdown("---")
                d1,d2=st.columns(2)
                with d1:
                    if t=="SF" and st.button("➕ Add FF inside", use_container_width=True):
                        n=len(sel_node.get("children",[]))+1
                        tree=add_child(tree,sel_id,make_ff(f"FF-{n:02d}",f"Following Failure {n}"))
                        tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()
                    if t=="FF" and st.button("➕ Add IF inside", use_container_width=True):
                        n=len(sel_node.get("children",[]))+1
                        tree=add_child(tree,sel_id,make_if(f"IF-{n:03d}",f"Initial Failure {n}"))
                        tree=redistribute(tree,st.session_state.dist_mode); set_tree(tree); st.rerun()
                with d2:
                    if st.button("🗑 Delete node", use_container_width=True):
                        tree=delete_node_from_tree(tree,sel_id)
                        tree=redistribute(tree,st.session_state.dist_mode)
                        st.session_state.selected_node_id=None; set_tree(tree); st.rerun()

    # node selector fallback
    st.divider()
    st.markdown("#### 🔍 Select Node by ID (if tree click doesn't register)")
    all_nodes_flat=[]
    def flatten(node):
        all_nodes_flat.append((node["id"], f"{node.get('node_id','')} — {node.get('label','')} [{node['type']}]"))
        for c in node.get("children",[]): flatten(c)
    flatten(tree)
    node_map={v:k for k,v in all_nodes_flat}
    sel_label=next((v for k,v in all_nodes_flat if k==st.session_state.selected_node_id),all_nodes_flat[0][1] if all_nodes_flat else "")
    chosen=st.selectbox("Select node", [v for _,v in all_nodes_flat], index=[v for _,v in all_nodes_flat].index(sel_label) if sel_label in [v for _,v in all_nodes_flat] else 0, key="node_selector")
    if st.button("Select this node", use_container_width=True):
        st.session_state.selected_node_id=node_map.get(chosen); st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_audit:
    st.markdown("### 🧮 Calculation Audit Trail")
    lines=[]
    hcalc2=calc_node(tree)
    lines.append(f"{'─'*60}")
    lines.append(f"PROJECT  : {st.session_state.project_name}")
    lines.append(f"HAZARD   : {tree.get('node_id','')}  {tree.get('label','')}")
    lines.append(f"TARGET   : {fmt(tree.get('value'))}")
    lines.append(f"GATE     : {tree.get('gate','OR')}")
    lines.append(f"{'─'*60}")
    for sf in tree.get("children",[]):
        sfc=calc_node(sf); sok2="✓" if sfc and sf.get("_target") and sfc<=sf["_target"]*1.001 else "✗"
        lines.append(f"\n  {sf.get('node_id','SF-??')}  {sf.get('label','')}  [gate:{sf.get('gate','OR')}]")
        lines.append(f"  calc:{fmt(sfc)}  target:{fmt(sf.get('_target'))}  {sok2}")
        if sf.get("note"): lines.append(f"  note: {sf['note']}")
        for ff in sf.get("children",[]):
            ffc=calc_node(ff); fok="✓" if ffc and ff.get("_target") and ffc<=ff["_target"]*1.001 else "✗"
            lines.append(f"    ├─ {ff.get('node_id','FF-??')}  {ff.get('label','')}  [gate:{ff.get('gate','OR')}]")
            lines.append(f"    │  calc:{fmt(ffc)}  tgt:{fmt(ff.get('_target'))}  {fok}")
            for ifn in ff.get("children",[]):
                ifv=ifn.get("value"); ift=ifn.get("_target")
                iok="✓" if ifv and ift and ifv<=ift*1.001 else "✗"
                flag_str=f"[{ifn.get('flag','')}]" if ifn.get("flag","none")!="none" else ""
                lines.append(f"    │  └─ {ifn.get('node_id','IF-??')}  {ifn.get('label','')}  P={fmt(ifv)}  tgt:{fmt(ift)}  {iok} {flag_str}")
    lines.append(f"\n{'─'*60}")
    lines.append(f"TOTAL CALC  : {fmt(hcalc2)}")
    lines.append(f"TARGET      : {fmt(tree.get('value'))}")
    if hcalc2 and tree.get("value"):
        pct2=hcalc2/tree["value"]*100
        lines.append(f"BUDGET USED : {pct2:.1f}%  {'✓ WITHIN TARGET' if pct2<=100 else '✗ EXCEEDS TARGET'}")
    st.code("\n".join(lines), language=None)

    st.divider()
    st.markdown("### 📋 Full Node Table")
    rows=[]
    for sf in tree.get("children",[]):
        sfc=calc_node(sf)
        for ff in sf.get("children",[]):
            ffc=calc_node(ff)
            for ifn in ff.get("children",[]):
                ifv=ifn.get("value"); ift=ifn.get("_target")
                rows.append({"SF":sf.get("node_id"),"SF Label":sf.get("label"),"SF Calc":fmt(sfc),"SF Tgt":fmt(sf.get("_target")),
                    "FF":ff.get("node_id"),"FF Label":ff.get("label"),"FF Gate":ff.get("gate"),"FF Calc":fmt(ffc),
                    "IF":ifn.get("node_id"),"IF Label":ifn.get("label"),"IF P":fmt(ifv),"IF Tgt":fmt(ift),
                    "OK":"✓" if ifv and ift and ifv<=ift*1.001 else "✗",
                    "Flag":FLAG_OPTIONS.get(ifn.get("flag","none"),""),"Note":ifn.get("note","")})
    if rows:
        df=pd.DataFrame(rows)
        st.dataframe(df,use_container_width=True,height=350)
        st.download_button("⬇ Download CSV",df.to_csv(index=False),
            file_name=f"{tree.get('node_id','hazard')}_audit.csv",mime="text/csv")
