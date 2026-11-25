"""Power model, DVFS governors and battery constants.

Why the power formula looks like this
-------------------------------------
Dynamic power of CMOS logic is  P_dyn = C * V^2 * f.
With DVFS the voltage V is lowered together with the frequency f (V is roughly
proportional to f), so P_dyn grows roughly with f^3.  A chip also leaks a fixed
amount of power while it is switched on (static power).  So, while busy:

        P(f) = P_STATIC + K * f^3            (watts, f in GHz)

When the CPU has nothing to run it enters an idle state that draws P_IDLE.

Units used everywhere in EnergOS
--------------------------------
time   : milliseconds (one simulation tick = 1 ms)
power  : watts
energy : millijoules   (1 W for 1 ms = 1 mJ)
"""

# ---- CPU frequency levels (GHz) that the governor may choose from ----
FREQS = [0.8, 1.2, 1.6, 2.0]
F_MAX = FREQS[-1]
F_MIN = FREQS[0]

# ---- power model constants ----
P_STATIC = 0.25      # W, leakage while the core is powered and busy
K_DYN = 0.20         # W / GHz^3, dynamic-power coefficient
P_IDLE = 0.05        # W, CPU in idle state (nothing to run)

# ---- other energy costs used by the memory and disk modules ----
E_PAGE_FAULT_MJ = 2.0        # mJ to service one page fault (read a page from flash + handler)
T_PAGE_FAULT_MS = 1.0        # ms extra time per page fault
E_SEEK_PER_CYL_MJ = 0.02     # mJ per cylinder of head movement
T_SEEK_PER_CYL_MS = 0.05     # ms per cylinder of head movement

# ---- battery ----
BATTERY_MWH = 15_000         # ~4000 mAh x 3.85 V, a typical phone battery


def busy_power(freq_ghz: float) -> float:
    """Power (W) drawn by a busy core running at freq_ghz."""
    return P_STATIC + K_DYN * freq_ghz ** 3


PERIOD_MS = 1000             # the workload is assumed to repeat once every second


def duty_cycle_power(energy_mj: float, busy_time_ms: float, period_ms: float = PERIOD_MS) -> float:
    """Average power if this workload runs once per period and the CPU idles for the rest.
    This is how a phone really behaves: a burst of work, then idle until the next event."""
    period = max(period_ms, busy_time_ms)
    return (energy_mj + P_IDLE * (period - busy_time_ms)) / period


def battery_life_hours(avg_power_w: float) -> float:
    """How long a full battery lasts at this average power."""
    if avg_power_w <= 0:
        return float("inf")
    return (BATTERY_MWH / 1000.0) / avg_power_w


# ======================================================================
#  DVFS governors – decide the CPU frequency for the next tick
# ======================================================================
class Governor:
    """Base class. `choose` is called once per tick while a process is running."""
    name = "base"

    def reset(self):
        pass

    def choose(self, ready_count: int, was_busy: bool, queued_work: float = 0.0) -> float:
        """ready_count: runnable processes (incl. the one about to run)
        was_busy:    did the CPU run something in the previous tick?
        queued_work: total remaining work (ms at F_MAX) of all runnable processes"""
        raise NotImplementedError


class Performance(Governor):
    """Always the highest frequency (Linux 'performance')."""
    name = "performance"

    def choose(self, ready_count, was_busy, queued_work=0.0):
        return F_MAX


class Powersave(Governor):
    """Always the lowest frequency (Linux 'powersave')."""
    name = "powersave"

    def choose(self, ready_count, was_busy, queued_work=0.0):
        return F_MIN


class OnDemand(Governor):
    """Scale with the number of runnable processes: more work waiting -> run faster."""
    name = "ondemand"

    def choose(self, ready_count, was_busy, queued_work=0.0):
        # ready_count includes the process about to run
        index = min(max(ready_count - 1, 0), len(FREQS) - 1)
        return FREQS[index]


class Schedutil(Governor):
    """Like Linux 'schedutil': f = 1.25 * f_max * utilisation, rounded up to a level.

    Utilisation is an exponential moving average of how busy the CPU was in
    recent ticks (1 = busy every tick, 0 = always idle).
    """
    name = "schedutil"

    def __init__(self, alpha: float = 0.2):
        self.alpha = alpha
        self.util = 0.0

    def reset(self):
        self.util = 0.0

    def choose(self, ready_count, was_busy, queued_work=0.0):
        self.util = (1 - self.alpha) * self.util + self.alpha * (1.0 if was_busy else 0.0)
        target = 1.25 * F_MAX * self.util
        for f in FREQS:
            if f >= target:
                return f
        return F_MAX


class LatencyBudget(Governor):
    """EnergOS's own governor: run *just fast enough* to clear all queued work
    within a latency budget L (default 40 ms).

        f_needed = F_MAX * queued_work / L        -> rounded up to the next level

    Little work waiting  -> low frequency (saves energy, nobody is waiting long).
    Lots of work waiting -> high frequency (keeps waiting time bounded).
    """
    name = "latency-budget"

    def __init__(self, budget_ms: float = 40.0):
        self.budget = budget_ms

    def choose(self, ready_count, was_busy, queued_work=0.0):
        needed = F_MAX * queued_work / self.budget
        for f in FREQS:
            if f >= needed:
                return f
        return F_MAX


GOVERNORS = {g.name: g for g in (Performance, Powersave, OnDemand, Schedutil, LatencyBudget)}


def make_governor(name: str, budget_ms: float = 40.0) -> Governor:
    if name == "latency-budget":
        return LatencyBudget(budget_ms)
    return GOVERNORS[name]()
