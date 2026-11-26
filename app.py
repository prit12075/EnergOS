"""EnergOS dashboard.  Run with:   streamlit run app.py"""
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from energos import battery_lab, cpu, deadlock, disk, energy, history, memory, sync
import ui
from ui import AMBER, BRAND, INDIGO, PALETTE, RED, TEAL, chart, icon, kpis, page_header, section

HERE = Path(__file__).parent
st.set_page_config(page_title="EnergOS · Energy-aware OS Simulator", page_icon=str(HERE / "assets/icon.svg"),
                   layout="wide", initial_sidebar_state="expanded")
ui.inject_css()
st.logo(str(HERE / "assets/logo.svg"), size="large", icon_image=str(HERE / "assets/icon.svg"))


# ======================================================================
#  helpers
# ======================================================================
def seg_power(s):
    return energy.P_IDLE if s.pid is None else energy.busy_power(s.freq)


def gantt(result: cpu.SimResult, t_mark=None, height=260):
    pids = [p.pid for p in result.processes]
    cmap = {pid: PALETTE[i % len(PALETTE)] for i, pid in enumerate(pids)}
    cmap.update({None: "#E5E7EB", "CS": "#94A3B8"})
    fig = go.Figure()
    shown = set()
    for s in result.segments:
        name = "idle" if s.pid is None else s.pid
        fig.add_bar(x=[s.end - s.start], base=[s.start], y=["Process"], orientation="h", marker_color=cmap.get(s.pid, "#999"),
                    marker_line=dict(color="white", width=1.5), name=name, legendgroup=name, showlegend=name not in shown,
                    text=[name if s.end - s.start >= 2 and s.pid else ""], textposition="inside", insidetextanchor="middle",
                    textfont=dict(color="white", size=11),
                    hovertemplate=f"<b>{name}</b><br>{s.start}–{s.end} ms<br>{s.freq:.1f} GHz<extra></extra>")
        shown.add(name)
        fig.add_bar(x=[s.end - s.start], base=[s.start], y=["CPU speed"], orientation="h", showlegend=False,
                    marker_color=ui.FREQ_COLOURS.get(s.freq, "#F1F5F9"), marker_line=dict(color="white", width=1),
                    text=[f"{s.freq:.1f}" if s.end - s.start >= 3 and s.freq else ""], textposition="inside",
                    textfont=dict(color="white", size=10), hovertemplate=f"{s.freq:.1f} GHz<extra></extra>")
    if t_mark is not None:
        fig.add_vline(x=t_mark, line_width=2, line_color=ui.INK, line_dash="dot")
    fig.update_layout(barmode="overlay", height=height, bargap=0.25, xaxis_title="time (ms)",
                      legend=dict(orientation="h", y=-0.35, x=0), yaxis=dict(autorange="reversed"), margin=dict(t=10, b=10))
    return fig


def gauge(hours, ref=None, title="Battery life"):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta" if ref else "gauge+number", value=hours, number=dict(suffix=" h", font=dict(size=36)),
        delta=dict(reference=ref, relative=True, valueformat=".0%") if ref else None,
        title=dict(text=title, font=dict(size=13, color=ui.MUTED)),
        gauge=dict(axis=dict(range=[0, max(60, hours * 1.2)], tickwidth=0), bar=dict(color=BRAND, thickness=0.28),
                   bgcolor="#F1F5F3", borderwidth=0,
                   steps=[dict(range=[0, 20], color="#FEE2E2"), dict(range=[20, 35], color="#FEF3C7"),
                          dict(range=[35, max(60, hours * 1.2)], color="#D1FAE5")])))
    fig.update_layout(height=230, margin=dict(l=30, r=36, t=40, b=0))
    return fig


def sankey(r: battery_lab.LabResult):
    busy = r.cpu.energy_busy_mj
    idle = r.energy_cpu_mj - busy
    labels = ["Battery", "CPU", "Memory", "Disk", "CPU running", "CPU idle / waiting", "Page faults", "Head seeks"]
    src = [0, 0, 0, 1, 1, 2, 3]
    dst = [1, 2, 3, 4, 5, 6, 7]
    val = [r.energy_cpu_mj, r.energy_mem_mj, r.energy_disk_mj, busy, idle, r.energy_mem_mj, r.energy_disk_mj]
    cols = ["#065F46", BRAND, AMBER, INDIGO, "#34D399", "#A7F3D0", "#FCD34D", "#A5B4FC"]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[f"{l}  {v:.0f} mJ" if i else f"Battery  {r.energy_total_mj:.0f} mJ"
                         for i, (l, v) in enumerate(zip(labels, [0, r.energy_cpu_mj, r.energy_mem_mj, r.energy_disk_mj, busy, idle,
                                                                   r.energy_mem_mj, r.energy_disk_mj]))],
                  color=cols, pad=18, thickness=16, line=dict(width=0)),
        link=dict(source=src, target=dst, value=val, color="rgba(16,185,129,0.18)")))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), font=dict(size=12))
    return fig


