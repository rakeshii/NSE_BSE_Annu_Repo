import streamlit as st
import asyncio
import os
import sys
from engine import ReportEngine
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Annual Report Downloader",
    page_icon="📊",
    layout="wide"
)

# --- Custom Styling ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        font-weight: bold;
    }
    .st-emotion-cache-16ids93 {
        background-color: #ffffff;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .report-status {
        padding: 10px;
        border-left: 5px solid #3498db;
        background: #eef2f7;
        margin: 5px 0;
    }
    </style>
""", unsafe_allow_html=True)

# --- App Logic ---
def main():
    st.title("📊 Annual Report Integrated Downloader")
    st.markdown("Download annual reports from **NSE** and **BSE** with ease.")

    with st.container():
        col1, col2 = st.columns([2, 1])
        
        with col1:
            companies_input = st.text_input(
                "Company Names (comma-separated)",
                value="Reliance Industries, HCL Technologies",
                help="Enter multiple companies separated by commas (e.g., Reliance, TCS, TATA Motors)"
            )
        
        with col2:
            current_year = datetime.now().year
            target_year = st.number_input(
                "Target Year",
                min_value=2000,
                max_value=current_year + 1,
                value=current_year,
                help="The year of the report you want to download."
            )

    st.info("💡 **Note**: NSE 2024 refers to FY 2024-25, while BSE 2024 refers to FY 2023-24.")

    save_dir = "Integrated_Downloads"
    
    col_bse, col_nse, col_both = st.columns(3)
    
    # Session state for logs
    if "logs" not in st.session_state:
        st.session_state.logs = []

    def streamlit_logger(msg):
        st.session_state.logs.append(msg)
        log_container.markdown("\n".join([f"`{m}`" for m in st.session_state.logs[-15:]]))

    # Execution 
    action = None
    if col_bse.button("🔍 Fetch BSE", type="secondary"):
        action = "BSE"
    if col_nse.button("🔍 Fetch NSE", type="secondary"):
        action = "NSE"
    if col_both.button("🚀 Fetch BOTH", type="primary"):
        action = "BOTH"

    log_container = st.empty()

    if action:
        companies = [c.strip() for c in companies_input.split(",") if c.strip()]
        if not companies:
            st.error("Please enter at least one company name.")
            return

        st.session_state.logs = [f"--- STARTING JOB: {action} for Year {target_year} ---"]
        
        progress_bar = st.progress(0)
        engine = ReportEngine(logger=streamlit_logger)
        
        for i, company in enumerate(companies):
            st.session_state.logs.append(f"**\nProcessing: {company}...**")
            
            async def run_jobs():
                tasks = []
                if action in ["BSE", "BOTH"]:
                    tasks.append(engine.run_bse(company, target_year, save_dir))
                if action in ["NSE", "BOTH"]:
                    tasks.append(engine.run_nse(company, target_year, save_dir))
                await asyncio.gather(*tasks)

            asyncio.run(run_jobs())
            progress_bar.progress((i + 1) / len(companies))

        st.success(f"Job completed! Files saved in `{save_dir}` folder.")
        st.balloons()

if __name__ == "__main__":
    main()
