"""Lance NOVA dans le terminal ou une cellule Colab :  python nova_cli.py"""
from nova_core import Nova

if __name__ == "__main__":
    nova = Nova()
    print(f"NOVA prête (modèle : {nova.llm.name}). Tape 'quitter' pour sortir.")
    print("Exemples : « crée un agent marketing TikTok » · « liste mes agents » · « retiens que ma niche est la poésie »")
    while True:
        try:
            q = input("\nToi > ").strip()
        except EOFError:
            break
        if q.lower() in ("quitter", "exit", "quit"):
            break
        if q:
            print("\nNOVA >", nova.handle(q))
