"""CPU scheduling algorithms and a tick-based, energy-aware simulator.

How the simulator works (one loop iteration = 1 ms tick)
-------------------------------------------------------
1. Processes whose arrival time has come are handed to the scheduler (ready queue).
2. The scheduler chooses which process runs in this tick (it may pre-empt).
3. The DVFS governor chooses the CPU frequency for this tick.
4. The chosen process does  f / F_MAX  units of work (bursts are given in ms at F_MAX),
   and the tick's energy  P(f) * 1 ms  is added to the totals.
5. If nothing is ready the CPU idles and draws P_IDLE.

At the maximum frequency the results are exactly the textbook ones, which our
tests check against the examples in Silberschatz, *Operating System Concepts*.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from . import energy

EPS = 1e-9


@dataclass
class Process:
    pid: str
    arrival: int
    burst: float            # ms of work at F_MAX
    priority: int = 0       # smaller number = higher priority
    # ---- filled in by the simulator ----
    remaining: float = field(default=0.0, repr=False)
    start: int | None = field(default=None, repr=False)
    completion: int | None = field(default=None, repr=False)
    run_ticks: int = field(default=0, repr=False)
    energy_mj: float = field(default=0.0, repr=False)

    def reset(self):
        self.remaining = self.burst
        self.start = None
        self.completion = None
        self.run_ticks = 0
        self.energy_mj = 0.0


# ======================================================================
#  Scheduling algorithms
#  Each scheduler keeps its own ready queue and answers one question per
#  tick:  "given the process that ran last tick (or None), who runs now?"
# ======================================================================
class Scheduler:
    name = "base"
    preemptive = False

    def __init__(self):
        self.ready: list[Process] = []

    def arrive(self, p: Process, t: int):
        self.ready.append(p)

    def ready_count(self) -> int:
        return len(self.ready)

    def waiting(self):                  # processes in the ready queue
        return self.ready

    def queued_work(self) -> float:
        return sum(p.remaining for p in self.waiting())

    def choose(self, t: int, current: Process | None) -> Process | None:
        raise NotImplementedError

    def ran(self, p: Process):          # called after p ran one tick
        pass

    def finished(self, p: Process):     # called when p completes
        pass

    # helper for the non-preemptive "pick best by key" algorithms
    def _take_best(self, key):
        if not self.ready:
            return None
        best = min(self.ready, key=key)
        self.ready.remove(best)
        return best


class FCFS(Scheduler):
    """First-Come, First-Served: non-preemptive, in order of arrival."""
    name = "FCFS"

    def choose(self, t, current):
        if current is not None:
            return current                       # never pre-empt
        return self._take_best(key=lambda p: (p.arrival, p.pid))


class SJF(Scheduler):
    """Shortest Job First (non-preemptive): pick the smallest burst."""
    name = "SJF"

    def choose(self, t, current):
        if current is not None:
            return current
        return self._take_best(key=lambda p: (p.burst, p.arrival, p.pid))


class SRTF(Scheduler):
    """Shortest Remaining Time First: preemptive SJF, re-decided every tick."""
    name = "SRTF"
    preemptive = True

    def choose(self, t, current):
        if current is not None:
            best = min(self.ready, key=lambda p: (p.remaining, p.arrival), default=None)
            if best is None or best.remaining >= current.remaining - EPS:
                return current                   # current is still the shortest
            self.ready.remove(best)
            self.ready.append(current)           # pre-empt current
            return best
        return self._take_best(key=lambda p: (p.remaining, p.arrival, p.pid))


class Priority(Scheduler):
    """Priority scheduling (smaller number = higher priority), optionally preemptive."""
    name = "Priority"

    def __init__(self, preemptive: bool = False):
        super().__init__()
        self.preemptive = preemptive
        self.name = "Priority (preemptive)" if preemptive else "Priority"

    def choose(self, t, current):
        if current is not None:
            if not self.preemptive:
                return current
            best = min(self.ready, key=lambda p: (p.priority, p.arrival), default=None)
            if best is None or best.priority >= current.priority:
                return current
            self.ready.remove(best)
            self.ready.append(current)
            return best
        return self._take_best(key=lambda p: (p.priority, p.arrival, p.pid))


class RoundRobin(Scheduler):
    """Round Robin with time quantum q. New arrivals join the queue before a
    process whose quantum just expired (the textbook convention)."""
    name = "Round Robin"
    preemptive = True

    def __init__(self, quantum: int = 4):
        super().__init__()
        self.q = quantum
        self.queue: deque[Process] = deque()
        self.used = 0
        self.name = f"Round Robin (q={quantum})"

    def arrive(self, p, t):
        self.queue.append(p)

    def ready_count(self):
        return len(self.queue)

    def waiting(self):
        return self.queue

    def choose(self, t, current):
        if current is not None and self.used < self.q:
            return current
        if current is not None:                  # quantum expired -> back of the queue
            self.queue.append(current)
        self.used = 0
        return self.queue.popleft() if self.queue else None

    def ran(self, p):
        self.used += 1

    def finished(self, p):
        self.used = 0


class MLFQ(Scheduler):
    """Multilevel Feedback Queue.

    Level 0: RR q=4   Level 1: RR q=8   Level 2: FCFS
    * new processes start at level 0
    * using a whole quantum -> demoted one level (CPU-bound jobs sink)
    * a process at a higher level pre-empts one at a lower level
    * every `boost` ms all processes move back to level 0 (ageing, prevents starvation)
    """
    name = "MLFQ"
    preemptive = True

    def __init__(self, quanta=(4, 8, None), boost: int = 60):
        super().__init__()
        self.quanta = quanta
        self.boost = boost
        self.levels = [deque() for _ in quanta]
        self.level: dict[str, int] = {}
        self.used = 0
        self.next_boost = boost

    def arrive(self, p, t):
        self.level[p.pid] = 0
        self.levels[0].append(p)

    def ready_count(self):
        return sum(len(q) for q in self.levels)

    def waiting(self):
        return [p for q in self.levels for p in q]

    def _quantum(self, p):
        return self.quanta[self.level[p.pid]]

    def choose(self, t, current):
        if self.boost and t >= self.next_boost:                   # priority boost
            self.next_boost += self.boost
            everyone = [p for q in self.levels for p in q]
            self.levels = [deque(everyone)] + [deque() for _ in self.quanta[1:]]
            for p in everyone:
                self.level[p.pid] = 0
            if current is not None:
                self.level[current.pid] = 0

        if current is not None:
            q = self._quantum(current)
            lvl = self.level[current.pid]
            if q is not None and self.used >= q:                   # used full quantum
                self.level[current.pid] = min(lvl + 1, len(self.quanta) - 1)
                self.levels[self.level[current.pid]].append(current)
                current = None
            elif any(self.levels[i] for i in range(lvl)):          # higher level waiting
                self.levels[lvl].append(current)
                current = None
        if current is not None:
            return current
        self.used = 0
        for q in self.levels:
            if q:
                return q.popleft()
        return None

    def ran(self, p):
        self.used += 1

    def finished(self, p):
        self.used = 0


def make_scheduler(name: str, quantum: int = 4) -> Scheduler:
    return {
        "FCFS": FCFS, "SJF": SJF, "SRTF": SRTF,
        "Priority": lambda: Priority(False), "Priority (preemptive)": lambda: Priority(True),
        "Round Robin": lambda: RoundRobin(quantum), "MLFQ": MLFQ,
    }[name]()


ALGORITHMS = ["FCFS", "SJF", "SRTF", "Priority", "Priority (preemptive)", "Round Robin", "MLFQ"]


# ======================================================================
#  The simulator
# ======================================================================
@dataclass
class Segment:
    start: int
    end: int
    pid: str | None          # None = idle, "CS" = context switch
    freq: float


@dataclass
class SimResult:
    algorithm: str
    governor: str
    processes: list[Process]
    segments: list[Segment]
    makespan: int
    busy_ticks: int
    energy_busy_mj: float
    energy_idle_mj: float
    context_switches: int

    # ---- textbook metrics ----
    def turnaround(self, p):  return p.completion - p.arrival
    def waiting(self, p):     return self.turnaround(p) - p.run_ticks   # time spent in the ready queue
    def response(self, p):    return p.start - p.arrival

    @property
    def avg_waiting(self):    return sum(self.waiting(p) for p in self.processes) / len(self.processes)
    @property
    def avg_turnaround(self): return sum(self.turnaround(p) for p in self.processes) / len(self.processes)
    @property
    def avg_response(self):   return sum(self.response(p) for p in self.processes) / len(self.processes)
    @property
    def cpu_utilisation(self): return self.busy_ticks / self.makespan if self.makespan else 0
    @property
    def throughput(self):     return len(self.processes) / self.makespan * 1000   # processes per second

    # ---- energy metrics ----
    @property
    def energy_mj(self):      return self.energy_busy_mj + self.energy_idle_mj
    @property
    def avg_power_w(self):    return self.energy_mj / self.makespan if self.makespan else 0   # mJ/ms = W, while running
    @property
    def battery_hours(self):
        """Battery life if this workload repeats every second and the CPU idles in between."""
        return energy.battery_life_hours(energy.duty_cycle_power(self.energy_mj, self.makespan))
    @property
    def edp(self):            return self.energy_mj * self.makespan     # energy-delay product (mJ*ms)

    def table(self):
        """One row per process – handy for pandas / the dashboard."""
        return [dict(PID=p.pid, Arrival=p.arrival, Burst=p.burst, Priority=p.priority,
                     Start=p.start, Completion=p.completion,
                     Turnaround=self.turnaround(p), Waiting=self.waiting(p), Response=self.response(p),
                     **{"Energy (mJ)": round(p.energy_mj, 2)}) for p in self.processes]


def simulate(processes: list[Process], algorithm: str = "FCFS", governor: str = "performance",
             quantum: int = 4, context_switch: int = 0, budget_ms: float = 40.0,
             max_time: int = 100_000) -> SimResult:
    """Run the workload and return per-process metrics, a Gantt timeline and energy totals."""
    procs = sorted((Process(p.pid, p.arrival, p.burst, p.priority) for p in processes),
                   key=lambda p: (p.arrival, p.pid))
    for p in procs:
        p.reset()
    sched = make_scheduler(algorithm, quantum)
    gov = energy.make_governor(governor, budget_ms)
    gov.reset()

    segments: list[Segment] = []
    def record(t, pid, f):
        if segments and segments[-1].pid == pid and segments[-1].freq == f and segments[-1].end == t:
            segments[-1].end = t + 1
        else:
            segments.append(Segment(t, t + 1, pid, f))

    t = 0
    i = 0                       # next process to arrive
    done = 0
    current = None
    last_pid = None
    was_busy = False
    e_busy = e_idle = 0.0
    busy = 0
    switches = 0
    cs_left = 0                 # remaining context-switch ticks
    pending = None              # process waiting for the context switch to finish

    while done < len(procs) and t < max_time:
        while i < len(procs) and procs[i].arrival <= t:      # 1. arrivals
            sched.arrive(procs[i], t)
            i += 1

        if cs_left == 0:                                     # 2. scheduling decision
            nxt = pending if pending is not None else sched.choose(t, current)
            pending = None
            if nxt is not None and last_pid is not None and nxt.pid != last_pid:
                switches += 1
                if context_switch > 0:
                    cs_left = context_switch
                    pending = nxt
                    current = None
        else:
            nxt = None

        if cs_left > 0:                                      # context-switch overhead tick
            f = gov.choose(sched.ready_count() + 1, True, sched.queued_work() + pending.remaining)
            e = energy.busy_power(f)
            e_busy += e
            busy += 1
            record(t, "CS", f)
            cs_left -= 1
            was_busy = True
            t += 1
            continue

        if nxt is not None:                                  # 3+4. run one tick
            f = gov.choose(sched.ready_count() + 1, was_busy, sched.queued_work() + nxt.remaining)
            e = energy.busy_power(f)
            nxt.remaining -= f / energy.F_MAX
            nxt.run_ticks += 1
            nxt.energy_mj += e
            if nxt.start is None:
                nxt.start = t
            e_busy += e
            busy += 1
            record(t, nxt.pid, f)
            sched.ran(nxt)
            last_pid = nxt.pid
            was_busy = True
            if nxt.remaining <= EPS:
                nxt.completion = t + 1
                sched.finished(nxt)
                done += 1
                current = None
            else:
                current = nxt
        else:                                                # 5. idle tick
            gov.choose(0, False, 0.0)
            e_idle += energy.P_IDLE
            record(t, None, 0.0)
            was_busy = False
            current = None
        t += 1

    return SimResult(algorithm=sched.name, governor=gov.name, processes=procs, segments=segments,
                     makespan=t, busy_ticks=busy, energy_busy_mj=e_busy, energy_idle_mj=e_idle,
                     context_switches=switches)


def compare(processes, algorithms=None, governors=None, quantum=4, context_switch=0, budget_ms=40.0):
    """Run every algorithm x governor combination and return summary rows."""
    rows = []
    for a in algorithms or ALGORITHMS:
        for g in governors or list(energy.GOVERNORS):
            r = simulate(processes, a, g, quantum, context_switch, budget_ms)
            rows.append({"Algorithm": a, "Governor": g,
                         "Avg waiting (ms)": round(r.avg_waiting, 2),
                         "Avg turnaround (ms)": round(r.avg_turnaround, 2),
                         "Avg response (ms)": round(r.avg_response, 2),
                         "Makespan (ms)": r.makespan,
                         "Energy (mJ)": round(r.energy_mj, 1),
                         "Avg power (W)": round(r.avg_power_w, 3),
                         "Battery life (h)": round(r.battery_hours, 2),
                         "EDP (J·ms)": round(r.edp / 1000, 1),
                         "Context switches": r.context_switches})
    return rows


def budget_sweep(processes, algorithm="Round Robin", budgets=(5, 10, 20, 40, 80, 160), quantum=4):
    """Trade-off curve of the latency-budget governor: small budget = fast & hungry, large = slow & frugal."""
    rows = []
    for b in budgets:
        r = simulate(processes, algorithm, "latency-budget", quantum, 0, b)
        rows.append({"Budget (ms)": b, "Avg waiting (ms)": round(r.avg_waiting, 2), "Energy (mJ)": round(r.energy_mj, 1)})
    return rows