# ======================================================================
#  pages
# ======================================================================
def page_overview():
    st.html(f"""<div class="hero"><div class="eyebrow">Operating Systems project · SRM University AP</div>
      <h1>Every OS decision has a battery cost. EnergOS measures it.</h1>
      <p>Classic CPU scheduling, paging, disk scheduling, synchronization and deadlock algorithms, written from scratch in Python,
      verified against the textbook and wired to one energy model, so you can see what each policy costs in millijoules and hours of battery.</p>
      <div class="pills"><span class="pill">29 algorithms</span><span class="pill">5 DVFS governors</span>
      <span class="pill">28 / 28 textbook checks</span><span class="pill">Real threads for sync demos</span></div></div>""")

    c1, c2 = st.columns([1, 2], gap="medium")
    with c1:
        mix = st.segmented_control("Workload", ["mixed", "interactive", "batch"], default="mixed", key="ov_mix") or "mixed"
        gov = st.selectbox("Governor", list(energy.GOVERNORS), index=4, key="ov_gov")
    tasks = battery_lab.generate_workload(8, 7, mix)
    r = battery_lab.run(tasks, "Round Robin", gov, 4, "LRU", 3, "SSTF")
    base = battery_lab.run(tasks, "Round Robin", "performance", 4, "LRU", 3, "SSTF")
    with c1:
        with st.container(border=True):
            chart(gauge(r.battery_hours, base.battery_hours, "Battery life vs. performance governor"))
    with c2:
        kpis([dict(label="Energy", value=f"{r.energy_total_mj:.0f}", unit="mJ", icon="bolt", tone="amber",
                   sub="one run of 8 processes"),
              dict(label="Waiting", value=f"{r.cpu.avg_waiting:.1f}", unit="ms", icon="clock", tone="indigo",
                   sub="avg, Round Robin q = 4"),
              dict(label="Faults", value=r.page_faults, icon="memory", tone="red", sub="LRU, 3 frames each"),
              dict(label="Power", value=f"{r.duty_power_w:.3f}", unit="W", icon="gauge", tone="teal",
                   sub="avg, workload every 1 s")])
        with st.container(border=True):
            section("Where the energy goes", "live run of the selected workload")
            chart(sankey(r), height=250)

    section("Modules", "pick one from the sidebar")
    mods = [("cpu", "indigo", "CPU scheduling + DVFS", "FCFS, SJF, SRTF, Priority, Round Robin, MLFQ with 5 frequency governors, including our latency-budget governor.", "Aarth Goyal"),
            ("memory", "green", "Memory: paging", "Address translation, FIFO, LRU, Optimal and Clock replacement, Belady's anomaly, step-by-step player.", "Prit Patel"),
            ("disk", "teal", "Disk scheduling", "FCFS, SSTF, SCAN, C-SCAN, LOOK and C-LOOK with an animated head and seek energy.", "Prit Patel"),
            ("lock", "amber", "Synchronization", "Race condition, producer–consumer with semaphores, dining philosophers, all on real threads.", "Krishna Karthikeya Burra"),
            ("alert", "red", "Deadlocks", "Banker's safety and request algorithms, detection and a wait-for graph with cycle highlighting.", "Krishna Karthikeya Burra"),
            ("battery", "green", "Battery lab + history", "Whole-workload energy breakdown, policy heat-map, and runs stored in SQLite.", "Krishna Karthikeya Burra")]
    st.html('<div class="mods">' + "".join(
        f'<div class="mod t-{t}"><span class="kpi-ic">{icon(i, 20, ui.TONES[t])}</span><h4>{n}</h4><p>{d}</p><div class="who">{w}</div></div>'
        for i, t, n, d, w in mods) + "</div>")


