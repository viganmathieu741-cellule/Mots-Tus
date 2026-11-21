"""NOVA - Agent Factory : crée un agent complet à partir d'une instruction, le teste et l'enregistre."""
import json
import os
import re
import unicodedata
from pathlib import Path

from nova_llm import extract_json

ALLOWED_TOOLS = ["redaction", "analyse", "planification", "recherche_web", "lecture_fichiers", "calendrier"]

FACTORY_SYSTEM = """Tu es l'Agent Factory de NOVA. À partir de la demande de l'utilisateur, conçois UN agent IA.
Réponds UNIQUEMENT avec un objet JSON de cette forme :
{"name": "identifiant-court-en-minuscules", "title": "Titre lisible", "role": "rôle en une phrase",
 "system_prompt": "instructions complètes de l'agent, en français, précises",
 "tools": ["..."], "test_prompts": ["2 courtes missions pour tester l'agent"]}
Outils possibles : %s. N'invente pas d'autres outils. Pas de texte hors du JSON.""" % ", ".join(ALLOWED_TOOLS)


def slugify(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "agent"


class AgentFactory:
    def __init__(self, memory, llm, registry_dir=None):
        self.mem, self.llm = memory, llm
        self.dir = Path(registry_dir or os.environ.get("NOVA_AGENTS_DIR", "agents_registry"))
        self.dir.mkdir(parents=True, exist_ok=True)

    def create(self, instruction):
        raw = self.llm.ask(FACTORY_SYSTEM, instruction, json_mode=True)
        spec = extract_json(raw)
        for k in ("name", "role", "system_prompt"):
            if not str(spec.get(k, "")).strip():
                raise ValueError(f"spécification incomplète : champ '{k}' manquant")
        spec["name"] = slugify(spec["name"])
        spec["title"] = spec.get("title") or spec["name"]
        spec["tools"] = [t for t in spec.get("tools", []) if t in ALLOWED_TOOLS]
        spec["kind"] = "llm"
        # permissions : l'agent ne peut jamais s'en donner plus que ce minimum sûr
        spec["permissions"] = {"publish": "ask", "spend_money": "never", "delete_data": "ask",
                               "external_messages": "ask"}
        # test de fumée : l'agent répond-il à ses missions de test ?
        results = []
        for p in list(spec.get("test_prompts", []))[:2]:
            try:
                out = self.llm.ask(spec["system_prompt"], p)
                results.append({"prompt": p, "ok": bool(out and out.strip()), "sample": out[:160]})
            except Exception as e:
                results.append({"prompt": p, "ok": False, "sample": str(e)[:160]})
        spec["tests"] = results
        spec["status"] = "actif" if results and all(r["ok"] for r in results) else "à vérifier"
        (self.dir / f"{spec['name']}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")
        self.mem.save_agent(spec)
        return spec

    def run(self, name, task):
        spec = self.mem.get_agent(name)
        if not spec:
            raise KeyError(f"agent inconnu : {name}")
        if spec.get("kind") != "llm":
            return (f"L'agent « {spec['title']} » ne tourne pas dans NOVA directement : {spec.get('how_to_run', '')}")
        ctx = self.mem.recall(task, 3)
        user = task + ("\n\nContexte mémorisé :\n- " + "\n- ".join(ctx) if ctx else "")
        return self.llm.ask(spec["system_prompt"], user)
