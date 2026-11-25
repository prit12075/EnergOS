"""Deadlock avoidance (Banker's algorithm) and deadlock detection.

Banker's algorithm keeps the system in a *safe state*: a state in which there is
at least one order (safe sequence) in which every process can get its maximum
need, finish and release its resources.  A request is granted only if the state
after granting it is still safe.
"""
from __future__ import annotations


def _leq(a, b):
    return all(x <= y for x, y in zip(a, b))


def need_matrix(maximum, allocation):
    return [[m - a for m, a in zip(mr, ar)] for mr, ar in zip(maximum, allocation)]


def safety(available, maximum, allocation, names=None):
    """Banker's safety algorithm.

    Returns {"safe": bool, "sequence": [...], "steps": [...]} where each step records
    which process was checked, its Need, the Work vector and whether it could finish.
    """
    n = len(allocation)
    names = names or [f"P{i}" for i in range(n)]
    need = need_matrix(maximum, allocation)
    work = list(available)
    finish = [False] * n
    sequence, steps = [], []

    i, idle_checks = 0, 0
    while idle_checks < n and not all(finish):          # scan round-robin until no progress in a full pass
        if not finish[i]:
            can = _leq(need[i], work)
            steps.append({"process": names[i], "need": need[i], "work_before": list(work), "can_finish": can})
            if can:
                work = [w + a for w, a in zip(work, allocation[i])]   # it finishes and releases its resources
                finish[i] = True
                sequence.append(names[i])
                steps[-1]["work_after"] = list(work)
                idle_checks = 0
            else:
                idle_checks += 1
        else:
            idle_checks += 1
        i = (i + 1) % n
    return {"safe": all(finish), "sequence": sequence, "steps": steps, "need": need,
            "unfinished": [names[k] for k in range(n) if not finish[k]]}


def request(pid: int, req, available, maximum, allocation, names=None):
    """Resource-request algorithm: can process `pid` be granted `req` right now?"""
    names = names or [f"P{i}" for i in range(len(allocation))]
    need = need_matrix(maximum, allocation)
    if not _leq(req, need[pid]):
        return {"granted": False, "reason": f"{names[pid]} asked for more than its declared maximum need"}
    if not _leq(req, available):
        return {"granted": False, "reason": f"Not enough resources available — {names[pid]} must wait"}
    # pretend to allocate, then test safety
    new_avail = [a - r for a, r in zip(available, req)]
    new_alloc = [row[:] for row in allocation]
    new_alloc[pid] = [a + r for a, r in zip(new_alloc[pid], req)]
    res = safety(new_avail, maximum, new_alloc, names)
    if res["safe"]:
        return {"granted": True, "reason": "State stays safe", "sequence": res["sequence"],
                "available": new_avail, "allocation": new_alloc}
    return {"granted": False, "reason": "Granting would lead to an UNSAFE state — request postponed",
            "unfinished": res["unfinished"]}


def detect(available, allocation, requests, names=None):
    """Deadlock-detection algorithm (several instances per resource type).
    Like the safety algorithm but uses current Requests instead of maximum Need."""
    n = len(allocation)
    names = names or [f"P{i}" for i in range(n)]
    work = list(available)
    finish = [all(a == 0 for a in allocation[i]) for i in range(n)]
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and _leq(requests[i], work):
                work = [w + a for w, a in zip(work, allocation[i])]
                finish[i] = True
                progress = True
    return [names[i] for i in range(n) if not finish[i]]


def wait_for_cycle(edges: dict[str, list[str]]):
    """Single-instance resources: find a cycle in the wait-for graph using DFS.
    edges = {"P1": ["P2"], ...} meaning P1 waits for P2. Returns the cycle as a list, or []."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {v: WHITE for v in set(edges) | {w for ws in edges.values() for w in ws}}
    stack = []

    def dfs(v):
        colour[v] = GREY
        stack.append(v)
        for w in edges.get(v, []):
            if colour[w] == GREY:                       # back edge -> cycle
                return stack[stack.index(w):] + [w]
            if colour[w] == WHITE:
                c = dfs(w)
                if c:
                    return c
        stack.pop()
        colour[v] = BLACK
        return []

    for v in sorted(colour):
        if colour[v] == WHITE:
            c = dfs(v)
            if c:
                return c
    return []


def wait_for_dot(edges: dict[str, list[str]], cycle: list[str] | None = None) -> str:
    """Graphviz DOT text for the wait-for graph, with the cycle highlighted in red."""
    cyc = set(zip(cycle, cycle[1:])) if cycle else set()
    lines = ["digraph G {", "rankdir=LR;", 'node [shape=circle, style=filled, fillcolor="#E8F5E9", fontname="Helvetica"];']
    for v, ws in edges.items():
        for w in ws:
            red = (v, w) in cyc
            lines.append(f'"{v}" -> "{w}" [color="{"#C62828" if red else "#555555"}", penwidth={3 if red else 1.2}];')
    for v in {x for e in cyc for x in e}:
        lines.append(f'"{v}" [fillcolor="#FFCDD2"];')
    lines.append("}")
    return "\n".join(lines)
