import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime

st.set_page_config(page_title="Gozo Intercity Intel", page_icon="🛣️", layout="centered")

# Highly targeted keywords for the outstation/intercity market
INTERCITY_KEYWORDS = (
    '"Gozo Cabs" OR "intercity cabs" OR "outstation taxi" OR '
    '"All India Tourist Permit" OR "MoRTH aggregator" OR "GNSS toll" OR '
    '"Uber Intercity" OR "Savaari" OR "MakeMyTrip cabs"'
)

@st.cache_data(ttl=3600)
def get_intercity_news():
    # URL encodes the query and restricts to Indian English publishers
    encoded_query = urllib.parse.quote(f"{INTERCITY_KEYWORDS} when:7d")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(rss_url).entries

st.title("🛣️ Gozo Cabs: Intercity Market Intel")
st.markdown("Live regulatory, infrastructure, and competitor updates for the Indian outstation market.")

if st.button("🔄 Refresh Intercity News"):
    st.cache_data.clear()

st.divider()

articles = get_intercity_news()

if not articles:
    st.info("No major outstation mobility news detected in the last 7 days.")
else:
    for article in articles:
        source = article.source.title if hasattr(article, 'source') else "Google News"
        
        with st.container():
            st.caption(f"📰 **{source}**")
            st.subheader(article.title)
            st.markdown(f"[Read Full Intelligence Report]({article.link})")
            st.divider()

st.caption(f"Last synchronized: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
