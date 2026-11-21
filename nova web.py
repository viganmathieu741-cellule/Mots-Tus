"""Mission Control : petite page web (aucune dépendance).  python nova_web.py --port 8000
Protège l'accès avec la variable NOVA_TOKEN (ouvre alors /?token=TON_CODE)."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from nova_core import Nova

HTML = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>NOVA</title>
<style>body{background:#0e0f13;color:#e8e8ee;font:16px system-ui;margin:0;padding:16px;max-width:760px;margin:auto}
h1{font-size:22px}h2{font-size:15px;color:#9aa;margin-top:22px}.card{background:#171921;border-radius:12px;padding:10px 14px;margin:8px 0}
input{width:100%;box-sizing:border-box;padding:12px;border-radius:10px;border:1px solid #333;background:#171921;color:#fff;font-size:16px}
button{margin-top:8px;padding:12px 18px;border:0;border-radius:10px;background:#7c5cff;color:#fff;font-size:16px}
pre{white-space:pre-wrap;background:#171921;border-radius:12px;padding:12px}</style>
<h1>NOVA · Mission Control</h1><div id=st></div>
<h2>Parler à NOVA</h2><input id=q placeholder="ex : crée un agent marketing TikTok"><button onclick=ask()>Envoyer</button><pre id=out></pre>
<script>const T=new URLSearchParams(location.search).get('token')||'';const H={'X-Nova-Token':T,'Content-Type':'application/json'};
async function load(){const s=await (await fetch('/api/state',{headers:H})).json();
document.getElementById('st').innerHTML='<div class=card>Modèle IA : <b>'+s.llm+'</b></div><h2>Agents ('+s.agents.length+')</h2>'+
s.agents.map(a=>'<div class=card><b>'+a.title+'</b> <small>['+(a.status||'')+']</small><br>'+a.role+'</div>').join('')+
'<h2>Projets ('+s.projects.length+')</h2>'+s.projects.map(p=>'<div class=card>#'+p.id+' <b>'+p.name+'</b> <small>['+p.status+']</small></div>').join('')}
async function ask(){const q=document.getElementById('q').value;if(!q)return;document.getElementById('out').textContent='…';
const r=await (await fetch('/api/ask',{method:'POST',headers:H,body:JSON.stringify({q})})).json();document.getElementById('out').textContent=r.answer;load()}
load()</script>"""


def make_handler(nova):
    token = os.environ.get("NOVA_TOKEN", "")

    class H(BaseHTTPRequestHandler):
        def _ok(self):
            if not token:
                return True
            q = parse_qs(urlparse(self.path).query).get("token", [""])[0]
            return self.headers.get("X-Nova-Token") == token or q == token

        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._ok():
                return self._send(401, '{"error":"accès refusé"}')
            p = urlparse(self.path).path
            if p == "/api/state":
                return self._send(200, json.dumps(nova.state(), ensure_ascii=False))
            return self._send(200, HTML, "text/html")

        def do_POST(self):
            if not self._ok():
                return self._send(401, '{"error":"accès refusé"}')
            n = int(self.headers.get("Content-Length", 0))
            try:
                q = json.loads(self.rfile.read(n))["q"]
            except Exception:
                return self._send(400, '{"error":"requête invalide"}')
            return self._send(200, json.dumps({"answer": nova.handle(q)}, ensure_ascii=False))

        def log_message(self, *a):
            pass
    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    nova = Nova()
    print(f"Mission Control sur http://{a.host}:{a.port}  (modèle : {nova.llm.name})")
    ThreadingHTTPServer((a.host, a.port), make_handler(nova)).serve_forever()
