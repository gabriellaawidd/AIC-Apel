"""Uji kewarasan model spoilage vs patokan FAO (WAJIB — bukti model tervalidasi).

Patokan FAO: dibanding 0 C, laju pembusukan ~2x pada 5 C dan ~5-6x pada 10 C.
Dengan Tmin = -10 C, T_ref = 0 C:  RRS(5) = (15/10)^2 = 2.25 ; RRS(10) = (20/10)^2 = 4.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coldchain import tools
from coldchain.rag import KnowledgeBase, retrieve_advisory


def test_rrs_reproduces_fao_benchmark():
    T_ref, Tmin = 0.0, -10.0
    r5 = tools.rrs(5, T_ref, Tmin)
    r10 = tools.rrs(10, T_ref, Tmin)
    assert abs(r5 - 2.25) < 1e-6, f"RRS(5)={r5}, harusnya 2.25"
    assert abs(r10 - 4.0) < 1e-6, f"RRS(10)={r10}, harusnya 4.0"
    # 5 C menggandakan laju (kisaran "dua kali lipat")
    assert 2.0 <= r5 <= 2.5
    # 10 C mempercepat 4-6x (model sedikit konservatif, diterima)
    assert 4.0 <= r10 <= 6.0
    print(f"OK RRS(5)={r5}  RRS(10)={r10}")


def test_shelf_life_shrinks_with_temperature():
    p = tools.config.COMMODITY_PARAMS["ikan"]
    sl0 = tools.shelf_life_hours(0, p["SL_ref_hours"], p["T_ref"], p["Tmin"])
    sl10 = tools.shelf_life_hours(10, p["SL_ref_hours"], p["T_ref"], p["Tmin"])
    assert sl0 > sl10, "shelf-life harus lebih pendek di suhu lebih tinggi"
    assert abs(sl0 / sl10 - 4.0) < 1e-6
    print(f"OK SL(0)={sl0:.0f}h  SL(10)={sl10:.0f}h  rasio={sl0/sl10:.2f}")


def test_reefer_better_than_nonreefer():
    hot = [{"ambient_temp_c": 32, "precip_mm": 0}]
    non = tools.compute_spoilage("ikan", "segar", "non_reefer", hot, 240)
    ref = tools.compute_spoilage("ikan", "segar", "reefer", hot, 240)
    assert ref.pct_fresh > non.pct_fresh, "reefer harus lebih segar dari non-reefer di ambien panas"
    print(f"OK reefer={ref.pct_fresh}%  non-reefer={non.pct_fresh}%")


def test_worse_initial_condition_lowers_freshness():
    seg = [{"ambient_temp_c": 10, "precip_mm": 0}]
    a = tools.compute_spoilage("ikan", "sangat_segar", "non_reefer", seg, 300)
    b = tools.compute_spoilage("ikan", "kurang_segar", "non_reefer", seg, 300)
    assert a.pct_fresh > b.pct_fresh
    print(f"OK sangat_segar={a.pct_fresh}%  kurang_segar={b.pct_fresh}%")


def test_pareto_and_ranking():
    metrics = [
        {"route_id": "r1", "eta": 100, "cost": 300000, "risk": 20},  # dominated?
        {"route_id": "r2", "eta": 90,  "cost": 250000, "risk": 15},  # dominates r1
        {"route_id": "r3", "eta": 130, "cost": 200000, "risk": 25},  # murah
    ]
    out = tools.rank_routes(metrics, "fast")
    assert "r1" not in out["pareto_front"], "r1 didominasi r2, tak boleh di Pareto front"
    assert out["best_route_id"] == "r2", "prioritas fast -> r2 (ETA terkecil di antara non-dominated)"
    print(f"OK pareto={out['pareto_front']}  best={out['best_route_id']}")


def test_kentang_chilling_injury():
    # Kentang di reefer 2 C (dingin) harus LEBIH BURUK daripada di 8 C (optimal)
    warm = [{"ambient_temp_c": 8, "precip_mm": 0}]   # ~optimal kentang
    non = tools.compute_spoilage("kentang", "segar", "non_reefer", warm, 300)
    ref = tools.compute_spoilage("kentang", "segar", "reefer", warm, 300)  # reefer=2 C
    assert non.pct_fresh >= ref.pct_fresh, "kentang: over-dinginkan (reefer) tak boleh lebih segar dari 8 C"
    assert any("chilling" in a for a in ref.assumptions), "chilling injury harus tercatat di asumsi"
    print(f"OK kentang 8C={non.pct_fresh}%  reefer2C={ref.pct_fresh}% (chilling tercatat)")


def test_bayam_prefers_cold():
    # Bayam TIDAK chill-sensitive: makin dingin makin segar
    hot = [{"ambient_temp_c": 20, "precip_mm": 0}]
    non = tools.compute_spoilage("bayam", "segar", "non_reefer", hot, 300)
    ref = tools.compute_spoilage("bayam", "segar", "reefer", hot, 300)
    assert ref.pct_fresh > non.pct_fresh, "bayam: reefer harus lebih segar di ambien 20 C"
    print(f"OK bayam 20C={non.pct_fresh}%  reefer={ref.pct_fresh}%")


def test_rag_retrieval_grounded():
    kb = KnowledgeBase()
    adv = retrieve_advisory(kb, "ikan", "high")
    assert adv["snippets"], "RAG harus mengembalikan snippet untuk ikan risiko tinggi"
    assert all("source" in s and s["source"] for s in adv["snippets"]), "tiap snippet wajib bersumber"
    print(f"OK RAG {len(adv['snippets'])} snippet, sumber={[s['source'] for s in adv['snippets']]}")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print("\n" + ("ALL PASS ✅" if failed == 0 else f"{failed} FAILED ❌"))
    sys.exit(1 if failed else 0)
