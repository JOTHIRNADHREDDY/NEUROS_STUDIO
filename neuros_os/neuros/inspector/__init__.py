"""
neuros.inspector
================
Phase 2 — Topic & Service Inspector + Node Graph Visualizer.

Web UI shows all active topics, message types, publish rates, subscribers.
Live interactive node graph in browser. Replaces rqt_graph.

Usage
-----
    from neuros.inspector import Inspector
    inspector = Inspector(robot, port=8800)
    inspector.start()
    # Open http://localhost:8800 in browser
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.inspector")


class _TopicStats:
    """Track statistics for a single topic."""
    __slots__ = ('topic', 'msg_count', 'last_time', 'first_time',
                 'sub_count', 'last_data', 'hz', '_recent_times')

    def __init__(self, topic: str):
        self.topic = topic
        self.msg_count = 0
        self.last_time = 0.0
        self.first_time = 0.0
        self.sub_count = 0
        self.last_data: Any = None
        self.hz = 0.0
        self._recent_times: list = []

    def record(self, data: Any) -> None:
        now = time.time()
        if self.msg_count == 0:
            self.first_time = now
        self.msg_count += 1
        self.last_time = now
        self.last_data = data
        self._recent_times.append(now)
        # Keep last 50 timestamps for Hz calc
        if len(self._recent_times) > 50:
            self._recent_times = self._recent_times[-50:]
        # Calculate Hz
        if len(self._recent_times) >= 2:
            dt = self._recent_times[-1] - self._recent_times[0]
            if dt > 0:
                self.hz = round((len(self._recent_times) - 1) / dt, 1)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic, "count": self.msg_count,
            "hz": self.hz, "subscribers": self.sub_count,
            "last_time": self.last_time,
            "last_data": _safe_serialize(self.last_data),
        }


class Inspector:
    """
    Live topic/service inspector with embedded web dashboard.

    Features:
    - Real-time topic statistics (Hz, message count, last value)
    - Node connectivity graph (JSON API for D3.js visualization)
    - Subscriber tracking
    - HTTP JSON API + single-page HTML dashboard
    """

    def __init__(self, robot: "Robot", *, port: int = 8800) -> None:
        self._robot = robot
        self._port = port
        self._stats: Dict[str, _TopicStats] = {}
        self._lock = threading.Lock()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None

    def start(self) -> "Inspector":
        """Start the inspector HTTP server and bus monitor."""
        self._running = True
        # Subscribe to all bus messages
        try:
            self._robot._bus.subscribe("#", self._on_message, node_id="__inspector__")
        except Exception as e:
            logger.warning("[INSPECTOR] Bus subscribe failed: %s", e)

        # Start polling thread for node info
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="neuros-inspector-poll", daemon=True)
        self._poll_thread.start()

        # Start HTTP server
        inspector = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self._respond(200, "text/html", _DASHBOARD_HTML)
                elif self.path == "/api/topics":
                    self._respond(200, "application/json",
                                  json.dumps(inspector.get_topics()))
                elif self.path == "/api/nodes":
                    self._respond(200, "application/json",
                                  json.dumps(inspector.get_nodes()))
                elif self.path == "/api/graph":
                    self._respond(200, "application/json",
                                  json.dumps(inspector.get_graph()))
                elif self.path == "/api/status":
                    self._respond(200, "application/json",
                                  json.dumps(inspector.get_status()))
                else:
                    self._respond(404, "text/plain", "Not Found")

            def _respond(self, code, content_type, body):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body.encode() if isinstance(body, str) else body)

            def log_message(self, *args):
                pass  # Suppress default logging

        try:
            self._server = HTTPServer(("0.0.0.0", self._port), Handler)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="neuros-inspector-http", daemon=True)
            self._thread.start()
            logger.info("[INSPECTOR] Dashboard: http://localhost:%d", self._port)
        except Exception as e:
            logger.error("[INSPECTOR] HTTP server failed: %s", e)
        return self

    def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.shutdown()
        try:
            self._robot._bus.unsubscribe("__inspector__")
        except Exception:
            pass

    def _on_message(self, msg) -> None:
        topic = str(msg.topic)
        with self._lock:
            if topic not in self._stats:
                self._stats[topic] = _TopicStats(topic)
            self._stats[topic].record(msg.data)

    def _poll_loop(self) -> None:
        while self._running:
            try:
                bus = self._robot._bus
                with self._lock:
                    for topic, stats in self._stats.items():
                        stats.sub_count = bus.subscriber_count(topic)
            except Exception:
                pass
            time.sleep(2.0)

    # ── API Methods ───────────────────────────────────────────────────────

    def get_topics(self) -> list:
        with self._lock:
            return sorted(
                [s.to_dict() for s in self._stats.values()],
                key=lambda x: x["topic"])

    def get_nodes(self) -> list:
        nodes = []
        try:
            for name, node in self._robot._nodes.items():
                nodes.append({
                    "name": name,
                    "type": node.__class__.__name__,
                    "state": node.state.name if hasattr(node.state, 'name') else str(node.state),
                    "priority": node.priority.name if hasattr(node.priority, 'name') else str(node.priority),
                    "hz": getattr(node, '_hz', 0),
                    "tick_count": getattr(node, '_tick_count', 0),
                })
        except Exception:
            pass
        return nodes

    def get_graph(self) -> dict:
        """Build a node-topic connectivity graph for D3.js visualization."""
        nodes_list = []
        links = []
        node_set = set()
        topic_set = set()

        try:
            for name, node in self._robot._nodes.items():
                if name not in node_set:
                    nodes_list.append({
                        "id": name, "type": "node",
                        "label": node.__class__.__name__,
                        "state": node.state.name if hasattr(node.state, 'name') else "UNKNOWN",
                    })
                    node_set.add(name)
        except Exception:
            pass

        with self._lock:
            for topic in self._stats:
                if topic not in topic_set:
                    nodes_list.append({
                        "id": topic, "type": "topic",
                        "label": topic.split("/")[-1],
                        "hz": self._stats[topic].hz,
                    })
                    topic_set.add(topic)

        # Infer connections from bus subscriptions
        try:
            bus = self._robot._bus
            for sub in bus._subs:
                # Match subscriptions to topics and nodes
                sub_node = sub.subscriber_id
                sub_pattern = sub.pattern
                if sub_node and sub_node in node_set:
                    for topic in topic_set:
                        # Check if subscription pattern matches this topic
                        if sub_pattern == "#" or sub_pattern == topic or topic.startswith(sub_pattern.rstrip("#")):
                            links.append({"source": topic, "target": sub_node, "type": "subscribe"})
        except Exception:
            pass

        return {"nodes": nodes_list, "links": links}

    def get_status(self) -> dict:
        return {
            "robot": self._robot.name,
            "uptime_s": round(time.time() - getattr(self._robot, '_start_time', time.time()), 1),
            "total_topics": len(self._stats),
            "total_nodes": len(self._robot._nodes) if hasattr(self._robot, '_nodes') else 0,
            "inspector_port": self._port,
        }


def _safe_serialize(data: Any) -> Any:
    if data is None:
        return None
    if isinstance(data, (str, int, float, bool)):
        return data
    if isinstance(data, dict):
        return {k: _safe_serialize(v) for k, v in list(data.items())[:20]}
    if isinstance(data, (list, tuple)):
        return [_safe_serialize(v) for v in data[:20]]
    return str(data)[:200]


# ── Embedded Dashboard HTML ───────────────────────────────────────────────
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEUROS Inspector</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0e1a;--s1:#0f1425;--s2:#141a2e;--b1:#1e2844;--t1:#dce8ff;--t2:#7090b8;
--t3:#3a5070;--accent:#3b82f6;--good:#10b981;--warn:#f59e0b;--danger:#ef4444}
body{background:var(--bg);color:var(--t1);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
.header{padding:20px 28px;border-bottom:1px solid var(--b1);display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:18px;font-weight:700;letter-spacing:2px}
.header h1 span{color:var(--accent)}
.header .status{font-size:11px;color:var(--t2)}
.tabs{display:flex;gap:1px;background:var(--b1);border-bottom:1px solid var(--b1)}
.tab{padding:10px 24px;font-size:12px;font-weight:600;cursor:pointer;background:var(--s1);
color:var(--t3);border-bottom:2px solid transparent;transition:.15s}
.tab:hover{color:var(--t2)}.tab.active{color:var(--accent);border-bottom-color:var(--accent);background:var(--bg)}
.panel{display:none;padding:20px 28px}.panel.active{display:block}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;padding:8px 12px;color:var(--t3);font-size:10px;letter-spacing:1.5px;
text-transform:uppercase;border-bottom:1px solid var(--b1)}
td{padding:8px 12px;border-bottom:1px solid var(--b1);color:var(--t2);font-family:'Consolas',monospace;font-size:11px}
tr:hover td{background:var(--s1);color:var(--t1)}
.hz{color:var(--good);font-weight:600}.count{color:var(--accent)}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:9px;font-weight:600;letter-spacing:.5px}
.badge-active{background:rgba(16,185,129,.15);color:var(--good)}
.badge-idle{background:rgba(112,144,184,.1);color:var(--t3)}
#graph-container{width:100%;height:500px;background:var(--s1);border:1px solid var(--b1);border-radius:6px;position:relative}
.node-card{background:var(--s1);border:1px solid var(--b1);border-left:3px solid var(--accent);
padding:12px 16px;margin-bottom:8px;border-radius:0 4px 4px 0}
.node-card h3{font-size:13px;font-weight:600;margin-bottom:4px}
.node-card .meta{font-size:10px;color:var(--t3);font-family:monospace}
.refresh-bar{height:2px;background:var(--b1);margin-top:-1px}
.refresh-bar .fill{height:100%;background:var(--accent);transition:width 1s linear;width:0%}
svg text{font-family:'Segoe UI',system-ui,sans-serif;font-size:10px}
</style>
</head>
<body>
<div class="header">
  <h1><span>NEUROS</span> INSPECTOR</h1>
  <div class="status" id="status">Connecting...</div>
</div>
<div class="refresh-bar"><div class="fill" id="refresh-fill"></div></div>
<div class="tabs">
  <div class="tab active" onclick="showPanel('topics')">TOPICS</div>
  <div class="tab" onclick="showPanel('nodes')">NODES</div>
  <div class="tab" onclick="showPanel('graph')">GRAPH</div>
</div>

<div class="panel active" id="panel-topics">
  <table><thead><tr><th>Topic</th><th>Hz</th><th>Messages</th><th>Subscribers</th><th>Last Value</th></tr></thead>
  <tbody id="topic-body"></tbody></table>
</div>

<div class="panel" id="panel-nodes">
  <div id="node-list"></div>
</div>

<div class="panel" id="panel-graph">
  <div id="graph-container"><svg id="graph-svg" width="100%" height="100%"></svg></div>
</div>

<script>
const API='';
let refreshInterval;

function showPanel(name){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  event.target.classList.add('active');
  if(name==='graph')loadGraph();
}

async function fetchJSON(url){
  try{const r=await fetch(API+url);return await r.json();}
  catch(e){return null;}
}

async function refresh(){
  const fill=document.getElementById('refresh-fill');
  fill.style.width='0%';
  setTimeout(()=>fill.style.width='100%',50);

  // Status
  const st=await fetchJSON('/api/status');
  if(st)document.getElementById('status').textContent=
    st.robot+' | '+st.total_topics+' topics | '+st.total_nodes+' nodes | '+st.uptime_s+'s uptime';

  // Topics
  const topics=await fetchJSON('/api/topics');
  if(topics){
    const tbody=document.getElementById('topic-body');
    tbody.innerHTML=topics.map(t=>`<tr>
      <td>${t.topic}</td>
      <td class="hz">${t.hz}</td>
      <td class="count">${t.count}</td>
      <td>${t.subscribers}</td>
      <td>${JSON.stringify(t.last_data).substring(0,80)}</td>
    </tr>`).join('');
  }

  // Nodes
  const nodes=await fetchJSON('/api/nodes');
  if(nodes){
    const nl=document.getElementById('node-list');
    nl.innerHTML=nodes.map(n=>`<div class="node-card">
      <h3>${n.name} <span class="badge ${n.state==='RUNNING'?'badge-active':'badge-idle'}">${n.state}</span></h3>
      <div class="meta">${n.type} | ${n.hz}Hz | ${n.tick_count} ticks | ${n.priority}</div>
    </div>`).join('');
  }
}

async function loadGraph(){
  const data=await fetchJSON('/api/graph');
  if(!data)return;
  const svg=document.getElementById('graph-svg');
  const W=svg.clientWidth||800,H=svg.clientHeight||500;
  svg.innerHTML='';

  // Simple force layout (no D3 dependency)
  const positions={};
  const nodeEls=data.nodes||[];
  const linkEls=data.links||[];

  nodeEls.forEach((n,i)=>{
    const angle=(2*Math.PI*i)/nodeEls.length;
    const r=Math.min(W,H)*0.35;
    positions[n.id]={x:W/2+r*Math.cos(angle),y:H/2+r*Math.sin(angle)};
  });

  // Draw links
  linkEls.forEach(l=>{
    const s=positions[l.source],t=positions[l.target];
    if(s&&t){
      const line=document.createElementNS('http://www.w3.org/2000/svg','line');
      line.setAttribute('x1',s.x);line.setAttribute('y1',s.y);
      line.setAttribute('x2',t.x);line.setAttribute('y2',t.y);
      line.setAttribute('stroke','#1e2844');line.setAttribute('stroke-width','1');
      svg.appendChild(line);
    }
  });

  // Draw nodes
  nodeEls.forEach(n=>{
    const p=positions[n.id];if(!p)return;
    const g=document.createElementNS('http://www.w3.org/2000/svg','g');
    const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');
    circle.setAttribute('cx',p.x);circle.setAttribute('cy',p.y);
    circle.setAttribute('r',n.type==='node'?12:6);
    circle.setAttribute('fill',n.type==='node'?'#3b82f6':'#10b981');
    circle.setAttribute('stroke','#0a0e1a');circle.setAttribute('stroke-width','2');
    g.appendChild(circle);
    const text=document.createElementNS('http://www.w3.org/2000/svg','text');
    text.setAttribute('x',p.x);text.setAttribute('y',p.y+22);
    text.setAttribute('text-anchor','middle');text.setAttribute('fill','#7090b8');
    text.textContent=n.label;
    g.appendChild(text);
    svg.appendChild(g);
  });
}

refresh();
refreshInterval=setInterval(refresh,2000);
</script>
</body>
</html>"""

__all__ = ["Inspector"]
