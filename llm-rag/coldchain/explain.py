from __future__ import annotations
from typing import Any, Dict, List, Optional
from .rag import KnowledgeBase, retrieve_advisory

_KB: Optional[KnowledgeBase] = None


def _kb() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase()
    return _KB

def fmt_rp(n: float) -> str:
    return "Rp" + f"{round(n or 0):,}".replace(",", ".")

def fmt_jam(h: float) -> str:
    total = int(round((h or 0) * 60))
    j, m = divmod(total, 60)
    if j and m:
        return f"{j} jam {m} menit"
    if j:
        return f"{j} jam"
    return f"{m} menit"


_RISK_LABEL = {"low": "aman", "medium": "waspada", "high": "berisiko"}

def _reason_waktu(opt: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    eta = opt["eta_hours"]
    a = opt.get("assumptions") or {}
    f_time = a.get("f_time")
    f_weather = a.get("f_weather")
    penalty = a.get("road_penalty")

    bagian = [
        f"Waktu tempuh diperkirakan {fmt_jam(eta['likely'])} "
        f"(rentang {fmt_jam(eta['optimistic'])}–{fmt_jam(eta['pessimistic'])}) "
        f"untuk {opt['distance_km']} km, setara kecepatan rata-rata "
        f"{opt.get('avg_speed_kmh', 0)} km/jam."
    ]
    faktor = []
    if f_time:
        faktor.append(f"kepadatan menurut jam berangkat ×{f_time}")
    if f_weather and f_weather != 1.0:
        faktor.append(f"cuaca ×{f_weather}")
    if penalty and penalty != 1.0:
        faktor.append(f"komposisi jalan ×{penalty} "
                      f"({opt.get('non_toll_km', 0)} km non-tol dari {opt['distance_km']} km)")
    if faktor:
        bagian.append("Angka itu adalah waktu bebas-hambatan OSRM yang dikoreksi oleh "
                      + ", ".join(faktor) + ".")
    return " ".join(bagian)


def _reason_kesegaran(opt: Dict[str, Any]) -> str:
    q = opt["quality"]
    segs = q.get("segments") or []
    amb = q.get("status_thresholds") or {}
    bagian = [
        f"Kesegaran saat tiba diperkirakan {q['pct_fresh_on_arrival']:.1f}% — "
        f"berstatus {q.get('status', '-').upper()}"
        + (f" (ambang layak jual komoditas ini {amb['berisiko_di_bawah']:.0f}%)"
           if amb.get("berisiko_di_bawah") is not None else "")
        + f", dengan risiko busuk {q['spoil_risk'] * 100:.0f}%."
    ]
    if segs:
        panas = max(segs, key=lambda s: s["temp_c"])
        bagian.append(
            f"Sepanjang perjalanan suhu kargo bergerak "
            f"{min(s['temp_c'] for s in segs):.0f}–{max(s['temp_c'] for s in segs):.0f}°C; "
            f"potongan terpanas ada di jam ke-{panas['from_h']:.1f} sampai "
            f"{panas['to_h']:.1f} ({panas['temp_c']:.0f}°C), dan di situlah "
            f"kesegaran turun paling cepat."
        )
    bagian.append(
        ("Barang masih layak jual saat tiba, dengan sisa umur simpan sekitar "
         if q["is_sellable"]
         else "Barang SUDAH TIDAK memenuhi ambang layak jual saat tiba; sisa umur simpan tinggal ")
        + f"{q['remaining_shelf_life_h_after_arrival']:.1f} jam untuk dibongkar dan didinginkan kembali."
    )
    return " ".join(bagian)


def _reason_biaya(opt: Dict[str, Any]) -> str:
    c = opt["cost_rp"]
    rincian = c.get("toll_breakdown") or []
    bagian = [
        f"Biaya total {fmt_rp(c['total'])}: BBM {fmt_rp(c['fuel'])}"
        + (f" (±{c['fuel_liters']} liter)" if c.get("fuel_liters") else "")
        + (f" dan tol {fmt_rp(c['toll'])}." if c["toll"] else " dan tanpa biaya tol.")
    ]
    if rincian:
        daftar = "; ".join(
            f"{b['ruas']} {fmt_rp(b['tarif_rp'])}" for b in rincian[:4]
        )
        ekor = f" (+{len(rincian) - 4} ruas lain)" if len(rincian) > 4 else ""
        bagian.append(f"Ruas tol yang dilewati: {daftar}{ekor}.")
        if any(b.get("perkiraan") for b in rincian):
            bagian.append("Sebagian tarif adalah perkiraan proporsional karena "
                          "gerbang masuk/keluar persisnya tidak diketahui dari data rute.")
    elif not opt["uses_toll"]:
        bagian.append("Tidak ada tarif tol sama sekali — inilah keunggulan biaya rute ini.")
    return " ".join(bagian)


def _reason_peringkat(opt: Dict[str, Any], payload: Dict[str, Any]) -> str:
    scoring = payload.get("scoring") or {}
    w = scoring.get("weights") or {}
    pref_label = {"fast": "kecepatan", "cheap": "biaya",
                  "balanced": "keseimbangan"}.get(scoring.get("preference"), "keseimbangan")

    bagian = []
    if opt.get("is_best"):
        bagian.append(
            f"Rute ini terpilih sebagai yang terbaik untuk prioritas {pref_label} "
            f"(skor {opt['score']:.3f}; makin kecil makin baik, bobot waktu "
            f"{w.get('eta', 0):.0%} / biaya {w.get('cost', 0):.0%} / "
            f"risiko {w.get('risk', 0):.0%})."
        )
    elif opt.get("is_pareto_optimal"):
        best = next((o for o in payload["options"] if o.get("is_best")), None)
        bagian.append(
            f"Rute ini tetap Pareto-optimal (tidak ada rute yang mengungguli di "
            f"waktu, biaya, DAN risiko sekaligus), jadi ia pilihan trade-off yang sah — "
            f"hanya kalah skor {opt['score']:.3f} melawan "
            f"{best['name'] if best else 'rute terbaik'} pada prioritas {pref_label}."
        )
    else:
        bagian.append(
            f"Rute ini gugur dari Pareto front: {opt.get('dominated_reason') or 'didominasi rute lain'}. "
            f"Artinya ada rute yang tidak lebih buruk di semua kriteria dan lebih baik di sebagian."
        )

    if not opt.get("meets_deadline", True):
        bagian.append(
            "Pada skenario pesimis rute ini melewati batas waktu pengiriman "
            "dan/atau batas umur simpan, jadi tidak aman dijadikan andalan."
        )
    return " ".join(bagian)


def _kapan_dipakai(opt: Dict[str, Any], payload: Dict[str, Any]) -> str:
    opts = payload["options"]
    termurah = min(opts, key=lambda o: o["cost_rp"]["total"])
    tercepat = min(opts, key=lambda o: o["eta_hours"]["likely"])
    tersegar = max(opts, key=lambda o: o["quality"]["pct_fresh_on_arrival"])

    if opt["route_id"] == tercepat["route_id"]:
        return "Pilih rute ini kalau waktu yang paling mahal — inilah yang paling cepat tiba."
    if opt["route_id"] == termurah["route_id"]:
        selisih = tercepat["cost_rp"]["total"] - opt["cost_rp"]["total"]
        tambah = (opt["eta_hours"]["likely"] - tercepat["eta_hours"]["likely"]) * 60
        return (f"Pilih rute ini kalau menekan ongkos lebih penting: hemat "
                f"{fmt_rp(selisih)} dengan tambahan waktu sekitar {tambah:.0f} menit.")
    if opt["route_id"] == tersegar["route_id"]:
        return "Pilih rute ini kalau kesegaran barang jadi taruhan utama — kondisi tiba paling baik."
    return ("Rute cadangan: berguna kalau rute utama terganggu (kecelakaan, "
            "perbaikan jalan, atau antrean gerbang tol).")


def explain_route(opt: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    q = opt["quality"]
    advisory = retrieve_advisory(
        _kb(),
        commodity=(payload.get("request_echo") or {}).get("commodity", ""),
        risk_level=q.get("risk_level", "medium"),
        top_k=2,
    )
    return {
        "route_id": opt["route_id"],
        "name": opt["name"],
        "headline": opt.get("summary") or opt["name"],
        "reasoning": [
            {"aspect": "Waktu tempuh", "text": _reason_waktu(opt, payload.get("scoring") or {})},
            {"aspect": "Kesegaran kargo", "text": _reason_kesegaran(opt)},
            {"aspect": "Biaya", "text": _reason_biaya(opt)},
            {"aspect": "Posisi dalam peringkat", "text": _reason_peringkat(opt, payload)},
        ],
        "when_to_pick": _kapan_dipakai(opt, payload),
        "advisory": advisory.get("snippets", []),
        "advisory_note": advisory.get("note", ""),
        "method_note": q.get("basis_human", ""),
        "method_technical": q.get("basis", ""),
    }

def _score_100(opt: Dict[str, Any]) -> int:
    s = opt.get("score")
    return 0 if s is None else int(round((1.0 - float(s)) * 100))


def _segmen_terburuk(opt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    segs = opt.get("quality", {}).get("segments") or []
    if not segs:
        return None
    worst = max(segs, key=lambda s: s.get("pct_drop", 0.0))
    return dict(worst, drop=worst.get("pct_drop", 0.0))


def build_insight(payload: Dict[str, Any], route_id: str = None) -> Dict[str, Any]:
    options = payload.get("options") or []
    if not options:
        return {"explanation": [], "recommendations": []}

    best = next((o for o in options if o.get("is_best")), options[0])
    subjek = next((o for o in options if o["route_id"] == route_id), best)
    is_best = subjek["route_id"] == best["route_id"]

    echo = payload.get("request_echo") or {}
    lain = [o for o in options if o["route_id"] != subjek["route_id"]]
    pembanding = (min(lain, key=lambda o: o.get("score", 1)) if lain else None) if is_best else best
    termurah = min(options, key=lambda o: o["cost_rp"]["total"])
    tercepat = min(options, key=lambda o: o["eta_hours"]["likely"])
    amb = subjek["quality"].get("status_thresholds") or {}

    angka = (f"kesegaran {subjek['quality']['pct_fresh_on_arrival']:.0f}% "
             + (f"(ambang layak jual {amb['berisiko_di_bawah']:.0f}%), "
                if amb.get("berisiko_di_bawah") is not None else "")
             + f"waktu tempuh {fmt_jam(subjek['eta_hours']['likely'])}, "
               f"biaya {fmt_rp(subjek['cost_rp']['total'])}.")

    if is_best:
        penjelasan = [{
            "label": "Rute terpilih",
            "text": f"{subjek['name']} dipilih sebagai rute terbaik dengan skor gabungan "
                    f"{_score_100(subjek)}/100 — {angka}",
        }]
    else:
        penjelasan = [{
            "label": "Rute yang sedang dilihat",
            "text": f"{subjek['name']} — skor gabungan {_score_100(subjek)}/100, {angka} "
                    f"Ini bukan rekomendasi utama untuk prioritas yang sedang aktif.",
        }]

    if pembanding:
        selisih = abs(_score_100(subjek) - _score_100(pembanding))
        unggul, kalah = [], []
        pasangan = [
            ("kesegaran kargo", subjek["quality"]["pct_fresh_on_arrival"],
             pembanding["quality"]["pct_fresh_on_arrival"], True),
            ("waktu tempuh", subjek["eta_hours"]["likely"],
             pembanding["eta_hours"]["likely"], False),
            ("biaya", subjek["cost_rp"]["total"], pembanding["cost_rp"]["total"], False),
        ]
        for nama, a_val, b_val, makin_besar_makin_baik in pasangan:
            if a_val == b_val:
                continue
            lebih_baik = (a_val > b_val) if makin_besar_makin_baik else (a_val < b_val)
            (unggul if lebih_baik else kalah).append(nama)

        potongan = []
        if unggul:
            potongan.append(f"unggul di {', '.join(unggul)}")
        if kalah:
            potongan.append(f"kalah di {', '.join(kalah)}")
        penjelasan.append({
            "label": "Pembanding",
            "text": f"Dibandingkan {pembanding['name']} (skor {_score_100(pembanding)}), "
                    f"selisihnya {selisih} poin"
                    + (f" — rute ini {'; '.join(potongan)}." if potongan else "."),
        })

    worst = _segmen_terburuk(subjek)
    if worst:
        penjelasan.append({
            "label": "Titik risiko",
            "text": f"Penurunan kesegaran terbesar terjadi pada jam ke-{worst['from_h']:.0f}"
                    f"–{worst['to_h']:.0f} perjalanan (suhu kargo {worst['temp_c']:.0f}°C, "
                    f"kesegaran turun {worst['drop']:.0f} poin ke "
                    f"{worst['pct_fresh_end']:.0f}%).",
        })

    rekomendasi = []
    a = subjek.get("assumptions") or {}
    jam = (echo.get("departure_time") or "")[11:16]
    if a.get("f_time", 1) > 1.2:
        rekomendasi.append(
            f"Berangkat lebih awal dari {jam or 'jam berangkat saat ini'} — jam berangkat "
            f"sekarang menambah waktu tempuh sekitar {(a['f_time'] - 1) * 100:.0f}% "
            f"karena kepadatan lalu lintas."
        )
    elif jam:
        rekomendasi.append(f"Jam berangkat {jam} sudah di luar jam padat — pertahankan jadwal ini.")

    berisiko = [s for s in (subjek["quality"].get("segments") or [])
                if s.get("status") in ("waspada", "berisiko")]
    if berisiko:
        rekomendasi.append(
            f"Pantau suhu kargo pada {len(berisiko)} jam perjalanan yang berstatus waspada/berisiko "
            f"(mulai jam ke-{berisiko[0]['from_h']:.0f}); siapkan tambahan es atau turunkan "
            f"setpoint pendingin sebelum masuk periode itu."
        )
    else:
        rekomendasi.append(
            "Seluruh jam perjalanan berstatus aman — cukup ikuti prosedur pemeriksaan suhu standar."
        )

    if not subjek["quality"]["is_sellable"]:
        rekomendasi.append(
            "Kesegaran saat tiba di bawah ambang layak jual — pertimbangkan truk berpendingin, "
            "kargo yang lebih segar saat muat, atau memecah pengiriman jadi rit lebih pendek."
        )
    elif echo.get("vehicle") == "non_reefer" and subjek["quality"]["spoil_risk"] >= 0.3:
        rekomendasi.append(
            f"Risiko busuk {subjek['quality']['spoil_risk'] * 100:.0f}% dengan truk biasa — "
            "truk berpendingin akan menaikkan kesegaran saat tiba secara berarti."
        )

    if not is_best:
        d_biaya = subjek["cost_rp"]["total"] - best["cost_rp"]["total"]
        d_menit = (subjek["eta_hours"]["likely"] - best["eta_hours"]["likely"]) * 60
        if d_biaya < 0:
            rekomendasi.append(
                f"Memilih rute ini menghemat {fmt_rp(-d_biaya)} dibanding rute terbaik, "
                f"dengan tambahan waktu sekitar {abs(d_menit):.0f} menit dan kesegaran "
                f"{subjek['quality']['pct_fresh_on_arrival']:.0f}% (rute terbaik "
                f"{best['quality']['pct_fresh_on_arrival']:.0f}%)."
            )
        else:
            rekomendasi.append(
                f"Rute ini {fmt_rp(d_biaya)} lebih mahal dan "
                f"{abs(d_menit):.0f} menit lebih {'lama' if d_menit >= 0 else 'cepat'} "
                f"dibanding rute terbaik — pakai hanya bila rute utama sedang terganggu."
            )
    elif termurah["route_id"] != subjek["route_id"]:
        rekomendasi.append(
            f"Jika biaya jadi prioritas utama, {termurah['name']} lebih hemat "
            f"{fmt_rp(subjek['cost_rp']['total'] - termurah['cost_rp']['total'])}, "
            f"namun kesegaran turun ke {termurah['quality']['pct_fresh_on_arrival']:.0f}%."
        )
    elif tercepat["route_id"] != subjek["route_id"]:
        rekomendasi.append(
            f"Kalau waktu lebih penting daripada biaya, {tercepat['name']} tiba "
            f"{(subjek['eta_hours']['likely'] - tercepat['eta_hours']['likely']) * 60:.0f} menit "
            f"lebih cepat."
        )

    return {
        "route_id": subjek["route_id"],
        "route_name": subjek["name"],
        "is_best": is_best,
        "explanation": penjelasan,
        "recommendations": rekomendasi,
    }

def explain_payload(payload: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
    options = payload.get("options") or []
    if not options:
        return {"routes": [], "overview": "Belum ada rute untuk dijelaskan.", "llm_used": False}

    routes = [explain_route(o, payload) for o in options]

    best = next((o for o in options if o.get("is_best")), options[0])
    scoring = payload.get("scoring") or {}
    overview_parts = [
        f"{len(options)} rute dibandingkan pada tiga kriteria yang sama: waktu tempuh, "
        f"biaya total, dan risiko busuk.",
        f"{best['name']} keluar sebagai pilihan untuk prioritas "
        f"{scoring.get('preference', 'balanced')} — tiba dalam {fmt_jam(best['eta_hours']['likely'])} "
        f"dengan kesegaran {best['quality']['pct_fresh_on_arrival']:.1f}% "
        f"dan biaya {fmt_rp(best['cost_rp']['total'])}.",
    ]
    if payload.get("alert"):
        overview_parts.append(f"Perhatian: {payload['alert']}")
    overview = " ".join(overview_parts)

    llm_used = False
    if use_llm:
        try:
            from .llm import polish_explanations
            polished = polish_explanations(routes, payload)
            if polished:
                routes = polished
                llm_used = True
        except Exception:
            pass

    insights = {o["route_id"]: build_insight(payload, o["route_id"]) for o in options}

    return {
        "routes": routes,
        "overview": overview,
        "insights": insights,
        "insight": insights.get(best["route_id"]),
        "llm_used": llm_used,
    }
