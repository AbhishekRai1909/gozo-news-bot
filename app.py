"""
Gozo Cabs — Intercity Business & Sales Intelligence Bot
==========================================================
Five lenses, ordered by how directly they drive revenue decisions:

1. DESTINATION WATCH     — news from the actual cities/corridors Gozo sells
                           (festivals, weather, road closures, tourist rush)
2. CORPORATE TRAVEL LEADS— businesses signalling they need a travel partner
3. COMPETITOR INTEL      — named competitors (Savaari, Cab Bazaar, Ola,
                           Uber, Rapido, BluSmart, InDrive)
4. TRUST & SENTIMENT     — industry-wide safety incidents & customer sentiment
5. REGULATORY & OPS      — cost/compliance signals (de-emphasized, own tab)

Run with:  streamlit run gozo_intel_bot.py
"""

import time
import urllib.parse
from datetime import datetime

import feedparser
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Gozo Intercity Intel", page_icon="🚕", layout="wide")

LOOKBACK_DAYS_DEFAULT = 7

# Destination clusters are built from Gozo's own top-cities / popular-routes
# list (gozocabs.com) so "recent developments" actually maps to corridors
# Gozo sells, not generic national news.
SEARCH_QUERIES = {
    # ---------------- DESTINATION WATCH ----------------
    "Destination Watch – North & Hill Circuit": {
        "group": "Destination Watch",
        "signal": "📍 Destination",
        "query": '("Delhi" OR "Jaipur" OR "Gurugram" OR "Noida" OR "Chandigarh" '
                 'OR "Haridwar" OR "Dehradun" OR "Rishikesh" OR "Shimla" OR "Manali") '
                 'AND ("festival" OR "traffic advisory" OR "highway" OR "weather alert" '
                 'OR "tourist rush" OR "wedding season" OR "road closed" OR "VIP movement")',
    },
    "Destination Watch – West & Goa Circuit": {
        "group": "Destination Watch",
        "signal": "📍 Destination",
        "query": '("Mumbai" OR "Pune" OR "Nashik" OR "Pimpri-Chinchwad" OR "Goa") '
                 'AND ("festival" OR "traffic advisory" OR "highway" OR "weather alert" '
                 'OR "tourist rush" OR "monsoon" OR "road closed")',
    },
    "Destination Watch – South Metros": {
        "group": "Destination Watch",
        "signal": "📍 Destination",
        "query": '("Bengaluru" OR "Chennai" OR "Hyderabad" OR "Mysuru") '
                 'AND ("festival" OR "traffic advisory" OR "highway" OR "weather alert" '
                 'OR "tourist rush" OR "road closed")',
    },
    "Destination Watch – Central India": {
        "group": "Destination Watch",
        "signal": "📍 Destination",
        "query": '("Bhopal" OR "Indore") AND '
                 '("festival" OR "traffic advisory" OR "highway" OR "weather alert" OR "road closed")',
    },

    # ---------------- CORPORATE TRAVEL LEADS ----------------
    "Corporate Travel RFPs & Leads": {
        "group": "Corporate Travel Leads",
        "signal": "💼 Lead",
        "query": '("travel management company" OR "corporate travel partner" '
                 'OR "ground transportation partner" OR "employee transportation solution" '
                 'OR "pan-India travel partner" OR "travel management partner") AND India '
                 'AND (appoints OR empanelment OR partners OR onboards OR selects OR tender)',
    },

    # ---------------- COMPETITOR INTEL ----------------
    "Competitor – Savaari & Cab Bazaar": {
        "group": "Competitor Intel",
        "signal": "🎯 Competitor",
        "query": '(("Savaari" AND ("cab" OR "car rental" OR "outstation" OR "taxi")) '
                 'OR "Cab Bazaar" OR "CabBazaar")',
    },
    "Competitor – Major Aggregators": {
        "group": "Competitor Intel",
        "signal": "🎯 Competitor",
        "query": '("Ola" OR "Uber" OR "InDrive" OR "BluSmart" OR "Rapido") AND '
                 '("intercity" OR "outstation" OR "funding" OR "expansion" OR "layoffs" OR "fare hike" '
                 'OR "new feature" OR "partnership")',
    },

    # ---------------- TRUST & SENTIMENT ----------------
    "Brand Trust & Safety Sentiment": {
        "group": "Trust & Sentiment",
        "signal": "🛡️ Trust",
        "query": '("cab driver" OR "taxi driver" OR "app-based cab" OR "ride-hailing driver" '
                 'OR "aggregator driver" OR "cab passenger") AND '
                 '("assault" OR "harassment" OR "molestation" OR "safety complaint" '
                 'OR "misconduct" OR "overcharging" OR "refused ride")',
    },
    "Aggregator Customer Sentiment": {
        "group": "Trust & Sentiment",
        "signal": "💬 Sentiment",
        "query": '("Ola" OR "Uber" OR "Rapido" OR "Savaari" OR "cab service" OR "ride hailing") AND '
                 '("customer complaint" OR "surge pricing anger" OR "customer service" '
                 'OR "cancellation fee" OR "consumer forum" OR "viral video")',
    },

    # ---------------- REGULATORY & OPS (de-emphasized) ----------------
    "Regulatory & Policy": {
        "group": "Regulatory & Ops",
        "signal": "⚖️ Risk",
        "query": '("cab aggregator" OR "app-based taxi") AND ("MoRTH" OR "Motor Vehicle Act" '
                 'OR "transport ministry" OR "RTO" OR "STA" OR "taxi ban" OR "licence suspended" '
                 'OR "aggregator rules" OR "surge pricing")',
    },
    "Highways & Travel Disruption": {
        "group": "Regulatory & Ops",
        "signal": "🚧 Ops",
        "query": '("national highway" OR "NHAI" OR "expressway" OR "toll hike" OR "FASTag" '
                 'OR "highway closure" OR "landslide" OR "flood alert" OR "road blocked" '
                 'OR "train cancelled" OR "flight cancelled" OR "transport strike" OR "bandh") AND India',
    },
    "Costs & Fleet Policy": {
        "group": "Regulatory & Ops",
        "signal": "⛽ Cost",
        "query": '("petrol price" OR "diesel price" OR "CNG price" OR "fuel price hike" '
                 'OR "LPG price" OR "EV policy" OR "electric vehicle subsidy" OR "FAME scheme" '
                 'OR "electric taxi" OR "EV fleet") AND India',
    },
}

