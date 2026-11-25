# EnergOS — an energy-aware Operating System simulator

**OS course project · SRM University AP · Aarth Goyal, Prit Patel, Krishna Karthikeya Burra**

EnergOS implements the core algorithms of an operating-systems course in plain, readable Python and asks one
extra question about each of them: *what does this decision cost in battery?*

| Module | Owner | What it does |
|---|---|---|
| `energos/energy.py`, `energos/cpu.py` | Aarth | FCFS, SJF, SRTF, Priority (± preemption), Round Robin, MLFQ on a tick-based simulator with 5 DVFS governors (performance, powersave, ondemand, schedutil, **latency-budget**) and an energy/battery model |
| `energos/memory.py`, `energos/disk.py` | Prit | Address translation, FIFO / LRU / Optimal / Clock page replacement, Belady's anomaly, FCFS / SSTF / SCAN / C-SCAN / LOOK / C-LOOK disk scheduling, with fault and seek energy |
| `energos/sync.py`, `energos/deadlock.py`, `energos/battery_lab.py`, `energos/history.py` | Krishna | Race condition, producer–consumer with semaphores, dining philosophers (real threads); Banker's algorithm, deadlock detection, wait-for graph; whole-workload battery lab; SQLite run history |
| `app.py` | all | Streamlit dashboard with one page per module |

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q          # 28 checks against textbook examples – all should pass
streamlit run app.py         # opens http://localhost:8501
```

Re-create the screenshots (with the app running): `python tools/capture_screens.py screenshots`
(needs `pip install playwright && playwright install chromium`).

## Energy model

* Busy core at frequency *f* (GHz): **P = 0.25 + 0.2·f³ W** (static leakage + dynamic power, since P_dyn = C·V²·f and V ∝ f)
* Idle core: 0.05 W · page fault: 2 mJ + 1 ms · disk head: 0.02 mJ + 0.05 ms per cylinder
* Battery life assumes the workload repeats once per second on a 15 Wh battery and the CPU idles in between.

All constants live at the top of `energos/energy.py` so they can be changed in one place.

## Verified against the textbook

| Example (Silberschatz, *Operating System Concepts*) | Expected | EnergOS |
|---|---|---|
| FCFS, bursts 24/3/3 — avg waiting | 17 | 17 |
| SJF, bursts 6/8/7/3 — avg waiting | 7 | 7 |
| SRTF, arrivals 0–3 — avg waiting | 6.5 | 6.5 |
| Priority, 5 processes — avg waiting | 8.2 | 8.2 |
| Round Robin q=4 — avg waiting | 5.66 | 5.67 |
| Page faults, 20-reference string, 3 frames: FIFO / LRU / OPT | 15 / 12 / 9 | 15 / 12 / 9 |
| Belady's anomaly (FIFO, 3 vs 4 frames) | 9 / 10 | 9 / 10 |
| Disk queue 98…67, head 53: FCFS / SSTF / SCAN↓ / C-SCAN↑ | 640 / 236 / 236 / 382 | 640 / 236 / 236 / 382 |
| Banker's state (3,3,2 available) | safe, starts with P1 | P1 → P3 → P4 → P0 → P2 |

## Repository contents

| Folder | What is inside |
|---|---|
| `energos/` | the simulator engines (one module per OS topic) |
| `app.py` | Streamlit dashboard |
| `tests/` | 28 pytest checks against textbook examples |

**Team:** Aarth Goyal (AP24110010685) · Prit Patel (AP24110011578) · Krishna Karthikeya Burra (AP24110011237)
**Guide:** Dr. Shaiju Panchikkil, Department of CSE, SRM University AP
