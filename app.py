"""
Gozo Cabs — Location Activity Calendar
=========================================
One job: tell the team, for each cluster of Gozo's destinations, whether it's
ACTIVE NOW, UPCOMING (with a countdown), or QUIET — based on the real demand
calendar (festivals, pilgrimage seasons, wedding season, tourist peaks).

Event dates below were verified against multiple sources in September 2026
(Hindu-calendar festivals shift every year, so don't trust memorized dates —
re-verify before reusing this file past ~March 2027, or whenever the curated
window runs out).

Run with:  streamlit run gozo_location_calendar.py
"""

from datetime import date, datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Gozo Location Activity Calendar", page_icon="📅", layout="wide")

DESTINATION_GROUPS = [
    "All-India",
    "North & Hill Circuit",   # Delhi, Jaipur, Gurugram, Noida, Chandigarh, Haridwar, Dehradun, Rishikesh, Shimla, Manali
    "West & Goa",             # Mumbai, Pune, Nashik, Pimpri-Chinchwad, Goa
    "South Metros",           # Bengaluru, Chennai, Hyderabad, Mysuru
    "Central India",          # Bhopal, Indore
]

# Curated demand calendar. Dates verified Sept 2026 against SmartPuja's 2026
# Hindu festival calendar and multiple panchang sources. Where an exact date
# isn't fixed by a national calendar (e.g. temple-committee decisions),
# "verified" is False and a re-check note is included.
EVENTS = [
    {
        "name": "Mysuru Dasara",
        "group": "South Metros",
        "start": date(2026, 10, 11),
        "end": date(2026, 10, 20),
        "why": "Mysuru's flagship 10-day festival culminating on Vijayadashami. Expect a major "
               "tourist surge into Mysuru, with strong outstation demand from Bengaluru.",
        "verified": True,
    },
    {
        "name": "Sharad Navratri & Durga Puja",
        "group": "All-India",
        "start": date(2026, 10, 11),
        "end": date(2026, 10, 19),
        "why": "Nine nights of Garba/Durga Puja pandal-hopping. Mostly short-hop city travel; "
               "lighter intercity effect than Dussehra or Diwali, but worth tracking in Delhi/NCR.",
        "verified": True,
    },
    {
        "name": "Dussehra (Vijayadashami)",
        "group": "North & Hill Circuit",
        "start": date(2026, 10, 17),
        "end": date(2026, 10, 20),
        "why": "Delhi's Ramlila Maidan events draw large crowds in the run-up to Oct 20. "
               "Watch for NCR traffic advisories and short-trip demand spikes.",
        "verified": True,
    },
    {
        "name": "Char Dham Yatra — season closing",
        "group": "North & Hill Circuit",
        "start": date(2026, 10, 25),
        "end": date(2026, 11, 10),
        "why": "Kedarnath/Badrinath/Gangotri/Yamunotri typically close for winter around "
               "Bhai Dooj. Expect a last-minute pilgrim surge on the Haridwar–Rishikesh–"
               "Dehradun corridor before the shutdown.",
        "verified": False,  # exact closing dates are set by temple committees — re-check closer to the date
    },
    {
        "name": "Diwali (Dhanteras → Bhai Dooj)",
        "group": "All-India",
        "start": date(2026, 11, 6),
        "end": date(2026, 11, 10),
        "why": "The single heaviest outstation travel window of the year — main day (Lakshmi "
               "Puja) is Nov 8. Nationwide homecoming travel drives a surge in one-way "
               "outstation bookings across every corridor.",
        "verified": True,
    },
    {
        "name": "Chhath Puja (Delhi/Mumbai → Bihar/UP outbound)",
        "group": "North & Hill Circuit",
        "start": date(2026, 11, 14),
        "end": date(2026, 11, 16),
        "why": "Major homecoming travel from Delhi/Mumbai to Bihar/UP/Jharkhand. Not a Gozo "
               "'top city' destination, but the outbound demand originates in Delhi/NCR — "
               "a real one-way booking opportunity even though the drop city isn't in the "
               "usual route list.",
        "verified": True,
    },
    {
        "name": "Winter Wedding Season",
        "group": "North & Hill Circuit",
        "start": date(2026, 11, 21),
        "end": date(2027, 2, 15),
        "why": "Peak destination-wedding season, especially Jaipur/Rajasthan. Expect sustained "
               "multi-day chauffeur bookings rather than one-off point-to-point trips.",
        "verified": True,
    },
    {
        "name": "Goa Peak Season",
        "group": "West & Goa",
        "start": date(2026, 12, 15),
        "end": date(2027, 1, 15),
        "why": "Goa's high-tourist-density window. Airport transfer and multi-day rental demand "
               "both spike.",
        "verified": True,
    },
    {
        "name": "Christmas & New Year Long Weekend",
        "group": "All-India",
        "start": date(2026, 12, 24),
        "end": date(2027, 1, 1),
        "why": "Nationwide leisure travel spike — hill stations (Shimla/Manali) for snow "
               "tourism, plus general long-weekend outstation bookings.",
        "verified": True,
    },
    {
        "name": "Makar Sankranti / Lohri / Pongal",
        "group": "All-India",
        "start": date(2027, 1, 13),
        "end": date(2027, 1, 15),
        "why": "Regional harvest festivals with strong homecoming travel: Lohri (Punjab/"
               "Chandigarh), Pongal (Chennai/South), Sankranti (Central India/Maharashtra).",
        "verified": True,
    },
    {
        "name": "Republic Day Long Weekend",
        "group": "All-India",
        "start": date(2027, 1, 24),
        "end": date(2027, 1, 26),
        "why": "A predictable long-weekend leisure bump, especially on hill-station and "
               "heritage-city routes.",
        "verified": True,
    },
]

