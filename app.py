"""
Gozo Cabs — Intercity Business Intelligence Bot
=================================================
A Streamlit dashboard that pulls together recent news across all the areas
that actually move an intercity cab business: regulation, fuel/toll costs,
highway & infrastructure disruptions, competitor moves, EV/CNG policy, and
seasonal travel-demand triggers.

Run with:  streamlit run gozo_intel_bot.py
"""

import time
import urllib.parse
from datetime import datetime, timedelta

import feedparser
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Gozo Intercity Intel", page_icon="🚕", layout="wide")

# Each category = { query: Google News search string, weight: base impact score }
# Google News RSS supports boolean OR / AND / quoted phrases reasonably well.
SEARCH_QUERIES = {
    "Regulatory & Policy": {
        "query": '("cab aggregator" OR "app-based taxi") AND ("MoRTH" OR "Motor Vehicle Act" '
                 'OR "transport ministry" OR "RTO" OR "STA" OR "taxi ban" OR "licence suspended" '
                 'OR "aggregator rules" OR "surge pricing")',
        "weight": 3,
    },
    "Intercity Permits & Highways": {
        "query": '("All India Tourist Permit" OR "AITP" OR "commercial vehicle fitness" '
                 'OR "interstate permit" OR "national highway" OR "NHAI" OR "expressway opening" '
                 'OR "toll hike" OR "FASTag")',
        "weight": 3,
    },
    "Fuel & Operating Costs": {
        "query": '("petrol price" OR "diesel price" OR "CNG price" OR "fuel price hike" '
                 'OR "LPG price") AND (India)',
        "weight": 2,
    },
    "EV & Green Mobility Policy": {
        "query": '("EV policy" OR "electric vehicle subsidy" OR "FAME scheme" '
                 'OR "electric taxi" OR "EV fleet") AND (India OR state)',
        "weight": 2,
    },
    "Competitor Moves": {
        "query": '("Ola" OR "Uber" OR "InDrive" OR "BluSmart" OR "Rapido") AND '
                 '("intercity" OR "outstation" OR "funding" OR "expansion" OR "layoffs" OR "fare hike")',
        "weight": 2,
    },
    "Travel Demand & Disruption": {
        "query": '("highway closure" OR "road accident blackspot" OR "landslide" OR "flood alert" '
                 'OR "train cancelled" OR "flight cancelled" OR "tourist season") AND India',
        "weight": 1,
    },
}

# Keywords that bump up an article's urgency, regardless of category.
HIGH_IMPACT_KEYWORDS = [
    "ban", "banned", "suspended", "suspension", "strike", "shutdown", "halt",
    "court order", "supreme court", "high court", "penalty", "fine imposed",
    "licence cancelled", "license cancelled", "seized", "protest",
]
MEDIUM_IMPACT_KEYWORDS = [
    "hike", "increase", "new rule", "guideline", "notification", "draft policy",
    "subsidy", "scheme launched", "toll", "fare revision",
]

LOOKBACK_DAYS_DEFAULT = 7


# ----------------------------------------------------------------------------
# DATA FETCHING
# ----------------------------------------------------------------------------

def build_rss_url(query: str, lookback_days: int) -> str:
    encoded_query = urllib.parse.quote_plus(f"{query} when:{lookback_days}d")
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"


