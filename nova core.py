"""NOVA Core : l'intelligence centrale. Reçoit une demande, choisit quoi faire, mémorise."""
import json
import re

from nova_agents import AgentFactory, slugify
from nova_llm import LLMUnavailable, extract_json, get_llm
from nova_memory import Memory

NOVA_SYSTEM = ("Tu es NOVA, l'assistant central de Mathieu. Tu réponds en français, de façon claire et "
               "courte. Tu ne prétends jamais connaître des chiffres ou des résultats que tu n'as pas.")

TEXTES_SYSTEM = """Tu écris UNE voix off pour le compte TikTok poésie « Les Mots Tus » (français).
RÈGLES :
- Un « tu » direct, intime, très émotionnel. Phrases courtes, mots simples du quotidien.
- 125 à 145 mots. Un saut de ligne = une légende = une pause. 2 à 6 mots par ligne.
- Première phrase qui accroche (ex : « J'ai connu des visages plus beaux que le tien. », « J'aurais dû te supplier de rester. »).
- Oppositions et retournements : « Ce n'est pas X, c'est Y. », « Avant toi... Aujourd'hui, je sais. »
- Détails concrets (un mardi, la pluie, un manteau, des clés).
- Dernière phrase qui reste, comme une maxime ou un retournement.
- INTERDIT : bataille, guerre, épée, armure, royaume, roi, combattre, chevalier, histoires narratives, grands mots abstraits, bla-bla.
- Thèmes : beauté, amour, manque, séparation, regrets, sacrifice amoureux (aimer c'est laisser partir), non-dits, souvenirs.
EXEMPLE DE TON :
J'aurais dû te supplier de rester.
Je ne l'ai pas fait.
Par fierté,
par peur du ridicule,
parce qu'on m'avait appris
qu'on ne retient pas
ceux qui veulent partir.
Alors j'ai dit
« d'accord ».
Le mot le plus lâche
que j'aie prononcé.
Réponds UNIQUEMENT avec le texte, lignes séparées par des sauts de ligne. Aucun titre, aucune numérotation, aucun commentaire."""

INTERDITS = ("bataille", "guerre", "epee", "épée", "armure", "royaume", "roi", "combattre", "chevalier")


def controle_texte(t):
    mots = re.findall(r"[\w'’-]+", t)
    pb = []
    if not 125 <= len(mots) <= 145:
        pb.append(f"{len(mots)} mots au lieu de 125-145")
    bad = [m for m in INTERDITS if m in set(re.findall(r"[\wéèêà]+", t.lower()))]
    if bad:
        pb.append("mots interdits : " + ", ".join(bad))
    return pb

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
        m = re.match(r"^(écris|ecris|génère|genere|fais|donne)(?:-moi)?\s+(\d{1,2})\s+textes?(?:\s+(?:sur|autour de|à propos de)\s+(.+))?$", low)
        if m:
            return self.write_texts(int(m.group(2)), m.group(3))
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
    def write_texts(self, n, theme=None):
        import os
        n = max(1, min(n, 6))
        blocs, notes = [], []
        for i in range(n):
            ask = "Écris la voix off" + (f" sur le thème : {theme}." if theme else " sur un thème de ta liste.")
            if n > 1:
                ask += f" (texte {i + 1}/{n}, différent des autres ; premier mot de départ distinct)"
            best, pb = "", ["vide"]
            for _ in range(3):
                t = re.sub(r"^```\w*\n?|```$", "", self.llm.ask(TEXTES_SYSTEM, ask).strip()).strip()
                p = controle_texte(t)
                if not best or len(p) < len(pb):
                    best, pb = t, p
                if not p:
                    break
                ask += f"\nCorrige : {'; '.join(p)}."
            blocs.append(best)
            if pb:
                notes.append(f"texte {i + 1} : {'; '.join(pb)}")
        out = "\n---\n".join(blocs)
        path = os.path.join(os.path.dirname(os.environ.get("NOVA_DB", "")) or ".", "textes_nova.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        warn = ("\n⚠️ " + " | ".join(notes)) if notes else "\n✅ Contrôle : 125-145 mots, aucun mot interdit."
        return f"✅ {len(blocs)} texte(s) enregistré(s) dans {path}{warn}\n\n{out}"

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
