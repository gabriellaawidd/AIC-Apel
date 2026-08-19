# main.py
from engine import compute_spoilage
from models import COMMODITY_DB, INITIAL_CONDITION_MAP

def run_interactive_test():
    print("=== COLD CHAIN AI: SPOILAGE ENGINE ===")
    print("Komoditas tersedia:", ", ".join(COMMODITY_DB.keys()))
    komoditas = input("Pilih komoditas: ").strip()
    
    if komoditas not in COMMODITY_DB:
        print("Komoditas tidak valid.")
        return

    print("Kondisi awal tersedia:", ", ".join(INITIAL_CONDITION_MAP.keys()))
    kondisi_awal = input("Pilih kondisi awal: ").strip()

    n = int(input("Berapa segmen perjalanan? "))
    segmen = []
    for i in range(n):
        print(f"Segmen {i+1}:")
        dur = float(input("  Durasi (jam): "))
        temp = float(input("  Suhu (C): "))
        segmen.append({"duration_hours": dur, "temp_c": temp})

    # Memanggil engine utama
    hasil = compute_spoilage(komoditas, segmen, kondisi_awal=kondisi_awal)
    
    print("\n--- HASIL PREDIKSI ---")
    for k, v in hasil.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    run_interactive_test()