"""EnergOS dashboard.  Run with:   streamlit run app.py"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from energos import battery_lab, cpu, deadlock, disk, energy, history, memory, sync

st.set_page_config(page_title="EnergOS – Energy-aware OS Simulator", page_icon="🔋", layout="wide")

GREEN, AMBER, RED, TEAL, INDIGO = "#2E7D32", "#F9A825", "#C62828", "#00838F", "#3949AB"
PALETTE = [GREEN, TEAL, INDIGO, AMBER, RED, "#6D4C41", "#8E24AA", "#5E7D32", "#00695C", "#283593"]
FREQ_COLOURS = {0.8: "#A5D6A7", 1.2: "#66BB6A", 1.6: "#2E7D32", 2.0: "#1B5E20"}

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 1rem;}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
[data-testid='stToolbar'], [data-testid='stDecoration'] {display:none;}
.owner {display:inline-block;background:#E8F5E9;color:#1B5E20;border-radius:12px;padding:2px 10px;font-size:.8rem;font-weight:600;margin-bottom:.4rem}
</style>""", unsafe_allow_html=True)

PAGES = {
    "home": "🏠 Overview",
    "cpu": "⚙️ CPU scheduling + DVFS",
    "memory": "🧠 Memory: paging",
    "disk": "💽 Disk scheduling",
    "sync": "🔒 Synchronization",
    "deadlock": "⛔ Deadlocks",
    "lab": "🔋 Battery lab",
    "history": "📈 History",
}
keys = list(PAGES)
start = st.query_params.get("page", "home")
st.sidebar.title("🔋 EnergOS")
st.sidebar.caption("Energy-aware Operating System simulator")
page = st.sidebar.radio("Module", keys, index=keys.index(start) if start in keys else 0, format_func=PAGES.get)
st.sidebar.divider()
st.sidebar.markdown("**Power model**")
st.sidebar.latex(r"P(f)=P_{static}+K f^3")
st.sidebar.caption(f"P_static = {energy.P_STATIC} W · K = {energy.K_DYN} W/GHz³ · idle = {energy.P_IDLE} W · "
                   f"levels {energy.FREQS} GHz · battery {energy.BATTERY_MWH/1000:.0f} Wh")


def owner(name):
    st.markdown(f"<span class='owner'>Module owner: {name}</span>", unsafe_allow_html=True)


def gantt(result: cpu.SimResult, height=300):
    rows = []
    for s in result.segments:
        rows.append({"Lane": "CPU", "Start": s.start, "Finish": s.end,
                     "What": "idle" if s.pid is None else s.pid, "Freq": s.freq})
    df = pd.DataFrame(rows)
    pids = [p.pid for p in result.processes]
    cmap = {pid: PALETTE[i % len(PALETTE)] for i, pid in enumerate(pids)}
    cmap.update({"idle": "#E0E0E0", "CS": "#9E9E9E"})
    fig = go.Figure()
    for what, g in df.groupby("What", sort=False):
        fig.add_bar(x=g["Finish"] - g["Start"], base=g["Start"], y=["Process"] * len(g), orientation="h",
                    name=what, marker_color=cmap.get(what, "#999"), text=[what if (b - a) >= 2 else "" for a, b in zip(g["Start"], g["Finish"])],
                    textposition="inside", insidetextanchor="middle", hovertemplate="%{text} %{base}–%{x}")
    fig.add_bar(x=df["Finish"] - df["Start"], base=df["Start"], y=["Frequency"] * len(df), orientation="h",
                marker_color=[FREQ_COLOURS.get(f, "#F5F5F5") for f in df["Freq"]], showlegend=False,
                text=[f"{f:.1f}" if (b - a) >= 3 and f else "" for f, a, b in zip(df["Freq"], df["Start"], df["Finish"])],
                textposition="inside", hovertemplate="%{text} GHz")
    fig.update_layout(barmode="overlay", height=height, margin=dict(l=10, r=10, t=10, b=30),
                      xaxis_title="time (ms)", legend=dict(orientation="h", y=-0.35), yaxis=dict(autorange="reversed"),
                      plot_bgcolor="white")
    fig.update_xaxes(showgrid=True, gridcolor="#EEE")
    return fig


