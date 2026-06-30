import streamlit as st
import requests
import matplotlib.pyplot as plt
import pandas as pd
import time

# Page Configuration
st.set_page_config(
    page_title="litmus7 | Product Review Intelligence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium Custom CSS
st.markdown("""
<style>
    /* Dark glassmorphic container styles */
    .stApp {
        background: linear-gradient(135deg, #0e1117 0%, #161a24 100%);
        color: #e2e8f0;
    }
    
    /* Header custom styles */
    .main-title {
        font-family: 'Outfit', 'Inter', sans-serif;
        background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    /* Subtitle styles */
    .subtitle {
        color: #94a3b8;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    
    /* Premium card containers */
    .metric-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    
    /* Custom insight card */
    .insight-card {
        background: rgba(30, 41, 59, 0.3);
        border-left: 4px solid #6366f1;
        border-radius: 6px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    
    /* Custom scrollable container for reviews */
    .reviews-container {
        max-height: 400px;
        overflow-y: auto;
        padding-right: 10px;
    }
</style>
""", unsafe_allow_html=True)

# API Endpoint Configurations
API_BASE = "http://127.0.0.1:8000"

st.markdown('<div class="main-title">litmus7</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Divide-and-Conquer Product Review Intelligence Platform</div>', unsafe_allow_html=True)

# Helper function to fetch products from backend
@st.cache_data(show_spinner=False)
def fetch_products():
    try:
        response = requests.get(f"{API_BASE}/db/products")
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    # Fallback to local default list if backend is not started
    return [
        {"id": 1, "asin": "B00F2SKPIM", "name": "Samsung Galaxy S10", "description": "Flagship Samsung smartphone."},
        {"id": 2, "asin": "B00836Y6B2", "name": "iPhone XR", "description": "Liquid Retina display, Face ID."},
        {"id": 3, "asin": "B07FZH9BGV", "name": "OnePlus 7 Pro", "description": "Fluid AMOLED display."}
    ]

# Fetch products
products_list = fetch_products()
product_names = [p["name"] for p in products_list]

# Sidebar selection
with st.sidebar:
    st.markdown("### 🛒 Product Selection")
    selected_product_name = st.selectbox("Choose a product for review analysis:", product_names)
    
    # Get selected product details
    selected_prod = next(p for p in products_list if p["name"] == selected_product_name)
    product_id = selected_prod["id"]
    asin = selected_prod.get("asin", "N/A")
    
    st.markdown("---")
    st.markdown(f"**ASIN:** `{asin}`")
    st.markdown(f"**Description:** {selected_prod.get('description', '')}")
    if "price" in selected_prod:
        st.markdown(f"**Price:** `${selected_prod['price']}`")
        
    st.markdown("---")
    st.markdown("### ⚙️ Pipeline Control")
    if st.button("🔄 Reload Products"):
        st.cache_data.clear()
        st.rerun()

# ----------------- Main Layout -----------------

# Fetch reviews for the selected product
reviews_data = []
try:
    resp = requests.get(f"{API_BASE}/reviews/{product_id}")
    if resp.status_code == 200:
        reviews_data = resp.json().get("reviews", [])
except Exception:
    st.error("🔌 Could not connect to FastAPI backend server. Please verify uvicorn is running on port 8000.")
    st.stop()

# Layout: Full-width AI Analytics Dashboard
st.markdown("### 📊 AI Analytics Dashboard")
st.write("Extract business intelligence using the divide-and-conquer agent pipeline.")

analyze_btn = st.button("🤖 Analyze Reviews", type="primary", use_container_width=True)

# Placeholder or display result
if analyze_btn:
    with st.spinner("Executing dynamic parallel sub-agents and aggregator flow..."):
        try:
            response = requests.get(f"{API_BASE}/analyze/{product_id}")
            if response.status_code == 200:
                result = response.json()
                insights = result.get("analysis", [])
                cached = result.get("cached", False)
                reviews_analyzed = result.get("reviews_analyzed", 0)
                execution_time = result.get("execution_time_seconds", 0.0)
                
                # Store results in session state to persist on redraw
                st.session_state["insights"] = insights
                st.session_state["cached"] = cached
                st.session_state["reviews_analyzed"] = reviews_analyzed
                st.session_state["execution_time"] = execution_time
                st.session_state["analyzed_prod_id"] = product_id
            else:
                st.error(f"Error running analysis: {response.text}")
        except Exception as e:
            st.error(f"Failed to communicate with analysis backend: {e}")

# Check if we have analysis results in session state for selected product
if "insights" in st.session_state and st.session_state.get("analyzed_prod_id") == product_id:
    insights = st.session_state["insights"]
    cached = st.session_state["cached"]
    reviews_analyzed = st.session_state["reviews_analyzed"]
    execution_time = st.session_state["execution_time"]
    
    # 1. Performance Indicator Cards
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        if cached:
            st.markdown("""
            <div class="metric-card">
                <div style="font-size: 1.8rem;">⚡</div>
                <div style="font-weight: bold; color: #10b981; font-size: 1.1rem;">CACHE HIT</div>
                <div style="color: #94a3b8; font-size: 0.85rem;">Loaded from MongoDB cache</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 1.8rem;">🤖</div>
                <div style="font-weight: bold; color: #6366f1; font-size: 1.1rem;">CACHE MISS ({execution_time}s)</div>
                <div style="color: #94a3b8; font-size: 0.85rem;">Generated by ADK agents</div>
            </div>
            """, unsafe_allow_html=True)
    with m_col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 1.8rem;">📁</div>
            <div style="font-weight: bold; color: #3b82f6; font-size: 1.1rem;">{reviews_analyzed} REVIEWS</div>
            <div style="color: #94a3b8; font-size: 0.85rem;">Processed in parallel</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # Check if insights is a string (fallback error) or actual list
    if isinstance(insights, str):
        st.warning("The model provider returned a raw text explanation instead of a parsed JSON array:")
        st.text(insights)
    elif not insights:
        st.info("No actionable business insights extracted from the review content.")
    else:
        # 2. Visualization Charts
        st.markdown("#### 📈 Key Takeaways Severity Chart")
        df_insights = pd.DataFrame(insights)
        
        # Matplotlib Chart Generation
        fig, ax = plt.subplots(figsize=(8, 3.5))
        fig.patch.set_facecolor('#0e1117')
        ax.set_facecolor('#1e293b')
        
        # Sort for display
        df_insights_sorted = df_insights.sort_values(by="score", ascending=True)
        
        colors = []
        for score in df_insights_sorted['score']:
            if score >= 2.0:
                colors.append('#ef4444') # Red for High
            elif score >= 1.3:
                colors.append('#f59e0b') # Amber for Medium
            else:
                colors.append('#3b82f6') # Blue for Low
                
        bars = ax.barh(
            df_insights_sorted['insight'].str.wrap(30), 
            df_insights_sorted['score'], 
            color=colors, 
            edgecolor='none', 
            height=0.6
        )
        
        # Customizing Axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#475569')
        ax.spines['bottom'].set_color('#475569')
        ax.tick_params(colors='#94a3b8', labelsize=8)
        ax.xaxis.grid(True, linestyle='--', alpha=0.1, color='#e2e8f0')
        ax.set_xlabel('Priority Score', color='#e2e8f0', fontsize=9)
        plt.tight_layout()
        
        st.pyplot(fig)
        
        st.markdown("---")
        
        # 3. Insights Cards List
        st.markdown("#### 💡 Detailed Strategic Insights")
        for idx, item in enumerate(insights):
            score = item.get("score", 0.0)
            freq = item.get("frequency", 1)
            quote = item.get("example_quote", "N/A")
            cat = item.get("category", "other").capitalize()
            
            # Tag mapping
            if score >= 2.0:
                tag_color = "#fef2f2"
                tag_text_color = "#ef4444"
                border_color = "#ef4444"
                badge = "🔴 High Priority"
            elif score >= 1.3:
                tag_color = "#fffbeb"
                tag_text_color = "#f59e0b"
                border_color = "#f59e0b"
                badge = "🟡 Medium Priority"
            else:
                tag_color = "#eff6ff"
                tag_text_color = "#3b82f6"
                border_color = "#3b82f6"
                badge = "🔵 Low Priority"
                
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.2); border-left: 4px solid {border_color}; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; border-top: 1px solid rgba(255,255,255,0.03); border-right: 1px solid rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="background-color: {tag_color}; color: {tag_text_color}; font-size: 0.8rem; font-weight: bold; padding: 0.2rem 0.6rem; border-radius: 20px;">{badge} (Score: {score})</span>
                    <span style="color: #94a3b8; font-size: 0.85rem;">📁 Category: <b>{cat}</b> | Frequency: {freq}</span>
                </div>
                <div style="font-size: 1rem; font-weight: bold; color: #f8fafc; margin-bottom: 0.6rem;">{item.get('insight', '')}</div>
                <div style="font-style: italic; color: #94a3b8; padding-left: 0.8rem; border-left: 2px solid rgba(255,255,255,0.1); font-size: 0.9rem;">
                    "{quote}"
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Click the 'Analyze Reviews' button to process the feedback and extract strategic business insights.")
