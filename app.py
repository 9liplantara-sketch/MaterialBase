"""
StreamlitベースのWebアプリケーション
マテリアル感のあるリッチなUI
"""
import streamlit as st
import os
import subprocess

def get_build_sha() -> str:
    # Streamlit Cloudではgitコマンドが使えることが多い
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return sha
    except Exception:
        return "unknown"


def get_running_sha() -> str:
    """
    現在実行中のコミットSHAを取得（常時表示用）
    
    Returns:
        short SHA文字列、取得失敗時は"unknown"
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def is_debug() -> bool:
    """
    DEBUGモードが有効かどうかを判定（os.environ + st.secrets の両方をチェック）
    
    Returns:
        DEBUGが有効ならTrue、それ以外はFalse
    """
    # os.environ をチェック
    if os.getenv("DEBUG") == "1":
        return True
    
    # st.secrets をチェック（例外時はFalse）
    try:
        return str(st.secrets.get("DEBUG", "0")) == "1"
    except Exception:
        return False


# is_debug_flag: 関数名衝突を避けるための alias（ファイル先頭で必ず定義）
# utils.settings から import を試みるが、失敗時は fallback で is_debug を使用
try:
    from utils.settings import is_debug as is_debug_flag
except Exception:
    # utils.settings が壊れている場合の fallback
    is_debug_flag = is_debug


# 実行順序の安全策: is_debug_flag が callable であることを確認
if not callable(is_debug_flag):
    # 万が一 callable でない場合は fallback
    is_debug_flag = is_debug


from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image as PILImage
import qrcode
from io import BytesIO
import base64
import pandas as pd
import plotly.express as px

# グローバル変数の初期化（NameErrorを防ぐ）
_card_generator_import_error = None
_card_generator_import_traceback = None
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter
import json
import uuid
import logging

from database import SessionLocal, Material, Property, Image, MaterialMetadata, ReferenceURL, UseExample, ProcessExampleImage, MaterialSubmission, init_db

# ロガーを設定（Cloudで確実に追えるように）
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(name)s] %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
from material_form_detailed import _normalize_required
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func
from utils.logo import render_site_header, render_logo_mark, show_logo_debug_info, get_logo_debug_info, get_project_root

# デプロイバージョン（Streamlit Cloudのデプロイ確認用）
DEPLOY_VERSION = "2026-01-15T15:05:00"

# card_generatorとschemasのimportは削除（起動時クラッシュを避けるため）
# これらのモジュールは使用する関数内でlazy importする

# エントリーポイント関数（本文の最初に必ず出るマーカー、main呼び出しの強制、例外の可視化）
import traceback

def _panic_screen(where: str, e: Exception):
    """例外を可視化するパニック画面"""
    st.error(f"💥 PANIC at: {where}")
    st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))

def run_app_entrypoint():
    """
    アプリのエントリーポイント
    - 本文の最初に必ず出るマーカー
    - main呼び出しの強制
    - 例外の可視化
    """
    # 1) まず本文に「動いてる」印を必ず出す（ここが出なければ main が呼ばれてない等）
    st.write("✅ app.py is running (entrypoint reached)")

    # 2) 先にサイドバーDebugを描画（既存関数がある想定）
    # 同一run内で1回だけ描画する（二重表示を防ぐ）
    if "debug_sidebar_rendered" not in st.session_state:
        try:
            if "render_debug_sidebar_early" in globals():
                render_debug_sidebar_early()
                st.session_state["debug_sidebar_rendered"] = True
            else:
                st.sidebar.info("render_debug_sidebar_early() not found")
        except Exception as e:
            _panic_screen("render_debug_sidebar_early", e)
            # st.stop()は呼ばない（本文を表示するため）

    # 3) DB初期化（落ちても本文に出す）
    try:
        from database import init_db
        init_db()
        st.write("✅ init_db() done")
    except Exception as e:
        _panic_screen("init_db", e)
        # st.stop()は呼ばない（本文を表示するため）

    # 4) ここから本来のUI（main）を"必ず"呼ぶ
    try:
        if "main" not in globals():
            raise RuntimeError("main() function is not defined in app.py")
        main()
    except Exception as e:
        _panic_screen("main()", e)
        # st.stop()は呼ばない（本文を表示するため）

from material_form_detailed import show_detailed_material_form
from periodic_table_ui import show_periodic_table
from material_detail_tabs import show_material_detail_tabs

# Git SHA取得関数（ビルド情報表示用）
import subprocess

def get_git_sha() -> str:
    """Gitの短縮SHAを取得（失敗時は'no-git'を返す）"""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return sha
    except (subprocess.CalledProcessError, FileNotFoundError, Exception):
        return "no-git"

# クラウド環境でのポート設定
if 'PORT' in os.environ:
    port = int(os.environ.get("PORT", 8501))

# ページ設定
st.set_page_config(
    page_title="Material Map",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# 画像パスの取得（複数のパスを試す）
def get_image_path(filename):
    """画像パスを取得"""
    possible_paths = [
        Path("static/images") / filename,
        Path("写真") / filename,
        Path(filename)
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    return None

def get_base64_image(image_path):
    """画像をBase64エンコード"""
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        except Exception as e:
            print(f"画像読み込みエラー: {e}")
            return None
    return None

# 背景画像の読み込み（メイン.webpのみ）
main_bg_path = get_image_path("メイン.webp")
main_bg_base64 = get_base64_image(main_bg_path) if main_bg_path else None

# アイコンファイルの読み込み（iconmonstr風のシンプルなSVGアイコン）
def get_icon_path(icon_name: str) -> Optional[str]:
    """アイコンファイルのパスを取得"""
    icon_path = Path("static/icons") / f"{icon_name}.svg"
    if icon_path.exists():
        return str(icon_path)
    return None

def get_icon_base64(icon_name: str) -> Optional[str]:
    """アイコンをBase64エンコードして返す"""
    icon_path = get_icon_path(icon_name)
    if icon_path:
        try:
            with open(icon_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            return None
    return None

def get_icon_svg_inline(icon_name: str, size: int = 48, color: str = "#999999") -> str:
    """アイコンをインラインSVGとして返す（色とサイズを調整）"""
    icon_path = get_icon_path(icon_name)
    if icon_path:
        try:
            with open(icon_path, "r", encoding="utf-8") as f:
                svg_content = f.read()
                # 色とサイズを置換
                svg_content = svg_content.replace('stroke="#999999"', f'stroke="{color}"')
                svg_content = svg_content.replace('width="48"', f'width="{size}"')
                svg_content = svg_content.replace('height="48"', f'height="{size}"')
                return base64.b64encode(svg_content.encode()).decode()
        except Exception:
            pass
    return ""

# デバッグスイッチ（サイドバーでCSSを無効化可能）
# 注意: この変数はmain()関数内で設定されるため、ここでは定義のみ
debug_no_css = False

# WOTA風シンプルなカスタムCSS（視認性重視・コントラスト確保）
def get_custom_css():
    """カスタムCSSを生成（WOTA風シンプルデザイン・コントラスト確保）"""
    return f"""
