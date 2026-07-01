import streamlit as st
import requests
import matplotlib.pyplot as plt
import pandas as pd
import time

# Category and Status Style Configuration
CATEGORY_COLORS = {
    "Quality": ("rgba(239, 68, 68, 0.15)", "#f87171"),       # Red
    "Support": ("rgba(245, 158, 11, 0.15)", "#fbbf24"),       # Amber
    "Usability": ("rgba(37, 99, 235, 0.15)", "#60a5fa"),     # Blue
    "Price": ("rgba(34, 197, 94, 0.15)", "#4ade80"),         # Green
    "Features": ("rgba(168, 85, 247, 0.15)", "#c084fc"),      # Purple
    "Other": ("rgba(107, 114, 128, 0.15)", "#9ca3af")         # Gray
}

STATUS_STYLES = {
    "Working well": {
        "bg": "rgba(34, 197, 94, 0.15)",
        "text": "#4ade80",
        "border": "rgba(34, 197, 94, 0.3)"
    },
    "Worth watching": {
        "bg": "rgba(234, 179, 8, 0.15)",
        "text": "#facc15",
        "border": "rgba(234, 179, 8, 0.3)"
    },
    "Needs attention": {
        "bg": "rgba(239, 68, 68, 0.15)",
        "text": "#f87171",
        "border": "rgba(239, 68, 68, 0.3)"
    }
}