# ======================================================================
if page == "home":
    st.title("EnergOS — an energy-aware Operating System simulator")
    st.markdown("Every core OS algorithm from our course, implemented in readable Python, checked against "
                "the textbook examples, and extended with one question the textbook doesn't ask: **what does each "
                "decision cost in battery?**")
    c = st.columns(4)
    c[0].metric("Algorithms implemented", "29")
    c[1].metric("DVFS governors", "5")
    c[2].metric("Automated textbook checks", "28 / 28 pass")
    c[3].metric("Lines of engine code", "≈ 1,300")
    st.subheader("Modules")
    m = st.columns(3)
    m[0].markdown("#### ⚙️ CPU + battery\n**Aarth Goyal**\n\nFCFS · SJF · SRTF · Priority · Round Robin · MLFQ\n\n"
                  "DVFS governors: performance · powersave · ondemand · schedutil · **latency-budget (ours)**")
    m[1].markdown("#### 🧠 Memory + 💽 Disk\n**Prit Patel**\n\nPaging & address translation · FIFO · LRU · Optimal · Clock · "
                  "Belady's anomaly\n\nFCFS · SSTF · SCAN · C-SCAN · LOOK · C-LOOK")
    m[2].markdown("#### 🔒 Sync + ⛔ Deadlock + 🔋 Lab\n**Krishna Karthikeya Burra**\n\nRace condition · producer–consumer "
                  "(semaphores) · dining philosophers\n\nBanker's algorithm · deadlock detection · battery lab · SQLite history")
    st.subheader("Energy model in one line")
    st.markdown("A busy core at frequency *f* draws **P = 0.25 + 0.2·f³ W**; an idle core draws 0.05 W. "
                "Each page fault costs 2 mJ and each cylinder of disk-head movement 0.02 mJ. "
                "Battery life assumes the workload repeats every second on a 15 Wh battery.")

# ======================================================================
elif page == "cpu":
    st.title("CPU scheduling with DVFS")
    owner("Aarth Goyal")
    left, right = st.columns([1, 2])
    with left:
        preset = st.selectbox("Workload", ["Textbook (Silberschatz 5.3.4)", "Mixed (random, seed 7)", "Custom"], index=1)
        if preset.startswith("Textbook"):
            data = [("P1", 0, 10, 3), ("P2", 0, 1, 1), ("P3", 0, 2, 4), ("P4", 0, 1, 5), ("P5", 0, 5, 2)]
        else:
            data = [(t.pid, t.arrival, t.burst, t.priority) for t in battery_lab.generate_workload(6, 7)]
        df_in = pd.DataFrame(data, columns=["PID", "Arrival", "Burst", "Priority"])
        df_in = st.data_editor(df_in, num_rows="dynamic", width="stretch", key="cpu_in_" + preset)
        algo = st.selectbox("Scheduling algorithm", cpu.ALGORITHMS, index=5)
        gov = st.selectbox("DVFS governor", list(energy.GOVERNORS), index=4)
        q = st.slider("Time quantum (RR)", 1, 10, 4)
        budget = st.slider("Latency budget L (ms) — for latency-budget governor", 5, 160, 40, 5)
        cs = st.slider("Context-switch cost (ms)", 0, 3, 0)
    procs = [cpu.Process(str(r.PID), int(r.Arrival), float(r.Burst), int(r.Priority)) for r in df_in.itertuples() if r.PID]
    res = cpu.simulate(procs, algo, gov, q, cs, budget)
    with right:
        k = st.columns(5)
        k[0].metric("Avg waiting", f"{res.avg_waiting:.2f} ms")
        k[1].metric("Avg turnaround", f"{res.avg_turnaround:.2f} ms")
        k[2].metric("Avg response", f"{res.avg_response:.2f} ms")
        k[3].metric("Energy", f"{res.energy_mj:.1f} mJ")
        k[4].metric("Battery life*", f"{res.battery_hours:.1f} h")
        st.caption("*CPU only, if this workload repeats once every second and the CPU idles in between (15 Wh battery).")
        st.markdown(f"**Gantt chart** — {res.algorithm}, governor *{res.governor}* (bottom lane = CPU frequency in GHz)")
        st.plotly_chart(gantt(res), width="stretch")
        st.dataframe(pd.DataFrame(res.table()), width="stretch", hide_index=True)

    st.subheader("Compare every algorithm × governor")
    comp = pd.DataFrame(cpu.compare(procs, quantum=q, context_switch=cs, budget_ms=budget))
    a, b = st.columns(2)
    fig = px.scatter(comp, x="Energy (mJ)", y="Avg waiting (ms)", color="Governor", hover_name="Algorithm",
                     color_discrete_sequence=[RED, GREEN, AMBER, TEAL, INDIGO], height=380,
                     title="Energy vs waiting (dot = algorithm) · bottom-left is best")
    fig.update_traces(marker=dict(size=12, line=dict(width=1, color="white")))
    a.plotly_chart(fig, width="stretch")
    pv = comp.pivot(index="Algorithm", columns="Governor", values="Battery life (h)")
    fig2 = px.imshow(pv, text_auto=".1f", color_continuous_scale="Greens", aspect="auto", height=380,
                     title="Battery life (h) if the workload repeats every second")
    b.plotly_chart(fig2, width="stretch")
    st.subheader("Our latency-budget governor: one knob for the energy ↔ speed trade-off")
    sw = pd.DataFrame(cpu.budget_sweep(procs, algo, quantum=q))
    others = comp[(comp["Algorithm"] == algo) & (comp["Governor"] != "latency-budget")]
    fig3 = px.line(sw, x="Energy (mJ)", y="Avg waiting (ms)", text="Budget (ms)", markers=True, height=360,
                   title=f"{algo}: latency-budget for L = 5 … 160 ms (labels) vs the standard governors")
    fig3.update_traces(line_color=INDIGO, textposition="top right")
    fig3.add_scatter(x=others["Energy (mJ)"], y=others["Avg waiting (ms)"], mode="markers+text", text=others["Governor"],
                     textposition="bottom center", marker=dict(size=12, color=AMBER), name="standard governors")
    st.plotly_chart(fig3, width="stretch")

