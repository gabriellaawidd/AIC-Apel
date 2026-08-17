"""Demo end-to-end. Jalan offline (fallback) atau dengan ANTHROPIC_API_KEY."""
import json
from coldchain import Orchestrator

SCENARIOS = [
    "Kirim ikan segar dari Jakarta ke Bandung siang ini, non-reefer, kondisi segar, prioritas cepat",
    "Kentang dari Bandung ke Jakarta pakai reefer, hemat biaya",       # uji: reefer justru merugikan kentang
    "Bayam dari Bogor ke Jakarta, sangat segar, balanced",
]


def main():
    orch = Orchestrator()  # KB di-index sekali
    for i, s in enumerate(SCENARIOS, 1):
        print("=" * 78)
        print(f"SKENARIO {i}: {s}")
        print("-" * 78)
        # departure_time tetap agar reproducible
        out = orch.run(s, now="2026-08-10T13:00", verbose=True)
        print("\n--- NARASI ---")
        print(out["narrative"])
        best = out["best_route_id"]
        print("\n--- RINGKAS CTX (rute terbaik) ---")
        print(json.dumps({
            "best": best,
            "eta": out["ctx"]["eta"][best],
            "spoilage": out["ctx"]["spoilage"][best],
            "ranking": out["ctx"]["ranking"],
        }, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
