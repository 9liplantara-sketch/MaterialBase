"""
セッション状態管理モジュール
session_stateキーとページ名定数、状態初期化関数を提供
"""
import streamlit as st
from typing import Optional

# ページ名定数
PAGE_HOME = "ホーム"
PAGE_MATERIALS_LIST = "材料一覧"
PAGE_REGISTRATION = "材料登録"
PAGE_DASHBOARD = "ダッシュボード"
PAGE_SEARCH = "検索"
PAGE_MATERIAL_CARDS = "素材カード"
PAGE_PERIODIC_TABLE = "元素周期表"
PAGE_SUBMISSION_STATUS = "投稿ステータス確認"
PAGE_APPROVAL_QUEUE = "承認待ち一覧"
PAGE_BULK_IMPORT = "一括登録"

# session_stateキー定数
KEY_PAGE = "page"
KEY_EDIT_MATERIAL_ID = "edit_material_id"
KEY_INCLUDE_UNPUBLISHED = "include_unpublished"
KEY_INCLUDE_DELETED = "include_deleted"
KEY_APPROVAL_SHOW_REJECTED = "approval_show_rejected"
KEY_APPROVAL_SEARCH = "approval_search"

# デフォルトページ
DEFAULT_PAGE = PAGE_HOME


def ensure_state_defaults():
    """
    session_stateのデフォルト値を設定
    必要なキーが存在しない場合のみ初期化（既存の値を保持）
    """
    if KEY_PAGE not in st.session_state:
        st.session_state[KEY_PAGE] = DEFAULT_PAGE
    
    if KEY_EDIT_MATERIAL_ID not in st.session_state:
        st.session_state[KEY_EDIT_MATERIAL_ID] = None
    
    if KEY_INCLUDE_UNPUBLISHED not in st.session_state:
        st.session_state[KEY_INCLUDE_UNPUBLISHED] = False
    
    if KEY_INCLUDE_DELETED not in st.session_state:
        st.session_state[KEY_INCLUDE_DELETED] = False
    
    if KEY_APPROVAL_SHOW_REJECTED not in st.session_state:
        st.session_state[KEY_APPROVAL_SHOW_REJECTED] = False
    
    if KEY_APPROVAL_SEARCH not in st.session_state:
        st.session_state[KEY_APPROVAL_SEARCH] = ""


def goto(page: str, **kwargs):
    """
    ページ遷移を実行
    
    Args:
        page: 遷移先のページ名（PAGE_*定数を使用）
        **kwargs: 追加のsession_stateキーと値のペア
    """
    st.session_state[KEY_PAGE] = page
    for key, value in kwargs.items():
        st.session_state[key] = value
    st.rerun()