def score_impact(title: str, summary: str) -> str:
    """Heuristic impact tag based on keyword hits in title/summary."""
    text = f"{title} {summary}".lower()
    if any(kw in text for kw in HIGH_IMPACT_KEYWORDS):
        return "High"
    if any(kw in text for kw in MEDIUM_IMPACT_KEYWORDS):
        return "Medium"
    return "Low"


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_news(lookback_days: int = LOOKBACK_DAYS_DEFAULT):
    """
    Fetch news across all configured categories.
    Returns (articles: list[dict], fetch_errors: list[str])
    """
    all_articles = []
    seen_links = set()
    fetch_errors = []

    for category, cfg in SEARCH_QUERIES.items():
        rss_url = build_rss_url(cfg["query"], lookback_days)
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            fetch_errors.append(f"{category}: request failed ({e})")
            continue

        if getattr(feed, "bozo", False) and not feed.entries:
            fetch_errors.append(f"{category}: feed parse issue, 0 entries returned")
            continue

        if not feed.entries:
            fetch_errors.append(f"{category}: 0 articles found in lookback window")

        for entry in feed.entries:
            link = getattr(entry, "link", None)
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            title = getattr(entry, "title", "Untitled")
            summary = getattr(entry, "summary", "")
            source = entry.source.title if hasattr(entry, "source") else "Google News"
            published_struct = entry.get("published_parsed")
            published_dt = (
                datetime(*published_struct[:6]) if published_struct else None
            )

            all_articles.append({
                "title": title,
                "link": link,
                "source": source,
                "category": category,
                "published_dt": published_dt,
                "impact": score_impact(title, summary),
                "summary": summary,
            })

        time.sleep(1)  # be polite to Google News

    # Sort newest first; undated articles sink to the bottom.
    all_articles.sort(
        key=lambda a: a["published_dt"] or datetime(1970, 1, 1),
        reverse=True,
    )
    return all_articles, fetch_errors


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

st.title("🚕 Gozo Cabs: Intercity Business Intelligence")
st.markdown(
    "Tracking news that affects Gozo's intercity operations: regulation, permits & highways, "
    "fuel costs, EV policy, competitor moves, and travel-demand disruptions."
)

# --- Sidebar controls ---
with st.sidebar:
    st.header("⚙️ Filters")
    lookback_days = st.slider("Lookback window (days)", 1, 30, LOOKBACK_DAYS_DEFAULT)

    selected_categories = st.multiselect(
        "Categories",
        options=list(SEARCH_QUERIES.keys()),
        default=list(SEARCH_QUERIES.keys()),
    )

    impact_filter = st.multiselect(
        "Impact level",
        options=["High", "Medium", "Low"],
        default=["High", "Medium", "Low"],
    )

    keyword_filter = st.text_input("Keyword search (optional)")

    st.divider()
    if st.button("🔄 Refresh all feeds"):
        st.cache_data.clear()
        st.rerun()

st.divider()

with st.spinner("Fetching latest regulatory & market news..."):
    articles, fetch_errors = get_all_news(lookback_days)

if fetch_errors:
    with st.expander(f"⚠️ {len(fetch_errors)} feed notice(s) — click to view", expanded=False):
        for err in fetch_errors:
            st.caption(err)

# --- Apply filters ---
filtered = [
    a for a in articles
    if a["category"] in selected_categories
    and a["impact"] in impact_filter
    and (keyword_filter.lower() in (a["title"] + a["summary"]).lower() if keyword_filter else True)
]

# --- Summary metrics ---
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Total articles", len(filtered))
col_m2.metric("High impact", sum(1 for a in filtered if a["impact"] == "High"))
col_m3.metric("Categories covered", len({a["category"] for a in filtered}))
col_m4.metric("Window", f"{lookback_days}d")

st.divider()

if not filtered:
    st.info("No articles match the current filters. Try widening the lookback window or clearing filters.")
else:
    col1, col2 = st.columns([3, 1])

    with col1:
        for a in filtered:
            impact_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}[a["impact"]]
            date_str = a["published_dt"].strftime("%d %b %Y, %H:%M") if a["published_dt"] else "Date unknown"

            with st.container():
                st.caption(f"📰 **{a['source']}** | 🏷️ {a['category']} | {impact_color} {a['impact']} impact | 🕒 {date_str}")
                st.subheader(a["title"])
                st.markdown(f"[Read Full Report]({a['link']})")
                st.divider()

    with col2:
        st.subheader("📊 Breakdown by category")
        df_counts = (
            pd.DataFrame(filtered)["category"]
            .value_counts()
            .rename_axis("Category")
            .reset_index(name="Articles")
        )
        st.dataframe(df_counts, hide_index=True, use_container_width=True)

        st.subheader("📥 Export")
        export_df = pd.DataFrame(filtered)[
            ["published_dt", "category", "impact", "source", "title", "link"]
        ]
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download as CSV",
            data=csv,
            file_name=f"gozo_intel_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

        st.subheader("Tracked keywords")
        for cat in SEARCH_QUERIES:
            st.markdown(f"- {cat}")

st.divider()
st.caption(f"Last synchronized: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Data via Google News RSS")