# ----------------------------------------------------------------------
def page_cpu():
    page_header("cpu", "Part A · Processes", "CPU scheduling with DVFS",
                "Who runs next, and how fast. Every millisecond is simulated and priced in energy.", "Aarth Goyal")
    kpi_slot = st.container()
    left, right = st.columns([1.25, 2.2], gap="medium")
    with left:
        with st.container(border=True):
            section("Workload")
            preset = st.selectbox("Preset", ["Textbook (Silberschatz 5.3.4)", "Mixed (random, seed 7)", "Custom"], index=1,
                                  label_visibility="collapsed")
            if preset.startswith("Textbook"):
                data = [("P1", 0, 10, 3), ("P2", 0, 1, 1), ("P3", 0, 2, 4), ("P4", 0, 1, 5), ("P5", 0, 5, 2)]
            else:
                data = [(t.pid, t.arrival, t.burst, t.priority) for t in battery_lab.generate_workload(6, 7)]
            df_in = st.data_editor(pd.DataFrame(data, columns=["PID", "Arrival", "Burst", "Priority"]), num_rows="dynamic",
                                   width="stretch", key="cpu_in_" + preset, hide_index=True,
                                   column_config={c: st.column_config.Column(width="small") for c in ["PID", "Arrival", "Burst", "Priority"]})
        with st.container(border=True):
            section("Policy")
            algo = st.selectbox("Scheduling algorithm", cpu.ALGORITHMS, index=5)
            gov = st.selectbox("DVFS governor", list(energy.GOVERNORS), index=4)
            q = st.slider("Time quantum (RR)", 1, 10, 4)
            budget = st.slider("Latency budget L (ms)", 5, 160, 40, 5, help="Only used by the latency-budget governor")
            cs = st.slider("Context-switch cost (ms)", 0, 3, 0)
    procs = [cpu.Process(str(r.PID), int(r.Arrival), float(r.Burst), int(r.Priority)) for r in df_in.itertuples() if r.PID]
    if not procs:
        st.warning("Add at least one process.")
        return
    res = cpu.simulate(procs, algo, gov, q, cs, budget)
    perf = cpu.simulate(procs, algo, "performance", q, cs, budget)
    saving = 1 - res.energy_mj / perf.energy_mj if perf.energy_mj else 0
    with kpi_slot:
        kpis([dict(label="Avg waiting", value=f"{res.avg_waiting:.2f}", unit="ms", icon="clock", tone="indigo"),
              dict(label="Turnaround", value=f"{res.avg_turnaround:.2f}", unit="ms", icon="route", tone="teal"),
              dict(label="Energy", value=f"{res.energy_mj:.1f}", unit="mJ", icon="bolt", tone="amber",
                   sub=(f'<span class="up">{saving:.0%} less</span> than full speed' if saving >= 0
                        else f'<span class="down">{-saving:.0%} more</span> than full speed')),
              dict(label="Battery life", value=f"{res.battery_hours:.1f}", unit="h", icon="battery", tone="green",
                   sub="repeats every 1 s"),
              dict(label="Switches", value=res.context_switches, icon="swap", tone="red")])
    with right:
        tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Per process", "Compare all policies", "Latency-budget sweep"])
        with tab1:
            with st.container(border=True):
                t = st.slider("Scrub through time (ms)", 0, max(res.makespan - 1, 1), min(10, res.makespan - 1), key="cpu_t")
                chart(gantt(res, t + 0.5))
                seg = next((s for s in res.segments if s.start <= t < s.end), None)
                spent = sum(seg_power(s) * max(0, min(s.end, t + 1) - s.start) for s in res.segments if s.start <= t)
                if seg:
                    who = "CPU idle" if seg.pid is None else f"<b>{seg.pid}</b> is running"
                    ui.banner("info", f"At t = {t} ms: {who} at <b>{seg.freq:.1f} GHz</b>, drawing <b>{seg_power(seg):.2f} W</b>. "
                                      f"Energy used so far: <b>{spent:.1f} mJ</b> of {res.energy_mj:.1f} mJ.", "clock")
        with tab2:
            tbl = pd.DataFrame(res.table())
            with st.container(border=True):
                fig = px.bar(tbl, x="PID", y=["Waiting", "Response"], barmode="group", color_discrete_sequence=[INDIGO, TEAL],
                             title="Waiting and response time per process (ms)")
                chart(fig, 300)
                st.dataframe(tbl, width="stretch", hide_index=True)
        with tab3:
            comp = pd.DataFrame(cpu.compare(procs, quantum=q, context_switch=cs, budget_ms=budget))
            a, b = st.columns(2)
            with a, st.container(border=True):
                fig = px.scatter(comp, x="Energy (mJ)", y="Avg waiting (ms)", color="Governor", symbol="Governor", hover_name="Algorithm",
                                 color_discrete_sequence=[RED, BRAND, AMBER, TEAL, INDIGO], title="Energy vs waiting · bottom-left is best")
                fig.update_traces(marker=dict(size=12, line=dict(width=1.5, color="white")))
                fig.update_layout(legend=dict(orientation="h", y=-0.25))
                chart(fig, 400)
            with b, st.container(border=True):
                pv = comp.pivot(index="Algorithm", columns="Governor", values="Battery life (h)")
                fig = px.imshow(pv, text_auto=".1f", color_continuous_scale=["#ECFDF5", "#34D399", "#065F46"], aspect="auto",
                                title="Battery life (h) for every algorithm × governor")
                fig.update_coloraxes(showscale=False)
                chart(fig, 400)
        with tab4:
            with st.container(border=True):
                sw = pd.DataFrame(cpu.budget_sweep(procs, algo, quantum=q))
                others = comp[(comp["Algorithm"] == algo) & (comp["Governor"] != "latency-budget")]
                fig = px.line(sw, x="Energy (mJ)", y="Avg waiting (ms)", text="Budget (ms)", markers=True,
                              title=f"{algo}: latency-budget with L = 5 … 160 ms (labels) vs the standard governors")
                fig.update_traces(line=dict(color=INDIGO, width=3), marker=dict(size=9), textposition="top right")
                fig.add_scatter(x=others["Energy (mJ)"], y=others["Avg waiting (ms)"], mode="markers+text", text=others["Governor"],
                                textposition="bottom center", marker=dict(size=13, color=AMBER, line=dict(width=1.5, color="white")),
                                name="standard governors")
                chart(fig, 400)
                st.caption("Small L = run fast, spend more energy. Large L = run slow, save energy, wait longer. One knob for the trade-off.")


