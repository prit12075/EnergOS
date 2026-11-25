"""Every algorithm is checked against worked examples from Silberschatz, Galvin & Gagne,
*Operating System Concepts* (10th ed.), and standard textbook exercises.
Run with:  python -m pytest -q
"""
from energos import cpu, deadlock, disk, energy, memory, sync, battery_lab


# ---------------------------------------------------------------- CPU scheduling
def P(pid, arr, burst, prio=0):
    return cpu.Process(pid, arr, burst, prio)

BOOK = [P("P1", 0, 24), P("P2", 0, 3), P("P3", 0, 3)]


def test_fcfs_average_waiting_is_17():
    assert cpu.simulate(BOOK, "FCFS").avg_waiting == 17


def test_sjf_example_average_waiting_is_7():
    ps = [P("P1", 0, 6), P("P2", 0, 8), P("P3", 0, 7), P("P4", 0, 3)]
    assert cpu.simulate(ps, "SJF").avg_waiting == 7


def test_srtf_example_average_waiting_is_6_5():
    ps = [P("P1", 0, 8), P("P2", 1, 4), P("P3", 2, 9), P("P4", 3, 5)]
    assert cpu.simulate(ps, "SRTF").avg_waiting == 6.5


def test_priority_example_average_waiting_is_8_2():
    ps = [P("P1", 0, 10, 3), P("P2", 0, 1, 1), P("P3", 0, 2, 4), P("P4", 0, 1, 5), P("P5", 0, 5, 2)]
    assert cpu.simulate(ps, "Priority").avg_waiting == 8.2


def test_round_robin_q4_average_waiting_is_5_66():
    r = cpu.simulate(BOOK, "Round Robin", quantum=4)
    assert round(r.avg_waiting, 2) == 5.67
    assert [(s.pid, s.start, s.end) for s in r.segments] == [("P1", 0, 4), ("P2", 4, 7), ("P3", 7, 10), ("P1", 10, 30)]


def test_mlfq_finishes_everything_and_short_jobs_first():
    ps = [P("Long", 0, 30), P("Short", 2, 3)]
    r = cpu.simulate(ps, "MLFQ")
    done = {p.pid: p.completion for p in r.processes}
    assert done["Short"] < done["Long"] and r.makespan == 33


def test_powersave_uses_less_energy_but_takes_longer():
    fast = cpu.simulate(BOOK, "FCFS", "performance")
    slow = cpu.simulate(BOOK, "FCFS", "powersave")
    assert slow.energy_mj < fast.energy_mj
    assert slow.makespan > fast.makespan


def test_energy_accounting_matches_power_model():
    r = cpu.simulate([P("A", 0, 10)], "FCFS", "performance")
    assert abs(r.energy_mj - 10 * energy.busy_power(energy.F_MAX)) < 1e-9


# ---------------------------------------------------------------- page replacement
REFS = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]


def test_fifo_15_faults():
    assert memory.simulate(REFS, 3, "FIFO").faults == 15


def test_lru_12_faults():
    assert memory.simulate(REFS, 3, "LRU").faults == 12


def test_optimal_9_faults():
    assert memory.simulate(REFS, 3, "Optimal").faults == 9


def test_clock_is_between_optimal_and_fifo():
    c = memory.simulate(REFS, 3, "Clock").faults
    assert 9 <= c <= 15


def test_beladys_anomaly():
    refs = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    assert memory.simulate(refs, 3, "FIFO").faults == 9
    assert memory.simulate(refs, 4, "FIFO").faults == 10        # more frames, MORE faults


def test_address_translation():
    r = memory.translate(5000, 1024, {4: 7})
    assert (r["page"], r["offset"], r["frame"], r["physical"]) == (4, 904, 7, 7 * 1024 + 904)
    assert memory.translate(100, 1024, {})["fault"]


# ---------------------------------------------------------------- disk scheduling
Q, HEAD = [98, 183, 37, 122, 14, 124, 65, 67], 53


def test_disk_fcfs_640():
    assert disk.schedule(Q, HEAD, "FCFS")["total_seek"] == 640


def test_disk_sstf_236():
    assert disk.schedule(Q, HEAD, "SSTF")["total_seek"] == 236


