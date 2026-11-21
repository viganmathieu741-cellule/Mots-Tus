"""Tests de NOVA avec un faux modèle IA (aucune clé nécessaire) :  python test_nova.py"""
import json
import os
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer

tmp = tempfile.mkdtemp()
os.environ["NOVA_DB"] = os.path.join(tmp, "t.db")
os.environ["NOVA_AGENTS_DIR"] = os.path.join(tmp, "agents")
os.environ["NOVA_TOKEN"] = "secret"

import nova_web
from nova_core import Nova


class FakeLLM:
    name = "faux-modele"

    def ask(self, system, user, json_mode=False):
        if "Agent Factory" in system:
            return "Voici :\n```json\n" + json.dumps({
                "name": "Marketing TikTok!", "title": "Agent Marketing", "role": "Idées et scripts TikTok",
                "system_prompt": "Tu es un expert marketing TikTok.", "tools": ["redaction", "hack_banque"],
                "test_prompts": ["Donne 1 idée", "Donne 1 hook"]}) + "\n```"
        if "SaaS Factory" in system:
            return json.dumps({"name": "Réservation Resto", "summary": "Réservations en ligne",
                               "features": ["réservations"], "architecture": "Python + SQLite",
                               "steps": ["maquette", "base de données"], "needs_approval": ["déploiement public"]})
        return "réponse: " + user[:40]


def check(c, msg):
    print(("✅ " if c else "❌ ") + msg)
    assert c, msg


nova = Nova(llm=FakeLLM())
r = nova.handle("crée un agent marketing TikTok")
check("Agent créé" in r and "marketing-tiktok" in r, "Agent Factory crée l'agent")
spec = nova.mem.get_agent("marketing-tiktok")
check(spec["tools"] == ["redaction"], "outils inventés supprimés")
check(spec["permissions"]["spend_money"] == "never", "permissions minimales imposées")
check(spec["status"] == "actif" and len(spec["tests"]) == 2, "tests de fumée passés")
check("marketing-tiktok" in nova.handle("liste mes agents") and "video" in nova.handle("liste mes agents"), "liste des agents")
check(nova.handle("demande à marketing-tiktok : une idée").startswith("réponse"), "exécution d'un agent")
check("Colab" in nova.handle("demande à video : fais une vidéo"), "agent vidéo externe expliqué")
check("Retenu" in nova.handle("retiens que ma niche est la poésie triste"), "mémoire : retenir")
check(nova.mem.recall("quelle est ma niche poésie")[0].startswith("ma niche"), "mémoire : retrouver")
r = nova.handle("crée un site de réservation pour restaurants")
check("à valider" in r and "reservation-resto" in r, "SaaS Factory produit un plan à valider")
check("reservation-resto" in nova.handle("liste mes projets"), "liste des projets")

srv = ThreadingHTTPServer(("127.0.0.1", 0), nova_web.make_handler(nova))
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
try:
    urllib.request.urlopen(base + "/api/state")
    check(False, "accès sans code refusé")
except urllib.error.HTTPError as e:
    check(e.code == 401, "Mission Control refuse sans code")
st = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/api/state", headers={"X-Nova-Token": "secret"})).read())
check(len(st["agents"]) == 2 and st["llm"] == "faux-modele", "Mission Control : état")
a = json.loads(urllib.request.urlopen(urllib.request.Request(
    base + "/api/ask", data=json.dumps({"q": "bonjour"}).encode(), headers={"X-Nova-Token": "secret"})).read())
check(a["answer"].startswith("réponse"), "Mission Control : conversation")

from nova_llm import OfflineLLM
off = Nova(llm=OfflineLLM(), memory=nova.mem)
check("indisponible" in off.handle("bonjour"), "message clair sans clé IA")
print("\nTous les tests passent.")
