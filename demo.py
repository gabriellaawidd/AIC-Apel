"""
demo.py — Demonstrasi rantai penuh M1 -> M2 -> M3
=================================================
Menjalankan pipeline pada koridor Jakarta -> Bandung untuk dua skenario
kendaraan (non-reefer vs reefer). Non-interaktif; cocok direkam untuk
video proof of work, dan dipakai sebagai entrypoint docker compose.

    python demo.py
"""

from datetime import datetime

import pipeline
from contracts import TripRequest


def main():
    pipeline.configure_cost(golongan="II_III")  # armada CDD (2 gandar)

    for veh in ("non_reefer", "reefer"):
        req = TripRequest(
            origin=(106.8272, -6.1751),       # Jakarta (lon, lat)
            destination=(107.6098, -6.9147),  # Bandung (lon, lat)
            commodity="ikan_segar",
            departure_time=datetime(2026, 8, 20, 8, 0),
            vehicle=veh,
            preference="balanced",
            deadline=datetime(2026, 8, 20, 13, 0),
            initial_condition="segar",
        )
        print("=" * 78)
        print(f"RANTAI PENUH  M1(RIO) -> M2(GAB) -> M3(DAVIN)   |   kendaraan: {veh}")
        print("=" * 78)
        pipeline.print_result(pipeline.run_pipeline(req))
        print()


if __name__ == "__main__":
    main()
