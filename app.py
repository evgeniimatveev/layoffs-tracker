import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

DB_PATH = Path("data/layoffs.duckdb")

st.set_page_config(
    page_title="Tech Layoffs Tracker",
    page_icon="📉",
    layout="wide",
)

@st.cache_resource
def get_conn():
    return duckdb.connect(str(DB_PATH), read_only=True)

@st.cache_data(ttl=3600)
def query(sql: str) -> pd.DataFrame:
    return get_conn().execute(sql).df()


def fmt_number(n: float) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(int(n))


# ── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.title("Filters")

years = query("SELECT DISTINCT year FROM layoffs WHERE year IS NOT NULL ORDER BY year")["year"].tolist()
sel_years = st.sidebar.multiselect("Year", years, default=years)

industries = query("SELECT DISTINCT industry FROM layoffs WHERE industry IS NOT NULL ORDER BY industry")["industry"].tolist()
sel_industries = st.sidebar.multiselect("Industry", industries, default=industries)

countries = query("SELECT DISTINCT country FROM layoffs WHERE country IS NOT NULL ORDER BY country")["country"].tolist()
sel_countries = st.sidebar.multiselect("Country", countries, default=countries)

# build WHERE clause — all subsequent queries append AND conditions
years_sql  = ",".join(f"'{y}'" for y in sel_years)  if sel_years  else "NULL"
ind_sql    = ",".join(f"'{i}'" for i in sel_industries) if sel_industries else "NULL"
ctry_sql   = ",".join(f"'{c}'" for c in sel_countries)  if sel_countries  else "NULL"

where = f"""
    WHERE year IN ({years_sql})
      AND (industry IN ({ind_sql}) OR industry IS NULL)
      AND (country IN ({ctry_sql}) OR country IS NULL)
"""

# ── Header ───────────────────────────────────────────────────────────────────
st.title("📉 Tech Layoffs Tracker")
st.caption("Data sourced from [layoffs.fyi](https://layoffs.fyi) via Kaggle · updated weekly")

# ── KPI cards ────────────────────────────────────────────────────────────────
kpis = query(f"""
    SELECT
        COUNT(*)                AS events,
        SUM(total_laid_off)     AS total_laid_off,
        COUNT(DISTINCT company) AS companies,
        COUNT(DISTINCT country) AS countries
    FROM layoffs {where}
""").iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Layoff Events",   f"{int(kpis['events']):,}")
c2.metric("People Laid Off", fmt_number(kpis["total_laid_off"] or 0))
c3.metric("Companies",       f"{int(kpis['companies']):,}")
c4.metric("Countries",       f"{int(kpis['countries']):,}")

st.divider()

# ── Timeline ─────────────────────────────────────────────────────────────────
st.subheader("Layoffs Over Time")

timeline = query(f"""
    SELECT month, SUM(total_laid_off) AS laid_off
    FROM layoffs {where}
      AND total_laid_off IS NOT NULL
      AND month IS NOT NULL
    GROUP BY month ORDER BY month
""")

if not timeline.empty:
    fig = px.bar(
        timeline, x="month", y="laid_off",
        labels={"month": "Month", "laid_off": "People Laid Off"},
        color_discrete_sequence=["#e74c3c"],
    )
    fig.update_layout(xaxis_tickangle=-45, height=350, margin=dict(t=20))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Industry + Top companies ──────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("By Industry")
    by_industry = query(f"""
        SELECT industry, SUM(total_laid_off) AS laid_off
        FROM layoffs {where}
          AND industry IS NOT NULL
          AND total_laid_off IS NOT NULL
        GROUP BY industry ORDER BY laid_off DESC LIMIT 15
    """)
    if not by_industry.empty:
        fig2 = px.bar(
            by_industry, x="laid_off", y="industry", orientation="h",
            labels={"laid_off": "People Laid Off", "industry": ""},
            color_discrete_sequence=["#3498db"],
        )
        fig2.update_layout(height=420, margin=dict(t=20), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig2, use_container_width=True)

with col_right:
    st.subheader("Top 15 Companies")
    by_company = query(f"""
        SELECT company, SUM(total_laid_off) AS laid_off
        FROM layoffs {where}
          AND total_laid_off IS NOT NULL
        GROUP BY company ORDER BY laid_off DESC LIMIT 15
    """)
    if not by_company.empty:
        fig3 = px.bar(
            by_company, x="laid_off", y="company", orientation="h",
            labels={"laid_off": "People Laid Off", "company": ""},
            color_discrete_sequence=["#9b59b6"],
        )
        fig3.update_layout(height=420, margin=dict(t=20), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Funding Stage ─────────────────────────────────────────────────────────────
st.subheader("Layoffs by Funding Stage")

by_stage = query(f"""
    SELECT stage, COUNT(*) AS events, SUM(total_laid_off) AS laid_off
    FROM layoffs {where}
      AND stage IS NOT NULL
      AND total_laid_off IS NOT NULL
    GROUP BY stage ORDER BY laid_off DESC
""")

if not by_stage.empty:
    fig4 = px.scatter(
        by_stage, x="events", y="laid_off", text="stage", size="laid_off",
        labels={"events": "Number of Events", "laid_off": "Total Laid Off"},
        color_discrete_sequence=["#e67e22"],
    )
    fig4.update_traces(textposition="top center")
    fig4.update_layout(height=380, margin=dict(t=20))
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Country map ───────────────────────────────────────────────────────────────
st.subheader("Global Distribution")

by_country = query(f"""
    SELECT country, SUM(total_laid_off) AS laid_off
    FROM layoffs {where}
      AND country IS NOT NULL
      AND total_laid_off IS NOT NULL
    GROUP BY country ORDER BY laid_off DESC
""")

if not by_country.empty:
    fig5 = px.choropleth(
        by_country, locations="country", locationmode="country names",
        color="laid_off", color_continuous_scale="Reds",
        labels={"laid_off": "People Laid Off"},
    )
    fig5.update_layout(
        height=450,
        margin=dict(t=20, b=0, l=0, r=0),
        paper_bgcolor="#0e1117",
        geo=dict(
            bgcolor="#0e1117",
            landcolor="#1e2130",
            oceancolor="#0e1117",
            showocean=True,
            lakecolor="#0e1117",
            showlakes=True,
            framecolor="#333",
        ),
    )
    st.plotly_chart(fig5, use_container_width=True)

st.divider()

# ── Raw data ──────────────────────────────────────────────────────────────────
with st.expander("Raw Data"):
    raw = query(f"""
        SELECT company, industry, country, stage,
               total_laid_off, percentage, date_layoffs
        FROM layoffs {where}
        ORDER BY date_layoffs DESC NULLS LAST
        LIMIT 500
    """)
    st.dataframe(raw, use_container_width=True)