CURATED_THROUGH = max(e["end"] for e in EVENTS)


# ----------------------------------------------------------------------------
# STATUS LOGIC
# ----------------------------------------------------------------------------

def get_status(event, today):
    if event["start"] <= today <= event["end"]:
        days_left = (event["end"] - today).days
        return "active", days_left
    elif event["start"] > today:
        days_until = (event["start"] - today).days
        return "upcoming", days_until
    else:
        return "past", None


def status_badge(status, value):
    if status == "active":
        return f"🟢 ACTIVE NOW · {value} day{'s' if value != 1 else ''} left"
    elif status == "upcoming":
        return f"🟡 UPCOMING · in {value} day{'s' if value != 1 else ''}"
    else:
        return "⚪ PASSED"


# ----------------------------------------------------------------------------
# TIMELINE (custom HTML/CSS Gantt — no extra chart library needed)
# ----------------------------------------------------------------------------

def build_timeline_html(events, today, window_days):
    window_end = today + timedelta(days=window_days)
    row_h = 46
    header_h = 34
    total_h = header_h + row_h * len(events) + 10

    # Month gridlines
    month_marks = []
    cursor = date(today.year, today.month, 1)
    while cursor <= window_end:
        offset = (cursor - today).days
        if 0 <= offset <= window_days:
            left_pct = offset / window_days * 100
            month_marks.append((left_pct, cursor.strftime("%b %Y")))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    gridlines_html = "".join(
        f'<div style="position:absolute;left:{pct:.2f}%;top:0;bottom:0;'
        f'border-left:1px solid #333;font-size:11px;color:#888;padding-left:4px;">{label}</div>'
        for pct, label in month_marks
    )

    today_line = (
        '<div style="position:absolute;left:0%;top:0;bottom:0;'
        'border-left:2px solid #e74c3c;z-index:5;"></div>'
        '<div style="position:absolute;left:0%;top:-2px;font-size:11px;'
        'color:#e74c3c;font-weight:bold;">TODAY</div>'
    )

    color_map = {"active": "#2ecc71", "upcoming": "#f1c40f", "past": "#555555"}

    rows_html = ""
    for i, ev in enumerate(events):
        status, _ = get_status(ev, today)
        clamped_start = max(ev["start"], today)
        left_offset = max(0, (clamped_start - today).days)
        raw_width = (ev["end"] - clamped_start).days + 1
        left_pct = min(100, left_offset / window_days * 100)
        width_pct = max(0.5, min(100 - left_pct, raw_width / window_days * 100))
        color = color_map[status]
        top = header_h + i * row_h + 6
        tooltip = f"{ev['name']} ({ev['start'].strftime('%d %b')} – {ev['end'].strftime('%d %b')})"

        rows_html += (
            f'<div style="position:absolute;left:0;top:{top}px;font-size:12px;color:#ddd;'
            f'width:100%;overflow:hidden;white-space:nowrap;">{ev["name"]}</div>'
            f'<div title="{tooltip}" style="position:absolute;left:{left_pct:.2f}%;top:{top + 16}px;'
            f'width:{width_pct:.2f}%;height:14px;background:{color};border-radius:4px;"></div>'
        )

    html = f"""
    <div style="position:relative;width:100%;height:{total_h}px;
                background:#1a1a1a;border-radius:8px;padding:10px 12px;
                font-family:sans-serif;overflow:hidden;">
        <div style="position:relative;height:{header_h}px;">{gridlines_html}</div>
        <div style="position:relative;height:{total_h - header_h}px;">
            {today_line}
            {rows_html}
        </div>
    </div>
    """
    return html, total_h + 20


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

