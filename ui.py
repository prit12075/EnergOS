"""EnergOS design system: colours, CSS, icons and small HTML components for the dashboard.

Kept separate from the OS engines (energos/) so the simulator code stays pure Python."""
from __future__ import annotations

import base64
import html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------- design tokens
BRAND = "#0E9F6E"      # emerald
BRAND_DARK = "#065F46"
INK = "#0F1B14"
MUTED = "#5B6B62"
LINE = "#E3E9E5"
AMBER = "#F59E0B"
RED = "#DC2626"
INDIGO = "#4F46E5"
TEAL = "#0891B2"
SLATE = "#94A3B8"
PALETTE = [BRAND, INDIGO, AMBER, TEAL, RED, "#7C3AED", "#DB2777", "#65A30D", "#0D9488", "#EA580C"]
FREQ_COLOURS = {0.8: "#A7F3D0", 1.2: "#34D399", 1.6: "#059669", 2.0: "#065F46"}

# ---------------------------------------------------------------- plotly theme
pio.templates["energos"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", size=12, color="#334155"),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=PALETTE,
    title=dict(font=dict(size=14, color=INK), x=0, xanchor="left"),
    xaxis=dict(gridcolor="#EEF2EF", zerolinecolor="#E3E9E5", linecolor="#E3E9E5", ticks=""),
    yaxis=dict(gridcolor="#EEF2EF", zerolinecolor="#E3E9E5", linecolor="#E3E9E5", ticks=""),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(family="Inter, sans-serif", color=INK)),
    margin=dict(l=10, r=10, t=36, b=10),
))
pio.templates.default = "plotly_white+energos"


def chart(fig, height=None, key=None):
    """Render a Plotly figure with our own template (Streamlit's theme switched off)."""
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", theme=None, key=key,
                    config={"displayModeBar": False, "displaylogo": False})


# ---------------------------------------------------------------- icons (inline SVG, stroke style)
_ICONS = {
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
    "memory": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10v4M10 10v4M14 10v4M18 10v4M6 18v3M10 18v3M14 18v3M18 18v3"/>',
    "disk": '<path d="M22 12H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><path d="M6 16h.01M10 16h.01"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "alert": '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86"/><path d="M12 8v4M12 16h.01"/>',
    "battery": '<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 11v2M6 11v2M10 11v2"/>',
    "history": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/>',
    "bolt": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "flask": '<path d="M9 3h6M10 9V3M14 9V3M10 9l-5.5 9.2A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.8L14 9"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    "swap": '<path d="M7 16V4m0 0L3 8m4-4 4 4M17 8v12m0 0 4-4m-4 4-4-4"/>',
    "users": '<circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2M16 3.13a4 4 0 0 1 0 7.75M21 21v-2a4 4 0 0 0-3-3.85"/>',
    "route": '<circle cx="6" cy="19" r="3"/><circle cx="18" cy="5" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>',
    "arrow": '<path d="M5 12h14M12 5l7 7-7 7"/>',
}


