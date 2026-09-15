import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Gozo Mobility Intel", page_icon="🚖", layout="centered")

# Search Keywords for Indian taxi and mobility news
KEYWORDS = '"Gozo Cabs" OR "taxi service" OR "cab aggregator" OR "intercity cabs" OR "Uber India" OR "Ola"'

@st.cache_data(ttl=3600)
def get_mobility_news():
    encoded_query = urllib.parse.quote(f"{KEYWORDS} when:24h")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(rss_url).entries

st.title("🚖 Gozo Cabs Market Intel")
st.markdown("Live updates on the Indian taxi and intercity mobility ecosystem.")

if st.button("🔄 Refresh News Now"):
    st.cache_data.clear()

st.divider()

articles = get_mobility_news()

if not articles:
    st.info("No breaking news in the Indian mobility sector in the last 24 hours.")
else:
    for article in articles:
        source_name = article.source.title if hasattr(article, 'source') else "Google News"
        with st.container():
            st.caption(f"📰 **{source_name}**")
            st.subheader(article.title)
            st.markdown(f"[Read Full Article]({article.link})")
            st.divider()

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