# ----------------------------------------------------------------------
def page_memory():
    page_header("memory", "Part B · Memory", "Paging and page replacement",
                "Which page leaves memory when a new one arrives, and what every page fault costs.", "Prit Patel")
    tab1, tab2, tab3 = st.tabs(["Replacement player", "Belady's anomaly", "Address translation"])
    with tab1:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1.2])
            refs_txt = c1.text_input("Reference string", "7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1")
            n = int(c2.number_input("Frames", 1, 8, 3))
            algo = c3.selectbox("Algorithm", memory.ALGORITHMS, index=1)
        try:
            refs = [int(x) for x in refs_txt.replace(",", " ").split()]
        except ValueError:
            st.error("Use whole numbers separated by spaces.")
            return
        r = memory.simulate(refs, n, algo)
        kpis([dict(label="Page faults", value=r.faults, icon="alert", tone="red"),
              dict(label="Hits", value=r.hits, icon="check", tone="green"),
              dict(label="Hit ratio", value=f"{r.hit_ratio:.0%}", icon="gauge", tone="indigo"),
              dict(label="Fault energy", value=f"{r.energy_mj:.0f}", unit="mJ", icon="bolt", tone="amber",
                   sub=f"+{r.fault_time_ms:.0f} ms of waiting")])
        a, b = st.columns([1.5, 1], gap="medium")
        with a, st.container(border=True):
            section("Step through it", "drag the slider or use the arrow keys")
            k = st.slider("Step", 1, len(r.steps), min(8, len(r.steps)), label_visibility="collapsed")
            s = r.steps[k - 1]
            strip = "".join(f'<div class="ref {("h" if x.hit else "f") if i < k else ""} {"cur" if i == k - 1 else ""}">{x.ref}</div>'
                            for i, x in enumerate(r.steps))
            slot = s.frames.index(s.ref)
            tiles = "".join(f'<div class="frame {("hit" if s.hit else "new") if j == slot else ""}"><small>Frame {j}</small>'
                            f'<b>{"–" if v is None else v}</b></div>' for j, v in enumerate(s.frames))
            what = (f'{ui.chip("HIT", "g")} page {s.ref} is already in frame {slot}' if s.hit else
                    f'{ui.chip("PAGE FAULT", "r")} page {s.ref} loaded into frame {slot}' +
                    (f', page <b>{s.victim}</b> evicted' if s.victim is not None else ", free frame used"))
            st.html(f'<div class="refstrip">{strip}</div><div class="frames">{tiles}</div>'
                    f'<div style="margin-top:.4rem;color:#334155">Step {k} of {len(r.steps)}: {what}</div>')
        with b, st.container(border=True):
            comp = pd.DataFrame(memory.compare(refs, n))
            fig = px.bar(comp, x="Algorithm", y="Page faults", text="Page faults", color="Algorithm",
                         color_discrete_sequence=[RED, BRAND, INDIGO, TEAL], title=f"Faults with {n} frames")
            fig.update_layout(showlegend=False)
            fig.update_traces(textposition="outside", marker_line_width=0)
            chart(fig, 330)
        with st.expander("Full frame table"):
            grid = {f"{i + 1}·{s.ref}": [("" if v is None else str(v)) for v in s.frames] + ["✓" if s.hit else "F"]
                    for i, s in enumerate(r.steps)}
            df = pd.DataFrame(grid, index=[f"Frame {i}" for i in range(n)] + ["Hit / Fault"])
            st.dataframe(df.style.apply(lambda col: ["background-color:#FEE2E2" if col.iloc[-1] == "F" else "background-color:#ECFDF5"]
                                        * len(col), axis=0), width="stretch")
    with tab2:
        with st.container(border=True):
            refs_b = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
            st.markdown("Reference string `1 2 3 4 1 2 5 1 2 3 4 5`. With FIFO, giving the process **more** frames causes **more** faults.")
            rows = [{"Frames": f, "Faults": x, "Algorithm": a} for a in ["FIFO", "LRU"] for f, x in memory.belady_curve(refs_b, 6, a)]
            fig = px.line(pd.DataFrame(rows), x="Frames", y="Faults", color="Algorithm", markers=True, color_discrete_sequence=[RED, BRAND])
            fig.update_traces(line=dict(width=3), marker=dict(size=10))
            fig.add_annotation(x=4, y=10, text="4 frames → 10 faults<br>(3 frames gave only 9)", showarrow=True, arrowhead=2, ax=70, ay=-40)
            chart(fig, 380)
    with tab3:
        with st.container(border=True):
            c1, c2 = st.columns([1, 1])
            ps = c1.select_slider("Page size (bytes)", [512, 1024, 2048, 4096], value=1024)
            la = int(c1.number_input("Logical address", 0, 1_000_000, 5000, step=100))
            pt_txt = c2.text_area("Page table (page:frame, one per line)", "0:5\n1:2\n2:9\n3:1\n4:7", height=140)
            table = {int(a): int(b) for a, b in (l.split(":") for l in pt_txt.split() if ":" in l)}
            t = memory.translate(la, ps, table)
            frame_box = (f'<div class="box fr"><small>Frame</small><b>{t["frame"]}</b></div>' if not t["fault"]
                         else '<div class="box" style="background:#FEF2F2;border-color:#FECACA"><small>Frame</small><b style="color:#991B1B">fault</b></div>')
            phys = (f'<div class="box fr"><small>Physical address</small><b>{t["physical"]}</b></div>' if not t["fault"]
                    else '<div class="box"><small>Physical address</small><b>—</b></div>')
            ar = f'<span class="arrow">{icon("arrow", 22, "#94A3B8")}</span>'
            st.html(f'<div class="xl"><div class="box"><small>Logical address</small><b>{la}</b></div>{ar}'
                    f'<div class="box pg"><small>Page = {la} ÷ {ps}</small><b>{t["page"]}</b></div>'
                    f'<div class="box off"><small>Offset = {la} mod {ps}</small><b>{t["offset"]}</b></div>{ar}{frame_box}{ar}{phys}</div>')
            if t["fault"]:
                ui.banner("bad", f"Page {t['page']} is not in the page table, so the OS raises a page fault and loads it from storage.", "alert")
            else:
                ui.banner("ok", f"physical = frame × page size + offset = {t['frame']} × {ps} + {t['offset']} = {t['physical']}")