# ======================================================================
elif page == "memory":
    st.title("Memory management: paging and page replacement")
    owner("Prit Patel")
    tab1, tab2, tab3 = st.tabs(["Page replacement", "Belady's anomaly", "Address translation"])
    with tab1:
        c1, c2, c3 = st.columns([3, 1, 1])
        refs_txt = c1.text_input("Reference string", "7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1")
        n = c2.number_input("Frames", 1, 8, 3)
        algo = c3.selectbox("Algorithm", memory.ALGORITHMS, index=1)
        refs = [int(x) for x in refs_txt.replace(",", " ").split()]
        r = memory.simulate(refs, int(n), algo)
        k = st.columns(4)
        k[0].metric("Page faults", r.faults)
        k[1].metric("Hits", r.hits)
        k[2].metric("Hit ratio", f"{r.hit_ratio:.0%}")
        k[3].metric("Fault energy", f"{r.energy_mj:.0f} mJ")
        grid = {f"t{i+1}·{s.ref}": [("" if v is None else str(v)) for v in s.frames] + ["✓" if s.hit else "F"] for i, s in enumerate(r.steps)}
        df = pd.DataFrame(grid, index=[f"Frame {i}" for i in range(int(n))] + ["Hit / Fault"])
        st.dataframe(df.style.apply(lambda col: ["background-color:#FFCDD2" if col.iloc[-1] == "F" else "background-color:#E8F5E9"] * len(col), axis=0),
                     width="stretch")
        comp = pd.DataFrame(memory.compare(refs, int(n)))
        st.plotly_chart(px.bar(comp, x="Algorithm", y="Page faults", text="Page faults", color="Algorithm",
                               color_discrete_sequence=[RED, GREEN, INDIGO, TEAL], height=320,
                               title=f"Page faults with {int(n)} frames"), width="stretch")
    with tab2:
        refs_b = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
        st.markdown("Reference string `1 2 3 4 1 2 5 1 2 3 4 5` — giving FIFO **more** frames can cause **more** faults.")
        rows = [{"Frames": f, "Faults": x, "Algorithm": a} for a in ["FIFO", "LRU"] for f, x in memory.belady_curve(refs_b, 6, a)]
        st.plotly_chart(px.line(pd.DataFrame(rows), x="Frames", y="Faults", color="Algorithm", markers=True,
                                color_discrete_sequence=[RED, GREEN], height=380), width="stretch")
    with tab3:
        c1, c2 = st.columns(2)
        ps = c1.selectbox("Page size (bytes)", [512, 1024, 2048, 4096], index=1)
        la = c1.number_input("Logical address", 0, 1_000_000, 5000)
        pt_txt = c2.text_area("Page table (page:frame per line)", "0:5\n1:2\n2:9\n3:1\n4:7")
        table = {int(a): int(b) for a, b in (l.split(":") for l in pt_txt.split() if ":" in l)}
        t = memory.translate(int(la), int(ps), table)
        k = st.columns(4)
        k[0].metric("Page number", t["page"]); k[1].metric("Offset", t["offset"])
        k[2].metric("Frame", "fault" if t["fault"] else t["frame"]); k[3].metric("Physical address", "—" if t["fault"] else t["physical"])
        st.code(f"page = {la} // {ps} = {t['page']}\noffset = {la} % {ps} = {t['offset']}\n" +
                ("PAGE FAULT – page not in memory" if t["fault"] else f"physical = frame × size + offset = {t['frame']} × {ps} + {t['offset']} = {t['physical']}"))