GROUPS = [
    "Destination Watch",
    "Corporate Travel Leads",
    "Competitor Intel",
    "Trust & Sentiment",
    "Regulatory & Ops",
]

HIGH_IMPACT_KEYWORDS = [
    "ban", "banned", "suspended", "suspension", "strike", "shutdown", "halt",
    "court order", "supreme court", "high court", "penalty", "fine imposed",
    "licence cancelled", "license cancelled", "seized", "protest", "assault",
    "harassment", "molestation", "funding", "appoints", "empanelment", "tender",
]
MEDIUM_IMPACT_KEYWORDS = [
    "hike", "increase", "new rule", "guideline", "notification", "draft policy",
    "subsidy", "scheme launched", "toll", "fare revision", "complaint",
    "festival", "tourist rush", "wedding season", "traffic advisory",
]


# ----------------------------------------------------------------------------
# DATA FETCHING
# ----------------------------------------------------------------------------

def build_rss_url(query: str, lookback_days: int) -> str:
    encoded_query = urllib.parse.quote_plus(f"{query} when:{lookback_days}d")
    return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"


def score_impact(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(kw in text for kw in HIGH_IMPACT_KEYWORDS):
        return "High"
    if any(kw in text for kw in MEDIUM_IMPACT_KEYWORDS):
        return "Medium"
    return "Low"


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_news(lookback_days: int = LOOKBACK_DAYS_DEFAULT):
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
            published_dt = datetime(*published_struct[:6]) if published_struct else None

            all_articles.append({
                "title": title,
                "link": link,
                "source": source,
                "category": category,
                "group": cfg["group"],
                "signal": cfg["signal"],
                "published_dt": published_dt,
                "impact": score_impact(title, summary),
                "summary": summary,
            })

        time.sleep(1)  # be polite to Google News

    all_articles.sort(key=lambda a: a["published_dt"] or datetime(1970, 1, 1), reverse=True)
    return all_articles, fetch_errors


def render_article_list(article_list):
    if not article_list:
        st.info("No articles match the current filters.")
        return
    for a in article_list:
        impact_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}[a["impact"]]
        date_str = a["published_dt"].strftime("%d %b %Y, %H:%M") if a["published_dt"] else "Date unknown"
        with st.container():
            st.caption(
                f"📰 **{a['source']}** | 🏷️ {a['category']} | {a['signal']} | "
                f"{impact_color} {a['impact']} | 🕒 {date_str}"
            )
            st.subheader(a["title"])
            st.markdown(f"[Read Full Report]({a['link']})")
            st.divider()


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