st.title("📅 Gozo Cabs: Location Activity Calendar")
st.markdown("When each destination cluster is active, or about to be — for route planning and fleet allocation.")

today = date.today()

with st.sidebar:
    st.header("⚙️ Filters")
    window_days = st.slider("Timeline window (days ahead)", 60, 180, 150, step=15)
    group_filter = st.multiselect("Destination groups", options=DESTINATION_GROUPS, default=DESTINATION_GROUPS)
    st.divider()
    st.caption(f"Today: {today.strftime('%d %b %Y')}")
    st.caption(f"Calendar curated through: {CURATED_THROUGH.strftime('%d %b %Y')}")
    if today > CURATED_THROUGH:
        st.warning("Today is past the curated window — this file needs a fresh set of dates.")
    unverified = [e["name"] for e in EVENTS if not e["verified"]]
    if unverified:
        with st.expander("⚠️ Dates needing re-verification"):
            for name in unverified:
                st.caption(f"• {name}")

filtered_events = [e for e in EVENTS if e["group"] in group_filter]
filtered_events.sort(key=lambda e: e["start"])

# --- Status grid: one glance per group ---
st.subheader("Status at a glance")
cols = st.columns(len(group_filter)) if group_filter else []
for col, group in zip(cols, group_filter):
    group_events = [e for e in filtered_events if e["group"] == group]
    active = [e for e in group_events if get_status(e, today)[0] == "active"]
    upcoming = sorted(
        [e for e in group_events if get_status(e, today)[0] == "upcoming"],
        key=lambda e: e["start"],
    )
    with col:
        st.markdown(f"**{group}**")
        if active:
            for e in active:
                _, days_left = get_status(e, today)
                st.success(f"🟢 {e['name']}\n\n{days_left}d left")
        elif upcoming:
            nxt = upcoming[0]
            _, days_until = get_status(nxt, today)
            st.warning(f"🟡 Next: {nxt['name']}\n\nin {days_until}d")
        else:
            st.info("⚪ Quiet")

st.divider()

# --- Timeline ---
st.subheader("Timeline")
if filtered_events:
    html, height = build_timeline_html(filtered_events, today, window_days)
    components.html(html, height=height, scrolling=False)
else:
    st.info("No events for the selected groups.")

st.divider()

# --- Detail list ---
st.subheader("Details")
for ev in filtered_events:
    status, value = get_status(ev, today)
    with st.container():
        st.markdown(f"**{ev['name']}**  ·  🏷️ {ev['group']}  ·  {status_badge(status, value)}")
        st.caption(f"{ev['start'].strftime('%d %b %Y')} – {ev['end'].strftime('%d %b %Y')}")
        st.write(ev["why"])
        if not ev["verified"]:
            st.caption("⚠️ Approximate date — confirm closer to the event.")
        st.divider()
