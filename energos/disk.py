"""Disk-scheduling algorithms.

A hard-disk head must physically move between cylinders. The order in which
pending requests are served decides the total head movement (seek distance),
which costs time and energy.  (Phones use flash memory, which has no head,
but the same scheduling ideas are used in OS I/O schedulers and in laptops/servers.)
"""
from __future__ import annotations

from . import energy

ALGORITHMS = ["FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK"]


def schedule(requests: list[int], head: int, algorithm: str = "FCFS", direction: str = "up",
             disk_size: int = 200) -> dict:
    """Return the order of head positions (starting at `head`) and the total seek distance.

    direction : "up" (towards higher cylinders) or "down", for SCAN/C-SCAN/LOOK/C-LOOK
    For C-SCAN the return sweep (end -> start) is counted in the total.
    """
    reqs = list(requests)
    path = [head]
    lo, hi = 0, disk_size - 1
    below = sorted(r for r in reqs if r < head)
    above = sorted(r for r in reqs if r >= head)

    if algorithm == "FCFS":
        path += reqs
    elif algorithm == "SSTF":
        pos, left = head, reqs[:]
        while left:
            nxt = min(left, key=lambda r: (abs(r - pos), r))   # closest request next
            path.append(nxt)
            left.remove(nxt)
            pos = nxt
    elif algorithm == "SCAN":            # elevator: go to the end, then reverse
        if direction == "up":
            path += above + ([hi] if below else []) + below[::-1]
        else:
            path += below[::-1] + ([lo] if above else []) + above
    elif algorithm == "C-SCAN":          # go to the end, jump to the other end, continue same way
        if direction == "up":
            path += above + ([hi, lo] if below else []) + below
        else:
            path += below[::-1] + ([lo, hi] if above else []) + above[::-1]
    elif algorithm == "LOOK":            # like SCAN but only as far as the last request
        path += (above + below[::-1]) if direction == "up" else (below[::-1] + above)
    elif algorithm == "C-LOOK":          # like C-SCAN but jump between the outermost requests
        path += (above + below) if direction == "up" else (below[::-1] + above[::-1])
    else:
        raise ValueError(algorithm)

    # remove duplicate consecutive points (e.g. a request exactly at the head)
    clean = [path[0]]
    for p in path[1:]:
        if p != clean[-1]:
            clean.append(p)
    total = sum(abs(b - a) for a, b in zip(clean, clean[1:]))
    return {"algorithm": algorithm, "path": clean, "total_seek": total,
            "seek_time_ms": total * energy.T_SEEK_PER_CYL_MS,
            "energy_mj": total * energy.E_SEEK_PER_CYL_MJ,
            "avg_seek": total / len(reqs) if reqs else 0}


def compare(requests, head, direction="up", disk_size=200):
    rows = []
    for a in ALGORITHMS:
        r = schedule(requests, head, a, direction, disk_size)
        rows.append({"Algorithm": a, "Total seek (cylinders)": r["total_seek"], "Avg seek": round(r["avg_seek"], 1),
                     "Seek time (ms)": round(r["seek_time_ms"], 2), "Energy (mJ)": round(r["energy_mj"], 2)})
    return rows