# ======================================================================
elif page == "disk":
    st.title("Disk scheduling")
    owner("Prit Patel")
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    q_txt = c1.text_input("Request queue (cylinders)", "98 183 37 122 14 124 65 67")
    head = c2.number_input("Head at", 0, 199, 53)
    direction = c3.selectbox("Direction", ["down", "up"])
    algo = c4.selectbox("Algorithm", disk.ALGORITHMS, index=1)
    reqs = [int(x) for x in q_txt.replace(",", " ").split()]
    r = disk.schedule(reqs, int(head), algo, direction)
    k = st.columns(4)
    k[0].metric("Total seek", f"{r['total_seek']} cyl")
    k[1].metric("Average seek", f"{r['avg_seek']:.1f} cyl")
    k[2].metric("Seek time", f"{r['seek_time_ms']:.1f} ms")
    k[3].metric("Seek energy", f"{r['energy_mj']:.2f} mJ")
    a, b = st.columns([3, 2])
    fig = go.Figure(go.Scatter(x=r["path"], y=list(range(len(r["path"]))), mode="lines+markers+text",
                               text=[str(p) for p in r["path"]], textposition="middle right", line=dict(color=GREEN, width=3)))
    fig.update_layout(height=420, yaxis=dict(autorange="reversed", title="order of service"),
                      xaxis=dict(range=[-5, 205], title="cylinder"), title=f"{algo}: head movement", plot_bgcolor="white", margin=dict(t=40))
    a.plotly_chart(fig, width="stretch")
    comp = pd.DataFrame(disk.compare(reqs, int(head), direction))
    b.plotly_chart(px.bar(comp, x="Algorithm", y="Total seek (cylinders)", text="Total seek (cylinders)", color="Algorithm",
                          color_discrete_sequence=PALETTE, height=420, title="Total head movement"), width="stretch")

# ======================================================================
elif page == "sync":
    st.title("Process synchronization (real threads)")
    owner("Krishna Karthikeya Burra")
    t1, t2, t3 = st.tabs(["Race condition", "Producer–consumer", "Dining philosophers"])
    with t1:
        n_th = st.slider("Threads", 2, 8, 4)
        inc = st.slider("Increments per thread", 500, 5000, 2000, 500)
        a, b = st.columns(2)
        no = sync.race_condition(n_th, inc, False)
        yes = sync.race_condition(n_th, inc, True)
        a.metric("Without lock — final counter", no["actual"], f"{-no['lost_updates']} lost updates", delta_color="normal")
        b.metric("With lock — final counter", yes["actual"], "0 lost updates", delta_color="off")
        st.code("value = counter      # read\n# <-- another thread can run here\ncounter = value + 1  # write: may overwrite another thread's update")
    with t2:
        c = st.columns(4)
        size = c[0].slider("Buffer size", 1, 10, 4)
        npro = c[1].slider("Producers", 1, 4, 2)
        ncon = c[2].slider("Consumers", 1, 4, 2)
        items = c[3].slider("Items per producer", 5, 30, 12)
        r = sync.producer_consumer(size, npro, ncon, items)
        k = st.columns(3)
        k[0].metric("Items", r["items"])
        k[1].metric("Max buffer occupancy", f"{r['max_occupancy']} / {size}")
        k[2].metric("Every item consumed exactly once", "✅ yes" if r["all_consumed_once"] and r["never_overflowed"] else "❌ no")
        log = pd.DataFrame(r["log"])
        fig = px.line(log, x="t_ms", y="buffer", line_shape="hv", height=320, title="Items in the buffer over time")
        fig.add_hline(y=size, line_dash="dash", line_color=RED, annotation_text="capacity (empty = 0 → producers block)")
        fig.update_traces(line_color=GREEN)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(log.head(12), width="stretch", hide_index=True)
    with t3:
        a, b = st.columns(2)
        naive = sync.dining_philosophers(5, "naive", meals=2, timeout=0.6)
        ordered = sync.dining_philosophers(5, "ordered", meals=3, timeout=2)
        a.markdown("**Naive: left fork, then right fork**")
        a.metric("Result", "DEADLOCK" if naive["deadlocked"] else "OK", f"{len(naive['stuck'])} philosophers stuck", delta_color="inverse")
        a.dataframe(pd.DataFrame(naive["log"]).head(10), hide_index=True, width="stretch")
        b.markdown("**Ordered: lower-numbered fork first**")
        b.metric("Result", "DEADLOCK" if ordered["deadlocked"] else "No deadlock", f"meals eaten {sum(ordered['meals_eaten'])}", delta_color="normal")
        b.dataframe(pd.DataFrame(ordered["log"]).head(10), hide_index=True, width="stretch")