def icon(name: str, size: int = 18, color: str = "#0E9F6E", stroke: float = 2) -> str:
    """Inline icon as an <img> with an SVG data URI (st.html strips raw <svg> tags)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_ICONS[name]}</svg>')
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return f'<img src="{uri}" width="{size}" height="{size}" alt="" style="display:block">'


TONES = {"green": "#059669", "amber": "#D97706", "red": "#DC2626", "indigo": "#4F46E5", "teal": "#0891B2"}


# ---------------------------------------------------------------- global CSS
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--brand:#0E9F6E;--brand-d:#065F46;--ink:#0F1B14;--muted:#5B6B62;--line:#E3E9E5;--bg:#F4F7F5;--card:#FFFFFF;
--amber:#F59E0B;--red:#DC2626;--indigo:#4F46E5;--teal:#0891B2;--shadow:0 1px 2px rgba(16,24,20,.04),0 4px 16px rgba(16,24,20,.05)}
.stApp{font-family:Inter,-apple-system,"Segoe UI",sans-serif}
.stApp{background:var(--bg)}
[data-testid="stHeader"]{background:transparent;height:0}
[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none}
.block-container{padding-top:1.6rem;padding-bottom:3rem;max-width:1380px}
h1,h2,h3{letter-spacing:-.01em}
/* sidebar */
[data-testid="stSidebar"]{border-right:1px solid #0E2419}
[data-testid="stSidebarNav"] a{border-radius:10px;margin:2px 0;padding:.45rem .7rem}
[data-testid="stSidebarNav"] a span{font-weight:500}
[data-testid="stSidebarNavSeparator"]{border-color:#1C3528}
.sb-brand{display:flex;align-items:center;gap:.7rem;padding:.2rem 0 .6rem}
.sb-logo{width:40px;height:40px;border-radius:11px;background:linear-gradient(135deg,#34D399,#059669);display:flex;align-items:center;justify-content:center;box-shadow:0 6px 18px rgba(16,185,129,.35)}
.sb-name{font-weight:800;font-size:1.15rem;color:#F0FDF4;line-height:1.1}
.sb-tag{font-size:.72rem;color:#8FB5A0;letter-spacing:.04em}
.sb-card{background:#12271C;border:1px solid #1C3528;border-radius:12px;padding:.8rem .9rem;margin-top:.6rem;color:#C9DDD0;font-size:.78rem;line-height:1.5}
.sb-card b{color:#F0FDF4}
.sb-eq{font-family:ui-monospace,Menlo,monospace;color:#6EE7B7;font-size:.86rem}
/* page header */
.ph{display:flex;align-items:center;gap:1.1rem;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1.1rem 1.3rem;box-shadow:var(--shadow);margin-bottom:1rem;position:relative;overflow:hidden}
.ph:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:linear-gradient(180deg,#34D399,#059669)}
.ph-ic{width:52px;height:52px;border-radius:14px;background:#ECFDF5;color:var(--brand);display:flex;align-items:center;justify-content:center;flex:none}
.ph-crumb{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--brand)}
.ph h1{font-size:1.55rem;font-weight:800;color:var(--ink);margin:.1rem 0 .15rem;padding:0;line-height:1.2}
.ph p{margin:0;color:var(--muted);font-size:.92rem}
.ph-owner{margin-left:auto;display:flex;align-items:center;gap:.6rem;background:#F6FAF8;border:1px solid var(--line);border-radius:12px;padding:.45rem .8rem .45rem .5rem;flex:none}
.av{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#065F46,#10B981);color:#fff;font-weight:700;font-size:.8rem;display:flex;align-items:center;justify-content:center}
.ph-owner b{display:block;font-size:.85rem;color:var(--ink)}
.ph-owner span{font-size:.72rem;color:var(--muted)}
/* kpi cards */
.kpis{display:grid;gap:.8rem;margin:.2rem 0 1rem}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;box-shadow:var(--shadow)}
.kpi-top{display:flex;align-items:center;gap:.5rem;color:var(--muted);font-size:.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;min-width:0}
.kpi-top>span:last-child{overflow:hidden;text-overflow:ellipsis}
.kpi-ic{width:30px;height:30px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex:none}
.kpi-val{white-space:nowrap;font-size:1.6rem;font-weight:800;color:var(--ink);margin-top:.45rem;line-height:1.1;font-variant-numeric:tabular-nums}
.kpi-unit{font-size:.9rem;font-weight:600;color:var(--muted);margin-left:.25rem}
.kpi-sub{font-size:.78rem;color:var(--muted);margin-top:.25rem}
.t-green .kpi-ic{background:#ECFDF5;color:#059669}.t-amber .kpi-ic{background:#FFFBEB;color:#D97706}
.t-red .kpi-ic{background:#FEF2F2;color:#DC2626}.t-indigo .kpi-ic{background:#EEF2FF;color:#4F46E5}.t-teal .kpi-ic{background:#ECFEFF;color:#0891B2}
.up{color:#059669;font-weight:700}.down{color:#DC2626;font-weight:700}
/* section title */
.sec{display:flex;align-items:baseline;gap:.6rem;margin:.4rem 0 .5rem}
.sec h3{font-size:1.02rem;font-weight:700;color:var(--ink);margin:0;padding:0}
.sec span{font-size:.82rem;color:var(--muted)}
/* bordered containers = cards */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]){background:var(--card)}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px!important;border-color:var(--line)!important;box-shadow:var(--shadow);background:var(--card)}
/* tabs as pills */
[role="tablist"]{gap:.3rem!important;background:#E6EDE9;padding:.3rem!important;border-radius:12px;width:fit-content;border:none!important;box-shadow:none!important}
[role="tablist"]::before,[role="tablist"]::after{display:none!important}
[data-testid="stTab"]{padding:.45rem 1rem!important;border-radius:9px!important;font-weight:600;color:var(--muted);border:none!important;margin:0!important}
[data-testid="stTab"] p{font-weight:600;font-size:.88rem}
[data-testid="stTab"][aria-selected="true"]{background:#fff!important;color:var(--ink)!important;box-shadow:0 1px 3px rgba(0,0,0,.1)}
[data-testid="stTab"]::after,[data-testid="stTab"]::before{display:none!important}
/* status banners */
.banner{display:flex;align-items:center;gap:.7rem;border-radius:12px;padding:.75rem 1rem;font-weight:600;margin:.3rem 0 .8rem}
.banner.ok{background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0}
.banner.bad{background:#FEF2F2;color:#991B1B;border:1px solid #FECACA}
.banner.info{background:#EEF2FF;color:#3730A3;border:1px solid #C7D2FE}
.chip{display:inline-flex;align-items:center;gap:.3rem;padding:.12rem .55rem;border-radius:999px;font-size:.74rem;font-weight:700}
.chip.g{background:#D1FAE5;color:#065F46}.chip.r{background:#FEE2E2;color:#991B1B}.chip.a{background:#FEF3C7;color:#92400E}.chip.i{background:#E0E7FF;color:#3730A3}
/* frames (page replacement player) */
.frames{display:flex;gap:.6rem;flex-wrap:wrap;margin:.4rem 0}
.frame{width:78px;height:86px;border-radius:12px;border:2px solid var(--line);background:#F8FAF9;display:flex;flex-direction:column;align-items:center;justify-content:center}
.frame small{font-size:.68rem;color:var(--muted);font-weight:600}
.frame b{font-size:1.7rem;color:var(--ink)}
.frame.new{border-color:#10B981;background:#ECFDF5}.frame.hit{border-color:#4F46E5;background:#EEF2FF}
.refstrip{display:flex;gap:4px;flex-wrap:wrap;margin:.2rem 0 .6rem}
.ref{width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;background:#F1F5F3;color:#64748B}
.ref.f{background:#FEE2E2;color:#991B1B}.ref.h{background:#D1FAE5;color:#065F46}.ref.cur{outline:3px solid var(--ink);outline-offset:1px}
/* address translation diagram */
.xl{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin:.4rem 0}
.xl .box{border-radius:12px;padding:.6rem .9rem;border:1px solid var(--line);background:#F8FAF9;text-align:center}
.xl .box small{display:block;font-size:.68rem;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.xl .box b{font-size:1.2rem;color:var(--ink);font-variant-numeric:tabular-nums}
.xl .pg{background:#EEF2FF;border-color:#C7D2FE}.xl .off{background:#FFFBEB;border-color:#FDE68A}.xl .fr{background:#ECFDF5;border-color:#A7F3D0}
.xl .arrow{color:var(--muted)}
/* module cards on overview */
.mods{display:grid;grid-template-columns:repeat(3,1fr);gap:.9rem}
.mod{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem;box-shadow:var(--shadow)}
.mod .kpi-ic{width:38px;height:38px;border-radius:11px}
.mod h4{margin:.6rem 0 .2rem;font-size:1rem;color:var(--ink);padding:0}
.mod p{margin:0;font-size:.84rem;color:var(--muted);line-height:1.5}
.mod .who{margin-top:.6rem;font-size:.75rem;font-weight:600;color:var(--brand-d)}
/* hero */
.hero{border-radius:18px;padding:1.6rem 1.8rem;background:radial-gradient(1200px 300px at 85% -40%,rgba(52,211,153,.35),transparent),linear-gradient(135deg,#052E1F 0%,#065F46 55%,#047857 100%);color:#ECFDF5;margin-bottom:1rem;box-shadow:0 10px 30px rgba(6,95,70,.25)}
.hero .eyebrow{font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#6EE7B7}
.hero h1{color:#fff;font-size:2rem;font-weight:800;margin:.3rem 0 .35rem;padding:0;line-height:1.15}
.hero p{color:#C7EAD9;max-width:760px;margin:0;font-size:.98rem;line-height:1.55}
.hero .pills{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1rem}
.hero .pill{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:.3rem .75rem;font-size:.8rem;font-weight:600;color:#ECFDF5}
/* widgets */
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{border-radius:10px;overflow:hidden}
.stButton>button{border-radius:10px;font-weight:600}
@media (max-width:900px){.mods{grid-template-columns:1fr}.ph{flex-wrap:wrap}.ph-owner{margin-left:0}}
</style>
"""


