"""
Phase 1: 共通UI部品
app.pyから共通UI部品を分離
"""
import streamlit as st


def setup_page_config():
    """
    ページ設定を初期化（st.set_page_config）
    Phase 1 Step 2: app.pyから移動
    """
    st.set_page_config(
        page_title="Material Map",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items=None
    )