# ----------------------------------------------------------------------
def page_disk():
    page_header("disk", "Part B · Storage", "Disk scheduling",
                "The order of requests decides how far the head travels, and travel costs time and energy.", "Prit Patel")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1.2])
        q_txt = c1.text_input("Request queue (cylinders 0–199)", "98 183 37 122 14 124 65 67")
        head = int(c2.number_input("Head at", 0, 199, 53))
        direction = c3.segmented_control("Direction", ["down", "up"], default="down") or "down"
        algo = c4.selectbox("Algorithm", disk.ALGORITHMS, index=1)
    reqs = [int(x) for x in q_txt.replace(",", " ").split()]
    r = disk.schedule(reqs, head, algo, direction)
    comp = pd.DataFrame(disk.compare(reqs, head, direction))
    best = comp.loc[comp["Total seek (cylinders)"].idxmin()]
    kpis([dict(label="Total seek", value=r["total_seek"], unit="cyl", icon="route", tone="indigo"),
          dict(label="Average seek", value=f"{r['avg_seek']:.1f}", unit="cyl", icon="gauge", tone="teal"),
          dict(label="Seek time", value=f"{r['seek_time_ms']:.1f}", unit="ms", icon="clock", tone="amber"),
          dict(label="Seek energy", value=f"{r['energy_mj']:.2f}", unit="mJ", icon="bolt", tone="green",
               sub=f"best here: {best['Algorithm']} ({best['Total seek (cylinders)']} cyl)")])
    a, b = st.columns([1.5, 1], gap="medium")
    path = r["path"]
    with a, st.container(border=True):
        steps = list(range(len(path)))
        frames = [go.Frame(data=[go.Scatter(x=path[:k + 1], y=steps[:k + 1]),
                                 go.Scatter(x=[path[k]], y=[k])], name=str(k)) for k in range(len(path))]
        fig = go.Figure(data=[go.Scatter(x=path, y=steps, mode="lines+markers+text", text=[str(p) for p in path],
                                         textposition="middle right", line=dict(color=BRAND, width=3), marker=dict(size=9),
                                         hoverinfo="skip"),
                              go.Scatter(x=[path[-1]], y=[len(path) - 1], mode="markers", marker=dict(size=18, color=INDIGO,
                                         symbol="diamond", line=dict(width=2, color="white")), hoverinfo="skip")],
                        frames=frames)
        fig.update_layout(title=dict(text=f"{algo}: head movement (press ▶ to animate)", y=0.99), showlegend=False, margin=dict(t=80),
                          yaxis=dict(autorange="reversed", title="order of service"),
                          xaxis=dict(range=[-5, 205], title="cylinder", side="top"),
                          updatemenus=[dict(type="buttons", x=0, y=-0.08, xanchor="left", direction="left", showactive=False,
                                            buttons=[dict(label="▶ Play", method="animate",
                                                          args=[None, dict(frame=dict(duration=550, redraw=True), fromcurrent=False,
                                                                           transition=dict(duration=250))]),
                                                     dict(label="⏸", method="animate",
                                                          args=[[None], dict(mode="immediate", frame=dict(duration=0))])])])
        chart(fig, 460, key=f"disk_{algo}_{direction}_{head}_{q_txt}")
    with b, st.container(border=True):
        fig = px.bar(comp.sort_values("Total seek (cylinders)"), y="Algorithm", x="Total seek (cylinders)", orientation="h",
                     text="Total seek (cylinders)", color="Algorithm", color_discrete_sequence=PALETTE, title="Total head movement")
        fig.update_layout(showlegend=False, margin=dict(r=40))
        fig.update_traces(textposition="outside", cliponaxis=False)
        chart(fig, 300)
        st.dataframe(comp, width="stretch", hide_index=True)


# ----------------------------------------------------------------------
def philosopher_ring(res, title):
    n = len(res["meals_eaten"])
    xs = [math.cos(2 * math.pi * i / n + math.pi / 2) for i in range(n)]
    ys = [math.sin(2 * math.pi * i / n + math.pi / 2) for i in range(n)]
    fx = [math.cos(2 * math.pi * (i + .5) / n + math.pi / 2) * .62 for i in range(n)]
    fy = [math.sin(2 * math.pi * (i + .5) / n + math.pi / 2) * .62 for i in range(n)]
    stuck = set(res["stuck"])
    fig = go.Figure()
    fig.add_shape(type="circle", x0=-.45, y0=-.45, x1=.45, y1=.45, fillcolor="#F1F5F3", line_color="#E3E9E5")
    fig.add_scatter(x=fx, y=fy, mode="markers", marker=dict(symbol="line-ns", size=18, line=dict(width=4, color="#94A3B8")),
                    hoverinfo="skip")
    fig.add_scatter(x=xs, y=ys, mode="markers+text", text=[f"P{i}" for i in range(n)], textfont=dict(color="white", size=13),
                    marker=dict(size=46, color=[RED if i in stuck else BRAND for i in range(n)], line=dict(width=3, color="white")),
                    hovertext=[f"P{i}: stuck, waiting" if i in stuck else f"P{i}: ate {res['meals_eaten'][i]} meals" for i in range(n)],
                    hoverinfo="text")
    fig.update_layout(title=title, showlegend=False, xaxis=dict(visible=False, range=[-1.4, 1.4]),
                      yaxis=dict(visible=False, range=[-1.4, 1.4], scaleanchor="x"), height=320, margin=dict(t=40, b=0))
    return fig


