"""Paging: address translation and page-replacement algorithms.

A process's memory is split into fixed-size *pages*; physical memory into
*frames* of the same size. The page table maps page -> frame.  When a process
touches a page that is not in any frame we get a *page fault*: the OS must load
the page from storage, and if all frames are full it must choose a *victim*
page to evict – that choice is the page-replacement algorithm.

Every page fault costs time and energy (reading flash), so fewer faults means
a faster and more battery-friendly system.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import energy

ALGORITHMS = ["FIFO", "LRU", "Optimal", "Clock"]


# ======================================================================
#  Address translation
# ======================================================================
def translate(logical: int, page_size: int, page_table: dict[int, int]):
    """Logical address -> (page, offset, frame, physical).  frame/physical are None on a page fault."""
    page, offset = divmod(logical, page_size)
    frame = page_table.get(page)
    physical = None if frame is None else frame * page_size + offset
    return {"page": page, "offset": offset, "frame": frame, "physical": physical, "fault": frame is None}


# ======================================================================
#  Page replacement
# ======================================================================
@dataclass
class Step:
    ref: int                 # page referenced
    frames: list             # frame contents after this reference (None = empty)
    hit: bool
    victim: int | None       # page evicted (None if no eviction)
    pointer: int | None = None   # clock hand position (Clock only)
    ref_bits: list | None = None # reference bits (Clock only)


@dataclass
class ReplacementResult:
    algorithm: str
    frames: int
    steps: list[Step]

    @property
    def faults(self):    return sum(not s.hit for s in self.steps)
    @property
    def hits(self):      return sum(s.hit for s in self.steps)
    @property
    def hit_ratio(self): return self.hits / len(self.steps) if self.steps else 0
    @property
    def energy_mj(self): return self.faults * energy.E_PAGE_FAULT_MJ
    @property
    def fault_time_ms(self): return self.faults * energy.T_PAGE_FAULT_MS


def simulate(refs: list[int], n_frames: int, algorithm: str = "FIFO") -> ReplacementResult:
    frames: list[int | None] = [None] * n_frames
    steps: list[Step] = []

    fifo_order: list[int] = []          # FIFO: oldest loaded page first
    last_used: dict[int, int] = {}      # LRU: page -> time of last use
    ref_bit = [0] * n_frames            # Clock: one reference bit per frame
    hand = 0                            # Clock: the "clock hand"

    for t, page in enumerate(refs):
        victim = None
        if page in frames:                                   # ---- hit ----
            hit = True
            if algorithm == "Clock":
                ref_bit[frames.index(page)] = 1
        else:                                                # ---- page fault ----
            hit = False
            if None in frames:                               # a free frame exists
                slot = frames.index(None)
            elif algorithm == "FIFO":
                victim = fifo_order.pop(0)
                slot = frames.index(victim)
            elif algorithm == "LRU":
                victim = min((p for p in frames), key=lambda p: last_used[p])
                slot = frames.index(victim)
            elif algorithm == "Optimal":
                # evict the page whose next use is farthest in the future (or never)
                def next_use(p):
                    try:
                        return refs.index(p, t + 1)
                    except ValueError:
                        return float("inf")
                victim = max(frames, key=lambda p: (next_use(p), -frames.index(p)))
                slot = frames.index(victim)
            elif algorithm == "Clock":
                # second chance: skip pages whose reference bit is 1 (and clear it)
                while ref_bit[hand] == 1:
                    ref_bit[hand] = 0
                    hand = (hand + 1) % n_frames
                slot = hand
                victim = frames[slot]
                hand = (hand + 1) % n_frames
            else:
                raise ValueError(algorithm)

            if victim is not None and victim in fifo_order:
                fifo_order.remove(victim)
            frames[slot] = page
            fifo_order.append(page)
            if algorithm == "Clock":
                ref_bit[slot] = 1
                if victim is None:                           # filling an empty frame
                    hand = (slot + 1) % n_frames
        last_used[page] = t
        steps.append(Step(page, list(frames), hit, victim,
                          hand if algorithm == "Clock" else None,
                          list(ref_bit) if algorithm == "Clock" else None))
    return ReplacementResult(algorithm, n_frames, steps)


def compare(refs: list[int], n_frames: int):
    return [{"Algorithm": a, "Page faults": (r := simulate(refs, n_frames, a)).faults, "Hits": r.hits,
             "Hit ratio": round(r.hit_ratio, 3), "Fault energy (mJ)": r.energy_mj} for a in ALGORITHMS]


def belady_curve(refs: list[int], max_frames: int = 7, algorithm: str = "FIFO"):
    """Page faults for 1..max_frames frames. FIFO can get MORE faults with more frames (Belady's anomaly)."""
    return [(n, simulate(refs, n, algorithm).faults) for n in range(1, max_frames + 1)]


def locality_refs(length: int, pages: int = 10, seed: int = 1, working_set: int = 4, shift_every: int = 12):
    """Generate a reference string with locality of reference: the process mostly touches a small
    working set of pages, and the working set slowly moves (like a program moving between functions)."""
    import random
    rng = random.Random(seed)
    base = 0
    refs = []
    for i in range(length):
        if i and i % shift_every == 0:
            base = (base + rng.randint(1, 3)) % pages
        if rng.random() < 0.9:
            refs.append((base + rng.randrange(working_set)) % pages)
        else:
            refs.append(rng.randrange(pages))
    return refs