def get_category_style(category: str):
    cat_cap = category.capitalize()
    return CATEGORY_COLORS.get(cat_cap, CATEGORY_COLORS["Other"])

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
        {"id": 1, "asin": "B00F2SKPIM", "name": "Samsung Galaxy Note 3", "description": "Classic Samsung phablet with S-Pen."},
        {"id": 2, "asin": "B00836Y6B2", "name": "Nokia Lumia 900", "description": "Classic Windows Phone with Zune integration."},
        {"id": 3, "asin": "B07FZH9BGV", "name": "Samsung Galaxy Note 9", "description": "Flagship smartphone with S-Pen and Bixby."}
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
    if st.button("🔄 Reload Products", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    if st.button("🗑️ Clear Analysis Cache", use_container_width=True):
        try:
            resp = requests.delete(f"{API_BASE}/analyze/{product_id}/cache")
            if resp.status_code == 200:
                if "insights" in st.session_state:
                    del st.session_state["insights"]
                st.sidebar.success("Analysis cache cleared successfully!")
                st.rerun()
            else:
                st.sidebar.error(f"Failed to clear cache: {resp.text}")
        except Exception as e:
            st.sidebar.error(f"Failed to communicate with backend: {e}")

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
                <div style="color: #94a3b8; font-size: 0.85rem;">Loaded from Sqlite3 cache</div>
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
        
        # Sort for display if 'score' exists
        if "score" in df_insights.columns:
            df_insights_sorted = df_insights.sort_values(by="score", ascending=True)
        else:
            df_insights_sorted = df_insights.copy()
            # Ensure the column exists for rendering logic below
            df_insights_sorted["score"] = 0.0
            
        if "insight" not in df_insights_sorted.columns:
            df_insights_sorted["insight"] = "Unknown Insight"
            
        num_insights = len(df_insights_sorted)
        
        # Dynamically scale figure height based on the number of insights to prevent overlapping labels
        fig_height = max(4.5, num_insights * 0.85)
        
        # Matplotlib Chart Generation
        fig, ax = plt.subplots(figsize=(10.5, fig_height))
        fig.patch.set_facecolor('#0e1117')
        ax.set_facecolor('#1e293b')
        
        colors = []
        for _, row in df_insights_sorted.iterrows():
            status = row.get('status', 'Needs attention')
            if status == "Working well":
                colors.append('#10b981') # Green
            elif status == "Worth watching":
                colors.append('#f59e0b') # Amber
            else:
                colors.append('#ef4444') # Red
                
        bars = ax.barh(
            df_insights_sorted['insight'].str.wrap(55), 
            df_insights_sorted['score'], 
            color=colors, 
            edgecolor='none', 
            height=0.55
        )
        
        # Add score labels next to the bars for readability
        max_score = df_insights_sorted['score'].max() if not df_insights_sorted.empty else 10.0
        for bar in bars:
            width = bar.get_width()
            ax.text(
                width + (max_score * 0.015),
                bar.get_y() + bar.get_height()/2,
                f'{width:.1f}',
                ha='left',
                va='center',
                color='#e2e8f0',
                fontsize=8,
                fontweight='bold'
            )
            
        # Customizing Axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#475569')
        ax.spines['bottom'].set_color('#475569')
        ax.tick_params(colors='#94a3b8', labelsize=8)
        ax.xaxis.grid(True, linestyle='--', alpha=0.1, color='#e2e8f0')
        ax.set_xlabel('Priority Score', color='#e2e8f0', fontsize=9)
        ax.set_xlim(0, max_score * 1.12)  # Give padding on the right for text labels
        
        fig.subplots_adjust(left=0.45, right=0.92, top=0.92, bottom=0.15)
        st.pyplot(fig)
        
        st.markdown("---")
        
        # 3. Insights Cards List
        st.markdown("#### 💡 Detailed Strategic Insights")
        
        # Category Filter and Sort Controls
        col1, col2 = st.columns(2)
        with col1:
            all_cats = ["All Categories"] + sorted(list(set(item.get("category", "other").capitalize() for item in insights)))
            selected_category = st.selectbox("Filter by Category", all_cats)
        with col2:
            sort_options = {
                "Biggest issues first": ("score", True),
                "Most talked about": ("frequency", False)
            }
            selected_sort = st.selectbox("Sort by", list(sort_options.keys()))
            
        # Filter insights
        filtered_insights = []
        for item in insights:
            cat = item.get("category", "other").capitalize()
            if selected_category == "All Categories" or cat == selected_category:
                filtered_insights.append(item)
                
        # Sort insights
        sort_field, ascending = sort_options[selected_sort]
        filtered_insights = sorted(filtered_insights, key=lambda x: float(x.get(sort_field, 0.0)), reverse=not ascending)
        
        # Render cards in a responsive 2-column grid
        for i in range(0, len(filtered_insights), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(filtered_insights):
                    item = filtered_insights[i + j]
                    cat = item.get("category", "other").capitalize()
                    status = item.get("status", "Needs attention")
                    score = item.get("score", 0.0)
                    freq = item.get("frequency", 1)
                    quote = item.get("example_quote", "N/A")
                    insight = item.get("insight", "")
                    
                    bg_cat, text_cat = get_category_style(cat)
                    status_style = STATUS_STYLES.get(status, STATUS_STYLES["Needs attention"])
                    border_color = status_style["text"]
                    
                    with cols[j]:
                        st.markdown(f"""
                        <div title="System Metrics -> Exact Score: {score} | Frequency: {freq}" 
                             style="background: rgba(30, 41, 59, 0.2); 
                                    border-left: 4px solid {border_color}; 
                                    border-radius: 8px; 
                                    padding: 1.2rem; 
                                    margin-bottom: 1rem; 
                                    border-top: 1px solid rgba(255,255,255,0.03); 
                                    border-right: 1px solid rgba(255,255,255,0.03); 
                                    border-bottom: 1px solid rgba(255,255,255,0.03);
                                    height: 100%;
                                    display: flex;
                                    flex-direction: column;
                                    justify-content: space-between;">
                            <div>
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
                                    <span style="background-color: {bg_cat}; color: {text_cat}; font-size: 0.75rem; font-weight: bold; padding: 0.2rem 0.6rem; border-radius: 20px;">
                                        📁 {cat}
                                    </span>
                                    <span style="background-color: {status_style['bg']}; color: {status_style['text']}; border: 1px solid {status_style['border']}; font-size: 0.75rem; font-weight: bold; padding: 0.2rem 0.6rem; border-radius: 20px;">
                                        {status}
                                    </span>
                                </div>
                                <div style="font-size: 1rem; font-weight: bold; color: #f8fafc; margin-bottom: 0.6rem; line-height: 1.4;">
                                    {insight}
                                </div>
                            </div>
                            <div>
                                <div style="display: flex; align-items: center; gap: 0.4rem; color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.6rem;">
                                    <span>👥</span>
                                    <span>{freq} customers brought this up</span>
                                </div>
                                <div style="font-style: italic; color: #94a3b8; padding-left: 0.8rem; border-left: 2px solid rgba(255,255,255,0.1); font-size: 0.85rem; line-height: 1.4;">
                                    "{quote}"
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
else:
    st.info("Click the 'Analyze Reviews' button to process the feedback and extract strategic business insights.")
