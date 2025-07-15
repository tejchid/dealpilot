import streamlit as st
import json
import pandas as pd
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re
import os

KEYWORDS = ["switch", "access point", "wireless", "wi-fi", "poe", "fiber", "network upgrade"]

# Utility: Download and extract text from HTML or PDF

def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type or url.lower().endswith('.pdf'):
            import io
            from PyPDF2 import PdfReader
            pdf = PdfReader(io.BytesIO(response.content))
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        return ""

# Main function: Process and score RFPs

def process_rfps(rfps, keywords=KEYWORDS, log_skipped=False):
    today = datetime.today().date()
    scored_bids = []
    skipped = []
    for rfp in rfps:
        if rfp.get('opportunity_status', '').upper() != 'OPEN':
            if log_skipped: skipped.append(rfp)
            continue
        due_date_str = rfp.get('due_date', '')
        try:
            due_date = datetime.strptime(due_date_str[:10], '%Y-%m-%d').date()
        except Exception:
            if log_skipped: skipped.append(rfp)
            continue
        if due_date < today:
            if log_skipped: skipped.append(rfp)
            continue
        score = 0
        matched_keywords = []
        fields_to_search = [rfp.get('title', ''), rfp.get('description', ''), str(rfp.get('bid_categories', ''))]
        detail_url = rfp.get('detail_url')
        if detail_url:
            fields_to_search.append(extract_text_from_url(detail_url))
        text = " ".join(fields_to_search).lower()
        for kw in keywords:
            count = len(re.findall(re.escape(kw.lower()), text))
            if count > 0:
                matched_keywords.append(kw)
            score += count
        features = []
        if any(kw in text for kw in ["wi-fi", "access point", "wireless"]):
            features.append("High-performance Wi-Fi 6 access points")
        if any(kw in text for kw in ["fiber", "poe", "switch"]):
            features.append("Fiber-ready switches with PoE and VLAN support")
        if features:
            features.append("Fast delivery, expert support, and competitive pricing")
        else:
            features = ["Fast delivery, expert support, and competitive pricing"]
        scored_bids.append({
            'title': rfp.get('title', ''),
            'due_date': due_date_str,
            'score': score,
            'opportunity_status': rfp.get('opportunity_status', ''),
            'detail_url': detail_url,
            'location': rfp.get('location', rfp.get('jurisdiction_title', '')),
            'description': rfp.get('description', ''),
            'bid_categories': rfp.get('bid_categories', ''),
            'agency': rfp.get('agency', ''),
            'rfp_id': rfp.get('id', rfp.get('rfp_id', '')),
            'matched_keywords': ", ".join(matched_keywords),
            'buyer_email': rfp.get('buyer_email', rfp.get('contact_email', '')),
            'buyer_title': rfp.get('buyer_title', ''),
            'buyer_first_name': rfp.get('buyer_first_name', ''),
            'buyer_last_name': rfp.get('buyer_last_name', ''),
            'features': features,
        })
    scored_bids.sort(key=lambda x: x['score'], reverse=True)
    return scored_bids, skipped

# Get API credentials from environment variables or use fallback
email = os.getenv('GOVNAV_EMAIL', 'marcelo.molinari@commscope.com')
token = os.getenv('GOVNAV_TOKEN', '22c7f7254d4202af5c73bd9108c527ed')
DEFAULT_FEED_URL = f"https://www.governmentnavigator.com/api/bidfeed?email={email}&token={token}"

st.title("Deal Pilot")
st.write("RFP Scoring Dashboard: Automatically loads and scores the live RFP feed.")

rfps = None
source = None
try:
    response = requests.get(DEFAULT_FEED_URL)
    response.raise_for_status()
    rfps = response.json()
    source = "live feed"
except Exception as e:
    st.error(f"Failed to fetch live feed: {e}")

# Try to load the image, fall back to text if it fails
try:
    st.sidebar.image("ruckus_battle_card.png", use_container_width=True)
except:
    st.sidebar.markdown("🏢 **RUCKUS NETWORKS**")
st.sidebar.markdown("<div style='text-align:center; font-size:2em;'><b>Deal Pilot</b></div>", unsafe_allow_html=True)

st.markdown("""
<style>
    .high-score {
        background-color: #e6ffe6 !important;
        border-left: 5px solid #2ecc40;
        margin-bottom: 1em;
        padding: 1em;
        border-radius: 8px;
    }
    .keyword {
        color: #2ecc40;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

if rfps:
    scored_bids, skipped = process_rfps(rfps)
    st.success(f"Processed {len(scored_bids)} relevant bids from {source}. Skipped {len(skipped)} bids.")
    if scored_bids:
        df = pd.DataFrame(scored_bids)
        st.write("All fields for top scored bids:")
        st.dataframe(df)
        high_score_bids = df[df['score'] >= 3]
        if not high_score_bids.empty:
            st.subheader("High-scoring bids (score ≥ 3):")
            for _, row in high_score_bids.iterrows():
                buyer_email = row.get('buyer_email', '')
                buyer_title = row.get('buyer_title', '')
                buyer_first = row.get('buyer_first_name', '')
                buyer_last = row.get('buyer_last_name', '')
                location = row.get('location', '')
                customer_name = f"{buyer_title} {buyer_first} {buyer_last}".strip()
                features = row.get('features', [])
                features_text = "".join([f"✅ {f}%0D%0A" for f in features])
                subject = f"Inquiry about RFP in {location}"
                body = (
                    f"Hi {customer_name},%0D%0A%0D%0A"
                    "We saw your request for a network upgrade and we think Ruckus Networks is a perfect fit.%0D%0A%0D%0A"
                    f"{features_text}"
                    "%0D%0AWould you like us to send a formal proposal?%0D%0A%0D%0A"
                    "Just reply “yes” and we’ll take care of the rest.%0D%0A%0D%0A"
                    "Best regards,%0D%0ARuckus Networks | CommScope%0D%0A"
                    "📞 +1 408 747 6626 | ✉️ joe.flynn@commscope.com"
                )
                mailto_link = f"mailto:{buyer_email}?subject={subject}&body={body}"
                st.markdown(f"""
                <div class='high-score'>
                    <b>{row['title']}</b> <br>
                    <i>Location:</i> {location} <br>
                    <i>Due Date:</i> {row['due_date']} <br>
                    <i>Score:</i> <span class='keyword'>{row['score']}</span> <br>
                    <i>Matched Keywords:</i> <span class='keyword'>{row['matched_keywords']}</span> <br>
                    <i>Description:</i> {row['description']} <br>
                    <a href='{row['detail_url']}' target='_blank'>View Details</a><br>
                    <a href='{mailto_link}' target='_blank'><button style='margin-top:10px;'>Generate Email Lead</button></a>
                </div>
                """, unsafe_allow_html=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download scored bids as CSV", data=csv, file_name="scored_bids.csv", mime="text/csv")
    else:
        st.warning("No relevant bids found.")
else:
    st.info("Please wait for the live feed to load.")