# ======================================================================
elif page == "deadlock":
    st.title("Deadlocks: avoidance and detection")
    owner("Krishna Karthikeya Burra")
    t1, t2 = st.tabs(["Banker's algorithm", "Wait-for graph"])
    with t1:
        c1, c2, c3 = st.columns(3)
        c1.markdown("**Allocation**")
        c2.markdown("**Max**")
        alloc = c1.data_editor(pd.DataFrame([[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], columns=list("ABC"),
                                            index=[f"P{i}" for i in range(5)]), key="alloc")
        mx = c2.data_editor(pd.DataFrame([[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], columns=list("ABC"),
                                         index=[f"P{i}" for i in range(5)]), key="max")
        avail = [int(x) for x in c3.text_input("**Available** (A B C)", "3 3 2").split()]
        res = deadlock.safety(avail, mx.values.tolist(), alloc.values.tolist())
        c3.dataframe(pd.DataFrame(res["need"], columns=list("ABC"), index=[f"P{i}" for i in range(5)]), width="stretch")
        c3.caption("Need = Max − Allocation")
        if res["safe"]:
            st.success("SAFE state — safe sequence: " + " → ".join(res["sequence"]))
        else:
            st.error("UNSAFE — cannot finish: " + ", ".join(res["unfinished"]))
        steps = pd.DataFrame([{"Check": s["process"], "Need": str(s["need"]), "Work before": str(s["work_before"]),
                               "Can finish?": "yes" if s["can_finish"] else "no", "Work after": str(s.get("work_after", ""))} for s in res["steps"]])
        st.dataframe(steps, width="stretch", hide_index=True)
        st.markdown("**Resource request**")
        r1, r2, r3 = st.columns([1, 2, 3])
        pid = r1.selectbox("Process", range(5), index=1, format_func=lambda i: f"P{i}")
        req = [int(x) for x in r2.text_input("Request (A B C)", "1 0 2").split()]
        out = deadlock.request(pid, req, avail, mx.values.tolist(), alloc.values.tolist())
        if out["granted"]:
            r3.success("GRANTED — " + out["reason"] + " (new safe sequence: " + " → ".join(out["sequence"]) + ")")
        else:
            r3.error("DENIED — " + out["reason"])
    with t2:
        edges_txt = st.text_area("Edges (Pi waits for Pj), one per line", "P1 P2\nP2 P3\nP3 P4\nP4 P2\nP5 P1")
        edges = {}
        for line in edges_txt.splitlines():
            parts = line.split()
            if len(parts) == 2:
                edges.setdefault(parts[0], []).append(parts[1])
        cyc = deadlock.wait_for_cycle(edges)
        if cyc:
            st.error("Deadlock: cycle " + " → ".join(cyc))
        else:
            st.success("No cycle — no deadlock")
        st.graphviz_chart(deadlock.wait_for_dot(edges, cyc), width="stretch")

# ======================================================================
elif page == "lab":
    st.title("Battery lab: where does the energy go?")
    owner("Krishna Karthikeya Burra")
    c = st.columns(6)
    n = c[0].slider("Processes", 3, 15, 8)
    seed = c[1].number_input("Seed", 1, 999, 7)
    mix = c[2].selectbox("Workload", ["mixed", "interactive", "batch"])
    sched = c[3].selectbox("Scheduler", cpu.ALGORITHMS, index=5)
    gov = c[4].selectbox("Governor", list(energy.GOVERNORS), index=4)
    rep = c[5].selectbox("Page replacement", memory.ALGORITHMS, index=1)
    c2 = st.columns(6)
    frames = c2[0].slider("Frames / process", 1, 8, 3)
    dalg = c2[1].selectbox("Disk algorithm", disk.ALGORITHMS, index=1)
    tasks = battery_lab.generate_workload(n, int(seed), mix)
    r = battery_lab.run(tasks, sched, gov, 4, rep, frames, dalg)
    k = st.columns(5)
    k[0].metric("Total energy", f"{r.energy_total_mj:.0f} mJ")
    k[1].metric("Page faults", r.page_faults)
    k[2].metric("Disk seek", f"{r.seek_total} cyl")
    k[3].metric("Avg power (1 s period)", f"{r.duty_power_w:.3f} W")
    k[4].metric("Battery life", f"{r.battery_hours:.1f} h")
    a, b = st.columns([1, 2])
    bd = r.breakdown()
    a.plotly_chart(px.pie(names=list(bd), values=list(bd.values()), hole=0.55, height=360, title="Energy breakdown",
                          color_discrete_sequence=[GREEN, AMBER, INDIGO]), width="stretch")
    comp = pd.DataFrame(battery_lab.compare_policies(tasks, replacement=rep, frames_per_process=frames, disk_algorithm=dalg))
    pv = comp.pivot(index="Scheduler", columns="Governor", values="Battery life (h)")
    b.plotly_chart(px.imshow(pv, text_auto=".1f", color_continuous_scale="Greens", aspect="auto", height=360,
                             title="Battery life (h) for every scheduler × governor"), width="stretch")
    fr = pd.DataFrame([{"Frames": f, **{a_: battery_lab.run(tasks, sched, gov, 4, a_, f, dalg).battery_hours for a_ in memory.ALGORITHMS}}
                       for f in range(1, 7)]).melt("Frames", var_name="Replacement", value_name="Battery life (h)")
    st.plotly_chart(px.line(fr, x="Frames", y="Battery life (h)", color="Replacement", markers=True, height=330,
                            color_discrete_sequence=[RED, GREEN, INDIGO, TEAL],
                            title="More frames → fewer page faults → longer battery life"), width="stretch")
    if st.button("💾 Save this run to history"):
        history.save(r, dict(scheduler=sched, governor=gov, replacement=rep, disk_algorithm=dalg, processes=n, seed=int(seed), workload=mix))
        st.success("Saved to energos_history.db")

# ======================================================================
elif page == "history":
    st.title("Run history (SQLite)")
    owner("Krishna Karthikeya Burra")
    runs = pd.DataFrame(history.all_runs())
    if runs.empty:
        st.info("No runs saved yet — use **Save this run** in the Battery lab.")
    else:
        k = st.columns(3)
        k[0].metric("Runs stored", len(runs))
        best = runs.loc[runs["battery_hours"].idxmax()]
        k[1].metric("Best battery life", f"{best['battery_hours']:.1f} h", f"{best['scheduler']} + {best['governor']}")
        k[2].metric("Lowest energy", f"{runs['energy_total'].min():.0f} mJ")
        runs_plot = runs.rename(columns={"energy_cpu": "CPU", "energy_mem": "Memory", "energy_disk": "Disk"})
        st.plotly_chart(px.bar(runs_plot, x="id", y=["CPU", "Memory", "Disk"], height=340,
                               labels={"value": "energy (mJ)", "id": "run", "variable": "part"},
                               color_discrete_sequence=[GREEN, AMBER, INDIGO], title="Energy of each saved run"), width="stretch")
        st.dataframe(runs.round(2), width="stretch", hide_index=True)
        if st.button("Clear history"):
            history.clear()
            st.rerun()
