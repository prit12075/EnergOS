"""Process synchronization with REAL threads.

* race_condition()     – shows lost updates when threads share a counter without a lock
* producer_consumer()  – the bounded-buffer problem solved with two counting semaphores
                         (empty, full) and a mutex
* dining_philosophers() – the naive solution deadlocks; ordering the forks prevents it
"""
from __future__ import annotations

import threading
import time
from collections import deque


# ======================================================================
#  1. Race condition
# ======================================================================
def race_condition(n_threads: int = 4, increments: int = 2000, use_lock: bool = False) -> dict:
    """Each thread adds 1 to a shared counter `increments` times.

    counter += 1 is really three steps:  read -> add -> write.  We make that visible
    (and give the scheduler a chance to switch threads in the middle with sleep(0)),
    so without a lock two threads can read the same value and one update is lost.
    """
    state = {"counter": 0}
    lock = threading.Lock()

    def worker():
        for _ in range(increments):
            if use_lock:
                with lock:                      # critical section protected
                    value = state["counter"]
                    time.sleep(0)
                    state["counter"] = value + 1
            else:
                value = state["counter"]        # read
                time.sleep(0)                   # thread switch may happen here
                state["counter"] = value + 1    # write (may overwrite someone else's update)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    start = time.perf_counter()
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    expected = n_threads * increments
    return {"expected": expected, "actual": state["counter"], "lost_updates": expected - state["counter"],
            "use_lock": use_lock, "seconds": round(time.perf_counter() - start, 3)}


# ======================================================================
#  2. Producer–consumer (bounded buffer)
# ======================================================================
def producer_consumer(buffer_size: int = 5, producers: int = 2, consumers: int = 2,
                      items_per_producer: int = 10, produce_delay: float = 0.004,
                      consume_delay: float = 0.007) -> dict:
    """Classic solution:
        empty = Semaphore(N)   counts free slots      producer: wait(empty) ... signal(full)
        full  = Semaphore(0)   counts filled slots    consumer: wait(full)  ... signal(empty)
        mutex = Lock()         protects the buffer itself
    Returns an event log, buffer occupancy over time and correctness checks.
    """
    empty = threading.Semaphore(buffer_size)
    full = threading.Semaphore(0)
    mutex = threading.Lock()
    buffer: deque = deque()
    log: list[dict] = []
    consumed: list = []
    max_seen = [0]
    t0 = time.perf_counter()
    total = producers * items_per_producer
    per_consumer = [total // consumers + (1 if k < total % consumers else 0) for k in range(consumers)]

    def stamp():
        return round((time.perf_counter() - t0) * 1000, 2)

    def producer(pid):
        for k in range(items_per_producer):
            time.sleep(produce_delay)                       # "make" the item
            item = f"P{pid}-{k}"
            empty.acquire()                                 # wait(empty): block if buffer is full
            with mutex:                                     # enter critical section
                buffer.append(item)
                max_seen[0] = max(max_seen[0], len(buffer))
                log.append({"t_ms": stamp(), "thread": f"Producer {pid}", "action": "put", "item": item, "buffer": len(buffer)})
            full.release()                                  # signal(full)

    def consumer(cid, count):
        for _ in range(count):
            full.acquire()                                  # wait(full): block if buffer is empty
            with mutex:
                item = buffer.popleft()
                consumed.append(item)
                log.append({"t_ms": stamp(), "thread": f"Consumer {cid}", "action": "take", "item": item, "buffer": len(buffer)})
            empty.release()                                 # signal(empty)
            time.sleep(consume_delay)                       # "use" the item

    threads = [threading.Thread(target=producer, args=(i + 1,)) for i in range(producers)]
    threads += [threading.Thread(target=consumer, args=(i + 1, per_consumer[i])) for i in range(consumers)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=30)

    produced = {f"P{p + 1}-{k}" for p in range(producers) for k in range(items_per_producer)}
    return {"log": log, "buffer_size": buffer_size, "max_occupancy": max_seen[0],
            "all_consumed_once": sorted(consumed) == sorted(produced),
            "never_overflowed": max_seen[0] <= buffer_size,
            "items": total}


# ======================================================================
#  3. Dining philosophers – deadlock and its prevention
# ======================================================================
def dining_philosophers(n: int = 5, strategy: str = "naive", meals: int = 3, timeout: float = 1.0) -> dict:
    """strategy="naive":   everyone picks up the LEFT fork, then the RIGHT one.
                           A barrier makes all philosophers hold their left fork first,
                           so a circular wait – a deadlock – is guaranteed.
       strategy="ordered": always pick up the LOWER-numbered fork first. This breaks the
                           circular-wait condition, so deadlock is impossible."""
    forks = [threading.Lock() for _ in range(n)]
    eaten = [0] * n
    stuck = []
    barrier = threading.Barrier(n) if strategy == "naive" else None
    give_up = threading.Barrier(n) if strategy == "naive" else None   # stuck philosophers let go together
    log = []
    t0 = time.perf_counter()

    def note(i, msg):
        log.append({"t_ms": round((time.perf_counter() - t0) * 1000, 1), "philosopher": i, "event": msg})

    def philosopher(i):
        left, right = i, (i + 1) % n
        first, second = (left, right) if strategy == "naive" else (min(left, right), max(left, right))
        for meal in range(meals):
            forks[first].acquire()
            note(i, f"picked fork {first}")
            if barrier is not None and meal == 0:
                try:
                    barrier.wait(timeout=timeout)
                except threading.BrokenBarrierError:
                    pass
            if not forks[second].acquire(timeout=timeout):  # would wait forever: deadlock
                note(i, f"waiting for fork {second} — DEADLOCK")
                stuck.append(i)
                if give_up is not None:          # keep holding until everyone has noticed the deadlock
                    try:
                        give_up.wait(timeout=timeout * 2)
                    except threading.BrokenBarrierError:
                        pass
                forks[first].release()
                return
            note(i, f"picked fork {second}, eating")
            eaten[i] += 1
            time.sleep(0.002)
            forks[second].release()
            forks[first].release()
            note(i, "released forks, thinking")

    threads = [threading.Thread(target=philosopher, args=(i,)) for i in range(n)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return {"strategy": strategy, "deadlocked": len(stuck) > 0, "stuck": sorted(stuck),
            "meals_eaten": eaten, "log": log}