def inject_css():
    st.html(CSS)


def _h(text) -> str:
    return html.escape(str(text))


def page_header(icon_name: str, crumb: str, title: str, subtitle: str, owner: str | None = None):
    who = ""
    if owner:
        initials = "".join(w[0] for w in owner.split()[:2]).upper()
        who = (f'<div class="ph-owner"><div class="av">{initials}</div><div><b>{_h(owner)}</b>'
               f'<span>Module owner</span></div></div>')
    st.html(f'<div class="ph"><div class="ph-ic">{icon(icon_name, 26, "#059669")}</div><div><div class="ph-crumb">{_h(crumb)}</div>'
            f'<h1>{_h(title)}</h1><p>{_h(subtitle)}</p></div>{who}</div>')


def kpis(items):
    """items: list of dicts {label, value, unit?, sub?, icon, tone?}."""
    cells = []
    for k in items:
        unit = f'<span class="kpi-unit">{_h(k["unit"])}</span>' if k.get("unit") else ""
        sub = f'<div class="kpi-sub">{k["sub"]}</div>' if k.get("sub") else ""
        cells.append(f'<div class="kpi t-{k.get("tone", "green")}"><div class="kpi-top"><span class="kpi-ic">'
                     f'{icon(k["icon"], 17, TONES.get(k.get("tone", "green")))}</span><span>{_h(k["label"])}</span></div><div class="kpi-val">{_h(k["value"])}{unit}</div>{sub}</div>')
    st.html(f'<div class="kpis" style="grid-template-columns:repeat({len(items)},minmax(0,1fr))">{"".join(cells)}</div>')


def section(title: str, caption: str = ""):
    cap = f"<span>{_h(caption)}</span>" if caption else ""
    st.html(f'<div class="sec"><h3>{_h(title)}</h3>{cap}</div>')


def banner(kind: str, text: str, icon_name: str = "check"):
    col = {"ok": "#065F46", "bad": "#991B1B", "info": "#3730A3"}[kind]
    st.html(f'<div class="banner {kind}">{icon(icon_name, 20, col)}<div>{text}</div></div>')


def chip(text: str, tone: str = "g") -> str:
    return f'<span class="chip {tone}">{_h(text)}</span>'