st.title("🚕 Gozo Cabs: Intercity Business & Sales Intelligence")
st.markdown(
    "Built around what moves the business: **where people are actually traveling**, "
    "**who's shopping for a travel partner**, and **what Savaari, Cab Bazaar & the aggregators are doing**."
)

with st.sidebar:
    st.header("⚙️ Filters")
    lookback_days = st.slider("Lookback window (days)", 1, 30, LOOKBACK_DAYS_DEFAULT)

    group_filter = st.multiselect("Group", options=GROUPS, default=GROUPS)

    available_categories = [c for c, cfg in SEARCH_QUERIES.items() if cfg["group"] in group_filter]
    selected_categories = st.multiselect(
        "Categories", options=available_categories, default=available_categories
    )

    impact_filter = st.multiselect("Impact level", options=["High", "Medium", "Low"],
                                    default=["High", "Medium", "Low"])

    keyword_filter = st.text_input("Keyword search (optional)")

    st.divider()
    if st.button("🔄 Refresh all feeds"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    with st.expander("ℹ️ About the Corporate Leads tab"):
        st.caption(
            "Google News rarely covers private RFP/tender activity for travel management "
            "vendors — that mostly lives on government tender portals (GeM), LinkedIn, and "
            "trade press (ET TravelWorld, TravelBizMonitor). This tab catches published "
            "'appoints/onboards' announcements, but treat a thin result as expected, not broken."
        )

st.divider()

with st.spinner("Fetching destination, lead, and competitor signals..."):
    articles, fetch_errors = get_all_news(lookback_days)

if fetch_errors:
    with st.expander(f"⚠️ {len(fetch_errors)} feed notice(s) — click to view", expanded=False):
        for err in fetch_errors:
            st.caption(err)

filtered = [
    a for a in articles
    if a["group"] in group_filter
    and a["category"] in selected_categories
    and a["impact"] in impact_filter
    and (keyword_filter.lower() in (a["title"] + a["summary"]).lower() if keyword_filter else True)
]

destination_signals = [a for a in filtered if a["group"] == "Destination Watch"]
lead_signals = [a for a in filtered if a["group"] == "Corporate Travel Leads"]
competitor_signals = [a for a in filtered if a["group"] == "Competitor Intel"]
trust_signals = [a for a in filtered if a["group"] == "Trust & Sentiment"]
regulatory_signals = [a for a in filtered if a["group"] == "Regulatory & Ops"]

# --- Top metrics ---
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("📍 Destination", len(destination_signals))
col_m2.metric("💼 Leads", len(lead_signals))
col_m3.metric("🎯 Competitor", len(competitor_signals))
col_m4.metric("🛡️ Trust/Sentiment", len(trust_signals))
col_m5.metric("🔴 High impact", sum(1 for a in filtered if a["impact"] == "High"))

st.divider()

tab_overview, tab_dest, tab_leads, tab_comp, tab_trust, tab_ops = st.tabs(
    ["🔎 Overview", "📍 Destination Watch", "💼 Corporate Leads",
     "🎯 Competitor Intel", "🛡️ Trust & Sentiment", "🏛️ Regulatory & Ops"]
)

with tab_overview:
    st.subheader("💼 Fresh leads")
    render_article_list(lead_signals[:5])

    st.subheader("🎯 Competitor moves")
    render_article_list(competitor_signals[:5])

    st.subheader("📍 Destination signals")
    render_article_list(destination_signals[:5])

    st.subheader("📊 Signal mix")
    if filtered:
        df_counts = (
            pd.DataFrame(filtered)["category"]
            .value_counts()
            .rename_axis("Category")
            .reset_index(name="Articles")
        )
        st.dataframe(df_counts, hide_index=True, use_container_width=True)

with tab_dest:
    render_article_list(destination_signals)

with tab_leads:
    render_article_list(lead_signals)

with tab_comp:
    render_article_list(competitor_signals)

with tab_trust:
    render_article_list(trust_signals)

with tab_ops:
    render_article_list(regulatory_signals)

    if filtered:
        export_df = pd.DataFrame(filtered)[
            ["published_dt", "group", "category", "signal", "impact", "source", "title", "link"]
        ]
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download all filtered results as CSV",
            data=csv,
            file_name=f"gozo_intel_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

st.divider()
st.caption(f"Last synchronized: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Data via Google News RSS")
