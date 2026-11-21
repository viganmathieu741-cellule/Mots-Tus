"""NOVA Core : l'intelligence centrale. Reçoit une demande, choisit quoi faire, mémorise."""
import json
import re

from nova_agents import AgentFactory, slugify
from nova_llm import LLMUnavailable, extract_json, get_llm
from nova_memory import Memory

NOVA_SYSTEM = ("Tu es NOVA, l'assistant central de Mathieu. Tu réponds en français, de façon claire et "
               "courte. Tu ne prétends jamais connaître des chiffres ou des résultats que tu n'as pas.")

PLAN_SYSTEM = """Tu es la SaaS Factory de NOVA. Réponds UNIQUEMENT en JSON :
{"name": "nom-court", "summary": "...", "features": ["..."], "architecture": "stack gratuite recommandée",
 "steps": ["étapes de construction, de la plus simple à la plus complète"],
 "needs_approval": ["actions sensibles qui demandent l'accord de l'utilisateur"]}"""

VIDEO_AGENT = {
    "name": "video", "title": "Agent vidéo Mots Tus", "kind": "externe", "status": "actif",
    "role": "Crée des vidéos 16:9 (voix off, sous-titres, fonds générés, chevalier).",
    "how_to_run": "ouvre Agent_Mots_Tus_tout_en_un.ipynb dans Google Colab et lance la cellule.",
    "tools": [], "permissions": {"publish": "ask", "spend_money": "never"},
}


class Nova:
    def __init__(self, llm=None, memory=None):
        self.llm = llm or get_llm()
        self.mem = memory or Memory()
        self.factory = AgentFactory(self.mem, self.llm)
        if not self.mem.get_agent("video"):
            self.mem.save_agent(VIDEO_AGENT)

    # --- routage simple (sans IA) pour les commandes claires
    def handle(self, text):
        t = text.strip()
        low = t.lower()
        self.mem.log("user", t)
        try:
            out = self._route(t, low)
        except LLMUnavailable as e:
            out = f"⚠️ Le modèle IA est indisponible : {e}"
        except Exception as e:
            out = f"⚠️ Erreur : {e}"
        self.mem.log("nova", out)
        return out

    def _route(self, t, low):
        if re.match(r"^(retiens|mémorise|memorise|souviens-toi)\b", low):
            fact = re.sub(r"^(retiens|mémorise|memorise|souviens-toi)\s*(que|:)?\s*", "", t, flags=re.I)
            self.mem.remember(fact)
            return f"✅ Retenu : {fact}"
        if re.search(r"\b(liste|montre|affiche)\b.*\bagents?\b|^agents\??$", low):
            return self.list_agents()
        if re.search(r"\b(projets?)\b", low) and re.search(r"\b(liste|montre|affiche)\b", low):
            return self.list_projects()
        m = re.match(r"^(demande à|demande a|agent)\s+([\w-]+)\s*[:,]?\s*(.+)$", t, re.I | re.S)
        if m:
            return self.factory.run(slugify(m.group(2)), m.group(3))
        if re.search(r"\b(crée|cree|créer|creer|fabrique|construis)\b.*\bagent", low):
            spec = self.factory.create(t)
            tests = ", ".join("✅" if r["ok"] else "❌" for r in spec["tests"]) or "aucun test"
            return (f"✅ Agent créé : « {spec['title']} » ({spec['name']})\nRôle : {spec['role']}\n"
                    f"Outils : {', '.join(spec['tools']) or 'aucun'}\nTests : {tests} → statut : {spec['status']}\n"
                    f"Utilisation : « demande à {spec['name']} : ta mission »")
        if re.search(r"\b(crée|cree|créer|creer|développe|developpe|construis)\b.*\b(site|saas|application|app|plateforme)\b", low):
            return self.plan_project(t)
        ctx = self.mem.recall(t, 4)
        hist = "\n".join(f"{h['role']}: {h['text']}" for h in self.mem.history(6)[:-1])
        user = t + ("\n\nSouvenirs utiles :\n- " + "\n- ".join(ctx) if ctx else "") + \
            ("\n\nConversation récente :\n" + hist if hist else "")
        return self.llm.ask(NOVA_SYSTEM, user)

    # --- composants
    def list_agents(self):
        ag = self.mem.list_agents()
        if not ag:
            return "Aucun agent pour le moment."
        return "\n".join(f"• {a['name']} — {a['title']} [{a.get('status', '?')}] : {a['role']}" for a in ag)

    def list_projects(self):
        pr = self.mem.list_projects()
        if not pr:
            return "Aucun projet pour le moment."
        return "\n".join(f"• #{p['id']} {p['name']} [{p['status']}]" for p in pr)

    def plan_project(self, request):
        """SaaS Factory v0 : produit un PLAN à valider. Aucune génération ni déploiement sans ton accord."""
        plan = extract_json(self.llm.ask(PLAN_SYSTEM, request, json_mode=True))
        name = slugify(plan.get("name", "projet"))
        self.mem.add_project(name, "plan à valider", plan)
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(plan.get("steps", [])))
        appr = ", ".join(plan.get("needs_approval", [])) or "—"
        return (f"📐 Plan créé pour « {name} » (statut : à valider)\n{plan.get('summary', '')}\n"
                f"Architecture : {plan.get('architecture', '')}\nÉtapes :\n{steps}\nDemandera ton accord pour : {appr}")

    def state(self):
        return {"llm": getattr(self.llm, "name", "?"), "agents": self.mem.list_agents(),
                "projects": self.mem.list_projects()}
