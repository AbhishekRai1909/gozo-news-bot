"""
Gozo Cabs — Intercity Business & Customer Intelligence Bot
============================================================
Tracks two distinct kinds of signal for Gozo's intercity business:

1. REGULATORY & OPS  — things that change cost, legality, or feasibility
   (permits, fuel, EV policy, competitor moves, highway disruption)
2. CUSTOMER INSIGHTS — things that change demand or trust
   (events driving travel demand, corporate/campus expansion opening new
   corridors, seasonal/tourism triggers, brand trust & safety sentiment,
   and voice-of-customer sentiment on aggregators)

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

# Each category belongs to a GROUP ("Regulatory & Ops" or "Customer Insights"),
# carries a display icon/signal label, and a targeted Google News query.
# Queries are deliberately scoped with transport-context keywords so that
# unrelated news (e.g. a celebrity's personal legal case) doesn't leak in
# just because it shares a broad term like "case" or "arrest".
SEARCH_QUERIES = {
    # ---------------- REGULATORY & OPS ----------------
    "Regulatory & Policy": {
        "group": "Regulatory & Ops",
        "signal": "⚖️ Risk",
        "query": '("cab aggregator" OR "app-based taxi") AND ("MoRTH" OR "Motor Vehicle Act" '
                 'OR "transport ministry" OR "RTO" OR "STA" OR "taxi ban" OR "licence suspended" '
                 'OR "aggregator rules" OR "surge pricing")',
    },
    "Intercity Permits & Highways": {
        "group": "Regulatory & Ops",
        "signal": "🛣️ Ops",
        "query": '("All India Tourist Permit" OR "AITP" OR "commercial vehicle fitness" '
                 'OR "interstate permit" OR "national highway" OR "NHAI" OR "expressway opening" '
                 'OR "toll hike" OR "FASTag")',
    },
    "Fuel & Operating Costs": {
        "group": "Regulatory & Ops",
        "signal": "⛽ Cost",
        "query": '("petrol price" OR "diesel price" OR "CNG price" OR "fuel price hike" '
                 'OR "LPG price") AND (India)',
    },
    "EV & Green Mobility Policy": {
        "group": "Regulatory & Ops",
        "signal": "🔋 Policy",
        "query": '("EV policy" OR "electric vehicle subsidy" OR "FAME scheme" '
                 'OR "electric taxi" OR "EV fleet") AND (India OR state)',
    },
    "Competitor Moves": {
        "group": "Regulatory & Ops",
        "signal": "🎯 Competitive",
        "query": '("Ola" OR "Uber" OR "InDrive" OR "BluSmart" OR "Rapido") AND '
                 '("intercity" OR "outstation" OR "funding" OR "expansion" OR "layoffs" OR "fare hike")',
    },
    "Travel Disruption & Delays": {
        "group": "Regulatory & Ops",
        "signal": "🚧 Disruption",
        "query": '("highway closure" OR "landslide" OR "flood alert" OR "road blocked" '
                 'OR "train cancelled" OR "flight cancelled" OR "transport strike" OR "bandh") AND India',
    },

    # ---------------- CUSTOMER INSIGHTS ----------------
    "Demand Triggers – Events": {
        "group": "Customer Insights",
        "signal": "📈 Demand",
        "query": '("IPL match" OR "cricket match" OR "concert" OR "music festival" '
                 'OR "election rally" OR "trade expo" OR "conference") AND India '
                 'AND (tickets OR crowd OR venue OR travel)',
    },
    "Corporate & Campus Expansion": {
        "group": "Customer Insights",
        "signal": "🏢 Demand",
        "query": '("signs MoU" OR "new campus" OR "industrial park" OR "IT park" '
                 'OR "semiconductor" OR "office opens" OR "SEZ" OR "manufacturing plant") '
                 'AND India AND (jobs OR investment OR employees)',
    },
    "Tourism & Seasonal Demand": {
        "group": "Customer Insights",
        "signal": "🎉 Demand",
        "query": '("tourist season" OR "wedding season" OR "pilgrimage" OR "festival rush" '
                 'OR "Kumbh" OR "Diwali travel" OR "Holi travel" OR "holiday rush") AND India',
    },
    "Brand Trust & Safety Sentiment": {
        "group": "Customer Insights",
        "signal": "🛡️ Trust",
        "query": '("cab driver" OR "taxi driver" OR "app-based cab" OR "ride-hailing driver" '
                 'OR "aggregator driver" OR "cab passenger") AND '
                 '("assault" OR "harassment" OR "molestation" OR "safety complaint" '
                 'OR "misconduct" OR "overcharging" OR "refused ride")',
    },
    "Aggregator Customer Sentiment": {
        "group": "Customer Insights",
        "signal": "💬 Sentiment",
        "query": '("Ola" OR "Uber" OR "Rapido" OR "cab service" OR "ride hailing") AND '
                 '("customer complaint" OR "surge pricing anger" OR "customer service" '
                 'OR "cancellation fee" OR "consumer forum" OR "viral video")',
    },
}

GROUPS = ["Regulatory & Ops", "Customer Insights"]

HIGH_IMPACT_KEYWORDS = [
    "ban", "banned", "suspended", "suspension", "strike", "shutdown", "halt",
    "court order", "supreme court", "high court", "penalty", "fine imposed",
    "licence cancelled", "license cancelled", "seized", "protest", "assault",
    "harassment", "molestation",
]
MEDIUM_IMPACT_KEYWORDS = [
    "hike", "increase", "new rule", "guideline", "notification", "draft policy",
    "subsidy", "scheme launched", "toll", "fare revision", "complaint",
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

st.title("🚕 Gozo Cabs: Intercity Business & Customer Intelligence")
st.markdown(
    "Two lenses on the same feed: **Regulatory & Ops** (cost, legality, feasibility) and "
    "**Customer Insights** (demand triggers and brand trust signals)."
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

with st.spinner("Fetching latest regulatory, market, and customer signal news..."):
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

demand_signals = [a for a in filtered if a["group"] == "Customer Insights" and "Demand" in a["signal"]]
trust_signals = [a for a in filtered if a["signal"] == "🛡️ Trust"]
regulatory_signals = [a for a in filtered if a["group"] == "Regulatory & Ops"]

# --- Top metrics ---
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Total articles", len(filtered))
col_m2.metric("📈 Demand signals", len(demand_signals))
col_m3.metric("🛡️ Trust/safety signals", len(trust_signals))
col_m4.metric("🔴 High impact", sum(1 for a in filtered if a["impact"] == "High"))

st.divider()

tab_overview, tab_customer, tab_regulatory, tab_all = st.tabs(
    ["🔎 Overview", "👥 Customer Insights", "🏛️ Regulatory & Ops", "📋 All News"]
)

with tab_overview:
    st.subheader("Top demand signals")
    if demand_signals:
        render_article_list(demand_signals[:3])
    else:
        st.info("No demand-trigger news in the current window/filters.")

    st.subheader("Top trust & safety signals")
    if trust_signals:
        render_article_list(trust_signals[:3])
    else:
        st.info("No brand trust/safety news in the current window/filters.")

    st.subheader("📊 Signal mix")
    if filtered:
        df_counts = (
            pd.DataFrame(filtered)["category"]
            .value_counts()
            .rename_axis("Category")
            .reset_index(name="Articles")
        )
        st.dataframe(df_counts, hide_index=True, use_container_width=True)

with tab_customer:
    customer_articles = [a for a in filtered if a["group"] == "Customer Insights"]
    if customer_articles:
        render_article_list(customer_articles)
    else:
        st.info("No customer-insight articles match the current filters.")

with tab_regulatory:
    if regulatory_signals:
        render_article_list(regulatory_signals)
    else:
        st.info("No regulatory/ops articles match the current filters.")

with tab_all:
    if filtered:
        render_article_list(filtered)
    else:
        st.info("No articles match the current filters.")

    if filtered:
        export_df = pd.DataFrame(filtered)[
            ["published_dt", "group", "category", "signal", "impact", "source", "title", "link"]
        ]
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download filtered results as CSV",
            data=csv,
            file_name=f"gozo_intel_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

st.divider()
st.caption(f"Last synchronized: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Data via Google News RSS")
