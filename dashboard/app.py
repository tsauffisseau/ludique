"""Streamlit dashboard - the BI layer on top of the Gold marts.

    streamlit run dashboard/app.py

Reads only the `marts` schema of the PostgreSQL warehouse: the dashboard contains
presentation logic, never business logic.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bgg_pipeline.config import get_settings  # noqa: E402
from bgg_pipeline.load import query_df  # noqa: E402

st.set_page_config(page_title="Board Game Market Analytics", page_icon="🎲", layout="wide")

# --------------------------------------------------------------------------- theme
# Reference data-viz palette: one series colour (slot 1), gray for de-emphasis,
# hairline recessive chrome. Light and dark are each selected, not auto-inverted.
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink2": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "series": "#2a78d6",
        "dim": "#c3c2b7",
        # First 3 categorical slots: validated all-pairs (CVD-safe) for scatter plots.
        "cat": ["#2a78d6", "#eb6834", "#1baf7a"],
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#f0efec",
        "ink2": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "series": "#3987e5",
        "dim": "#52514e",
        "cat": ["#3987e5", "#d95926", "#199e70"],
    },
}
theme_type = getattr(getattr(st.context, "theme", None), "type", None) or "light"
T = THEMES["dark" if theme_type == "dark" else "light"]
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def style(fig: go.Figure, height: int = 340, **layout) -> go.Figure:
    axis = dict(
        gridcolor=T["grid"],
        gridwidth=1,
        linecolor=T["axis"],
        zeroline=False,
        tickfont=dict(color=T["muted"], size=11),
        title_font=dict(color=T["ink2"], size=12),
    )
    layout.setdefault("showlegend", False)
    layout.setdefault("margin", dict(l=8, r=16, t=36, b=8))
    fig.update_layout(
        height=height,
        paper_bgcolor=T["surface"],
        plot_bgcolor=T["surface"],
        font=dict(family=FONT, color=T["ink"], size=12),
        title_font=dict(size=14, color=T["ink"]),
        hoverlabel=dict(bgcolor=T["surface"], font_color=T["ink"], bordercolor=T["axis"]),
        bargap=0.25,
        barcornerradius=4,
        **layout,
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def table_view(df: pd.DataFrame, label: str = "View data") -> None:
    with st.expander(label):
        st.dataframe(df, hide_index=True, width="stretch")


# --------------------------------------------------------------------------- data
DSN = get_settings().pg_dsn


@st.cache_data(show_spinner=False, ttl=600)
def query(sql: str) -> pd.DataFrame:
    df = query_df(DSN, sql)
    # NUMERIC (Decimal) or all-NULL columns -> float for plotting
    for col in [c for c in df.columns if pd.api.types.is_object_dtype(df[c])]:
        values = df[col].dropna()
        if values.map(lambda v: isinstance(v, (Decimal, int, float)) and not isinstance(v, bool)).all():
            df[col] = df[col].astype(float)
    return df


def table_exists(name: str) -> bool:
    return bool(query(f"SELECT to_regclass('{name}') IS NOT NULL AS ok").ok.iloc[0])


try:
    if not table_exists("marts.mart_catalog_kpis"):
        raise LookupError
except (psycopg.OperationalError, LookupError):
    st.error("Warehouse not reachable or not built yet. Run `docker compose up` or `make run-pipeline`.")
    st.stop()

kpi = query("SELECT * FROM mart_catalog_kpis").iloc[0]
decades = query("SELECT * FROM mart_decade_trends WHERE decade_sort >= 1950 ORDER BY decade_sort")
mechanics = query("SELECT * FROM mart_top_mechanics_trends")
complexity = query("SELECT * FROM mart_complexity_vs_rating")
niches = query("SELECT * FROM mart_niche_opportunities")
movers = query("SELECT * FROM mart_rank_movers")
is_synthetic = bool(query("SELECT BOOL_OR(source_run_id LIKE 'synthetic%') AS s FROM silver.games").s.iloc[0])

# --------------------------------------------------------------------------- header
st.title("Board Game Market Analytics")
if is_synthetic:
    st.info(
        "**Demo mode: synthetic data.** The public repository ships invented, BGG-shaped games "
        "(the BGG licence does not cover redistributing its data). Real results are in the README; "
        "run `python -m bgg_pipeline run --source api` with your own BGG token to analyse real data.",
        icon="ℹ️",
    )
st.caption(
    f"BoardGameGeek catalogue sample · PostgreSQL star schema · {int(kpi.n_snapshots)} snapshot(s), "
    f"latest {pd.Timestamp(kpi.latest_snapshot_date):%Y-%m-%d}. Quality metrics use games with "
    f"≥ 30 ratings (BGG's own ranking threshold); supply metrics use every game."
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Games in catalogue", f"{int(kpi.n_games):,}")
c2.metric("With ≥ 30 ratings", f"{int(kpi.n_games_reliable):,}")
c3.metric("Average rating", f"{kpi.avg_rating_reliable:.2f} / 10")
c4.metric("Median complexity", f"{kpi.median_weight_reliable:.2f} / 5")
c5.metric("Distinct mechanics", f"{int(kpi.n_mechanics):,}")

# --------------------------------------------------------------------------- Q1
st.header("1 · How has the hobby evolved decade by decade?")
cols = st.columns(3)
small_multiples = [
    ("n_games_released", "Games released", "bar", "{:,.0f} games"),
    ("avg_rating", "Average rating (/10)", "line", "{:.2f}"),
    ("avg_weight", "Average complexity (/5)", "line", "{:.2f}"),
]
for col, (field, title, kind, fmt) in zip(cols, small_multiples, strict=True):
    hover = "%{x}<br>" + title + ": %{y}<extra></extra>"
    if kind == "bar":
        trace = go.Bar(
            x=decades.decade_label, y=decades[field], marker_color=T["series"], hovertemplate=hover
        )
    else:
        trace = go.Scatter(
            x=decades.decade_label,
            y=decades[field],
            mode="lines+markers",
            line=dict(color=T["series"], width=2),
            marker=dict(size=8, color=T["series"], line=dict(width=2, color=T["surface"])),
            hovertemplate=hover,
        )
    fig = style(go.Figure(trace), height=280, title=title)
    last = decades.dropna(subset=[field]).iloc[-1]
    fig.add_annotation(
        x=last.decade_label,
        y=last[field],
        text=fmt.format(last[field]),
        showarrow=False,
        yshift=14,
        font=dict(color=T["ink2"], size=11),
    )
    col.plotly_chart(fig, width="stretch")
table_view(decades.drop(columns="decade_sort"))

# --------------------------------------------------------------------------- Q2
st.header("2 · Which mechanics win players, and which are on the rise?")
left, right = st.columns([1, 1])
with left:
    metric = st.radio(
        "Rank mechanics by",
        {
            "owned_share_pct": "Market share (owned copies)",
            "rating_lift": "Rating lift",
            "momentum_index": "Momentum",
        }.keys(),
        format_func={
            "owned_share_pct": "Market share (owned copies)",
            "rating_lift": "Rating lift",
            "momentum_index": "Momentum (2015+ vs 2000-14)",
        }.get,
        horizontal=True,
    )
    min_games = st.slider("Minimum reliable games per mechanic", 3, 50, 15)
    eligible = mechanics[mechanics.n_games_reliable >= min_games].dropna(subset=[metric])
    top = eligible.nlargest(15, metric).sort_values(metric)
    fig = go.Figure(
        go.Bar(
            x=top[metric],
            y=top.mechanic_name,
            orientation="h",
            marker_color=T["series"],
            customdata=top[["n_games", "avg_rating"]],
            hovertemplate="<b>%{y}</b><br>value: %{x}<br>games: %{customdata[0]}"
            "<br>avg rating: %{customdata[1]}<extra></extra>",
        )
    )
    st.plotly_chart(style(fig, height=470, title="Top 15 mechanics"), width="stretch")

with right:
    scatter = eligible.dropna(subset=["momentum_index", "rating_lift"])
    # Selective direct labels: the 3 fastest-growing and the 3 best-rated mechanics only.
    labelled = set(scatter.nlargest(3, "momentum_index").mechanic_name) | set(
        scatter.nlargest(3, "rating_lift").mechanic_name
    )
    fig = go.Figure(
        go.Scatter(
            x=scatter.momentum_index,
            y=scatter.rating_lift,
            mode="markers+text",
            text=[n if n in labelled else "" for n in scatter.mechanic_name],
            textposition="top center",
            textfont=dict(color=T["ink2"], size=10),
            marker=dict(size=10, color=T["series"], opacity=0.85, line=dict(width=2, color=T["surface"])),
            customdata=scatter[["mechanic_name", "n_games"]],
            hovertemplate="<b>%{customdata[0]}</b><br>momentum: %{x:.2f}<br>rating lift: %{y:+.2f}"
            "<br>games: %{customdata[1]}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line=dict(color=T["axis"], width=1))
    fig.add_vline(x=1, line=dict(color=T["axis"], width=1))
    style(
        fig,
        height=560,
        title="Rising & loved: momentum vs rating lift",
        xaxis_title="Momentum index (> 1 = growing share of releases)",
        yaxis_title="Rating lift vs catalogue",
    )
    if len(scatter):  # head-room so edge labels are not clipped
        fig.update_xaxes(range=[0, scatter.momentum_index.max() * 1.2])
    st.plotly_chart(fig, width="stretch")
table_view(eligible.drop(columns="mechanic_id").sort_values(metric, ascending=False))

# --------------------------------------------------------------------------- Q3
st.header("3 · Do players reward complexity?")
eras = ["All eras"] + sorted(e for e in complexity.market_era.unique() if e != "All eras")
era = st.selectbox("Market era", eras, format_func=lambda e: e.split(". ", 1)[-1])
sub = complexity[(complexity.market_era == era) & (complexity.weight_bucket != "0. Unknown")]
c_left, c_right = st.columns([3, 1])
with c_left:
    # Dot + line rather than bars: bars must start at zero, a dot plot can zoom on the
    # 5.5-8 rating band honestly.
    fig = go.Figure(
        go.Scatter(
            x=sub.weight_bucket.str.split(". ", n=1).str[1],
            y=sub.avg_rating,
            mode="lines+markers+text",
            text=[f"{v:.2f}" for v in sub.avg_rating],
            textposition="top center",
            textfont=dict(color=T["ink2"], size=11),
            line=dict(color=T["series"], width=2),
            marker=dict(size=10, color=T["series"], line=dict(width=2, color=T["surface"])),
            customdata=sub[["n_games", "median_owned"]],
            hovertemplate="<b>%{x}</b><br>avg rating: %{y:.2f}<br>games: %{customdata[0]}"
            "<br>median owned: %{customdata[1]:,.0f}<extra></extra>",
        )
    )
    style(fig, height=340, title="Average rating by complexity bucket", yaxis_title="Average rating")
    fig.update_yaxes(range=[max(1, sub.avg_rating.min() - 0.5), sub.avg_rating.max() + 0.4])
    st.plotly_chart(fig, width="stretch")
with c_right:
    r = sub.corr_weight_rating.iloc[0] if len(sub) else float("nan")
    st.metric("Correlation weight ↔ rating", f"{r:+.2f}")
    st.caption("Pearson r between complexity and average rating, reliable games of the selected era.")
table_view(sub)

# --------------------------------------------------------------------------- Q4
st.header("4 · Where are the under-served niches?")
st.caption(
    "Mechanic × category pairs. **Opportunity score** = z(rating) + z(wishlists / owned copies) "
    "− z(log number of games): loved, wanted, yet rarely published."
)
f1, f2 = st.columns([1, 2])
min_support = f1.slider("Minimum reliable games per niche", 3, 20, 3)
categories = f2.multiselect("Categories", sorted(niches.category_name.unique()))
view = niches[niches.n_games_reliable >= min_support]
if categories:
    view = view[view.category_name.isin(categories)]
top_ids = set(view.nsmallest(10, "opportunity_rank").index)
is_top = view.index.isin(top_ids)

fig = go.Figure()
for mask, color, name in [(~is_top, T["dim"], "Other niches"), (is_top, T["series"], "Top 10 opportunities")]:
    d = view[mask]
    fig.add_trace(
        go.Scatter(
            x=d.n_games,
            y=d.avg_rating,
            mode="markers",
            name=name,
            marker=dict(
                size=(8 + 30 * d.wish_to_own_ratio.clip(upper=1)).tolist(),
                color=color,
                opacity=0.9,
                line=dict(width=2, color=T["surface"]),
            ),
            customdata=d[["mechanic_name", "category_name", "wish_to_own_ratio", "opportunity_score"]],
            hovertemplate="<b>%{customdata[0]}</b> × <b>%{customdata[1]}</b><br>games: %{x}"
            "<br>avg rating: %{y:.2f}<br>wish/own: %{customdata[2]:.2f}"
            "<br>score: %{customdata[3]:+.2f}<extra></extra>",
        )
    )
style(
    fig,
    height=460,
    title="Supply vs quality (bubble size = wishlists per owned copy)",
    xaxis_title="Games in the niche (supply, log scale)",
    yaxis_title="Average rating",
    showlegend=True,
    legend=dict(orientation="h", y=1.08, x=1, xanchor="right", font=dict(color=T["ink2"])),
)
fig.update_xaxes(type="log")
st.plotly_chart(fig, width="stretch")

st.subheader("Top opportunities")
st.dataframe(
    view.nsmallest(15, "opportunity_rank")[
        [
            "opportunity_rank",
            "mechanic_name",
            "category_name",
            "n_games",
            "avg_rating",
            "wish_to_own_ratio",
            "opportunity_score",
        ]
    ],
    hide_index=True,
    width="stretch",
)

# --------------------------------------------------------------------------- segments
st.header("5 · Which kinds of games make up the market? (K-means segmentation)")
if table_exists("marts.cluster_profiles"):
    profiles = query("SELECT * FROM marts.cluster_profiles ORDER BY segment_id")
    selection = query("SELECT * FROM marts.cluster_selection ORDER BY k")
    st.caption(
        "K-means on duration (log), complexity and popularity (log ratings), released games with "
        "≥ 30 ratings. k chosen by silhouette (k ≥ 3), cross-checked with the elbow of the inertia "
        "curve. Each segment is named from its centroid."
    )
    s_left, s_right = st.columns([3, 2])
    with s_left:
        games_seg = query(
            "SELECT c.segment_id, c.segment_name, g.game_name, g.playing_time, f.weight_complexity, "
            "f.users_rated FROM marts.game_clusters c JOIN dw.dim_game g USING (game_id) "
            "JOIN dw.fact_game_latest f USING (game_id)"
        )
        fig = go.Figure()
        palette = T["cat"] if len(profiles) <= 3 else [T["series"]] * len(profiles)
        for (_, p), color in zip(profiles.iterrows(), palette, strict=False):
            d = games_seg[games_seg.segment_id == p.segment_id]
            fig.add_trace(
                go.Scatter(
                    x=d.weight_complexity,
                    y=d.playing_time,
                    mode="markers",
                    name=p.segment_name,
                    marker=dict(size=8, color=color, opacity=0.75, line=dict(width=1, color=T["surface"])),
                    customdata=d[["game_name", "users_rated"]],
                    hovertemplate="<b>%{customdata[0]}</b><br>complexity: %{x:.2f}<br>"
                    "duration: %{y} min<br>ratings: %{customdata[1]:,}<extra>" + p.segment_name + "</extra>",
                )
            )
        style(
            fig,
            height=420,
            title="Games by segment: complexity vs duration",
            xaxis_title="Complexity (1-5)",
            yaxis_title="Playing time (min, log scale)",
            showlegend=True,
            margin=dict(l=8, r=16, t=72, b=8),
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(color=T["ink2"])),
        )
        fig.update_yaxes(type="log")
        st.plotly_chart(fig, width="stretch")
    with s_right:
        for metric_name, title in [
            ("silhouette", "Silhouette (higher = better)"),
            ("inertia", "Inertia (elbow)"),
        ]:
            chosen = selection[selection.is_chosen]
            fig = go.Figure(
                go.Scatter(
                    x=selection.k,
                    y=selection[metric_name],
                    mode="lines+markers",
                    line=dict(color=T["series"], width=2),
                    marker=dict(size=8, color=T["series"]),
                    hovertemplate="k=%{x}<br>" + metric_name + ": %{y:.3f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=chosen.k,
                    y=chosen[metric_name],
                    mode="markers+text",
                    text=["  chosen"],
                    textposition="middle right",
                    textfont=dict(color=T["ink2"], size=11),
                    marker=dict(size=14, color=T["series"], line=dict(width=2, color=T["surface"])),
                    hoverinfo="skip",
                )
            )
            style(fig, height=200, title=title, xaxis_title="k")
            low, high = selection[metric_name].min(), selection[metric_name].max()
            pad = (high - low) * 0.25 or 0.1
            fig.update_yaxes(range=[low - pad, high + pad])  # head-room for the "chosen" label
            st.plotly_chart(fig, width="stretch")
    st.dataframe(
        profiles.rename(columns={"segment_name": "segment"}).drop(columns="segment_id"),
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("Segmentation not computed yet (needs at least 50 reliable games).")

# --------------------------------------------------------------------------- history
st.header("6 · Who is climbing the ranking? (weekly snapshots)")
if len(movers):
    climbers = movers.nlargest(12, "rank_change").sort_values("rank_change")
    fig = go.Figure(
        go.Bar(
            x=climbers.rank_change,
            y=climbers.game_name,
            orientation="h",
            marker_color=T["series"],
            customdata=climbers[["previous_rank", "latest_rank", "new_ratings"]],
            hovertemplate="<b>%{y}</b><br>rank %{customdata[0]} → %{customdata[1]}"
            "<br>new ratings: %{customdata[2]:,}<extra></extra>",
        )
    )
    first, last = movers.previous_date.min(), movers.latest_date.max()
    style(fig, height=420, title=f"Places gained in the BGG ranking ({first} → {last})")
    st.plotly_chart(fig, width="stretch")
    table_view(movers.sort_values("rank_change", ascending=False))
else:
    st.caption("Only one snapshot loaded so far: run `python -m bgg_pipeline refresh` next week.")

st.divider()
st.caption(
    "Data: [BoardGameGeek](https://boardgamegeek.com) XML API2 — **Powered by BGG**. "
    "Pipeline & methodology: see README."
)
