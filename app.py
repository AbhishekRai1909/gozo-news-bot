import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime
import time

st.set_page_config(page_title="Gozo Regulatory Intel", page_icon="🏛️", layout="wide")

# We use three distinct search buckets to catch all angles of government news
SEARCH_QUERIES = {
    "National Policy": '"cab aggregator" AND ("MoRTH" OR "Motor Vehicle Act" OR "transport ministry")',
    "State Level Orders": '("transport authority" OR "RTO" OR "STA") AND ("taxi ban" OR "licence suspended" OR "aggregator rules")',
    "Intercity & Permits": '("All India Tourist Permit" OR "AITP" OR "commercial vehicle fitness")'
}

@st.cache_data(ttl=3600)
def get_pan_india_news():
    all_articles = []
    seen_links = set()
    
    # Run a separate search for each category
    for category, query in SEARCH_QUERIES.items():
        encoded_query = urllib.parse.quote(f"{query} when:7d")
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if entry.link not in seen_links:
                # Tag the article with its category
                entry['gozo_category'] = category
                all_articles.append(entry)
                seen_links.add(entry.link)
                
        # Pause briefly to respect Google's API limits
        time.sleep(1)
        
    # Sort all combined articles by newest first (if published date is available)
    all_articles.sort(key=lambda x: x.get('published_parsed', time.gmtime()), reverse=True)
    return all_articles

st.title("🏛️ Gozo Cabs: Pan-India Regulatory Intel")
st.markdown("Live tracking of state transport authority orders, MoRTH guidelines, and aggregator bans.")

if st.button("🔄 Refresh Pan-India News"):
    st.cache_data.clear()

st.divider()

articles = get_pan_india_news()

if not articles:
    st.info("No major regulatory news detected in the last 7 days.")
else:
    # Use Streamlit columns to organize the layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        for article in articles:
            source = article.source.title if hasattr(article, 'source') else "Google News"
            category_tag = article.get('gozo_category', 'General')
            
            with st.container():
                st.caption(f"📰 **{source}** | 🏷️ {category_tag}")
                st.subheader(article.title)
                st.markdown(f"[Read Full Report]({article.link})")
                st.divider()
                
    with col2:
        st.subheader("Data Sources")
        st.write("Tracking active keywords for:")
        st.markdown("- MoRTH Guidelines")
        st.markdown("- RTO/STA State Orders")
        st.markdown("- AITP Regulations")
        st.markdown("- Aggregator Licence Bans")

st.caption(f"Last synchronized: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