def page_sync():
    page_header("lock", "Part C · Concurrency", "Process synchronization",
                "Real Python threads sharing data: what goes wrong without protection, and how locks and semaphores fix it.",
                "Krishna Karthikeya Burra")
    t1, t2, t3 = st.tabs(["Race condition", "Producer–consumer", "Dining philosophers"])
    with t1:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, .6])
            n_th = c1.slider("Threads", 2, 8, 4)
            inc = c2.slider("Increments per thread", 500, 5000, 2000, 500)
            c3.write("")
            c3.button("Run again", icon=":material/replay:", width="stretch")
        no = sync.race_condition(n_th, inc, False)
        yes = sync.race_condition(n_th, inc, True)
        kpis([dict(label="Expected", value=f"{no['expected']:,}", icon="check", tone="indigo"),
              dict(label="Without lock", value=f"{no['actual']:,}", icon="alert", tone="red",
                   sub=f'<span class="down">{no["lost_updates"]:,} updates lost</span>'),
              dict(label="With lock", value=f"{yes['actual']:,}", icon="lock", tone="green", sub='<span class="up">0 lost</span>')])
        a, b = st.columns([1, 1], gap="medium")
        with a, st.container(border=True):
            fig = go.Figure(go.Bar(x=["Expected", "No lock", "With lock"], y=[no["expected"], no["actual"], yes["actual"]],
                                   marker_color=[INDIGO, RED, BRAND], text=[f"{v:,}" for v in (no["expected"], no["actual"], yes["actual"])],
                                   textposition="outside"))
            fig.update_layout(title="Final counter value")
            chart(fig, 320)
        with b, st.container(border=True):
            section("Why updates get lost")
            st.code("value = counter       # 1. read\n# another thread may run here\n"
                    "counter = value + 1   # 2. write (can overwrite)", language="python")
            st.markdown("With `with lock:` around both lines only one thread is inside the **critical section** at a time, "
                        "so every increment survives.")
    with t2:
        with st.container(border=True):
            c = st.columns(4)
            size = c[0].slider("Buffer size", 1, 10, 4)
            npro = c[1].slider("Producers", 1, 4, 2)
            ncon = c[2].slider("Consumers", 1, 4, 2)
            items = c[3].slider("Items per producer", 5, 30, 12)
        r = sync.producer_consumer(size, npro, ncon, items)
        ok = r["all_consumed_once"] and r["never_overflowed"]
        kpis([dict(label="Items produced", value=r["items"], icon="layers", tone="indigo"),
              dict(label="Max in buffer", value=f"{r['max_occupancy']} / {size}", icon="database", tone="amber"),
              dict(label="Correct", value="Yes" if ok else "No", icon="check" if ok else "alert", tone="green" if ok else "red",
                   sub="each item consumed exactly once")])
        log = pd.DataFrame(r["log"])
        with st.container(border=True):
            fig = px.line(log, x="t_ms", y="buffer", line_shape="hv", title="Items in the buffer over time")
            fig.add_hline(y=size, line_dash="dash", line_color=RED, annotation_text="capacity: producers block on empty")
            fig.add_hline(y=0, line_dash="dot", line_color=ui.SLATE, annotation_text="empty: consumers block on full",
                          annotation_position="bottom right")
            fig.update_traces(line=dict(color=BRAND, width=2.5), fill="tozeroy", fillcolor="rgba(16,185,129,0.12)")
            fig.update_layout(xaxis_title="time (ms)", yaxis_title="items")
            chart(fig, 320)
            with st.expander("Event log"):
                st.dataframe(log, width="stretch", hide_index=True, height=260)
    with t3:
        naive = sync.dining_philosophers(5, "naive", meals=2, timeout=0.6)
        ordered = sync.dining_philosophers(5, "ordered", meals=3, timeout=2)
        a, b = st.columns(2, gap="medium")
        with a, st.container(border=True):
            chart(philosopher_ring(naive, "Naive: left fork, then right fork"))
            ui.banner("bad", f"DEADLOCK: all {len(naive['stuck'])} philosophers hold one fork and wait forever for the next.", "alert")
            st.dataframe(pd.DataFrame(naive["log"]), hide_index=True, width="stretch", height=200)
        with b, st.container(border=True):
            chart(philosopher_ring(ordered, "Ordered: lower-numbered fork first"))
            ui.banner("ok", f"No deadlock: the circular wait is broken, {sum(ordered['meals_eaten'])} meals eaten.")
            st.dataframe(pd.DataFrame(ordered["log"]), hide_index=True, width="stretch", height=200)