def test_disk_scan_towards_0_is_236():
    assert disk.schedule(Q, HEAD, "SCAN", "down")["total_seek"] == 236


def test_disk_cscan_up_is_382():
    assert disk.schedule(Q, HEAD, "C-SCAN", "up")["total_seek"] == 382


def test_disk_look_and_clook():
    assert disk.schedule(Q, HEAD, "LOOK", "down")["total_seek"] == 208
    assert disk.schedule(Q, HEAD, "LOOK", "up")["total_seek"] == 299
    assert disk.schedule(Q, HEAD, "C-LOOK", "up")["total_seek"] == 322


# ---------------------------------------------------------------- deadlock
AV = [3, 3, 2]
MAX = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]
ALLOC = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]


def test_bankers_book_state_is_safe():
    r = deadlock.safety(AV, MAX, ALLOC)
    assert r["safe"] and r["sequence"][0] == "P1" and len(r["sequence"]) == 5
    assert r["need"][0] == [7, 4, 3]


def test_bankers_requests_from_the_book():
    assert deadlock.request(1, [1, 0, 2], AV, MAX, ALLOC)["granted"]          # P1 (1,0,2): granted
    after = deadlock.request(1, [1, 0, 2], AV, MAX, ALLOC)
    assert not deadlock.request(4, [3, 3, 0], after["available"], MAX, after["allocation"])["granted"]   # not available
    assert not deadlock.request(0, [0, 2, 0], after["available"], MAX, after["allocation"])["granted"]   # unsafe


def test_detection_algorithm():
    alloc = [[0, 1, 0], [2, 0, 0], [3, 0, 3], [2, 1, 1], [0, 0, 2]]
    req_ok = [[0, 0, 0], [2, 0, 2], [0, 0, 0], [1, 0, 0], [0, 0, 2]]
    assert deadlock.detect([0, 0, 0], alloc, req_ok) == []
    req_bad = [[0, 0, 0], [2, 0, 2], [0, 0, 1], [1, 0, 0], [0, 0, 2]]
    assert deadlock.detect([0, 0, 0], alloc, req_bad) == ["P1", "P2", "P3", "P4"]


def test_wait_for_cycle():
    assert deadlock.wait_for_cycle({"P1": ["P2"], "P2": ["P3"], "P3": ["P1"]}) == ["P1", "P2", "P3", "P1"]
    assert deadlock.wait_for_cycle({"P1": ["P2"], "P2": ["P3"]}) == []


# ---------------------------------------------------------------- synchronization (real threads)
def test_lock_prevents_lost_updates():
    r = sync.race_condition(4, 500, use_lock=True)
    assert r["actual"] == r["expected"]


def test_producer_consumer_is_correct():
    r = sync.producer_consumer(buffer_size=3, producers=2, consumers=3, items_per_producer=8,
                               produce_delay=0.001, consume_delay=0.002)
    assert r["all_consumed_once"] and r["never_overflowed"]


def test_naive_philosophers_deadlock_and_ordered_do_not():
    naive = sync.dining_philosophers(5, "naive", meals=2, timeout=0.5)
    assert naive["deadlocked"] and naive["stuck"] == [0, 1, 2, 3, 4]
    ok = sync.dining_philosophers(5, "ordered", meals=3, timeout=2)
    assert not ok["deadlocked"] and ok["meals_eaten"] == [3] * 5


# ---------------------------------------------------------------- battery lab
def test_battery_lab_breakdown_adds_up():
    tasks = battery_lab.generate_workload(6, seed=3)
    r = battery_lab.run(tasks)
    assert abs(sum(r.breakdown().values()) - r.energy_total_mj) < 1e-6
    assert r.battery_hours > 0


def test_latency_budget_trades_speed_for_energy():
    ps = [cpu.Process(t.pid, t.arrival, t.burst, t.priority) for t in battery_lab.generate_workload(8, 7)]
    sweep = cpu.budget_sweep(ps, "Round Robin")
    energies = [r["Energy (mJ)"] for r in sweep]
    waits = [r["Avg waiting (ms)"] for r in sweep]
    assert energies == sorted(energies, reverse=True)      # bigger budget -> less energy
    assert waits == sorted(waits)                          # ...but longer waiting
