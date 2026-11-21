"""NOVA - accès aux modèles IA gratuits (Gemini ou Groq) via leur API, sans aucune dépendance à installer.

Les clés se mettent dans des variables d'environnement (jamais dans le dépôt) :
  GEMINI_API_KEY  (Google AI Studio)   ou   GROQ_API_KEY
Les noms de modèles changent souvent : ils se règlent avec NOVA_GEMINI_MODEL / NOVA_GROQ_MODEL.
"""
import json
import os
import re
import urllib.error
import urllib.request


class LLMUnavailable(RuntimeError):
    pass


def extract_json(text):
    """Récupère le premier objet JSON d'une réponse (même entouré de texte ou de ```)."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("pas de JSON dans la réponse du modèle")
    return json.loads(m.group(0))


def _post(url, headers, payload, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        raise LLMUnavailable(f"HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        raise LLMUnavailable(str(e))


class GeminiLLM:
    name = "gemini"

    def __init__(self, key):
        self.key = key
        self.model = os.environ.get("NOVA_GEMINI_MODEL", "gemini-flash-latest")

    def ask(self, system, user, json_mode=False):
        body = {"system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}]}
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        r = _post(url, {"x-goog-api-key": self.key}, body)
        try:
            return r["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            raise LLMUnavailable(f"réponse inattendue: {str(r)[:200]}")


class GroqLLM:
    name = "groq"

    def __init__(self, key):
        self.key = key
        self.model = os.environ.get("NOVA_GROQ_MODEL", "llama-3.3-70b-versatile")

    def ask(self, system, user, json_mode=False):
        body = {"model": self.model, "messages": [{"role": "system", "content": system},
                                                   {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = _post("https://api.groq.com/openai/v1/chat/completions",
                  {"Authorization": f"Bearer {self.key}"}, body)
        try:
            return r["choices"][0]["message"]["content"]
        except Exception:
            raise LLMUnavailable(f"réponse inattendue: {str(r)[:200]}")


class OfflineLLM:
    name = "hors-ligne"

    def ask(self, system, user, json_mode=False):
        raise LLMUnavailable("Aucune clé IA trouvée. Définis GEMINI_API_KEY ou GROQ_API_KEY (gratuites).")


def get_llm():
    pref = os.environ.get("NOVA_LLM", "").lower()
    g, q = os.environ.get("GEMINI_API_KEY"), os.environ.get("GROQ_API_KEY")
    if pref == "groq" and q:
        return GroqLLM(q)
    if g and pref != "groq":
        return GeminiLLM(g)
    if q:
        return GroqLLM(q)
    return OfflineLLM()
