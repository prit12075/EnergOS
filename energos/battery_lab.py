"""Battery lab: run a whole workload through CPU, memory and disk and report
where the energy goes and how long the battery would last.

A workload is a set of processes. Each process has
  * a CPU burst (scheduled by the CPU module),
  * a page-reference string (run through the page-replacement module),
  * a few disk requests (run through the disk-scheduling module).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import cpu, disk, energy, memory


@dataclass
class Task:
    pid: str
    arrival: int
    burst: int
    priority: int
    refs: list[int] = field(default_factory=list)
    disk_requests: list[int] = field(default_factory=list)


def generate_workload(n: int = 8, seed: int = 7, mix: str = "mixed") -> list[Task]:
    """Random but reproducible workload.
    mix = "interactive" (many short bursts), "batch" (long CPU-bound bursts) or "mixed"."""
    rng = random.Random(seed)
    tasks, t = [], 0
    for k in range(n):
        kind = mix if mix != "mixed" else rng.choice(["interactive", "interactive", "batch"])
        burst = rng.randint(2, 8) if kind == "interactive" else rng.randint(12, 30)
        tasks.append(Task(
            pid=f"P{k + 1}", arrival=t, burst=burst, priority=rng.randint(1, 5),
            refs=memory.locality_refs(length=burst * 3, pages=12, seed=seed * 100 + k),
            disk_requests=[rng.randrange(200) for _ in range(rng.randint(1, 3))]))
        t += rng.randint(0, 6)
    return tasks


@dataclass
class LabResult:
    cpu: cpu.SimResult
    page_faults: int
    energy_cpu_mj: float
    energy_mem_mj: float
    energy_disk_mj: float
    seek_total: int
    extra_time_ms: float

    @property
    def energy_total_mj(self):
        return self.energy_cpu_mj + self.energy_mem_mj + self.energy_disk_mj

    @property
    def total_time_ms(self):
        return self.cpu.makespan + self.extra_time_ms

    @property
    def avg_power_w(self):
        return self.energy_total_mj / self.total_time_ms

    @property
    def duty_power_w(self):
        """Average power if the workload repeats every second (idle in between)."""
        return energy.duty_cycle_power(self.energy_total_mj, self.total_time_ms)

    @property
    def battery_hours(self):
        return energy.battery_life_hours(self.duty_power_w)

    def breakdown(self):
        return {"CPU": self.energy_cpu_mj, "Memory (page faults)": self.energy_mem_mj, "Disk (seeks)": self.energy_disk_mj}


def run(tasks: list[Task], scheduler="Round Robin", governor="schedutil", quantum=4,
        replacement="LRU", frames_per_process=3, disk_algorithm="SSTF", head=50) -> LabResult:
    procs = [cpu.Process(t.pid, t.arrival, t.burst, t.priority) for t in tasks]
    sim = cpu.simulate(procs, scheduler, governor, quantum)

    faults = sum(memory.simulate(t.refs, frames_per_process, replacement).faults for t in tasks)
    e_mem = faults * energy.E_PAGE_FAULT_MJ

    # disk requests are queued in the order the processes finish their CPU work
    order = sorted(sim.processes, key=lambda p: p.completion)
    by_pid = {t.pid: t for t in tasks}
    queue = [r for p in order for r in by_pid[p.pid].disk_requests]
    d = disk.schedule(queue, head, disk_algorithm)

    extra = faults * energy.T_PAGE_FAULT_MS + d["seek_time_ms"]
    # while waiting for page faults and seeks the CPU sits idle
    e_cpu = sim.energy_mj + extra * energy.P_IDLE
    return LabResult(sim, faults, e_cpu, e_mem, d["energy_mj"], d["total_seek"], extra)


def compare_policies(tasks, governors=None, schedulers=None, **kw):
    rows = []
    for s in schedulers or cpu.ALGORITHMS:
        for g in governors or list(energy.GOVERNORS):
            r = run(tasks, s, g, **kw)
            rows.append({"Scheduler": s, "Governor": g,
                         "Avg waiting (ms)": round(r.cpu.avg_waiting, 2),
                         "Total time (ms)": round(r.total_time_ms, 1),
                         "Energy (mJ)": round(r.energy_total_mj, 1),
                         "Avg power (W)": round(r.duty_power_w, 3),
                         "Battery life (h)": round(r.battery_hours, 2)})
    return rows