# ----------------------------------------------------------------------
def page_deadlock():
    page_header("alert", "Part C · Resources", "Deadlock avoidance and detection",
                "Banker's algorithm keeps the system in a safe state; the wait-for graph finds deadlocks that already happened.",
                "Krishna Karthikeya Burra")
    t1, t2 = st.tabs(["Banker's algorithm", "Wait-for graph"])
    with t1:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, .9], gap="medium")
            idx = [f"P{i}" for i in range(5)]
            c1.markdown("**Allocation**")
            alloc = c1.data_editor(pd.DataFrame([[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], columns=list("ABC"), index=idx), key="alloc")
            c2.markdown("**Max**")
            mx = c2.data_editor(pd.DataFrame([[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], columns=list("ABC"), index=idx), key="max")
            avail = [int(x) for x in c3.text_input("Available (A B C)", "3 3 2").split()]
            res = deadlock.safety(avail, mx.values.tolist(), alloc.values.tolist())
            c3.markdown("**Need = Max − Allocation**")
            c3.dataframe(pd.DataFrame(res["need"], columns=list("ABC"), index=idx), width="stretch")
        if res["safe"]:
            seq = f' <span style="display:inline-block;vertical-align:middle">{icon("arrow", 14, "#065F46")}</span> '.join(ui.chip(p, "g") for p in res["sequence"])
            ui.banner("ok", f"SAFE state. Safe sequence: {seq}")
        else:
            ui.banner("bad", "UNSAFE state. These processes can never finish: " + ", ".join(res["unfinished"]), "alert")
        a, b = st.columns([1.4, 1], gap="medium")
        with a, st.container(border=True):
            section("How the algorithm decided", "Work grows each time a process can finish")
            steps = pd.DataFrame([{"Check": s["process"], "Need": str(s["need"]), "Work before": str(s["work_before"]),
                                   "Can finish?": "yes" if s["can_finish"] else "no", "Work after": str(s.get("work_after", ""))}
                                  for s in res["steps"]])
            st.dataframe(steps.style.apply(lambda row: ["background-color:#ECFDF5" if row["Can finish?"] == "yes" else ""] * len(row), axis=1),
                         width="stretch", hide_index=True)
        with b, st.container(border=True):
            section("Try a resource request")
            pid = st.selectbox("Process", range(5), index=1, format_func=lambda i: f"P{i}")
            req = [int(x) for x in st.text_input("Request (A B C)", "1 0 2").split()]
            out = deadlock.request(pid, req, avail, mx.values.tolist(), alloc.values.tolist())
            if out["granted"]:
                ui.banner("ok", f"GRANTED. {out['reason']}. New safe sequence: {' → '.join(out['sequence'])}")
            else:
                ui.banner("bad", f"DENIED. {out['reason']}", "alert")
    with t2:
        a, b = st.columns([1, 2], gap="medium")
        with a, st.container(border=True):
            edges_txt = st.text_area("Edges: Pi waits for Pj (one per line)", "P1 P2\nP2 P3\nP3 P4\nP4 P2\nP5 P1", height=200)
            edges = {}
            for line in edges_txt.splitlines():
                parts = line.split()
                if len(parts) == 2:
                    edges.setdefault(parts[0], []).append(parts[1])
            cyc = deadlock.wait_for_cycle(edges)
            if cyc:
                ui.banner("bad", "Deadlock found: " + " → ".join(cyc), "alert")
            else:
                ui.banner("ok", "No cycle, so no deadlock")
        with b, st.container(border=True):
            st.graphviz_chart(deadlock.wait_for_dot(edges, cyc), width="stretch")


# ----------------------------------------------------------------------
def page_lab():
    page_header("battery", "Part C · Whole system", "Battery lab",
                "Run a whole workload through CPU, memory and disk at once, and see where every millijoule goes.",
                "Krishna Karthikeya Burra")
    with st.container(border=True):
        c = st.columns(4)
        n = c[0].slider("Processes", 3, 15, 8)
        seed = int(c[1].number_input("Seed", 1, 999, 7))
        mix = c[2].selectbox("Workload", ["mixed", "interactive", "batch"])
        frames = c[3].slider("Frames / process", 1, 8, 3)
        c = st.columns(4)
        sched = c[0].selectbox("Scheduler", cpu.ALGORITHMS, index=5)
        gov = c[1].selectbox("Governor", list(energy.GOVERNORS), index=4)
        rep = c[2].selectbox("Page replacement", memory.ALGORITHMS, index=1)
        dalg = c[3].selectbox("Disk algorithm", disk.ALGORITHMS, index=1)
    tasks = battery_lab.generate_workload(n, seed, mix)
    r = battery_lab.run(tasks, sched, gov, 4, rep, frames, dalg)
    kpis([dict(label="Total energy", value=f"{r.energy_total_mj:.0f}", unit="mJ", icon="bolt", tone="amber"),
          dict(label="Page faults", value=r.page_faults, icon="memory", tone="red"),
          dict(label="Disk seek", value=r.seek_total, unit="cyl", icon="disk", tone="teal"),
          dict(label="Avg power", value=f"{r.duty_power_w:.3f}", unit="W", icon="gauge", tone="indigo"),
          dict(label="Battery life", value=f"{r.battery_hours:.1f}", unit="h", icon="battery", tone="green")])
    a, b = st.columns([1, 2], gap="medium")
    with a, st.container(border=True):
        chart(gauge(r.battery_hours))
        if st.button("Save this run to history", icon=":material/save:", type="primary", width="stretch"):
            history.save(r, dict(scheduler=sched, governor=gov, replacement=rep, disk_algorithm=dalg, processes=n, seed=seed, workload=mix))
            st.toast("Run saved to energos_history.db", icon=":material/check_circle:")
    with b, st.container(border=True):
        section("Energy flow", "battery → component → cause")
        chart(sankey(r))
    a, b = st.columns(2, gap="medium")
    with a, st.container(border=True):
        comp = pd.DataFrame(battery_lab.compare_policies(tasks, replacement=rep, frames_per_process=frames, disk_algorithm=dalg))
        pv = comp.pivot(index="Scheduler", columns="Governor", values="Battery life (h)")
        fig = px.imshow(pv, text_auto=".1f", color_continuous_scale=["#ECFDF5", "#34D399", "#065F46"], aspect="auto",
                        title="Battery life (h): every scheduler × governor")
        fig.update_coloraxes(showscale=False)
        chart(fig, 360)
    with b, st.container(border=True):
        fr = pd.DataFrame([{"Frames": f, **{a_: battery_lab.run(tasks, sched, gov, 4, a_, f, dalg).battery_hours for a_ in memory.ALGORITHMS}}
                           for f in range(1, 7)]).melt("Frames", var_name="Replacement", value_name="Battery life (h)")
        fig = px.line(fr, x="Frames", y="Battery life (h)", color="Replacement", markers=True,
                      color_discrete_sequence=[RED, BRAND, INDIGO, TEAL], title="More frames → fewer faults → longer battery")
        fig.update_traces(line=dict(width=3), marker=dict(size=8))
        fig.update_layout(legend=dict(orientation="h", y=-0.2))
        chart(fig, 360)


# ----------------------------------------------------------------------
def page_history():
    page_header("history", "Part C · Storage", "Run history",
                "Every saved battery-lab run lives in one SQLite file, so results can be compared over time.",
                "Krishna Karthikeya Burra")
    runs = pd.DataFrame(history.all_runs())
    if runs.empty:
        ui.banner("info", "No runs saved yet. Open the Battery lab and press <b>Save this run to history</b>.", "database")
        return
    best = runs.loc[runs["battery_hours"].idxmax()]
    kpis([dict(label="Runs stored", value=len(runs), icon="database", tone="indigo"),
          dict(label="Best battery life", value=f"{best['battery_hours']:.1f}", unit="h", icon="battery", tone="green",
               sub=f"{best['scheduler']} + {best['governor']}"),
          dict(label="Lowest energy", value=f"{runs['energy_total'].min():.0f}", unit="mJ", icon="bolt", tone="amber"),
          dict(label="Power while busy", value=f"{runs['avg_power'].mean():.2f}", unit="W", icon="gauge", tone="teal", sub="average over runs")])
    a, b = st.columns([1.6, 1], gap="medium")
    with a, st.container(border=True):
        rp = runs.rename(columns={"energy_cpu": "CPU", "energy_mem": "Memory", "energy_disk": "Disk"})
        rp["run"] = "#" + rp["id"].astype(str)
        fig = px.bar(rp, x="run", y=["CPU", "Memory", "Disk"], labels={"value": "energy (mJ)", "variable": "part", "run": ""},
                     color_discrete_sequence=[BRAND, AMBER, INDIGO], title="Energy of each saved run")
        fig.update_layout(legend=dict(orientation="h", y=-0.2), bargap=0.35)
        chart(fig, 340)
    with b, st.container(border=True):
        fig = px.scatter(runs, x="avg_waiting", y="battery_hours", color="governor", size="energy_total", hover_name="scheduler",
                         labels={"avg_waiting": "avg waiting (ms)", "battery_hours": "battery life (h)"},
                         title="Speed vs battery for each run", color_discrete_sequence=PALETTE)
        fig.update_layout(legend=dict(orientation="h", y=-0.25))
        chart(fig, 340)
    with st.container(border=True):
        section("All runs")
        st.dataframe(runs.round(2), width="stretch", hide_index=True)
        if st.button("Clear history", icon=":material/delete:"):
            history.clear()
            st.rerun()


# ======================================================================
#  navigation + sidebar
# ======================================================================
pages = {
    "": [st.Page(page_overview, title="Overview", icon=":material/space_dashboard:", url_path="overview", default=True)],
    "Part A · Aarth": [st.Page(page_cpu, title="CPU scheduling", icon=":material/memory:", url_path="cpu")],
    "Part B · Prit": [st.Page(page_memory, title="Memory paging", icon=":material/view_module:", url_path="memory"),
                      st.Page(page_disk, title="Disk scheduling", icon=":material/storage:", url_path="disk")],
    "Part C · Krishna": [st.Page(page_sync, title="Synchronization", icon=":material/sync_lock:", url_path="sync"),
                         st.Page(page_deadlock, title="Deadlocks", icon=":material/block:", url_path="deadlock"),
                         st.Page(page_lab, title="Battery lab", icon=":material/battery_charging_full:", url_path="lab"),
                         st.Page(page_history, title="History", icon=":material/monitoring:", url_path="history")],
}
nav = st.navigation(pages, position="sidebar")
with st.sidebar:
    st.html(f"""<div class="sb-card"><b>Power model</b><br><span class="sb-eq">P(f) = {energy.P_STATIC} + {energy.K_DYN}·f³ W</span><br>
      idle {energy.P_IDLE} W · levels {", ".join(str(f) for f in energy.FREQS)} GHz<br>
      page fault {energy.E_PAGE_FAULT_MJ:.0f} mJ · seek {energy.E_SEEK_PER_CYL_MJ} mJ/cyl<br>battery {energy.BATTERY_MWH / 1000:.0f} Wh</div>
      <div class="sb-card"><b>Team</b><br>Aarth Goyal · Prit Patel<br>Krishna Karthikeya Burra<br>
      <span style="color:#8FB5A0">Guide: Dr. Shaiju Panchikkil</span></div>""")
nav.run()