<style>
    /* CSS変数（コントラスト確保のための共通ルール） */
    :root {{
        --bg: #ffffff;
        --text: #111111;
        --muted: #666666;
        --surface: #f7f7f7;
        --border: #e5e5e5;
        --primary: #1a1a1a;
        --on-primary: #ffffff;
    }}
    
    /* ベースフォント - シンプルなサンセリフ（WOTA風） */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
    }}
    
    /* ベース文字色を確保（視認性向上） */
    html, body, [class*="st-"], p, span, div, h1, h2, h3, h4, h5, h6 {{
        color: var(--text) !important;
    }}
    
    /* メイン背景 - WOTA風シンプル（白背景） */
    .stApp {{
        background: #ffffff;
        position: relative;
        min-height: 100vh;
    }}
    
    .stApp::before {{
        display: none;
    }}
    
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        position: relative;
        z-index: 10;
        background: transparent;
        max-width: 1200px;
    }}
    
    /* ヘッダー - WOTA風シンプルデザイン */
    .main-header {{
        font-size: 2.5rem;
        font-weight: 600;
        color: #1a1a1a;
        text-align: left;
        margin-bottom: 0.5rem;
        letter-spacing: -0.02em;
        position: relative;
        z-index: 2;
        line-height: 1.3;
        margin-top: 0;
    }}
    
    .main-header::after {{
        display: none;
    }}
    
    /* サブ背景画像を装飾として使用（非表示に変更 - 白飛び防止） */
    .material-decoration {{
        display: none;
        position: absolute;
        opacity: 0.05;
        z-index: -1;
        pointer-events: none;
    }}
    
    .decoration-1 {{
        display: none;
    }}
    
    .decoration-2 {{
        display: none;
    }}
    
    /* カードスタイル - WOTA風シンプル */
    .material-card-container {{
        background: #ffffff;
        border-radius: 0;
        padding: 32px;
        margin: 24px 0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
        transition: all 0.2s ease;
        border: 1px solid rgba(0, 0, 0, 0.08);
        position: relative;
        overflow: hidden;
    }}
    
    .material-card-container::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: #1a1a1a;
        opacity: 1;
    }}
    
    .material-card-container:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
        border-color: rgba(0, 0, 0, 0.15);
    }}
    
    /* カテゴリバッジ - 読みやすく、タグとして表示 */
    .category-badge {{
        display: inline-block;
        background: #f0f0f0;
        color: #1a1a1a;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
        margin: 4px 4px 0 0;
        box-shadow: none;
        text-transform: none;
        letter-spacing: 0;
        border: 1px solid #ddd;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        line-height: 1.4;
        max-width: 100%;
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: normal;
    }}
    
    /* 素材画像のヒーロー領域 */
    .material-hero-image {{
        width: 100%;
        aspect-ratio: 16 / 9;
        object-fit: cover;
        background: #f5f5f5;
        border-radius: 0;
        margin-bottom: 16px;
    }}
    
    /* 統計カード - WOTA風シンプル */
    .stat-card {{
        background: #ffffff;
        border-radius: 0;
        padding: 32px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
        transition: all 0.2s ease;
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-top: 2px solid #1a1a1a;
        position: relative;
        overflow: hidden;
    }}
    
    .stat-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }}
    
    .stat-value {{
        font-size: 2.5rem;
        font-weight: 600;
        color: #1a1a1a;
        margin: 15px 0;
        position: relative;
        z-index: 1;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    .stat-label {{
        color: #666666;
        font-size: 14px;
        font-weight: 400;
        text-transform: none;
        letter-spacing: 0;
        position: relative;
        z-index: 1;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    /* ボタンスタイル - WOTA風シンプル（コントラスト確保・白文字強制） */
    .stButton>button,
    button[data-baseweb="button"],
    [data-testid="baseButton-secondary"],
    [data-testid="baseButton-primary"],
    [data-testid="baseButton-secondary"] button,
    [data-testid="baseButton-primary"] button,
    button[type="button"] {{
        background: #1a1a1a !important;
        color: #ffffff !important;
        border: 1px solid #1a1a1a !important;
        border-radius: 4px;
        padding: 0.75rem 2rem;
        font-weight: 500;
        transition: all 0.2s ease;
        box-shadow: none;
        text-transform: none;
        letter-spacing: 0;
        font-size: 15px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    .stButton>button *,
    button[data-baseweb="button"] *,
    [data-testid="baseButton-secondary"] *,
    [data-testid="baseButton-primary"] *,
    button[type="button"] *,
    .stButton>button span,
    button[data-baseweb="button"] span {{
        color: #ffffff !important;
    }}
    
    .stButton>button:hover,
    button[data-baseweb="button"]:hover,
    [data-testid="baseButton-secondary"]:hover button,
    [data-testid="baseButton-primary"]:hover button,
    button[type="button"]:hover {{
        background: #333333 !important;
        border-color: #333333 !important;
        color: #ffffff !important;
        transform: none;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }}
    
    .stButton>button:hover *,
    button[data-baseweb="button"]:hover *,
    button[type="button"]:hover * {{
        color: #ffffff !important;
    }}
    
    /* 黒背景のヘッダー/バー部分の文字色を白に統一 */
    [style*="background: #1a1a1a"],
    [style*="background:#1a1a1a"],
    [style*="background-color: #1a1a1a"],
    [style*="background-color:#1a1a1a"],
    .black-bar,
    .dark-header {{
        color: #ffffff !important;
    }}
    
    .black-bar *,
    .dark-header * {{
        color: #ffffff !important;
    }}
    
    /* Streamlitのヘッダーバーの文字色を白に */
    [data-testid="stHeader"],
    header[data-testid="stHeader"],
    [data-testid="stHeader"] *,
    header[data-testid="stHeader"] *,
    [data-testid="stHeader"] p,
    [data-testid="stHeader"] span,
    [data-testid="stHeader"] div,
    [data-testid="stHeader"] a {{
        color: #ffffff !important;
    }}
    
    /* Streamlitのメニューボタン（ハンバーガーメニュー）の色 */
    [data-testid="stHeader"] button,
    [data-testid="stHeader"] button *,
    header[data-testid="stHeader"] button,
    header[data-testid="stHeader"] button * {{
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
    }}
    
    /* Streamlitのツールバー（右上のメニュー） */
    [data-testid="stToolbar"],
    [data-testid="stToolbar"] *,
    [data-testid="stToolbar"] button,
    [data-testid="stToolbar"] button * {{
        color: #ffffff !important;
    }}
    
    /* 黒背景の任意の要素 */
    div[style*="background: #1a1a1a"],
    div[style*="background:#1a1a1a"],
    div[style*="background-color: #1a1a1a"],
    div[style*="background-color:#1a1a1a"],
    section[style*="background: #1a1a1a"],
    section[style*="background:#1a1a1a"] {{
        color: #ffffff !important;
    }}
    
    div[style*="background: #1a1a1a"] *,
    div[style*="background:#1a1a1a"] *,
    div[style*="background-color: #1a1a1a"] *,
    div[style*="background-color:#1a1a1a"] *,
    section[style*="background: #1a1a1a"] *,
    section[style*="background:#1a1a1a"] * {{
        color: #ffffff !important;
    }}
    
    /* サイドバー - WOTA風シンプル */
    [data-testid="stSidebar"] {{
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(0, 0, 0, 0.08);
    }}
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        color: #1a1a1a;
        font-weight: 400;
    }}
    
    /* ラジオボタン - シンプルなメニュー */
    [data-testid="stRadio"] label {{
        font-size: 15px;
        font-weight: 400;
        color: #1a1a1a;
        padding: 8px 12px;
        border-radius: 4px;
        transition: background 0.2s ease;
    }}
    
    [data-testid="stRadio"] label:hover {{
        background: rgba(0, 0, 0, 0.04);
    }}
    
    [data-testid="stRadio"] input[type="radio"]:checked + label {{
        background: rgba(0, 0, 0, 0.08);
        font-weight: 500;
    }}
    
    /* 入力フィールド - WOTA風シンプル */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>select {{
        border-radius: 4px;
        border: 1px solid rgba(0, 0, 0, 0.15);
        background: #ffffff;
        transition: all 0.2s ease;
        box-shadow: none;
        font-size: 15px;
        padding: 0.5rem 0.75rem;
    }}
    
    .stTextInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus,
    .stSelectbox>div>div>select:focus {{
        border-color: #1a1a1a;
        box-shadow: 0 0 0 2px rgba(26, 26, 26, 0.1);
        background: #ffffff;
        outline: none;
    }}
    
    /* メトリクス - WOTA風 */
    [data-testid="stMetricValue"] {{
        font-size: 2rem;
        font-weight: 600;
        color: #1a1a1a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    [data-testid="stMetricLabel"] {{
        font-size: 14px;
        font-weight: 400;
        color: #666666;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    /* グラデーションテキスト - WOTA風シンプル（削除） */
    
    /* マテリアル装飾要素 */
    .material-texture {{
        position: relative;
        overflow: hidden;
    }}
    
    .material-texture::after {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: none;
        background-size: 200%;
        background-position: center;
        opacity: 0.03;
        pointer-events: none;
        mix-blend-mode: multiply;
    }}
    
    /* カードグリッド */
    .card-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 25px;
        margin: 30px 0;
    }}
    
    /* ヒーローセクション - WOTA風シンプル */
    .hero-section {{
        background: #ffffff;
        border-radius: 0;
        padding: 40px 0;
        text-align: left;
        margin: 40px 0;
        box-shadow: none;
        border: none;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        position: relative;
        overflow: hidden;
    }}
    
    .hero-section::before {{
        display: none;
    }}
    
    /* セクションタイトル - WOTA風 */
    .section-title {{
        font-size: 2rem;
        font-weight: 600;
        color: #1a1a1a;
        margin: 40px 0 24px 0;
        text-align: left;
        position: relative;
        padding-bottom: 16px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        letter-spacing: -0.01em;
    }}
    
    .section-title::after {{
        content: '';
        display: block;
        width: 40px;
        height: 2px;
        background: #1a1a1a;
        margin: 16px 0 0;
        border-radius: 0;
    }}
    
    /* 見出しの視認性向上 */
    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        font-weight: 600 !important;
        color: #1a1a1a !important;
        letter-spacing: -0.01em;
    }}
    
    /* 本文の視認性向上 */
    p, span, div, li {{
        font-size: 15px;
        line-height: 1.6;
        color: #1a1a1a;
    }}
    
    /* 統計情報を左下に固定表示 */
    .stats-fixed {{
        position: fixed;
        bottom: 20px;
        left: 20px;
        background: rgba(255, 255, 255, 0.95);
        padding: 12px 20px;
        border: 1px solid rgba(0, 0, 0, 0.08);
        font-size: 11px;
        color: #666;
        z-index: 1000;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    .stats-fixed div {{
        margin: 2px 0;
    }}
    
    .stats-fixed strong {{
        color: #1a1a1a;
        font-weight: 600;
    }}
    
    /* サイトヘッダー（ロゴ表示用） */
    .site-header {{
        display: flex;
        align-items: flex-start;
        gap: 12px;
        margin-top: 4px;
        margin-bottom: 12px;
    }}
    
    .site-title-block {{
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0;
    }}
    
    .site-logo svg {{
        height: 36px;
        width: auto;
        vertical-align: middle;
    }}
    
    .site-mark {{
        /* サイズは render_logo_mark(height_px=72) の inline style で指定 */
        /* ここでは余白や整列のみ */
    }}
    
    .site-logo-fallback {{
        font-size: 36px;
        font-weight: 600;
        color: #1a1a1a;
    }}
    
    .site-subtitle {{
        font-size: 14px;
        color: #666;
        margin-top: 8px;
    }}
    
    /* モバイル対応（画面幅が小さい場合） */
    @media (max-width: 768px) {{
        .site-header {{
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }}
        
        .site-logo svg {{
            height: 28px;
        }}
        
        /* ロゴマークのサイズは render_logo_mark(height_px=72) の inline style で指定 */
        
        .site-subtitle {{
            margin-top: 8px;
            line-height: 1.4;
        }}
    }}
</style>
"""

# データベース初期化
# DB初期化（常に実行：既存DBでも不足カラムを自動追加）
init_db()

def get_material_count_sqlite(db_path: Path) -> int:
    """
    sqlite3で直接materials件数を取得（ORMを使わない安全な方法）
    
    Args:
        db_path: データベースファイルのパス
    
    Returns:
        materials件数（エラー時は0）
    """
    if not db_path.exists():
        return 0
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path.absolute()))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM materials")
            count = cursor.fetchone()[0]
            return count if count is not None else 0
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning: get_material_count_sqlite failed: {e}")
        return 0


def should_init_sample_data() -> bool:
    """
    サンプルデータを初期化すべきか判定
    
    Returns:
        True: 初期化すべき（INIT_SAMPLE_DATA=1 かつ DBが空）
        False: 初期化しない
    """
    # 環境変数フラグが設定されていない場合は実行しない
    if os.getenv("INIT_SAMPLE_DATA") != "1":
        return False
    
    # DBが空の場合のみ実行
    db_path = Path("materials.db")
    count = get_material_count_sqlite(db_path)
    return count == 0


def maybe_init_sample_data():
    """
    サンプルデータを初期化する（環境変数がONのときだけ）
    
    注意:
    - 起動時（トップレベル）では import しない
    - 環境変数 INIT_SAMPLE_DATA=1 が設定されている場合のみ実行
    - セッション内で1回だけ実行（st.session_stateでガード）
    - 例外が出てもアプリ起動を殺さない（ログのみ）
    """
    if os.getenv("INIT_SAMPLE_DATA") != "1":
        return
    
    # セッション内で1回だけ実行（Streamlitの再実行特性に対応）
    if st.session_state.get("_seed_done", False):
        return
    
    try:
        # Lazy import: 起動時にimportしない（SyntaxErrorがあっても起動できる）
        from init_sample_data import init_sample_data
        init_sample_data()
        print("[INFO] Sample data initialized successfully")
    except Exception as e:
        # 落とさない（DEBUG時だけ表示でもOK）
        import traceback
        print(f"[WARN] init_sample_data failed: {e}")
        if os.getenv("DEBUG", "0") == "1":
            print(traceback.format_exc())
    finally:
        # 成功/失敗問わず、セッション内で1回だけ実行するフラグを立てる
        st.session_state["_seed_done"] = True

def get_db():
    """データベースセッションを取得"""
    return SessionLocal()


@st.cache_data(ttl=30)
def get_material_count_cached(db_url: str, include_unpublished: bool = False, include_deleted: bool = False) -> int:
    """
    材料件数を取得（キャッシュ付き、30秒TTL）
    
    Args:
        db_url: データベースURL（キャッシュキー用）
        include_unpublished: Trueの場合、非公開（is_published=0）も含める
        include_deleted: Trueの場合、論理削除済み（is_deleted=1）も含める
    
    Returns:
        材料件数
    """
    import time
    # 実行順序の安全策: is_debug_flag が存在することを確認
    if "is_debug_flag" not in globals() or not callable(globals().get("is_debug_flag")):
        debug_enabled = os.getenv("DEBUG", "0") == "1"
    else:
        debug_enabled = is_debug_flag()
    t0 = time.perf_counter() if debug_enabled else None
    
    from utils.db import get_sessionmaker
    from sqlalchemy import select, func
    SessionLocal = get_sessionmaker(db_url)
    db = SessionLocal()
    try:
        stmt = select(func.count()).select_from(Material)
        
        if not include_deleted:
            if hasattr(Material, 'is_deleted'):
                stmt = stmt.filter(Material.is_deleted == 0)
        
        if not include_unpublished:
            if hasattr(Material, 'is_published'):
                stmt = stmt.filter(Material.is_published == 1)
        
        count = db.execute(stmt).scalar_one()
        
        if t0 is not None:
            print(f"[PERF] get_material_count_cached: {time.perf_counter() - t0:.3f}s")
        
        return count
    finally:
        db.close()


@st.cache_data(ttl=30)
def fetch_materials_page_cached(
    db_url: str,
    include_unpublished: bool = False,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    search_query: str = None
) -> List[Dict[str, Any]]:
    """
    材料一覧をページングで取得（キャッシュ付き、30秒TTL、dict化して返す）
    
    Args:
        db_url: データベースURL（キャッシュキー用）
        include_unpublished: Trueの場合、非公開（is_published=0）も含める
        include_deleted: Trueの場合、論理削除済み（is_deleted=1）も含める
        limit: 取得件数
        offset: オフセット
        search_query: 検索クエリ（材料名で部分一致）
    
    Returns:
        材料データのdictリスト（表示用）
    """
    import time
    # 実行順序の安全策: is_debug_flag が存在することを確認
    if "is_debug_flag" not in globals() or not callable(globals().get("is_debug_flag")):
        debug_enabled = os.getenv("DEBUG", "0") == "1"
    else:
        debug_enabled = is_debug_flag()
    t0 = time.perf_counter() if debug_enabled else None
    
    from utils.db import get_sessionmaker
    from utils.material_cache import freeze_material_row
    from sqlalchemy import select
    from sqlalchemy.orm import noload, load_only
    
    SessionLocal = get_sessionmaker(db_url)
    db = SessionLocal()
    try:
        # 一覧表示用：必要な列だけをロードし、リレーションは全てnoload（高速化）
        stmt = (
            select(Material)
            .options(
                # 必要な列だけをロード（パフォーマンス向上）
                load_only(
                    Material.id,
                    Material.uuid,
                    Material.name_official,
                    Material.name,  # 後方互換
                    Material.category_main,
                    Material.category,  # 後方互換
                    Material.is_published,
                    Material.is_deleted,
                    Material.created_at,
                    Material.updated_at,
                ),
                # リレーションは全てnoload（一覧では不要）
                noload(Material.properties),
                noload(Material.images),
                noload(Material.reference_urls),
                noload(Material.use_examples),
                noload(Material.metadata_items),
                noload(Material.process_example_images),
            )
        )
        
        # フィルタ
        if not include_deleted:
            if hasattr(Material, 'is_deleted'):
                stmt = stmt.filter(Material.is_deleted == 0)
        
        if not include_unpublished:
            if hasattr(Material, 'is_published'):
                stmt = stmt.filter(Material.is_published == 1)
        
        # 検索クエリ
        if search_query and search_query.strip():
            stmt = stmt.filter(Material.name_official.ilike(f"%{search_query.strip()}%"))
        
        # ソート
        stmt = stmt.order_by(
            Material.created_at.desc() if hasattr(Material, 'created_at') else Material.id.desc()
        )
        
        # ページング
        stmt = stmt.limit(limit).offset(offset)
        
        # 実行
        result = db.execute(stmt)
        materials = result.unique().scalars().all()
        
        # dict化（DetachedInstanceErrorを防ぐ、scalar列のみ参照）
        material_dicts = [freeze_material_row(m) for m in materials]
        
        if t0 is not None:
            print(f"[PERF] fetch_materials_page_cached(limit={limit}, offset={offset}): {time.perf_counter() - t0:.3f}s")
        
        return material_dicts
    finally:
        db.close()


def get_all_materials(include_unpublished: bool = False, include_deleted: bool = False):
    """
    全材料を取得（Eager Loadでリレーションも先読み・全リレーション網羅）
    重複を除去して返す（DB由来のデータに一本化）
    
    Args:
        include_unpublished: Trueの場合、非公開（is_published=0）も含める
        include_deleted: Trueの場合、論理削除済み（is_deleted=1）も含める
    
    OperationalErrorをキャッチしてUI崩壊を防ぐ
    スキーマドリフト検知: images.kind が存在しない場合は安全モードで動作
    """
    # スキーマドリフト検知（軽量、キャッシュ済み）
    try:
        from database import get_schema_drift_status
        from utils.settings import get_database_url
        schema_status = get_schema_drift_status(get_database_url())
        
        # スキーマチェックが成功した場合のみ images_ok を使用
        if schema_status.get("ok", False):
            images_ok = schema_status.get("images_ok", False)
            # 後方互換: images_kind_exists も確認（images_ok が無い場合のフォールバック）
            if "images_ok" not in schema_status:
                images_ok = schema_status.get("images_kind_exists", False)
        else:
            # スキーマチェック失敗時は安全側に倒す（images をロードしない）
            images_ok = False
            if os.getenv("DEBUG", "0") == "1":
                print(f"[SCHEMA] schema check failed (ok=False), using safe mode: {schema_status.get('errors', [])}")
    except Exception as e:
        # スキーマチェック失敗時は安全側に倒す（images をロードしない）
        images_ok = False
        if os.getenv("DEBUG", "0") == "1":
            print(f"[SCHEMA] schema check exception, using safe mode: {e}")
    
    db = get_db()
    try:
        # 安全モード: images の必須列が欠けている場合は images をロードしない
        if images_ok:
            # 通常モード: 全リレーションを先読み
            stmt = (
                select(Material)
                .options(
                    selectinload(Material.properties),
                    selectinload(Material.images),
                    selectinload(Material.metadata_items),
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.process_example_images),  # 加工例画像
                )
            )
        else:
            # 安全モード: images をロードしない（スキーマ不整合を回避）
            from sqlalchemy.orm import noload
            stmt = (
                select(Material)
                .options(
                    selectinload(Material.properties),
                    noload(Material.images),  # images をロードしない
                    selectinload(Material.metadata_items),
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.process_example_images),
                )
            )
        
        # is_deletedフィルタ（デフォルトで削除されていないもののみ）
        if not include_deleted:
            if hasattr(Material, 'is_deleted'):
                stmt = stmt.filter(Material.is_deleted == 0)
        
        # is_publishedフィルタ（デフォルトで公開のみ）
        if not include_unpublished:
            if hasattr(Material, 'is_published'):
                stmt = stmt.filter(Material.is_published == 1)
        
        stmt = stmt.order_by(Material.created_at.desc() if hasattr(Material, 'created_at') else Material.id.desc())
        
        # SQLAlchemy 2.0のunique()で重複を除去
        result = db.execute(stmt)
        materials = result.unique().scalars().all()
        return materials
    except Exception as e:
        from sqlalchemy.exc import OperationalError
        import sqlite3
        
        # OperationalErrorをキャッチ（DB query failed）
        if isinstance(e, (OperationalError, sqlite3.OperationalError)) or "no such column" in str(e).lower():
            # DB query failed (OperationalError) - 本文に表示してst.stop()
            st.error("DB query failed (OperationalError)")
            st.code(str(e))
            st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
            # PRAGMA table_info(materials) を全部出す
            db_path = Path("materials.db")
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path.absolute()))
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(materials)")
                    columns = cursor.fetchall()
                    st.write("**PRAGMA table_info(materials):**")
                    for col in columns:
                        st.write(f"- {col[1]} ({col[2]})")
                    conn.close()
                except Exception as inner_e:
                    st.exception(inner_e)
            st.stop()  # 以降のUIを止める（崩壊させない）
        raise  # その他のエラーは再発生
    finally:
        db.close()

def get_material_by_id(material_id: int):
    """
    IDで材料を取得（Eager Loadでリレーションも先読み・全リレーション網羅）
    スキーマドリフト検知: images.kind が存在しない場合は安全モードで動作
    """
    # スキーマドリフト検知（軽量、キャッシュ済み）
    try:
        from database import get_schema_drift_status
        from utils.settings import get_database_url
        schema_status = get_schema_drift_status(get_database_url())
        
        # スキーマチェックが成功した場合のみ images_ok を使用
        if schema_status.get("ok", False):
            images_ok = schema_status.get("images_ok", False)
            # 後方互換: images_kind_exists も確認（images_ok が無い場合のフォールバック）
            if "images_ok" not in schema_status:
                images_ok = schema_status.get("images_kind_exists", False)
        else:
            # スキーマチェック失敗時は安全側に倒す
            images_ok = False
    except Exception:
        # スキーマチェック失敗時は安全側に倒す
        images_ok = False
    
    db = get_db()
    try:
        # 安全モード: images の必須列が欠けている場合は images をロードしない
        if images_ok:
            # 通常モード: 全リレーションを先読み
            stmt = (
                select(Material)
                .options(
                    selectinload(Material.properties),
                    selectinload(Material.images),
                    selectinload(Material.metadata_items),
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.process_example_images),  # 加工例画像
                )
                .filter(Material.id == material_id)
            )
        else:
            # 安全モード: images をロードしない（スキーマ不整合を回避）
            from sqlalchemy.orm import noload
            stmt = (
                select(Material)
                .options(
                    selectinload(Material.properties),
                    noload(Material.images),  # images をロードしない
                    selectinload(Material.metadata_items),
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.process_example_images),
                )
                .filter(Material.id == material_id)
            )
        material = db.execute(stmt).scalar_one_or_none()
        return material
    finally:
        db.close()

def create_material(name, category, description, properties_data):
    """材料を作成"""
    db = get_db()
    try:
        material = Material(
            name=name,
            category=category,
            description=description
        )
        db.add(material)
        db.flush()
        
        for prop in properties_data:
            if prop.get('name') and prop.get('value'):
                db_property = Property(
                    material_id=material.id,
                    property_name=prop['name'],
                    value=float(prop['value']) if prop['value'] else None,
                    unit=prop.get('unit', '')
                )
                db.add(db_property)
        
        db.commit()
        return material
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def generate_qr_code(material_id: int):
    """QRコードを生成（後方互換性のため残すが、新しいコードではgenerate_qr_png_bytesを使用）"""
    from utils.qr import generate_qr_png_bytes
    qr_bytes = generate_qr_png_bytes(f"Material ID: {material_id}")
    if qr_bytes:
        from PIL import Image as PILImage
        from io import BytesIO
        return PILImage.open(BytesIO(qr_bytes))
    return None

def create_category_chart(materials):
    """カテゴリ別の円グラフを作成"""
    if not materials:
        return None
    
    categories = [m.category or "未分類" for m in materials]
    category_counts = Counter(categories)
    
    fig = px.pie(
        values=list(category_counts.values()),
        names=list(category_counts.keys()),
        title="カテゴリ別分布",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>数量: %{value}<br>割合: %{percent}<extra></extra>'
    )
    fig.update_layout(
        font=dict(size=14),
        showlegend=True,
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def create_timeline_chart(materials):
    """登録タイムラインを作成"""
    if not materials:
        return None
    
    dates = [m.created_at.date() if m.created_at else datetime.now().date() for m in materials]
    date_counts = Counter(dates)
    sorted_dates = sorted(date_counts.items())
    
    df = pd.DataFrame(sorted_dates, columns=['日付', '登録数'])
    df['累計'] = df['登録数'].cumsum()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['日付'],
        y=df['累計'],
        mode='lines+markers',
        name='累計登録数',
        line=dict(color='#667eea', width=3),
        marker=dict(size=8, color='#764ba2')
    ))
    fig.update_layout(
        title="登録数の推移",
        xaxis_title="日付",
        yaxis_title="累計登録数",
        height=300,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    return fig

def show_materials_duplicate_diagnostics():
    """材料重複診断UIを表示"""
    st.markdown("# 🔍 材料重複診断")
    st.markdown("材料の重複状況を診断します")
    st.markdown("---")
    
    db = get_db()
    try:
        # DB materials count
        db_count = db.execute(select(func.count(Material.id))).scalar() or 0
        
        # UI materials count（get_all_materials()から取得）
        materials = get_all_materials()
        ui_count = len(materials)
        
        # Unique names count
        unique_names = {m.name_official or m.name for m in materials if m.name_official or m.name}
        unique_names_count = len(unique_names)
        
        # Duplicate name list（同名の材料を検出）
        from collections import Counter
        name_counter = Counter([m.name_official or m.name for m in materials if m.name_official or m.name])
        duplicates = {name: count for name, count in name_counter.items() if count > 1}
        duplicate_list = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # 統計表示
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("DB materials count", db_count)
        with col2:
            st.metric("UI materials count", ui_count, delta=f"{ui_count - db_count}" if ui_count != db_count else None)
        with col3:
            st.metric("Unique names count", unique_names_count)
        with col4:
            st.metric("Duplicate names", len(duplicates))
        
        # 重複チェック結果
        if ui_count == unique_names_count:
            st.success("✅ 重複なし: UI materials count == Unique names count")
        else:
            st.warning(f"⚠️ 重複あり: UI materials count ({ui_count}) != Unique names count ({unique_names_count})")
        
        # 重複リスト表示
        if duplicate_list:
            st.markdown("### 重複材料名（上位20件）")
            for name, count in duplicate_list:
                st.markdown(f"- **{name}**: {count}件")
                
                # 重複している材料のIDを表示
                duplicate_materials = [m for m in materials if (m.name_official or m.name) == name]
                ids = [str(m.id) for m in duplicate_materials]
                st.caption(f"  ID: {', '.join(ids)}")
        else:
            st.info("重複している材料名はありません。")
        
        # 詳細情報
        with st.expander("詳細情報"):
            st.markdown("#### 全材料名リスト")
            all_names = sorted([m.name_official or m.name or "名称不明" for m in materials])
            for name in all_names:
                st.text(f"- {name}")
    
    finally:
        db.close()


def show_asset_diagnostics(asset_stats: dict):
    """Asset診断UIを表示"""
    st.markdown("# 🔍 Asset診断モード")
    st.markdown("生成物（元素画像など）の存在状況を診断します")
    st.markdown("---")
    
    from utils.paths import get_generated_dir, resolve_path
    from PIL import Image as PILImage
    
    # 元素画像の診断
    if "elements" in asset_stats:
        st.markdown("## 元素画像")
        elem_stats = asset_stats["elements"]
        
        if "error" in elem_stats:
            st.error(f"エラー: {elem_stats['error']}")
        else:
            total = elem_stats.get("total", 0)
            existing = elem_stats.get("existing", 0)
            generated = elem_stats.get("generated", 0)
            failed = elem_stats.get("failed", 0)
            missing = elem_stats.get("missing_files", [])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("総数", total)
            with col2:
                st.metric("存在", existing, delta=f"{existing/total*100:.1f}%" if total > 0 else "0%")
            with col3:
                st.metric("生成", generated)
            with col4:
                st.metric("欠損", failed, delta=f"-{failed}" if failed > 0 else None, delta_color="inverse")
            
            if missing:
                with st.expander(f"欠損ファイル一覧 ({len(missing)}件)", expanded=False):
                    for filename in missing[:20]:  # 最大20件表示
                        st.text(f"  • {filename}")
                    if len(missing) > 20:
                        st.text(f"  ... 他 {len(missing) - 20} 件")
            
            # 代表的な画像のプレビュー
            if existing > 0:
                st.markdown("#### プレビュー（代表例）")
                elem_dir = get_generated_dir("elements")
                preview_files = list(elem_dir.glob("element_*.png"))[:6]  # 最大6件
                
                if preview_files:
                    cols = st.columns(min(3, len(preview_files)))
                    for idx, filepath in enumerate(preview_files):
                        with cols[idx % 3]:
                            try:
                                from utils.image_display import display_image_unified
                                display_image_unified(filepath, caption=filepath.name, width=150)
                            except Exception as e:
                                st.caption(f"{filepath.name} (読み込みエラー)")
    
    # 加工例画像の診断
    if "process_examples" in asset_stats:
        st.markdown("---")
        st.markdown("## 加工例画像")
        proc_stats = asset_stats["process_examples"]
        
        if "error" in proc_stats:
            st.error(f"エラー: {proc_stats['error']}")
        else:
            total = proc_stats.get("total", 0)
            existing = proc_stats.get("existing", 0)
            generated = proc_stats.get("generated", 0)
            failed = proc_stats.get("failed", 0)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("総数", total)
            with col2:
                st.metric("存在", existing)
            with col3:
                st.metric("生成", generated)
            with col4:
                st.metric("欠損", failed, delta_color="inverse" if failed > 0 else "normal")
    
    # カテゴリ画像の診断
    if "categories" in asset_stats:
        st.markdown("---")
        st.markdown("## カテゴリ画像")
        cat_stats = asset_stats["categories"]
        
        if "error" in cat_stats:
            st.error(f"エラー: {cat_stats['error']}")
        else:
            total = cat_stats.get("total", 0)
            existing = cat_stats.get("existing", 0)
            st.metric("総数", total)
            st.metric("存在", existing)
    
    st.markdown("---")
    st.info("💡 ヒント: 欠損がある場合は、アプリを再起動すると自動生成されます。")

# メインアプリケーション
def get_assets_mode_stats():
    """
    Assets Mode診断: URLを持つ画像数をカウント
    
    Returns:
        (mode, url_count, total_count) のタプル
    """
    db = get_db()
    try:
        # Imageテーブル
        total_images = db.query(func.count(Image.id)).scalar() or 0
        url_images = db.query(func.count(Image.id)).filter(
            Image.url != None,
            Image.url != ""
        ).scalar() or 0
        
        # Material.texture_image_url
        total_textures = db.query(func.count(Material.id)).filter(
            Material.texture_image_path != None,
            Material.texture_image_path != ""
        ).scalar() or 0
        url_textures = db.query(func.count(Material.id)).filter(
            Material.texture_image_url != None,
            Material.texture_image_url != ""
        ).scalar() or 0
        
        # UseExample.image_url
        total_use_cases = db.query(func.count(UseExample.id)).filter(
            UseExample.image_path != None,
            UseExample.image_path != ""
        ).scalar() or 0
        url_use_cases = db.query(func.count(UseExample.id)).filter(
            UseExample.image_url != None,
            UseExample.image_url != ""
        ).scalar() or 0
        
        # ProcessExampleImage.image_url
        total_process = db.query(func.count(ProcessExampleImage.id)).filter(
            ProcessExampleImage.image_path != None,
            ProcessExampleImage.image_path != ""
        ).scalar() or 0
        url_process = db.query(func.count(ProcessExampleImage.id)).filter(
            ProcessExampleImage.image_url != None,
            ProcessExampleImage.image_url != ""
        ).scalar() or 0
        
        total_count = total_images + total_textures + total_use_cases + total_process
        url_count = url_images + url_textures + url_use_cases + url_process
        
        if url_count > 0:
            mode = "url" if url_count == total_count else "mixed"
        else:
            mode = "local"
        
        return mode, url_count, total_count
    finally:
        db.close()


def render_debug_sidebar_early():
    """
    Debugを先に描画（UIが出る前に死ぬ問題を回避）
    DBのpath/sha/columns/件数を表示
    例外が起きても最後まで描く（st.stop()は絶対に呼ばない）
    """
    import traceback
    import hashlib
    from pathlib import Path
    import sqlite3
    
    with st.sidebar:
        try:
            st.caption(f"build: {get_git_sha()}")
            st.caption(f"time: {datetime.now().isoformat(timespec='seconds')}")
        except Exception as e:
            # sidebarで例外が起きたら警告を出して続行（本体描画を止めない）
            st.sidebar.warning("Sidebar: build/time debug failed")
            with st.sidebar.expander("詳細", expanded=False):
                st.sidebar.exception(e)
        
        # デバッグ情報（DEBUG=1のときのみ表示）
        if os.getenv("DEBUG", "0") == "1":
            with st.expander("🔧 Debug", expanded=False):
                # 環境情報（例外が起きても続行）
                try:
                    st.write("**環境情報:**")
                    st.write(f"- **cwd:** {str(Path.cwd())}")
                    st.write(f"- **__file__:** {__file__}")
                except Exception as e:
                    # sidebarで例外が起きたら警告を出して続行（本体描画を止めない）
                    st.sidebar.warning("Sidebar: env debug failed")
                    with st.sidebar.expander("詳細", expanded=False):
                        st.sidebar.exception(e)
                
                st.write("---")
                
                # DB fingerprint（ここで落ちてもアプリは止めない）
                try:
                    # 絶対パス固定（相対パス事故を潰す）
                    db_path = Path(__file__).parent / "materials.db"
                    st.write("**materials.db fingerprint:**")
                    
                    if not db_path.exists():
                        st.error(f"missing: {db_path}")
                    else:
                        b = db_path.read_bytes()
                        st.write(f"- **abs path:** {str(db_path.resolve())}")
                        st.write(f"- **size:** {db_path.stat().st_size:,} bytes")
                        st.write(f"- **mtime:** {datetime.fromtimestamp(db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write(f"- **sha256:** {hashlib.sha256(b).hexdigest()[:16]}")
                        
                        con = sqlite3.connect(str(db_path))
                        try:
                            cnt = con.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                            st.write(f"- **count(materials):** {cnt} 件")
                            
                            cols = [r[1] for r in con.execute("PRAGMA table_info(materials)")]
                            if len(cols) > 50:
                                st.write(f"- **cols (先頭50件):** {', '.join(cols[:50])} ...")
                                st.write(f"  (他 {len(cols) - 50} 列)")
                            else:
                                st.write(f"- **cols (全{len(cols)}件):** {', '.join(cols)}")
                            
                            if cnt > 0:
                                first = con.execute("SELECT name_official, name FROM materials LIMIT 1").fetchone()
                                if first:
                                    first_name = first[0] or first[1] or "N/A"
                                    st.write(f"- **first material name:** {first_name}")
                        finally:
                            con.close()
                except Exception as e:
                    # sidebarで例外が起きたら警告を出して続行（本体描画を止めない）
                    st.sidebar.warning("Sidebar: DB fingerprint failed")
                    with st.sidebar.expander("詳細", expanded=False):
                        st.sidebar.exception(e)
                
                st.write("---")
                
                # card_generator/schemasのimportエラー情報（防御的に参照）
                try:
                    err = globals().get("_card_generator_import_error")
                    tb = globals().get("_card_generator_import_traceback")
                    if err:
                        st.write("**card_generator/schemas import エラー:**")
                        st.write(f"- **エラー:** {err}")
                        if tb:
                            with st.expander("詳細なトレースバック", expanded=False):
                                st.code(tb, language="python")
                    else:
                        st.write("**card_generator/schemas import:** ✅ 成功")
                except Exception as e:
                    # sidebarで例外が起きたら警告を出して続行（本体描画を止めない）
                    st.sidebar.warning("Sidebar: import error debug failed")
                    with st.sidebar.expander("詳細", expanded=False):
                        st.sidebar.exception(e)
                
                st.write("---")
                
                # 画像探索の詳細情報（Cloud上で実際のフォルダ・画像を確認）
                try:
                    from utils.image_display import get_material_image_ref
                    import re
                    
                    base = Path(__file__).parent / "static" / "images" / "materials"
                    # Cloud Secretsの前提を明記
                    image_base_url = os.getenv("IMAGE_BASE_URL")
                    image_version = os.getenv("IMAGE_VERSION")
                    st.write("**Cloud Secrets:**")
                    st.write(f"- **IMAGE_BASE_URL:** {'設定済み' if image_base_url else '未設定'}")
                    if image_base_url:
                        # 伏字で表示（最初の10文字のみ）
                        masked = image_base_url[:10] + "..." if len(image_base_url) > 10 else image_base_url
                        st.write(f"  - 値: {masked}")
                    st.write(f"- **IMAGE_VERSION:** {'設定済み' if image_version else '未設定'}")
                    if image_version:
                        st.write(f"  - 値: {image_version[:10]}...")
                    
                    st.write("**画像探索情報:**")
                    st.write(f"- **base dir:** {str(base)}")
                    
                    if base.exists():
                        dirs = [p.name for p in base.iterdir() if p.is_dir()]
                        primaries = list(base.glob("*/primary.jpg"))
                        st.write(f"- **dir count:** {len(dirs)}")
                        st.write(f"- **dirs (sample, 先頭30):** {dirs[:30]}")
                        st.write(f"- **primary.jpg count:** {len(primaries)}")
                    else:
                        st.warning(f"base dir not exists: {base}")
                        dirs = []
                    
                    # materialsを取得できている前提（取れない時はDB debugだけ出す）
                    try:
                        materials = get_all_materials()
                        if materials:
                            st.write(f"- **materials count:** {len(materials)}")
                            st.write("**素材ごとの探索結果:**")
                            
                            for m in materials[:30]:  # 先頭30件のみ
                                try:
                                    # get_material_image_refを使用して画像参照を取得
                                    # project_rootはbaseの親の親の親（static/images/materials -> static/images -> static -> プロジェクトルート）
                                    project_root = base.parent.parent.parent
                                    primary_src, primary_debug = get_material_image_ref(m, "primary", project_root)
                                    space_src, space_debug = get_material_image_ref(m, "space", project_root)
                                    product_src, product_debug = get_material_image_ref(m, "product", project_root)
                                    
                                    material_display_name = getattr(m, 'name_official', None) or getattr(m, 'name', None) or "N/A"
                                    
                                    with st.expander(f"📦 {material_display_name}", expanded=False):
                                        # safe_slugとbase_dir_sampleを表示
                                        safe_slug = primary_debug.get('safe_slug', 'N/A')
                                        base_dir_sample = primary_debug.get('base_dir_sample', [])
                                        chosen_branch = primary_debug.get('chosen_branch', 'unknown')
                                        final_src_type = primary_debug.get('final_src_type', 'unknown')
                                        final_path_exists = primary_debug.get('final_path_exists', False)
                                        
                                        st.write(f"**safe_slug:** {safe_slug}")
                                        st.write(f"**base_dir_sample:** {', '.join(base_dir_sample[:10])}..." if len(base_dir_sample) > 10 else f"**base_dir_sample:** {', '.join(base_dir_sample)}")
                                        st.write(f"**chosen_branch:** {chosen_branch}")
                                        st.write(f"**final_src_type:** {final_src_type}")
                                        st.write(f"**final_path_exists:** {final_path_exists}")
                                        
                                        if primary_src:
                                            if isinstance(primary_src, str):
                                                st.write(f"**final_url:** {primary_src[:80]}..." if len(primary_src) > 80 else f"**final_url:** {primary_src}")
                                            elif isinstance(primary_src, Path):
                                                st.write(f"**final_path:** {primary_src.resolve()}")
                                        else:
                                            st.warning("⚠️ primary.jpg not found")
                                        
                                        # candidate_pathsとfailed_pathsを表示
                                        candidate_paths = primary_debug.get('candidate_paths', [])
                                        failed_paths = primary_debug.get('failed_paths', [])
                                        if candidate_paths:
                                            st.write(f"**candidate_paths:** {len(candidate_paths)}件")
                                        if failed_paths:
                                            st.write(f"**failed_paths:** {len(failed_paths)}件")
                                        
                                        # 詳細情報はexpanderへ
                                        with st.expander("🔍 詳細デバッグ情報", expanded=False):
                                            st.json(primary_debug)
                                except Exception as e:
                                    st.write(f"❌ {getattr(m, 'name_official', None) or 'N/A'}: {e}")
                                    with st.expander("詳細", expanded=False):
                                        st.code(traceback.format_exc())
                        else:
                            st.write("- **materials:** 0件（DBが空）")
                    except Exception as e:
                        st.warning("materials取得失敗（DB debugだけ表示）")
                        with st.expander("詳細", expanded=False):
                            st.code(traceback.format_exc())
                except Exception as e:
                    # sidebarで例外が起きたら警告を出して続行（本体描画を止めない）
                    st.sidebar.warning("Sidebar: 画像探索情報の取得に失敗")
                    with st.sidebar.expander("詳細", expanded=False):
                        st.sidebar.exception(e)


def main():
    # 実行順序の安全策: is_debug_flag が存在することを確認
    if "is_debug_flag" not in globals() or not callable(globals().get("is_debug_flag")):
        # 万が一 is_debug_flag が存在しない場合は警告を出して続行
        st.warning("⚠️ is_debug_flag is not available. Using fallback.")
        # fallback を定義
        globals()["is_debug_flag"] = is_debug
    
    # パフォーマンス計測（DEBUG=1のみ）
    import time
    t0_main = time.perf_counter() if is_debug_flag() else None
    
    # 起動順序を固定：Debug表示 → init_db() → その後に通常処理
    
    # 常時表示: 実行中のコミットSHA（反映確認用）
    st.caption(f"RUNNING_SHA: {get_running_sha()}")
    
    # DEBUG判定とデバッグ情報表示
    if is_debug_flag():
        debug_info = {
            "DEPLOY_VERSION": DEPLOY_VERSION,
            "APP_FILE": __file__,
            "DEBUG_ENV": os.getenv("DEBUG"),
            "DEBUG_SECRET": None,
            "DB_URL": None,
        }
        # st.secretsからDEBUGを取得
        try:
            debug_info["DEBUG_SECRET"] = st.secrets.get("DEBUG")
        except Exception:
            pass
        
        # DB接続先情報を取得（マスク済み）
        try:
            import utils.settings as settings
            db_url = settings.get_database_url()
            debug_info["DB_URL"] = settings.mask_db_url(db_url)
            debug_info["DB_DIALECT"] = settings.get_db_dialect(db_url)
            
            # utils.settings のデバッグ情報（原因特定用）
            try:
                debug_info["utils.settings"] = {
                    "__file__": str(getattr(settings, "__file__", "unknown")),
                    "has_get_flag": hasattr(settings, "get_flag"),
                    "get_flag_callable": callable(getattr(settings, "get_flag", None)),
                    "version": getattr(settings, "SETTINGS_VERSION", "unknown"),
                    "dir_contains_get_flag": "get_flag" in dir(settings),
                }
                # get_flag が呼べるかテスト
                test_flag = settings.get_flag("DEBUG", False)
                debug_info["utils.settings"]["test_get_flag_result"] = test_flag
            except Exception as e:
                debug_info["utils.settings"] = {"error": str(e)}
            
            # utils.r2_storage のデバッグ情報（実行されているモジュールを確定）
            try:
                import utils.r2_storage as r2
                debug_info["utils.r2_storage"] = {
                    "__file__": str(getattr(r2, "__file__", None)),
                    "has_upload_uploadedfile_to_prefix": hasattr(r2, "upload_uploadedfile_to_prefix"),
                    "r2_storage_version": getattr(r2, "R2_STORAGE_VERSION", None),
                    "dir_contains_prefix": "upload_uploadedfile_to_prefix" in dir(r2),
                }
                # upload_uploadedfile_to_prefix が呼べるかテスト（callableチェック）
                if hasattr(r2, "upload_uploadedfile_to_prefix"):
                    debug_info["utils.r2_storage"]["prefix_callable"] = callable(getattr(r2, "upload_uploadedfile_to_prefix", None))
                else:
                    debug_info["utils.r2_storage"]["prefix_callable"] = False
            except Exception as e:
                debug_info["utils.r2_storage"] = {"error": str(e)}
            
            # 実行中ファイルの内容を確認する診断（ファイルプローブ）
            def _file_probe(path: str, needles: list[str], head_chars: int = 1200):
                """ファイルの内容を確認する診断関数"""
                import hashlib
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    text = data.decode("utf-8", errors="replace")
                    return {
                        "path": path,
                        "sha256": hashlib.sha256(data).hexdigest()[:12],
                        "contains": {n: (n in text) for n in needles},
                        "head": text[:head_chars],
                    }
                except Exception as e:
                    return {"path": path, "error": str(e)}
            
            # utils.settings と utils.r2_storage の実行中ファイルをプローブ
            try:
                import utils.settings as settings
                import utils.r2_storage as r2
                debug_info["runtime_file_probe"] = {
                    "utils.settings": _file_probe(
                        getattr(settings, "__file__", ""),
                        needles=["def get_flag", "SETTINGS_VERSION"]
                    ),
                    "utils.r2_storage": _file_probe(
                        getattr(r2, "__file__", ""),
                        needles=["def upload_uploadedfile_to_prefix", "R2_STORAGE_VERSION"]
                    ),
                }
            except Exception as e:
                debug_info["runtime_file_probe"] = {"error": str(e)}
        except Exception as e:
            debug_info["DB_ERROR"] = str(e)
        
        st.json(debug_info)
    
    # 本文到達マーカー（DBやoption_menuより前に必ず出す）
    st.markdown("### ✅ App booted (body reached)")
    print("[BOOT] body reached")  # runtime logsで見える
    
    # 1. Debugを先に描画（UIが出る前に死ぬ問題を回避）
    # 例外が起きても最後まで描く（st.stop()は呼ばない）
    # 同一run内で1回だけ描画する（二重表示を防ぐ）
    if "debug_sidebar_rendered" not in st.session_state:
        try:
            render_debug_sidebar_early()
            # ロゴファイルのデバッグ情報を表示（DEBUG=1の時のみ）
            try:
                show_logo_debug_info()
            except Exception as e:
                st.sidebar.warning(f"ロゴデバッグ情報の表示に失敗: {e}")
            st.session_state["debug_sidebar_rendered"] = True
        except Exception as e:
            _panic_screen("render_debug_sidebar_early in main()", e)
            # st.stop()は呼ばない（本文を表示するため）
    
    # 2. init_db()を呼ぶ（常に）
    # 例外が起きても本文を表示する（st.stop()は呼ばない）
    try:
        init_db()
        print("[BOOT] init_db() done")
    except Exception as e:
        # 例外を可視化（本文に出す）
        st.error("DB初期化エラー")
        st.exception(e)
        st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
        # st.stop()は呼ばない（本文を表示するため）
    
    # 3. スキーマドリフト検知（軽量、キャッシュ済み）
    try:
        from database import get_schema_drift_status
        from utils.settings import get_database_url
        schema_status = get_schema_drift_status(get_database_url())
        
        # スキーマチェックが成功した場合のみ、スキーマ不整合の警告を表示
        if schema_status.get("ok", False):
            # スキーマ不整合がある場合は警告を表示
            images_ok = schema_status.get("images_ok", False)
            # 後方互換: images_kind_exists も確認
            if not images_ok and not schema_status.get("images_kind_exists", False):
                missing_columns = schema_status.get("images_missing_columns", [])
                if missing_columns:
                    missing_cols_str = ", ".join(missing_columns)
                    st.warning(f"""
                    ⚠️ **DB Schema Mismatch Detected**
                    
                    The `images` table is missing required columns: **{missing_cols_str}**
                    
                    This may cause errors when loading materials.
                    
                    **To fix:**
                    1. Set `MIGRATE_ON_START=1` in Streamlit Secrets
                    2. Reboot the application
                    3. The migration will run automatically and add the missing columns
                    
                    **Current status:** Running in safe mode (images are not loaded to prevent crashes)
                    """)
                else:
                    st.warning("""
                    ⚠️ **DB Schema Mismatch Detected**
                    
                    The `images` table is missing required columns. This may cause errors when loading materials.
                    
                    **To fix:**
                    1. Set `MIGRATE_ON_START=1` in Streamlit Secrets
                    2. Reboot the application
                    3. The migration will run automatically and add the missing columns
                    
                    **Current status:** Running in safe mode (images are not loaded to prevent crashes)
                    """)
                
                # 管理者向けに詳細情報を表示（is_admin は後で定義されるが、ここでは直接チェック）
                if os.getenv("DEBUG", "0") == "1" or os.getenv("ADMIN", "0") == "1":
                    with st.expander("🔍 Schema Status Details", expanded=False):
                        st.json(schema_status)
            
            # エラーがある場合は表示（ok==True の場合でも）
            if schema_status.get("errors"):
                for error in schema_status["errors"]:
                    st.warning(f"Schema check warning: {error}")
        else:
            # スキーマチェックが失敗した場合（ok==False）
            st.warning("""
            ⚠️ **DB Schema Check Failed**
            
            Unable to verify database schema. Running in safe mode to prevent crashes.
            
            **Details:**
            """)
            if schema_status.get("errors"):
                for error in schema_status["errors"]:
                    st.error(f"Schema check error: {error}")
            
            # 管理者向けに詳細情報を表示
            if os.getenv("DEBUG", "0") == "1" or os.getenv("ADMIN", "0") == "1":
                with st.expander("🔍 Schema Status Details", expanded=False):
                    st.json(schema_status)
    except Exception as e:
        # スキーマチェック失敗時は警告を表示して続行（PANICしない）
        st.warning(f"⚠️ DB Schema check failed: {e}. Running in safe mode.")
        if os.getenv("DEBUG", "0") == "1":
            print(f"[SCHEMA] schema check exception: {e}")
            import traceback
            traceback.print_exc()
    
    # 4. その後に通常処理（Debugは既にrender_debug_sidebar_early()で表示済み）
    
    # アセット確保（生成物の自動生成）
    try:
        from utils.ensure_assets import ensure_all_assets
        asset_stats = ensure_all_assets()
    except Exception as e:
        # 例外を可視化（本文に出す）
        st.warning(f"アセット確保エラー: {e}")
        st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
        asset_stats = {}
    
    # サンプルデータの自動投入（INIT_SAMPLE_DATA=1 かつ DBが空の時だけ実行）
    # init_db()の後に実行（スキーマ補完完了後）
    # 例外が出てもアプリ起動を殺さない
    try:
        maybe_init_sample_data()
    except Exception as e:
        # 例外はログのみ（起動時クラッシュを防ぐため、画面には出さない）
        import traceback
        print(f"[WARN] maybe_init_sample_data() failed: {e}")
        if os.getenv("DEBUG", "0") == "1":
            st.warning(f"maybe_init_sample_data() failed: {e}")
            st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
        # アプリ起動は続行
    
    # 画像の自動修復（INIT_SAMPLE_DATA=1 の時だけ）
    # init_db()の後に実行（スキーマ補完完了後）
    if os.getenv("INIT_SAMPLE_DATA") == "1":
        try:
            from utils.ensure_images import ensure_images
            ensure_images(Path.cwd())
        except Exception as e:
            # 例外を可視化（本文に出す）
            st.warning(f"画像自動修復エラー: {e}")
            st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
            # アプリ起動は続行
    
    # デバッグスイッチ（サイドバーでCSSを無効化可能）
    debug_no_css = st.sidebar.checkbox("Debug: CSSを無効化", value=False, help="白飛びが発生している場合、このチェックをONにするとCSSを無効化して表示を確認できます")
    
    # 画像診断モード（開発用）
    debug_images = st.sidebar.checkbox("🔍 画像診断モード", value=False, help="画像の健康状態を診断します（原因切り分け用）")
    
    # Asset診断モード（新規）
    debug_assets = st.sidebar.checkbox("🔍 Asset診断モード", value=False, help="生成物（元素画像など）の存在状況を診断します")
    
    # 材料重複診断モード（新規）
    debug_materials_duplicate = st.sidebar.checkbox("🔍 材料重複診断", value=False, help="材料の重複状況を診断します")
    
    # CSS適用（デバッグモードでない場合のみ）
    if not debug_no_css:
        st.markdown(get_custom_css(), unsafe_allow_html=True)
    else:
        # デバッグモード: 最小限のCSSのみ（可読性確保）
        st.markdown("""
        <style>
            /* デバッグモード: 最小限のスタイル */
            body, html {
                color: #111 !important;
                background: #f5f5f5 !important;
            }
            .stApp {
                background: #f5f5f5 !important;
            }
            .stApp::before {
                display: none !important;
            }
            [class*="st-"] {
                color: #111 !important;
            }
        </style>
        """, unsafe_allow_html=True)
        st.warning("デバッグモード: CSS（<style>注入）が無効化されています。ロゴ/画像描画は正常に実行されます。")
    
    # ヘッダー - WOTA風シンプル
    # 本文UIの開始（Debug sidebarはrun_app_entrypointで先に描画済み）
    # タイトルは各ページでロゴとして表示（show_home()など）
    
    # 素材件数の表示（エラーハンドリング付き）
    try:
        materials = get_all_materials()
        st.write(f"素材件数: {len(materials)} 件")
    except Exception as e:
        st.error("❌ main() 内でエラーが発生しました")
        import traceback
        st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
        # エラー時も続行（materialsを空リストとして扱う）
        materials = []
    
    # ページ状態の初期化
    if 'page' not in st.session_state:
        st.session_state.page = "ホーム"
    if 'selected_material_id' not in st.session_state:
        st.session_state.selected_material_id = None
    
    # 詳細ページへの遷移がリクエストされた場合
    if st.session_state.selected_material_id and st.session_state.page != "detail":
        # 詳細ページに遷移する場合は、ページを"材料一覧"に設定（詳細表示モード）
        st.session_state.page = "材料一覧"
    
    # サイドバー - WOTA風シンプル
    with st.sidebar:
        st.markdown("""
        <div style="text-align: left; padding: 20px 0 24px 0; border-bottom: 1px solid rgba(0,0,0,0.08);">
            <h2 style="color: #1a1a1a; margin: 0; font-weight: 600; font-size: 18px; letter-spacing: -0.01em;">メニュー</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # 管理者表示チェック（DEBUG=1 or ADMIN=1のときのみ）
        is_admin = os.getenv("DEBUG", "0") == "1" or os.getenv("ADMIN", "0") == "1"
        
        # ページ選択（詳細ページ表示中は選択を変更しない）
        if st.session_state.selected_material_id:
            # 詳細ページ表示中は、ページ選択を一時的に無効化
            st.session_state.page = "材料一覧"
            page = "材料一覧"
        else:
            # 管理者の場合は「承認待ち一覧」を追加
            page_options = ["ホーム", "材料一覧", "材料登録", "ダッシュボード", "検索", "素材カード", "元素周期表"]
            if is_admin:
                page_options.append("承認待ち一覧")
            
            page = st.radio(
                "ページを選択",
                page_options,
                index=page_options.index(st.session_state.page) if st.session_state.page in page_options else 0,
                label_visibility="collapsed"
            )
            st.session_state.page = page
        
        st.markdown("---")
        
        # 管理者認証（ADMIN_PASSWORD）
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if admin_password:
            # セッション状態で認証状態を管理
            if "admin_authenticated" not in st.session_state:
                st.session_state["admin_authenticated"] = False
            
            if not st.session_state["admin_authenticated"]:
                st.markdown("---")
                st.markdown("### 🔐 管理者認証")
                password_input = st.text_input(
                    "管理者パスワード",
                    type="password",
                    key="admin_password_input"
                )
                if st.button("認証", key="admin_auth_button"):
                    if password_input == admin_password:
                        st.session_state["admin_authenticated"] = True
                        st.success("✅ 認証成功")
                        st.rerun()
                    else:
                        st.error("❌ パスワードが正しくありません")
                # 認証されていない場合は管理者機能を無効化
                is_admin = False
            else:
                if st.button("🔓 ログアウト", key="admin_logout"):
                    st.session_state["admin_authenticated"] = False
                    st.rerun()
        
        # 管理者表示チェック（既に上で定義済み）
        if is_admin:
            include_unpublished = st.checkbox(
                "管理者表示（非公開も表示）",
                value=st.session_state.get("include_unpublished", False),
                key="admin_include_unpublished"
            )
            st.session_state["include_unpublished"] = include_unpublished
        else:
            include_unpublished = False
        
        # 統計情報（画面左下に小さく表示）
        include_deleted = st.session_state.get("include_deleted", False) if is_admin else False
        materials = get_all_materials(include_unpublished=include_unpublished, include_deleted=include_deleted)
        
        # SQLで直接カウント（DetachedInstanceError回避）
        db = get_db()
        try:
            total_properties = db.execute(select(func.count(Property.id))).scalar() or 0
        finally:
            db.close()
        
        categories = len(set([m.category for m in materials if m.category])) if materials else 0
        
        # 左下に小さく配置
        st.markdown("""
        <div class="stats-fixed">
            <div>材料数: <strong>{}</strong></div>
            <div>カテゴリ: <strong>{}</strong></div>
            <div>物性データ: <strong>{}</strong></div>
        </div>
        """.format(len(materials), categories, total_properties), unsafe_allow_html=True)
        
        st.markdown("""
        <div style="text-align: center; padding: 20px 0; color: #666;">
            <small>Material Map v1.0</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Asset診断モード（デバッグ時のみ表示）
    if debug_assets:
        show_asset_diagnostics(asset_stats)
        return  # 診断モード時は他のページを表示しない
    
    # 画像診断モード（デバッグ時のみ表示）
    if debug_images:
        from utils.image_diagnostics import show_image_diagnostics
        materials = get_all_materials()
        show_image_diagnostics(materials, Path.cwd())
        return  # 診断モード時は他のページを表示しない
    
    # 管理者表示フラグを取得
    include_unpublished = st.session_state.get("include_unpublished", False)
    include_deleted = st.session_state.get("include_deleted", False) if is_admin else False
    
    # ページルーティング
    if page == "ホーム":
        show_home()
    elif page == "材料一覧":
        show_materials_list(include_unpublished=include_unpublished, include_deleted=include_deleted)
    elif page == "材料登録":
        # 編集モードの場合はmaterial_idを渡す
        edit_material_id = st.session_state.get("edit_material_id")
        if edit_material_id:
            show_detailed_material_form(material_id=edit_material_id)
            # 編集完了後はedit_material_idをクリア
            if st.session_state.get("edit_completed"):
                st.session_state.edit_material_id = None
                st.session_state.edit_completed = False
        else:
            show_detailed_material_form()
    elif page == "ダッシュボード":
        show_dashboard()
    elif page == "検索":
        show_search()
    elif page == "素材カード":
        show_material_cards()
    elif page == "元素周期表":
        show_periodic_table()
    elif page == "承認待ち一覧":
        # 管理者のみアクセス可能
        if is_admin:
            show_approval_queue()
        else:
            st.error("❌ このページは管理者のみアクセス可能です。")
    elif page == "投稿ステータス確認":
        show_submission_status()

def resolve_home_main_visual(project_root: Optional[Path] = None) -> tuple[Optional[Path], Optional[bytes]]:
    """
    ホームのメインビジュアル画像のパスと画像データを解決
    static/images/メイン.jpg を優先し、WebPが読めない環境ではjpg/pngにフォールバック
    PILで開けるかを検証して、開けない候補はスキップ
    
    Args:
        project_root: プロジェクトルート（Noneの場合は自動解決）
    
    Returns:
        (見つかった画像のPath, 画像データのbytes) のタプル、見つからなければ (None, None)
    """
    if project_root is None:
        # Path解決は Path(__file__).resolve().parent を project_root として開始
        project_root = Path(__file__).resolve().parent
        
        # 念のため static/ が存在する上位ディレクトリまで最大3階層だけ辿って見つける（Cloudのcwdズレ対策）
        current = project_root
        for _ in range(3):
            static_dir = current / "static"
            if static_dir.exists() and static_dir.is_dir():
                project_root = current
                break
            if current == current.parent:
                break
            current = current.parent
    
    # WebPサポートチェック
    webp_supported = False
    try:
        from PIL import features
        webp_supported = features.check("webp")
    except Exception:
        pass
    
    # 候補の優先順（まず static/images を正とする）
    candidate_paths = [
        project_root / "static" / "images" / "メイン.jpg",
        project_root / "static" / "images" / "メイン.png",
    ]
    
    if webp_supported:
        # WebP対応時のみWebP候補を追加
        candidate_paths.append(project_root / "static" / "images" / "メイン.webp")
    
    candidate_paths.extend([
        project_root / "写真" / "メイン.jpg",
        project_root / "写真" / "メイン.png",
    ])
    
    if webp_supported:
        candidate_paths.append(project_root / "写真" / "メイン.webp")
    
    # 必要なら static/メイン.* も最後尾
    candidate_paths.extend([
        project_root / "static" / "メイン.jpg",
        project_root / "static" / "メイン.png",
    ])
    
    if webp_supported:
        candidate_paths.append(project_root / "static" / "メイン.webp")
    
    # 各候補を「存在する & 実際に読み込める」順に選ぶ
    for path in candidate_paths:
        if not path.exists() or not path.is_file():
            continue
        
        # PILで開けるかを検証
        try:
            from PIL import Image
            with Image.open(path) as img:
                # 画像を開いて検証（実際に読み込めるか確認）
                img.verify()
            
            # 検証後、再度開いてbytesに変換
            # verify()で検証した後は画像が閉じられるので、再度開く必要がある
            img = Image.open(path)
            try:
                # RGBに変換（RGBAやPモードなどに対応）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # BytesIOに保存してbytesを取得
                from io import BytesIO
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=95)
                image_bytes = buffer.getvalue()
                
                return (path, image_bytes)
            finally:
                img.close()
        except Exception as e:
            # 開けない候補はスキップして次へ（エラーはデバッグ情報に含める）
            continue
    
    return (None, None)


def get_main_visual_debug_info() -> Dict[str, Any]:
    """
    メインビジュアル画像のデバッグ情報を辞書形式で返す（DEBUG表示用）
    
    Returns:
        デバッグ情報の辞書
    """
    # Path解決は Path(__file__).resolve().parent を project_root として開始
    project_root = Path(__file__).resolve().parent
    
    # 念のため static/ が存在する上位ディレクトリまで最大3階層だけ辿って見つける
    current = project_root
    for _ in range(3):
        static_dir = current / "static"
        if static_dir.exists() and static_dir.is_dir():
            project_root = current
            break
        if current == current.parent:
            break
        current = current.parent
    
    # WebPサポートチェック
    webp_supported = False
    try:
        from PIL import features
        webp_supported = features.check("webp")
    except Exception:
        pass
    
    # 候補の優先順（まず static/images を正とする）
    candidate_paths = [
        project_root / "static" / "images" / "メイン.jpg",
        project_root / "static" / "images" / "メイン.png",
    ]
    
    if webp_supported:
        candidate_paths.append(project_root / "static" / "images" / "メイン.webp")
    
    candidate_paths.extend([
        project_root / "写真" / "メイン.jpg",
        project_root / "写真" / "メイン.png",
    ])
    
    if webp_supported:
        candidate_paths.append(project_root / "写真" / "メイン.webp")
    
    candidate_paths.extend([
        project_root / "static" / "メイン.jpg",
        project_root / "static" / "メイン.png",
    ])
    
    if webp_supported:
        candidate_paths.append(project_root / "static" / "メイン.webp")
    
    # 各候補の存在確認とPILで開けるか検証
    candidates = []
    for path in candidate_paths:
        exists = path.exists() and path.is_file()
        open_ok = False
        error = None
        
        if exists:
            try:
                from PIL import Image
                with Image.open(path) as img:
                    img.verify()
                open_ok = True
            except Exception as e:
                error = str(e)
        
        candidates.append({
            "path": str(path),
            "exists": exists,
            "size": path.stat().st_size if exists else 0,
            "mtime": path.stat().st_mtime if exists else 0,
            "open_ok": open_ok,
            "error": error,
        })
    
    # 最終的に選ばれたパスと画像データ
    selected_path, selected_bytes = resolve_home_main_visual(project_root)
    
    return {
        "project_root": str(project_root),
        "pil_webp_supported": webp_supported,
        "candidates": candidates,
        "selected_path": str(selected_path) if selected_path else None,
        "selected_exists": selected_path.exists() if selected_path else False,
        "selected_size": selected_path.stat().st_size if selected_path and selected_path.exists() else 0,
        "selected_mtime": selected_path.stat().st_mtime if selected_path and selected_path.exists() else 0,
        "selected_bytes_size": len(selected_bytes) if selected_bytes else 0,
    }


def show_home():
    """ホームページ"""
    # 実行順序の安全策: is_debug_flag が存在することを確認
    if "is_debug_flag" not in globals() or not callable(globals().get("is_debug_flag")):
        # 万が一 is_debug_flag が存在しない場合は fallback
        debug_enabled = os.getenv("DEBUG", "0") == "1"
    else:
        debug_enabled = is_debug_flag()
    
    # パフォーマンス計測（DEBUG=1のみ）
    import time
    t0 = time.perf_counter() if debug_enabled else None
    
    # DEBUGタグ（反映確認用）
    if debug_enabled:
        st.caption("BUILD_TAG: APPROVAL_IMG_EDIT_FIX_V1")
    
    # デバッグモードかどうか（ローカル変数名を debug_enabled に統一）
    debug_enabled = os.getenv("DEBUG", "0") == "1"
    
    # 修正1: DEBUGモードでもロゴ/画像描画は必ず実行（CSS無効化は<style>注入だけ）
    # ロゴマークとタイプロゴを表示（ホームでは常に表示）
    # st.components.v1.htmlを使用して確実に表示
    col1, col2 = st.columns([1, 4])
    with col1:
        # ロゴマークを確実に描画（st.components.v1.htmlで直接描画）
        render_logo_mark(height_px=72, debug=is_debug, use_component=True)
    
    with col2:
        # タイプロゴとサブタイトルを描画（st.components.v1.htmlで直接描画）
        render_site_header(subtitle="素材の可能性を探索するデータベース", debug=is_debug, use_component=True)
    
    # 修正2: components描画スモークテスト（DEBUG=1時のみ）
    if is_debug:
        import streamlit.components.v1 as components
        components.html(
            "<div style='padding:6px;border:1px solid #f00;background:#fff;'>components ok</div>",
            height=40,
            scrolling=False
        )
    
    # 修正3,4: DEBUG=1のときは診断情報をst.jsonで表示（CSS無効でも読める）
    if is_debug:
        st.markdown("---")
        st.markdown("### 🔍 デバッグ情報（CSS無効でも表示）")
        
        # ロゴデバッグ情報
        logo_debug = get_logo_debug_info()
        
        # メインビジュアルデバッグ情報
        main_visual_debug = get_main_visual_debug_info()
        
        st.json({
            "logo_debug": logo_debug,
            "main_visual_debug": main_visual_debug,
        })
        
        st.markdown("---")
    
    # メイン画像をメインビジュアルとして表示
    # st.image(bytes)で直接表示（Streamlit Cloudでも安定）
    main_image_path, main_image_bytes = resolve_home_main_visual()
    
    if main_image_path and main_image_bytes:
        try:
            # CSSはDEBUG=1のときだけ無効化（<style>挿入だけ止める）
            if not is_debug:
                st.markdown("""
                <style>
                    .main-visual {
                        border-radius: 12px;
                        margin-top: 12px;
                        margin-bottom: 24px;
                        overflow: hidden;
                    }
                </style>
                """, unsafe_allow_html=True)
            
            st.markdown('<div class="main-visual">', unsafe_allow_html=True)
            # st.imageにbytesを渡して直接表示（相対パス/CWD依存を避ける）
            st.image(main_image_bytes, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e:
            if is_debug:
                st.warning(f"メイン画像の表示に失敗: {e}")
    elif is_debug:
        # 選べなければ通常は何も出さず、DEBUG=1時だけwarningを出す（ユーザー体験を壊さない）
        st.warning("⚠️ メイン画像が見つかりませんでした")
    
    # 管理者表示フラグを取得
    include_unpublished = st.session_state.get("include_unpublished", False)
    
    # DBアクセス計測
    t1 = time.perf_counter() if t0 is not None else None
    materials = get_all_materials(include_unpublished=include_unpublished)
    if t1 is not None:
        print(f"[PERF] show_home() get_all_materials: {time.perf_counter() - t1:.3f}s")
    
    # ヒーローセクション
    st.markdown("""
    <div class="hero-section">
        <h2 style="color: #2c3e50; margin-bottom: 20px; font-size: 2.5rem; font-weight: 800;">✨ ようこそ！</h2>
        <p style="font-size: 1.2rem; color: #555; line-height: 1.8; max-width: 800px; margin: 0 auto; font-weight: 500;">
            素材カード形式でマテリアル情報を管理する、美しく使いやすいデータベースシステムです。<br>
            デザイナーやエンジニアが、材料の可能性を探索するためのツールです。
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 機能紹介カード（iconmonstr風のアイコンを使用）
    st.markdown('<h3 class="section-title">主な機能</h3>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    icon1 = get_icon_svg_inline("icon-register", 40, "#999999")
    icon2 = get_icon_svg_inline("icon-chart", 40, "#999999")
    icon3 = get_icon_svg_inline("icon-card", 40, "#999999")
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div style="margin-bottom: 15px; text-align: center;">
                <img src="data:image/svg+xml;base64,{icon1}" style="width: 40px; height: 40px; opacity: 0.6;" />
            </div>
            <h3 style="color: #1a1a1a; margin: 15px 0; font-weight: 600; font-size: 1.1rem;">材料登録</h3>
            <p style="color: #666; margin: 0; font-size: 14px;">簡単に材料情報を登録・管理</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div style="margin-bottom: 15px; text-align: center;">
                <img src="data:image/svg+xml;base64,{icon2}" style="width: 40px; height: 40px; opacity: 0.6;" />
            </div>
            <h3 style="color: #1a1a1a; margin: 15px 0; font-weight: 600; font-size: 1.1rem;">データ可視化</h3>
            <p style="color: #666; margin: 0; font-size: 14px;">グラフで材料データを分析</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div style="margin-bottom: 15px; text-align: center;">
                <img src="data:image/svg+xml;base64,{icon3}" style="width: 40px; height: 40px; opacity: 0.6;" />
            </div>
            <h3 style="color: #1a1a1a; margin: 15px 0; font-weight: 600; font-size: 1.1rem;">素材カード</h3>
            <p style="color: #666; margin: 0; font-size: 14px;">素材カードを自動生成</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 強制画像テスト（診断用：DEBUG=1時のみ、かつチェックボックスONのときだけ表示）
    if os.getenv("DEBUG", "0") == "1" and materials:
        if st.checkbox("🔍 診断: 強制画像テストを表示", value=False, key="dbg_force_img_test"):
            st.markdown("---")
            st.markdown("### 🔍 強制画像テスト（診断用）")
            test_material = materials[0]
            from utils.image_display import get_material_image_ref
            from utils.logo import get_project_root
            test_src, test_debug = get_material_image_ref(test_material, "primary", get_project_root())
            
            st.write(f"**テスト対象:** {test_material.name_official or test_material.name}")
            st.write(f"**chosen_branch:** {test_debug.get('chosen_branch', 'N/A')}")
            st.write(f"**final_src_type:** {test_debug.get('final_src_type', 'N/A')}")
            
            if test_src:
                if isinstance(test_src, Path):
                    st.write(f"**Path:** {test_src.resolve()}")
                    st.write(f"**exists:** {test_src.exists()}")
                    st.write(f"**is_file:** {test_src.is_file()}")
                    if test_src.exists() and test_src.is_file():
                        st.image(test_src, width=200, caption="Path直接表示テスト")
                elif isinstance(test_src, str):
                    st.write(f"**URL:** {test_src}")
                    st.image(test_src, width=200, caption="URL直接表示テスト")
            else:
                st.warning("画像が見つかりませんでした")
            
            with st.expander("🔍 詳細デバッグ情報", expanded=True):
                st.json(test_debug)
    
    # パフォーマンス計測ログ（DEBUG=1のみ）
    if t0 is not None:
        elapsed = time.perf_counter() - t0
        print(f"[PERF] show_home() total: {elapsed:.3f}s")
    
    # 最近登録された材料
    if materials:
        st.markdown('<h3 class="section-title">最近登録された材料</h3>', unsafe_allow_html=True)
        recent_materials = sorted(materials, key=lambda x: x.created_at if x.created_at else datetime.min, reverse=True)[:6]
        
        # 2カラムレイアウト（左: サムネ、右: 情報）
        for material in recent_materials:
            with st.container():
                col_img, col_info = st.columns([1, 3])
                
                with col_img:
                    # サムネ画像を表示（キャッシュ対策: Base64エンコードで直接表示）
                    from utils.image_display import get_material_image_ref, display_image_unified
                    import hashlib
                    import time
                    
                    # 材料の主画像を取得（get_material_image_refを使用）
                    # get_material_image_refを使用
                    from utils.logo import get_project_root
                    image_src, image_debug = get_material_image_ref(material, "primary", get_project_root())
                    image_source = image_src
                    
                    # サムネサイズで表示（プレースホルダー付き）
                    if image_source:
                        # ローカルパス（Pathまたはstrでファイルがexists）の場合はPILImageとして扱う
                        if isinstance(image_source, (Path, str)) and not str(image_source).startswith(('http://', 'https://', 'data:')):
                            # ローカルファイルパスの場合
                            path = Path(image_source) if isinstance(image_source, str) else image_source
                            if path.exists() and path.is_file():
                                # PILImageとして開いて表示（キャッシュバスター不要）
                                pil_img = PILImage.open(path)
                                if pil_img.mode != 'RGB':
                                    if pil_img.mode in ('RGBA', 'LA', 'P'):
                                        rgb_img = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                                        if pil_img.mode == 'RGBA':
                                            rgb_img.paste(pil_img, mask=pil_img.split()[3])
                                        elif pil_img.mode == 'LA':
                                            rgb_img.paste(pil_img.convert('RGB'), mask=pil_img.split()[1])
                                        else:
                                            rgb_img = pil_img.convert('RGB')
                                        pil_img = rgb_img
                                    else:
                                        pil_img = pil_img.convert('RGB')
                                thumb_size = (120, 120)
                                pil_img.thumbnail(thumb_size, PILImage.Resampling.LANCZOS)
                                st.image(pil_img, width=120)
                            else:
                                display_image_unified(None, width=120, placeholder_size=(120, 120))
                        elif isinstance(image_source, str) and image_source.startswith(('http://', 'https://')):
                            # http/https URLの場合はキャッシュバスターを追加
                            try:
                                from material_map_version import APP_VERSION
                            except ImportError:
                                APP_VERSION = get_git_sha()
                            separator = "&" if "?" in image_source else "?"
                            st.image(f"{image_source}{separator}v={APP_VERSION}", width=120)
                        else:
                            # Path/PILImageの場合はto_png_bytes()で統一処理（サムネイルサイズ指定）
                            from utils.image_display import to_png_bytes
                            png_bytes = to_png_bytes(image_source, max_size=(120, 120))
                            if png_bytes:
                                img_base64 = base64.b64encode(png_bytes).decode()
                                # 画像のハッシュをキーとして使用（キャッシュ対策）
                                img_hash = hashlib.md5(png_bytes).hexdigest()[:8]
                                st.image(f"data:image/png;base64,{img_base64}", width=120)
                            else:
                                # プレースホルダーを表示
                                display_image_unified(None, width=120)
                    else:
                        # プレースホルダーを表示
                        display_image_unified(None, width=120, placeholder_size=(120, 120))
                
                with col_info:
                    # 材料名
                    st.markdown(f"### {material.name_official or material.name}")
                    
                    # カテゴリバッジ
                    category_name = material.category_main or material.category or '未分類'
                    if len(category_name) > 20:
                        category_display = category_name[:17] + "..."
                        category_title = category_name
                    else:
                        category_display = category_name
                        category_title = ""
                    st.markdown(f'<span class="category-badge" title="{category_title}">{category_display}</span>', unsafe_allow_html=True)
                    
                    # 説明
                    if material.description:
                        st.markdown(f"<p style='color: #666; margin-top: 8px; font-size: 0.9rem;'>{material.description[:100]}{'...' if len(material.description) > 100 else ''}</p>", unsafe_allow_html=True)
                    
                    # 主要物性（1〜2個）
                    if material.properties:
                        props = material.properties[:2]
                        prop_text = " / ".join([f"{p.property_name}: {p.value} {p.unit or ''}" for p in props])
                        st.markdown(f"<small style='color: #999;'>{prop_text}</small>", unsafe_allow_html=True)
                    
                    # 登録日
                    if material.created_at:
                        st.markdown(f"<small style='color: #999;'>登録日: {material.created_at.strftime('%Y/%m/%d')}</small>", unsafe_allow_html=True)
                
                st.markdown("---")
    
    # 将来の機能（iconmonstr風のアイコンを使用）
    st.markdown("---")
    st.markdown('<h3 class="section-title">将来の機能（LLM統合予定）</h3>', unsafe_allow_html=True)
    
    future_features = [
        ("icon-search", "自然言語検索", "「高強度で軽量な材料」など、自然な言葉で検索"),
        ("icon-recommend", "材料推奨", "要件に基づいて最適な材料を自動推奨"),
        ("icon-predict", "物性予測", "AIによる物性データの予測"),
        ("icon-similarity", "類似度分析", "材料間の類似性を分析")
    ]
    
    cols = st.columns(4)
    for idx, (icon_name, title, desc) in enumerate(future_features):
        icon = get_icon_svg_inline(icon_name, 48, "#999999")
        with cols[idx]:
            st.markdown(f"""
            <div class="material-card-container" style="padding: 25px; text-align: center;">
                <div style="margin-bottom: 15px; text-align: center;">
                    <img src="data:image/svg+xml;base64,{icon}" style="width: 48px; height: 48px; opacity: 0.6;" />
                </div>
                <h4 style="color: #1a1a1a; margin: 15px 0; font-weight: 600; font-size: 1rem;">{title}</h4>
                <p style="color: #666; font-size: 13px; margin: 0; line-height: 1.6;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

def show_materials_list(include_unpublished: bool = False, include_deleted: bool = False):
    """材料一覧ページ"""
    # パフォーマンス計測（DEBUG=1のみ）
    import time
    # is_debug 関数を呼ぶ前に、ローカル変数名を debug_enabled に変更（シャドーイング回避）
    debug_enabled = is_debug_flag()
    t0 = time.perf_counter() if debug_enabled else None
    
    debug_enabled = os.getenv("DEBUG", "0") == "1"
    st.markdown(render_site_header(debug=debug_enabled), unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">材料一覧</h2>', unsafe_allow_html=True)
    
    # 詳細表示モードのチェック
    if st.session_state.selected_material_id:
        material_id = st.session_state.selected_material_id
        material = get_material_by_id(material_id)
        
        if material:
            # 戻るボタン
            if st.button("← 一覧に戻る", key="back_to_list"):
                st.session_state.selected_material_id = None
                st.rerun()
            
            st.markdown("---")
            st.markdown(f"# {material.name_official or material.name}")
            
            # 管理者モードの場合は編集・削除ボタンを表示
            is_admin = os.getenv("DEBUG", "0") == "1" or os.getenv("ADMIN", "0") == "1"
            if is_admin:
                col1, col2, col3 = st.columns([1, 1, 8])
                with col1:
                    if st.button("✏️ 編集", key=f"edit_{material.id}"):
                        st.session_state.edit_material_id = material.id
                        st.session_state.page = "材料登録"
                        st.rerun()
                with col2:
                    if st.button("🗑️ 削除", key=f"delete_{material.id}"):
                        st.session_state.delete_material_id = material.id
                        st.rerun()
            
            # 削除確認（2段階確認）
            if st.session_state.get("delete_material_id") == material.id:
                st.warning("⚠️ この材料を削除しますか？")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 削除を実行", key=f"confirm_delete_{material.id}", type="primary"):
                        # 論理削除を実行
                        db = SessionLocal()
                        try:
                            db_material = db.query(Material).filter(Material.id == material.id).first()
                            if db_material:
                                db_material.is_deleted = 1
                                db_material.deleted_at = datetime.utcnow()
                                db.commit()
                                st.success("✅ 材料を削除しました")
                                st.session_state.delete_material_id = None
                                st.session_state.selected_material_id = None
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ 削除エラー: {e}")
                            db.rollback()
                        finally:
                            db.close()
                with col2:
                    if st.button("❌ キャンセル", key=f"cancel_delete_{material.id}"):
                        st.session_state.delete_material_id = None
                        st.rerun()
                return
            
            # 3タブ構造で詳細表示（eager load済みのmaterialを渡す）
            # 念のため、再度取得してeager loadを保証
            material = get_material_by_id(material.id)
            if material:
                show_material_detail_tabs(material)
            return
        else:
            st.error("材料が見つかりませんでした。")
            st.session_state.selected_material_id = None
    
    materials = get_all_materials(include_unpublished=include_unpublished, include_deleted=include_deleted)
    
    if not materials:
        st.info("まだ材料が登録されていません。「材料登録」から材料を追加してください。")
        return
    
    # フィルタリング
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        categories = ["すべて"] + list(set([m.category_main or m.category for m in materials if m.category_main or m.category]))
        selected_category = st.selectbox("カテゴリでフィルタ", categories)
    with col2:
        search_term = st.text_input("材料名で検索", placeholder="材料名を入力...")
    with col3:
        st.write("")  # スペーサー
        st.write("")  # スペーサー
    
    # フィルタリング適用
    filtered_materials = materials
    if selected_category and selected_category != "すべて":
        filtered_materials = [m for m in filtered_materials if (m.category_main or m.category) == selected_category]
    if search_term:
        filtered_materials = [m for m in filtered_materials if search_term.lower() in (m.name_official or m.name or "").lower()]
    
    st.markdown(f"### **{len(filtered_materials)}件**の材料が見つかりました")
    
    # 材料カード表示（グリッドレイアウト）
    cols = st.columns(3)
    for idx, material in enumerate(filtered_materials):
        with cols[idx % 3]:
            with st.container():
                properties_text = ""
                if material.properties:
                    props = material.properties[:3]
                    properties_text = "<br>".join([
                        f"<small style='color: #666;'>• {p.property_name}: <strong style='color: #667eea;'>{p.value} {p.unit or ''}</strong></small>"
                        for p in props
                    ])
                
                material_name = material.name_official or material.name or "名称不明"
                material_desc = material.description or ""
                
                # 素材画像を取得（キャッシュ対策: Base64エンコードで直接表示）
                from utils.image_display import get_material_image_ref, display_image_unified
                import hashlib
                import time
                
                image_source = None
                image_debug = None
                # get_material_image_refを使用（常に呼び出す、material.imagesガードを削除）
                from utils.logo import get_project_root
                image_src, image_debug = get_material_image_ref(material, "primary", get_project_root())
                image_source = image_src
                
                # DEBUG=1の時だけ画像探索結果を表示
                if os.getenv("DEBUG", "0") == "1" and image_debug:
                    with st.expander(f"🔍 画像探索デバッグ: {material_name}", expanded=False):
                        st.json(image_debug)
                
                # 画像HTML（プレースホルダー含む、キャッシュ回避）
                if image_source:
                    if isinstance(image_source, str):
                        # URLの場合はhttp/httpsのみキャッシュバスターを追加
                        if image_source.startswith(('http://', 'https://')):
                            try:
                                from material_map_version import APP_VERSION
                            except ImportError:
                                APP_VERSION = get_git_sha()
                            separator = "&" if "?" in image_source else "?"
                            img_html = f'<img src="{image_source}{separator}v={APP_VERSION}" class="material-hero-image" alt="{material_name}" />'
                        elif image_source.startswith('data:'):
                            # data:URLの場合はそのまま
                            img_html = f'<img src="{image_source}" class="material-hero-image" alt="{material_name}" />'
                        else:
                            # ローカルパスの場合はdata URLに変換
                            path = Path(image_source)
                            if path.exists() and path.is_file():
                                with open(path, 'rb') as f:
                                    img_bytes = f.read()
                                    img_base64 = base64.b64encode(img_bytes).decode()
                                    # 拡張子からMIMEタイプを判定
                                    ext = path.suffix.lower()
                                    mime_type = {
                                        '.jpg': 'image/jpeg',
                                        '.jpeg': 'image/jpeg',
                                        '.png': 'image/png',
                                        '.webp': 'image/webp',
                                        '.gif': 'image/gif'
                                    }.get(ext, 'image/png')
                                    img_html = f'<img src="data:{mime_type};base64,{img_base64}" class="material-hero-image" alt="{material_name}" />'
                            else:
                                img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                    elif isinstance(image_source, Path):
                        # Pathの場合はto_data_url()またはto_png_bytes()でdata URLに変換
                        from utils.image_display import to_data_url, to_png_bytes
                        data_url = to_data_url(image_source)
                        if data_url:
                            img_html = f'<img src="{data_url}" class="material-hero-image" alt="{material_name}" />'
                        else:
                            # to_data_urlが失敗した場合はto_png_bytesでPNG bytes化
                            png_bytes = to_png_bytes(image_source)
                            if png_bytes:
                                img_base64 = base64.b64encode(png_bytes).decode()
                                img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material_name}" />'
                            else:
                                img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                    else:
                        # PILImageの場合はto_png_bytes()でPNG bytes化
                        from utils.image_display import to_png_bytes
                        png_bytes = to_png_bytes(image_source)
                        if png_bytes:
                            img_base64 = base64.b64encode(png_bytes).decode()
                            img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material_name}" />'
                        else:
                            img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                else:
                    # プレースホルダー
                    img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                
                # カテゴリ名（長い場合は省略）
                category_name = material.category_main or material.category or '未分類'
                if len(category_name) > 20:
                    category_display = category_name[:17] + "..."
                    category_title = category_name
                else:
                    category_display = category_name
                    category_title = ""
                
                st.markdown(f"""
                <div class="material-card-container material-texture">
                    {img_html}
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px; margin-top: 16px;">
                        <h3 style="color: #1a1a1a; margin: 0; font-size: 1.4rem; font-weight: 700; flex: 1;">{material_name}</h3>
                    </div>
                    <div style="margin-bottom: 12px;">
                        <span class="category-badge" title="{category_title}">{category_display}</span>
                    </div>
                    <p style="color: #666; margin: 0; font-size: 0.95rem; line-height: 1.6;">
                        {material_desc[:80] if material_desc else '説明なし'}...
                    </p>
                    <div style="margin: 20px 0;">
                        {properties_text}
                    </div>
                    <div style="margin-top: 20px; display: flex; justify-content: space-between; align-items: center;">
                        <small style="color: #999;">ID: {material.id}</small>
                        {f'<small style="color: #999;">{"✅ 公開" if getattr(material, "is_published", 1) == 1 else "🔒 非公開"}</small>' if include_unpublished else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 管理者表示時は公開/非公開切り替えスイッチを表示
                if include_unpublished:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        pass  # 詳細ボタンのスペース
                    with col2:
                        current_status = getattr(material, "is_published", 1)
                        new_status = st.toggle(
                            "公開" if current_status == 1 else "非公開",
                            value=current_status == 1,
                            key=f"toggle_publish_{material.id}"
                        )
                        if new_status != (current_status == 1):
                            # ステータス変更
                            from database import SessionLocal
                            db = SessionLocal()
                            try:
                                # データベースから再取得して更新
                                from database import Material
                                db_material = db.query(Material).filter(Material.id == material.id).first()
                                if db_material:
                                    db_material.is_published = 1 if new_status else 0
                                    db.commit()
                                    st.rerun()
                            except Exception as e:
                                st.error(f"更新エラー: {e}")
                                import traceback
                                st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)), language="python")
                                db.rollback()
                            finally:
                                db.close()
                
                # 管理者モードの場合は編集・削除ボタンを表示
                is_admin = os.getenv("DEBUG", "0") == "1" or os.getenv("ADMIN", "0") == "1"
                admin_buttons_html = ""
                if is_admin:
                    admin_buttons_html = f"""
                    <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                        <button onclick="window.streamlitEdit_{material.id}()" style="background: #4a90e2; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.9rem;">✏️ 編集</button>
                        <button onclick="window.streamlitDelete_{material.id}()" style="background: #e74c3c; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.9rem;">🗑️ 削除</button>
                    </div>
                    """
                
                # 管理者モードの場合は編集・削除ボタンを表示
                if is_admin:
                    col1, col2, col3 = st.columns([1, 1, 8])
                    with col1:
                        if st.button("✏️ 編集", key=f"edit_list_{material.id}"):
                            st.session_state.edit_material_id = material.id
                            st.session_state.page = "材料登録"
                            st.rerun()
                    with col2:
                        if st.button("🗑️ 削除", key=f"delete_list_{material.id}"):
                            st.session_state.delete_material_id = material.id
                            st.rerun()
                    with col3:
                        pass
                
                # 削除確認（2段階確認）
                if st.session_state.get("delete_material_id") == material.id:
                    st.warning("⚠️ この材料を削除しますか？")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ 削除を実行", key=f"confirm_delete_list_{material.id}", type="primary"):
                            # 論理削除を実行
                            from database import SessionLocal, Material
                            db = SessionLocal()
                            try:
                                db_material = db.query(Material).filter(Material.id == material.id).first()
                                if db_material:
                                    db_material.is_deleted = 1
                                    db_material.deleted_at = datetime.utcnow()
                                    db.commit()
                                    st.success("✅ 材料を削除しました")
                                    st.session_state.delete_material_id = None
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ 削除エラー: {e}")
                                db.rollback()
                            finally:
                                db.close()
                    with col2:
                        if st.button("❌ キャンセル", key=f"cancel_delete_list_{material.id}"):
                            st.session_state.delete_material_id = None
                            st.rerun()
                
                # ボタンのスタイルを明示的に設定（白文字を確実に表示、上に15px移動）
                button_key = f"detail_{material.id}"
                st.markdown(f"""
                <div class="material-card-actions" style="margin-top: -15px;">
                    <style>
                        .material-card-actions button[key="{button_key}"],
                        .material-card-actions button[data-testid*="{button_key}"] {{
                            background-color: #1a1a1a !important;
                            color: #ffffff !important;
                            border: 1px solid #1a1a1a !important;
                        }}
                        .material-card-actions button[key="{button_key}"]:hover,
                        .material-card-actions button[data-testid*="{button_key}"]:hover {{
                            background-color: #333333 !important;
                            color: #ffffff !important;
                        }}
                        .material-card-actions button[key="{button_key}"] *,
                        .material-card-actions button[data-testid*="{button_key}"] * {{
                            color: #ffffff !important;
                        }}
                    </style>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"詳細を見る", key=button_key, width='stretch'):
                    st.session_state.selected_material_id = material.id
                    st.session_state.page = "材料一覧"  # 一覧ページの詳細表示モード
                    st.rerun()

def show_dashboard():
    """ダッシュボードページ"""
    is_debug = os.getenv("DEBUG", "0") == "1"
    st.markdown(render_site_header(debug=is_debug), unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">ダッシュボード</h2>', unsafe_allow_html=True)
    
    # 管理者表示フラグを取得
    include_unpublished = st.session_state.get("include_unpublished", False)
    
    materials = get_all_materials(include_unpublished=include_unpublished)
    
    if not materials:
        st.info("ダッシュボードを表示するには、まず材料を登録してください。")
        return
    
    # 統計カード
    st.markdown("### 統計情報")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{len(materials)}</div>
            <div class="stat-label">登録材料数</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        categories = len(set([m.category for m in materials if m.category]))
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{categories}</div>
            <div class="stat-label">カテゴリ数</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # SQLで直接カウント（DetachedInstanceError回避）
        db = get_db()
        try:
            total_properties = db.execute(select(func.count(Property.id))).scalar() or 0
        finally:
            db.close()
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{total_properties}</div>
            <div class="stat-label">物性データ数</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        avg_properties = total_properties / len(materials) if materials else 0
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{avg_properties:.1f}</div>
            <div class="stat-label">平均物性数</div>
        </div>
        """, unsafe_allow_html=True)
    
    # グラフ
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_category_chart(materials)
        if fig:
            st.plotly_chart(fig, width='stretch')
    
    with col2:
        fig = create_timeline_chart(materials)
        if fig:
            st.plotly_chart(fig, width='stretch')
    
    # カテゴリ別詳細
    st.markdown("### カテゴリ別詳細")
    category_data = {}
    for material in materials:
        cat = material.category or "未分類"
        if cat not in category_data:
            category_data[cat] = []
        category_data[cat].append(material)
    
    for category, mats in category_data.items():
        with st.expander(f"📁 {category} ({len(mats)}件)", expanded=False):
            for mat in mats:
                # SQLで直接カウント（DetachedInstanceError回避）
                db = get_db()
                try:
                    prop_count = db.execute(
                        select(func.count(Property.id))
                        .where(Property.material_id == mat.id)
                    ).scalar() or 0
                finally:
                    db.close()
                st.write(f"• **{mat.name}** - {prop_count}個の物性データ")

def show_search():
    """検索ページ"""
    is_debug = os.getenv("DEBUG", "0") == "1"
    st.markdown(render_site_header(debug=is_debug), unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">材料検索</h2>', unsafe_allow_html=True)
    
    search_query = st.text_input("検索キーワード", placeholder="材料名、カテゴリ、説明などで検索...", key="search_input")
    
    # 管理者表示フラグを取得
    include_unpublished = st.session_state.get("include_unpublished", False)
    
    if search_query:
        materials = get_all_materials(include_unpublished=include_unpublished)
        results = []
        
        for material in materials:
            # 材料名、カテゴリ、説明で検索
            if (search_query.lower() in material.name.lower() or
                (material.category and search_query.lower() in material.category.lower()) or
                (material.description and search_query.lower() in material.description.lower())):
                results.append(material)
        
        if results:
            st.success(f"**{len(results)}件**の結果が見つかりました")
            
            cols = st.columns(2)
            for idx, material in enumerate(results):
                with cols[idx % 2]:
                    with st.container():
                        # SQLで直接カウント（DetachedInstanceError回避）
                        db = get_db()
                        try:
                            prop_count = db.execute(
                                select(func.count(Property.id))
                                .where(Property.material_id == material.id)
                            ).scalar() or 0
                        finally:
                            db.close()
                        
                        prop_text = f'<p style="color: #555; margin-top: 12px;"><strong>物性データ:</strong> {prop_count}個</p>' if prop_count > 0 else ''
                        
                        # 素材画像を取得（主役として表示、URL優先）
                        from utils.image_display import get_material_image_ref
                        from utils.logo import get_project_root
                        # get_material_image_refを使用
                        image_src, image_debug = get_material_image_ref(material, "primary", get_project_root())
                        image_source = image_src
                        
                        # 画像HTML（プレースホルダー含む、キャッシュ回避）
                        if image_source:
                            if isinstance(image_source, str):
                                # URLの場合はhttp/httpsのみキャッシュバスターを追加
                                if image_source.startswith(('http://', 'https://')):
                                    try:
                                        from material_map_version import APP_VERSION
                                    except ImportError:
                                        APP_VERSION = get_git_sha()
                                    separator = "&" if "?" in image_source else "?"
                                    img_html = f'<img src="{image_source}{separator}v={APP_VERSION}" class="material-hero-image" alt="{material.name}" />'
                                elif image_source.startswith('data:'):
                                    # data:URLの場合はそのまま
                                    img_html = f'<img src="{image_source}" class="material-hero-image" alt="{material.name}" />'
                                else:
                                    # ローカルパス文字列の場合はPathとして処理
                                    path = Path(image_source)
                                    if path.exists() and path.is_file():
                                        from utils.image_display import to_data_url, to_png_bytes
                                        data_url = to_data_url(path)
                                        if data_url:
                                            img_html = f'<img src="{data_url}" class="material-hero-image" alt="{material.name}" />'
                                        else:
                                            # to_data_urlが失敗した場合はto_png_bytesでPNG bytes化
                                            png_bytes = to_png_bytes(path)
                                            if png_bytes:
                                                img_base64 = base64.b64encode(png_bytes).decode()
                                                img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material.name}" />'
                                            else:
                                                img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                                    else:
                                        img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                            elif isinstance(image_source, Path):
                                # Pathの場合はto_data_url()またはto_png_bytes()でdata URLに変換
                                from utils.image_display import to_data_url, to_png_bytes
                                data_url = to_data_url(image_source)
                                if data_url:
                                    img_html = f'<img src="{data_url}" class="material-hero-image" alt="{material.name}" />'
                                else:
                                    # to_data_urlが失敗した場合はto_png_bytesでPNG bytes化
                                    png_bytes = to_png_bytes(image_source)
                                    if png_bytes:
                                        img_base64 = base64.b64encode(png_bytes).decode()
                                        img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material.name}" />'
                                    else:
                                        img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                            else:
                                # PILImageの場合はto_png_bytes()でPNG bytes化
                                from utils.image_display import to_png_bytes
                                png_bytes = to_png_bytes(image_source)
                                if png_bytes:
                                    img_base64 = base64.b64encode(png_bytes).decode()
                                    img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material.name}" />'
                                else:
                                    img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                        else:
                            # プレースホルダー
                            img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                        
                        # カテゴリ名（長い場合は省略）
                        category_name = material.category or '未分類'
                        if len(category_name) > 20:
                            category_display = category_name[:17] + "..."
                            category_title = category_name
                        else:
                            category_display = category_name
                            category_title = ""
                        
                        st.markdown(f"""
                        <div class="material-card-container material-texture">
                            {img_html}
                            <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px;">
                                <h3 style="color: #1a1a1a; margin: 0; font-size: 1.3rem; font-weight: 700; flex: 1;">{material.name}</h3>
                            </div>
                            <div style="margin-bottom: 12px;">
                                <span class="category-badge" title="{category_title}">{category_display}</span>
                            </div>
                            <p style="color: #666; margin: 0; line-height: 1.6; font-size: 0.9rem;">{material.description or '説明なし'}</p>
                            {prop_text}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 詳細を見るボタン（白文字を確実に表示）
                        button_key = f"search_detail_{material.id}"
                        st.markdown(f"""
                        <style>
                            button[key="{button_key}"],
                            button[data-testid*="{button_key}"] {{
                                background-color: #1a1a1a !important;
                                color: #ffffff !important;
                                border: 1px solid #1a1a1a !important;
                            }}
                            button[key="{button_key}"]:hover,
                            button[data-testid*="{button_key}"]:hover {{
                                background-color: #333333 !important;
                                color: #ffffff !important;
                            }}
                            button[key="{button_key}"] *,
                            button[data-testid*="{button_key}"] * {{
                                color: #ffffff !important;
                            }}
                        </style>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"詳細を見る", key=button_key, width='stretch'):
                            st.session_state.selected_material_id = material.id
                            st.session_state.page = "材料一覧"  # 一覧ページの詳細表示モードに遷移
                            st.rerun()
        else:
            st.info("検索結果が見つかりませんでした。別のキーワードで検索してみてください。")

def show_approval_queue():
    """承認待ち一覧ページ（管理者のみ）"""
    # パフォーマンス計測（DEBUG=1のみ）
    import time
    # is_debug 関数を呼ぶ前に、ローカル変数名を debug_enabled に変更（シャドーイング回避）
    debug_enabled = is_debug_flag()
    t0 = time.perf_counter() if debug_enabled else None
    
    debug_enabled = os.getenv("DEBUG", "0") == "1"
    st.markdown(render_site_header(debug=debug_enabled), unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📋 承認待ち一覧</h2>', unsafe_allow_html=True)
    
    db = SessionLocal()
    try:
        # フィルタ：rejectedも表示するか
        # 初期化はwidget作成前にのみ行う
        if "approval_show_rejected" not in st.session_state:
            st.session_state["approval_show_rejected"] = False
        
        show_rejected = st.checkbox(
            "却下済みも表示",
            key="approval_show_rejected"
        )
        
        # 検索：name_official部分一致
        # 初期化はwidget作成前にのみ行う
        if "approval_search" not in st.session_state:
            st.session_state["approval_search"] = ""
        
        search_query = st.text_input(
            "材料名で検索（部分一致）",
            key="approval_search"
        )
        
        # ステータスフィルタ
        if show_rejected:
            status_filter = ["pending", "rejected"]
        else:
            status_filter = ["pending"]
        
        # submissionsを取得（新しい順）
        query = db.query(MaterialSubmission).filter(
            MaterialSubmission.status.in_(status_filter)
        )
        
        # 検索フィルタ
        if search_query and search_query.strip():
            # payload_jsonにname_officialが含まれるものを検索
            # SQLiteではJSON検索が難しいので、全件取得してフィルタ
            all_submissions = query.order_by(MaterialSubmission.created_at.desc()).all()
            filtered_submissions = []
            for sub in all_submissions:
                try:
                    payload = json.loads(sub.payload_json)
                    name_official = payload.get('name_official', '')
                    if search_query.lower() in name_official.lower():
                        filtered_submissions.append(sub)
                except:
                    pass
            submissions = filtered_submissions
        else:
            submissions = query.order_by(MaterialSubmission.created_at.desc()).all()
        
        # ステータス別の件数表示
        pending_count = len([s for s in submissions if s.status == "pending"])
        rejected_count = len([s for s in submissions if s.status == "rejected"])
        approved_count = len([s for s in submissions if s.status == "approved"])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("承認待ち", pending_count)
        with col2:
            st.metric("却下済み", rejected_count)
        with col3:
            st.metric("承認済み", approved_count)
        
        if not submissions:
            st.info("✅ 該当する投稿はありません。")
            return
        
        for submission in submissions:
            # ステータスに応じたアイコンと色
            status_icon = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "❌"
            }.get(submission.status, "📄")
            
            status_color = {
                "pending": "#FFA500",
                "approved": "#28A745",
                "rejected": "#DC3545"
            }.get(submission.status, "#666")
            
            with st.expander(
                f"{status_icon} {submission.created_at.strftime('%Y-%m-%d %H:%M')} - {submission.submitted_by or '匿名'} - {submission.status}",
                expanded=False
            ):
                # payload_jsonをパースして表示
                try:
                    payload = json.loads(submission.payload_json)
                    st.markdown("### 投稿内容")
                    
                    # 主要フィールドを表示
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**材料名（正式）**: {payload.get('name_official', 'N/A')}")
                        st.write(f"**カテゴリ**: {payload.get('category_main', 'N/A')}")
                        st.write(f"**供給元**: {payload.get('supplier_org', 'N/A')}")
                    with col2:
                        st.write(f"**投稿者**: {submission.submitted_by or '匿名'}")
                        st.write(f"**投稿日時**: {submission.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.markdown(f"**ステータス**: <span style='color: {status_color}'>{submission.status}</span>", unsafe_allow_html=True)
                        if submission.approved_material_id:
                            st.write(f"**承認済み材料ID**: {submission.approved_material_id}")
                    
                    # editor_noteを表示・編集
                    st.markdown("---")
                    st.markdown("### 編集者メモ")
                    editor_note_key = f"editor_note_edit_{submission.id}"
                    editor_note_value = st.text_area(
                        "編集者メモ（いつでも編集可能）",
                        value=submission.editor_note or "",
                        key=editor_note_key,
                        placeholder="編集者メモを入力・編集できます"
                    )
                    if st.button("💾 メモを保存", key=f"save_note_{submission.id}"):
                        submission.editor_note = editor_note_value.strip() if editor_note_value.strip() else None
                        db.commit()
                        st.success("✅ メモを保存しました")
                        st.rerun()
                    
                    # 却下理由を表示（rejectedの場合）
                    if submission.status == "rejected" and submission.reject_reason:
                        st.markdown("---")
                        st.markdown("### 却下理由")
                        st.warning(submission.reject_reason)
                    
                    # 差分表示（既存materialsとの比較）
                    st.markdown("---")
                    st.markdown("### 差分表示（既存材料との比較）")
                    existing_material = db.query(Material).filter(
                        Material.name_official == payload.get('name_official')
                    ).first()
                    
                    if existing_material:
                        diff = calculate_submission_diff(existing_material, payload)
                        if diff:
                            with st.expander("📊 変更された項目", expanded=True):
                                for key, (old_val, new_val) in diff.items():
                                    st.markdown(f"**{key}**:")
                                    st.markdown(f"- 既存: `{old_val}`")
                                    st.markdown(f"- 新規: `{new_val}`")
                                    st.markdown("---")
                        else:
                            st.info("既存材料と差分はありません（新規登録または同一内容）")
                    else:
                        st.info("既存材料が見つかりません（新規登録）")
                    
                    # アップロードされた画像のプレビュー
                    uploaded_images = payload.get('uploaded_images', [])
                    if uploaded_images:
                        st.markdown("---")
                        st.markdown("### 📷 アップロードされた画像")
                        for img_info in uploaded_images:
                            kind = img_info.get('kind', 'primary')
                            public_url = img_info.get('public_url')
                            if public_url:
                                st.markdown(f"**{kind}画像:**")
                                st.image(public_url, caption=f"{kind}画像", use_container_width=True)
                                st.caption(f"URL: {public_url}")
                    
                    # プレビュー（簡易表示）
                    st.markdown("---")
                    st.markdown("### プレビュー（全データ）")
                    with st.expander("JSONデータ", expanded=False):
                        st.json(payload)
                    
                    # アクション（ステータスに応じて表示）
                    st.markdown("---")
                    st.markdown("### アクション")
                    
                    if submission.status == "pending":
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("✅ 承認", key=f"approve_{submission.id}", type="primary"):
                                result = approve_submission(submission.id, editor_note=submission.editor_note, db=None)
                                if result.get("ok"):
                                    st.success("✅ 承認しました！（非公開状態で保存されました）")
                                    st.info("💡 承認後、材料一覧で公開トグルをONにしてください。")
                                    if result.get("image_warning"):
                                        st.warning(f"⚠️ {result['image_warning']}")
                                    st.cache_data.clear()  # キャッシュをクリア
                                    st.rerun()
                                else:
                                    st.error(f"❌ エラー: {result.get('error', '不明なエラー')}")
                                    if result.get("traceback"):
                                        with st.expander("🔍 エラー詳細", expanded=False):
                                            st.code(result["traceback"], language="python")
                        
                        with col2:
                            reject_reason_key = f"reject_reason_{submission.id}"
                            reject_reason = st.text_input(
                                "却下理由（任意）",
                                key=reject_reason_key,
                                placeholder="却下理由を入力してください"
                            )
                            if st.button("❌ 却下", key=f"reject_{submission.id}"):
                                result = reject_submission(submission.id, reject_reason, db)
                                if result.get("ok"):
                                    st.success("❌ 却下しました。")
                                    st.cache_data.clear()  # キャッシュをクリア
                                    st.rerun()
                                else:
                                    st.error(f"❌ エラー: {result.get('error', '不明なエラー')}")
                    
                    elif submission.status == "rejected":
                        if st.button("🔄 再審査（pendingに戻す）", key=f"reopen_{submission.id}", type="primary"):
                            result = reopen_submission(submission.id, db)
                            if result.get("ok"):
                                st.success("🔄 再審査に戻しました。")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ エラー: {result.get('error', '不明なエラー')}")
                    
                    elif submission.status == "approved":
                        if submission.approved_material_id:
                            material = db.query(Material).filter(Material.id == submission.approved_material_id).first()
                            if material:
                                st.info(f"✅ 承認済み材料: {material.name_official} (ID: {material.id})")
                                st.info(f"📢 公開状態: {'公開' if material.is_published == 1 else '非公開'}")
                                if st.button("📝 材料詳細を見る", key=f"view_material_{submission.id}"):
                                    st.session_state.selected_material_id = material.id
                                    st.session_state.page = "材料一覧"
                                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"❌ payload_jsonのパースに失敗しました: {e}")
                    st.code(submission.payload_json)
    
    finally:
        db.close()


def approve_submission(submission_id: int, editor_note: str = None, db=None):
    """
    投稿を承認してmaterialsテーブルに反映（トランザクション分離版）
    
    Args:
        submission_id: MaterialSubmissionのID
        editor_note: 承認メモ（任意）
        db: データベースセッション（Noneの場合は新規作成、使用しない）
    
    Returns:
        dict: {"ok": True/False, "material_id": int, "error": str, "traceback": str}
    
    Note:
        トランザクションを3つに分離:
        - Tx1: materials反映（commit）
        - Tx2: images upsert（失敗しても rollback、全体は落とさない）
        - Tx3: submissions更新（commit）
    """
    import traceback as tb
    
    # セッションは都度生成（使い回さない）
    db_tx1 = SessionLocal()
    db_tx2 = SessionLocal()
    db_tx3 = SessionLocal()
    
    material_id = None
    image_upsert_error = None
    
    try:
        # ===== Tx1: submission取得とpayloadパース =====
        submission = db_tx1.query(MaterialSubmission).filter(
            MaterialSubmission.id == submission_id
        ).first()
        
        if not submission:
            return {"ok": False, "error": "Submission not found"}
        
        if submission.status != "pending":
            return {"ok": False, "error": f"Submission is not pending (status: {submission.status})"}
        
        # payload_jsonをパース
        try:
            form_data = json.loads(submission.payload_json)
        except json.JSONDecodeError as e:
            logger.exception(f"[APPROVE] Failed to parse payload_json: {e}")
            return {"ok": False, "error": f"Failed to parse payload_json: {e}"}
        
        # 必須フィールドの補完
        form_data = _normalize_required(form_data, existing=None)
        
        # payload をサニタイズ：Material カラムだけに絞る（relationship キーとシステム列を除去）
        allowed_columns = {c.name for c in Material.__table__.columns}
        relationship_keys = {"images", "uploaded_images", "reference_urls", "use_examples", "properties", "metadata_items", "process_example_images"}
        # システム列を明示的に除外（id混入を防ぐ）
        system_keys = {"id", "created_at", "updated_at", "deleted_at", "uuid"}
        payload_for_material = {
            k: v for k, v in form_data.items()
            if k in allowed_columns 
            and k not in relationship_keys 
            and k not in system_keys
            and v is not None
        }
        
        # ===== Tx1: materialsテーブルに新規作成（commit） =====
        try:
            # 承認時は原則「新規作成」（既存更新は行わない）
            material_uuid = str(uuid.uuid4())
            material = Material(uuid=material_uuid)
            db_tx1.add(material)
            action = 'created'
            
            # Material カラムのみを設定（システム列は除外済み）
            for k, v in payload_for_material.items():
                # 念のため再度システム列チェック（二重防御）
                if k not in system_keys:
                    setattr(material, k, v)
            
            material.is_published = 0
            material.is_deleted = 0
            
            # Materialデータを設定（新規作成時）
            material.name_official = form_data['name_official']
            material.name_aliases = json.dumps(form_data.get('name_aliases', []), ensure_ascii=False)
            material.supplier_org = form_data['supplier_org']
            material.supplier_type = form_data['supplier_type']
            material.supplier_other = form_data.get('supplier_other')
            material.category_main = form_data['category_main']
            material.category_other = form_data.get('category_other')
            material.material_forms = json.dumps(form_data['material_forms'], ensure_ascii=False)
            material.material_forms_other = form_data.get('material_forms_other')
            material.origin_type = form_data['origin_type']
            material.origin_other = form_data.get('origin_other')
            material.origin_detail = form_data['origin_detail']
            material.recycle_bio_rate = form_data.get('recycle_bio_rate')
            material.recycle_bio_basis = form_data.get('recycle_bio_basis')
            material.color_tags = json.dumps(form_data.get('color_tags', []), ensure_ascii=False)
            material.transparency = form_data['transparency']
            material.hardness_qualitative = form_data['hardness_qualitative']
            material.hardness_value = form_data.get('hardness_value')
            material.weight_qualitative = form_data['weight_qualitative']
            material.specific_gravity = form_data.get('specific_gravity')
            material.water_resistance = form_data['water_resistance']
            material.heat_resistance_temp = form_data.get('heat_resistance_temp')
            material.heat_resistance_range = form_data['heat_resistance_range']
            material.weather_resistance = form_data['weather_resistance']
            material.processing_methods = json.dumps(form_data['processing_methods'], ensure_ascii=False)
            material.processing_other = form_data.get('processing_other')
            material.equipment_level = form_data['equipment_level']
            material.prototyping_difficulty = form_data['prototyping_difficulty']
            material.use_categories = json.dumps(form_data['use_categories'], ensure_ascii=False)
            material.use_other = form_data.get('use_other')
            material.procurement_status = form_data['procurement_status']
            material.cost_level = form_data['cost_level']
            material.cost_value = form_data.get('cost_value')
            material.cost_unit = form_data.get('cost_unit')
            material.safety_tags = json.dumps(form_data['safety_tags'], ensure_ascii=False)
            material.safety_other = form_data.get('safety_other')
            material.restrictions = form_data.get('restrictions')
            material.visibility = form_data['visibility']
            material.is_published = 0
            material.is_deleted = 0
            material.development_motives = json.dumps(form_data.get('development_motives', []), ensure_ascii=False)
            material.development_motive_other = form_data.get('development_motive_other')
            material.development_background_short = form_data.get('development_background_short')
            material.development_story = form_data.get('development_story')
            material.tactile_tags = json.dumps(form_data.get('tactile_tags', []), ensure_ascii=False)
            material.tactile_other = form_data.get('tactile_other')
            material.visual_tags = json.dumps(form_data.get('visual_tags', []), ensure_ascii=False)
            material.visual_other = form_data.get('visual_other')
            material.sound_smell = form_data.get('sound_smell')
            material.circularity = form_data.get('circularity')
            material.certifications = json.dumps(form_data.get('certifications', []), ensure_ascii=False)
            material.certifications_other = form_data.get('certifications_other')
            material.main_elements = form_data.get('main_elements')
            material.name = form_data['name_official']
            material.category = form_data['category_main']
            
            db_tx1.flush()
            
            # 参照URL保存（新規作成時は削除不要）
            for ref in form_data.get('reference_urls', []):
                if ref.get('url'):
                    ref_url = ReferenceURL(
                        material_id=material.id,
                        url=ref['url'],
                        url_type=ref.get('type'),
                        description=ref.get('desc')
                    )
                    db_tx1.add(ref_url)
            
            # 使用例保存（新規作成時は削除不要）
            for ex in form_data.get('use_examples', []):
                if ex.get('name'):
                    use_ex = UseExample(
                        material_id=material.id,
                        example_name=ex['name'],
                        example_url=ex.get('url'),
                        description=ex.get('desc')
                    )
                    db_tx1.add(use_ex)
            
            # material.id を確定（flush してから取得）
            db_tx1.flush()
            material_id = material.id
            if not material_id:
                raise ValueError("material.id is None after flush")
            
            db_tx1.commit()
            logger.info(f"[APPROVE] Tx1 success: material_id={material_id}, action={action}, uuid={material.uuid}")
            
        except Exception as e:
            db_tx1.rollback()
            logger.exception(f"[APPROVE] Tx1 failed (materials upsert): {e}")
            return {
                "ok": False,
                "error": f"Failed to create/update material: {e}",
                "traceback": tb.format_exc(),
            }
        finally:
            db_tx1.close()
        
        # ===== Tx2: images upsert（失敗しても rollback、全体は落とさない） =====
        uploaded_images = form_data.get('uploaded_images', [])
        if uploaded_images and material_id:
            try:
                from utils.image_repo import upsert_image
                
                for img_info in uploaded_images:
                    kind = img_info.get('kind', 'primary')
                    # Phase1: bytes列には書かない（BYTEA型の可能性があるため）
                    # ファイルサイズを保存したい場合は size_bytes(BIGINT)列を新設予定
                    
                    upsert_image(
                        db=db_tx2,
                        material_id=material_id,
                        kind=kind,
                        r2_key=img_info.get('r2_key'),
                        public_url=img_info.get('public_url'),
                        bytes=None,  # Phase1: bytes列には書かない（常にNone）
                        mime=img_info.get('mime'),
                        sha256=img_info.get('sha256'),
                    )
                
                db_tx2.commit()
                logger.info(f"[APPROVE] Tx2 success: images upserted for material_id={material_id}")
                
            except Exception as e:
                db_tx2.rollback()
                image_upsert_error = str(e)
                logger.exception(f"[APPROVE] Tx2 failed (images upsert): {e}")
                # 画像保存失敗は警告のみ（承認は成功させる）
            finally:
                db_tx2.close()
        
        # ===== Tx3: submissionを更新（commit） =====
        try:
            # submissionを再取得（Tx1とは別セッション）
            submission_tx3 = db_tx3.query(MaterialSubmission).filter(
                MaterialSubmission.id == submission_id
            ).first()
            
            if not submission_tx3:
                logger.error(f"[APPROVE] Submission {submission_id} not found in Tx3")
                return {"ok": False, "error": "Submission not found in Tx3"}
            
            submission_tx3.status = "approved"
            # approved_material_id を Tx1 で確定した material_id に設定（確実に設定）
            if not material_id:
                logger.error(f"[APPROVE] material_id is None in Tx3, cannot set approved_material_id")
                return {"ok": False, "error": "material_id is None in Tx3"}
            submission_tx3.approved_material_id = material_id
            if editor_note and editor_note.strip():
                submission_tx3.editor_note = editor_note.strip()
            
            db_tx3.commit()
            logger.info(f"[APPROVE] Tx3 success: submission_id={submission_id}, approved_material_id={material_id}")
            
        except Exception as e:
            db_tx3.rollback()
            logger.exception(f"[APPROVE] Tx3 failed (submission update): {e}")
            return {
                "ok": False,
                "error": f"Failed to update submission: {e}",
                "traceback": tb.format_exc(),
            }
        finally:
            db_tx3.close()
        
        # 成功（画像保存失敗があっても承認は成功）
        # material_id は Tx1 で確定した値を使用（関数ローカル変数）
        if not material_id:
            logger.error(f"[APPROVE] material_id is None after Tx1")
            return {
                "ok": False,
                "error": "material_id is None after material creation",
                "traceback": tb.format_exc(),
            }
        
        result = {
            "ok": True,
            "material_id": material_id,  # Tx1 で確定した material.id
            "action": action,
            "uuid": material_uuid if 'material_uuid' in locals() else None,
        }
        
        if image_upsert_error:
            result["image_warning"] = f"画像保存に失敗しましたが、承認は完了しました: {image_upsert_error}"
        
        return result
        
    except Exception as e:
        logger.exception(f"[APPROVE] Unexpected error: {e}")
        return {
            "ok": False,
            "error": str(e),
            "traceback": tb.format_exc(),
        }


def calculate_submission_diff(existing_material: Material, payload: dict) -> dict:
    """
    既存材料とsubmission payloadの差分を計算
    
    Args:
        existing_material: 既存のMaterialオブジェクト
        payload: submissionのpayload_json（パース済み）
    
    Returns:
        dict: {key: (old_value, new_value)} の形式で差分のみを返す
    """
    diff = {}
    
    # 比較対象のフィールド（主要なもの）
    compare_fields = [
        'name_official', 'category_main', 'supplier_org', 'supplier_type',
        'origin_type', 'origin_detail', 'transparency', 'hardness_qualitative',
        'weight_qualitative', 'water_resistance', 'heat_resistance_range',
        'weather_resistance', 'equipment_level', 'prototyping_difficulty',
        'procurement_status', 'cost_level', 'visibility', 'is_published'
    ]
    
    for field in compare_fields:
        old_val = getattr(existing_material, field, None)
        new_val = payload.get(field)
        
        # Noneや空文字列を正規化
        if old_val is None:
            old_val = ""
        if new_val is None:
            new_val = ""
        if isinstance(old_val, str):
            old_val = old_val.strip()
        if isinstance(new_val, str):
            new_val = new_val.strip()
        
        # 差分がある場合のみ追加
        if old_val != new_val and new_val not in (None, ""):
            diff[field] = (str(old_val), str(new_val))
    
    return diff


def reopen_submission(submission_id: int, db=None):
    """
    却下済みsubmissionを再審査（pendingに戻す）
    
    Args:
        submission_id: MaterialSubmissionのID
        db: データベースセッション（Noneの場合は新規作成）
    
    Returns:
        dict: {"ok": True/False, "error": str, "traceback": str}
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        # submissionを取得
        submission = db.query(MaterialSubmission).filter(
            MaterialSubmission.id == submission_id
        ).first()
        
        if not submission:
            return {"ok": False, "error": "Submission not found"}
        
        if submission.status != "rejected":
            return {"ok": False, "error": f"Submission is not rejected (status: {submission.status})"}
        
        # pendingに戻す
        submission.status = "pending"
        submission.reject_reason = None  # 却下理由をクリア
        
        db.commit()
        
        return {"ok": True}
        
    except Exception as e:
        db.rollback()
        import traceback
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        if should_close:
            db.close()


def reject_submission(submission_id: int, reject_reason: str = None, db=None):
    """
    投稿を却下
    
    Args:
        submission_id: MaterialSubmissionのID
        reject_reason: 却下理由
        db: データベースセッション（Noneの場合は新規作成）
    
    Returns:
        dict: {"ok": True/False, "error": str, "traceback": str}
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        # submissionを取得
        submission = db.query(MaterialSubmission).filter(
            MaterialSubmission.id == submission_id
        ).first()
        
        if not submission:
            return {"ok": False, "error": "Submission not found"}
        
        if submission.status != "pending":
            return {"ok": False, "error": f"Submission is not pending (status: {submission.status})"}
        
        # 却下処理
        submission.status = "rejected"
        submission.reject_reason = reject_reason if reject_reason and reject_reason.strip() else None
        
        db.commit()
        
        return {"ok": True}
        
    except Exception as e:
        db.rollback()
        import traceback
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        if should_close:
            db.close()


def show_submission_status():
    """投稿ステータス確認ページ（投稿者用）"""
    is_debug = os.getenv("DEBUG", "0") == "1"
    st.markdown(render_site_header(debug=is_debug), unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">📋 投稿ステータス確認</h2>', unsafe_allow_html=True)
    st.info("💡 投稿時に表示された投稿IDまたはUUIDを入力してください。")
    
    submission_id_input = st.text_input(
        "投稿ID または UUID",
        placeholder="例: 1 または abc123-def456-...",
        key="submission_status_id"
    )
    
    if submission_id_input and submission_id_input.strip():
        db = SessionLocal()
        try:
            # IDまたはUUIDで検索
            submission = None
            if submission_id_input.strip().isdigit():
                submission = db.query(MaterialSubmission).filter(
                    MaterialSubmission.id == int(submission_id_input.strip())
                ).first()
            else:
                submission = db.query(MaterialSubmission).filter(
                    MaterialSubmission.uuid == submission_id_input.strip()
                ).first()
            
            if submission:
                st.markdown("---")
                st.markdown("### 📄 投稿情報")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**投稿ID**: {submission.id}")
                    st.write(f"**UUID**: {submission.uuid}")
                    st.write(f"**投稿者**: {submission.submitted_by or '匿名'}")
                    st.write(f"**投稿日時**: {submission.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    status_icon = {
                        "pending": "⏳",
                        "approved": "✅",
                        "rejected": "❌"
                    }.get(submission.status, "📄")
                    
                    status_color = {
                        "pending": "#FFA500",
                        "approved": "#28A745",
                        "rejected": "#DC3545"
                    }.get(submission.status, "#666")
                    
                    st.markdown(f"**ステータス**: <span style='color: {status_color}; font-size: 1.2em'>{status_icon} {submission.status}</span>", unsafe_allow_html=True)
                    st.write(f"**更新日時**: {submission.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    if submission.approved_material_id:
                        st.write(f"**承認済み材料ID**: {submission.approved_material_id}")
                
                # payload_jsonをパースして表示
                try:
                    payload = json.loads(submission.payload_json)
                    st.markdown("---")
                    st.markdown("### 📝 投稿内容")
                    st.write(f"**材料名（正式）**: {payload.get('name_official', 'N/A')}")
                    st.write(f"**カテゴリ**: {payload.get('category_main', 'N/A')}")
                    st.write(f"**供給元**: {payload.get('supplier_org', 'N/A')}")
                except:
                    pass
                
                # ステータス別のメッセージ
                if submission.status == "pending":
                    st.info("⏳ 承認待ちです。管理者の承認をお待ちください。")
                elif submission.status == "approved":
                    st.success("✅ 承認されました！")
                    if submission.approved_material_id:
                        material = db.query(Material).filter(Material.id == submission.approved_material_id).first()
                        if material:
                            st.info(f"📝 材料名: {material.name_official} (ID: {material.id})")
                            st.info(f"📢 公開状態: {'公開' if material.is_published == 1 else '非公開（管理者が公開するまでお待ちください）'}")
                elif submission.status == "rejected":
                    st.warning("❌ 却下されました。")
                    if submission.reject_reason:
                        st.markdown("### 却下理由")
                        st.error(submission.reject_reason)
                
                # 編集者メモ（あれば）
                if submission.editor_note:
                    st.markdown("---")
                    st.markdown("### 📝 編集者メモ")
                    st.info(submission.editor_note)
            else:
                st.error("❌ 投稿が見つかりませんでした。投稿IDまたはUUIDを確認してください。")
        
        finally:
            db.close()
    else:
        st.info("💡 投稿IDまたはUUIDを入力してください。")


def show_material_cards():
    """素材カード表示ページ（3タブ構造）"""
    is_debug = os.getenv("DEBUG", "0") == "1"
    st.markdown(render_site_header(debug=is_debug), unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">素材カード</h2>', unsafe_allow_html=True)
    
    # 管理者表示フラグを取得
    include_unpublished = st.session_state.get("include_unpublished", False)
    
    materials = get_all_materials(include_unpublished=include_unpublished)
    
    if not materials:
        st.info("材料が登録されていません。")
        return
    
    material_options = {f"{m.name_official or m.name or '名称不明'} (ID: {m.id})": m.id for m in materials}
    selected_material_name = st.selectbox("材料を選択", list(material_options.keys()))
    material_id = material_options[selected_material_name]
    
    material = get_material_by_id(material_id)
    
    if material:
        # 材料名と基本情報
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"## {material.name_official or material.name}")
            if material.category_main or material.category:
                st.markdown(f"**カテゴリ**: {material.category_main or material.category}")
            if material.description:
                st.markdown(f"**説明**: {material.description}")
        
        with col2:
            # QRコードをPNG bytesとして生成（TypeErrorを防ぐ）
            from utils.qr import generate_qr_png_bytes
            qr_bytes = generate_qr_png_bytes(f"Material ID: {material.id}")
            if qr_bytes:
                st.image(qr_bytes, caption="QRコード", width=150)
            else:
                st.caption("QRコード生成に失敗しました")
        
        # 3タブ構造で詳細表示
        show_material_detail_tabs(material)
        
        # カードのHTML生成と表示（印刷用）
        st.markdown("---")
        st.markdown("### 素材カード（印刷用）")
        
        # Lazy import: card_generatorとschemas（起動時クラッシュを避けるため）
        card_html = None
        error_message = None
        
        # グローバル変数の宣言（tryブロックの外で宣言）
        global _card_generator_import_error, _card_generator_import_traceback
        
        try:
            # 使用する時だけimportする（lazy import）
            from schemas import MaterialCardPayload, MaterialCard, PropertyDTO
            from card_generator import generate_material_card
            # 成功時はエラー情報をクリア
            _card_generator_import_error = None
            _card_generator_import_traceback = None
            # 主要画像を取得（安全に）
            primary_image = None
            primary_image_path = None
            primary_image_type = None
            primary_image_description = None
            
            # 画像情報の取得（安全モード対応）
            # 注意: 安全モードでは material.images は noload されているため空のリストになる
            # そのため、hasattr と len チェックで安全に処理
            primary_image = None
            primary_image_path = None
            primary_image_type = None
            primary_image_description = None
            
            try:
                # material.images にアクセス（安全モードでは空のリスト）
                if hasattr(material, 'images') and material.images and len(material.images) > 0:
                    primary_image = material.images[0]
                    primary_image_path = getattr(primary_image, 'file_path', None) if primary_image else None
                    primary_image_type = getattr(primary_image, 'image_type', None) if primary_image else None
                    primary_image_description = getattr(primary_image, 'description', None) if primary_image else None
            except Exception as img_e:
                # 安全モードやスキーマ不整合時は material.images が空またはアクセス不可
                # エラーは握り潰して続行（画像なしでカード生成）
                if os.getenv("DEBUG", "0") == "1":
                    print(f"画像取得エラー（続行、安全モードの可能性）: {img_e}")
            
            # 物性データをDTOに変換（安全に）
            properties_dto = []
            try:
                if hasattr(material, 'properties') and material.properties:
                    for prop in material.properties:
                        try:
                            prop_name = getattr(prop, 'property_name', None) or "不明"
                            prop_value = getattr(prop, 'value', None)
                            prop_unit = getattr(prop, 'unit', None)
                            prop_condition = getattr(prop, 'measurement_condition', None)
                            
                            prop_dto = PropertyDTO(
                                property_name=str(prop_name),
                                value=float(prop_value) if prop_value is not None else None,
                                unit=str(prop_unit) if prop_unit else None,
                                measurement_condition=str(prop_condition) if prop_condition else None
                            )
                            properties_dto.append(prop_dto)
                        except Exception as prop_e:
                            # 個別の物性データでエラーが発生しても続行
                            print(f"物性データ変換エラー（スキップ）: {prop_e}")
                            continue
            except Exception as props_e:
                print(f"物性データ取得エラー（続行）: {props_e}")
            
            # DTOを作成（欠損はNone/[]に埋める）
            material_name = material.name or getattr(material, 'name_official', None) or "名称不明"
            material_name_official = getattr(material, 'name_official', None)
            material_category = material.category or getattr(material, 'category_main', None)
            material_category_main = getattr(material, 'category_main', None)
            material_description = getattr(material, 'description', None)
            
            card_payload = MaterialCardPayload(
                id=int(material.id),
                name=str(material_name),
                name_official=str(material_name_official) if material_name_official else None,
                category=str(material_category) if material_category else None,
                category_main=str(material_category_main) if material_category_main else None,
                description=str(material_description) if material_description else None,
                properties=properties_dto,
                primary_image_path=str(primary_image_path) if primary_image_path else None,
                primary_image_type=str(primary_image_type) if primary_image_type else None,
                primary_image_description=str(primary_image_description) if primary_image_description else None
            )
            
            card_data = MaterialCard(payload=card_payload)
            # Materialオブジェクトを直接渡せるようにする（画像URL取得のため）
            # 重要: material_objを必ず設定する（card_generatorで画像取得に必要）
            if material is None:
                st.warning(f"⚠️ material is None for card generation (ID: {card_payload.id})")
            else:
                card_data.material_obj = material
            card_html = generate_material_card(card_data)
            
        except Exception as e:
            # ImportError/KeyError/その他すべての例外をキャッチ（ホームは必ず表示される）
            error_message = str(e)
            import traceback
            error_traceback = traceback.format_exc()
            # グローバル変数に記録（render_debug_sidebar_early で表示される）
            _card_generator_import_error = error_message
            _card_generator_import_traceback = error_traceback
            print(f"カード生成エラー: {error_message}")
            print(error_traceback)
            
            # カード画面にエラーを表示（ホームには出さない）
            st.error(f"⚠️ カード生成中にエラーが発生しました: {error_message}")
            if os.getenv("DEBUG", "0") == "1":
                with st.expander("詳細エラー情報", expanded=False):
                    st.code(error_traceback, language="python")
            
            # フォールバック：最低限の情報だけのカード
            try:
                material_name = material.name or getattr(material, 'name_official', None) or 'Unknown'
                material_desc = material.description or 'No description'
                card_html = f"""
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Material Card - {material_name}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; padding: 20px; }}
                        h1 {{ color: #333; }}
                        p {{ color: #666; }}
                    </style>
                </head>
                <body>
                    <h1>{material_name}</h1>
                    <p><strong>ID:</strong> {material.id}</p>
                    <p><strong>説明:</strong> {material_desc}</p>
                    <p style="color: #999; font-size: 12px; margin-top: 20px;">※ 詳細なカード生成に失敗しました。基本情報のみ表示しています。</p>
                </body>
                </html>
                """
            except Exception as fallback_e:
                # フォールバックも失敗した場合
                card_html = f"""
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Material Card - Error</title>
                </head>
                <body>
                    <h1>カード生成エラー</h1>
                    <p>材料ID: {material.id if material else 'N/A'}</p>
                    <p>エラー: {str(fallback_e)}</p>
                </body>
                </html>
                """
        
        # HTMLを表示
        if card_html:
            try:
                st.components.v1.html(card_html, height=800, scrolling=True)
            except:
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            # エラーが発生した場合、フォールバックカードが表示されない場合
            st.warning("⚠️ カード生成に失敗しました。上記のエラーメッセージを確認してください。")
        
        # ダウンロードボタン
        st.download_button(
            label="📥 カードをHTMLとしてダウンロード",
            data=card_html,
            file_name=f"material_card_{material.id}.html",
            mime="text/html",
            width='stretch'
        )


# --- すべての関数定義（main含む）が終わった一番最後に置く ---
# Streamlit 実行では __name__ ガードで事故ることがあるので、ガード無しで呼ぶ
run_app_entrypoint()
