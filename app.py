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
from pathlib import Path
from typing import Optional
from PIL import Image as PILImage
import qrcode
from io import BytesIO
import base64
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter

from database import SessionLocal, Material, Property, Image, MaterialMetadata, ReferenceURL, UseExample, ProcessExampleImage, init_db
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func

# card_generatorとschemasのimport（循環インポート対策）
# エラー情報をグローバル変数に保存（Debug欄で表示用）
_card_generator_import_error = None
_card_generator_import_traceback = None

try:
    from card_generator import generate_material_card
    from schemas import MaterialCard
except Exception as e:
    # importエラー時のフォールバック（最低限の動作を保証）
    import traceback
    _card_generator_import_error = str(e)
    _card_generator_import_traceback = traceback.format_exc()
    print(f"Warning: card_generator/schemas import failed: {e}")
    traceback.print_exc()
    def generate_material_card(card_data):
        """フォールバック: 仮のカードHTMLを返す"""
        return f"<html><body><h1>Material Card (Fallback)</h1><p>ID: {getattr(card_data.payload, 'id', 'N/A')}</p></body></html>"
    # MaterialCardのフォールバック定義
    from pydantic import BaseModel
    class MaterialCardPayload(BaseModel):
        id: int
        name: str
    class MaterialCard(BaseModel):
        payload: MaterialCardPayload

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

# 背景画像の読み込み
main_bg_path = get_image_path("メイン.webp")
sub_bg_path = get_image_path("サブ.webp")
main_bg_base64 = get_base64_image(main_bg_path) if main_bg_path else None
sub_bg_base64 = get_base64_image(sub_bg_path) if sub_bg_path else None

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
        background: {'url("data:image/webp;base64,' + sub_bg_base64 + '")' if sub_bg_base64 else 'none'};
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


def ensure_sample_data():
    """
    サンプルデータが存在しない場合、自動投入（idempotent）
    
    注意: 
    - 環境変数 INIT_SAMPLE_DATA=1 が設定されている場合のみ実行
    - DBが空（materials件数==0）の時だけ実行
    - 例外が出てもアプリ起動を殺さない（ログ＆Debug表示）
    """
    # 初期化すべきか判定
    if not should_init_sample_data():
        return
    
    db = None
    try:
        # サンプルデータを投入
        from init_sample_data import init_sample_data
        init_sample_data()
        st.info("サンプルデータを自動投入しました。ページをリロードしてください。")
    except Exception as e:
        # 例外はログに出力（アプリ起動を殺さない）
        import traceback
        error_msg = f"サンプルデータの投入中にエラーが発生しました: {e}\n{traceback.format_exc()}"
        print(f"ERROR: {error_msg}")
        # Debug欄に表示（st.errorは表示されない場合があるため、printでログに残す）
        # アプリ起動は続行
    finally:
        if db:
            try:
                db.close()
            except:
                pass

def get_db():
    """データベースセッションを取得"""
    return SessionLocal()

def get_all_materials():
    """
    全材料を取得（Eager Loadでリレーションも先読み・全リレーション網羅）
    重複を除去して返す（DB由来のデータに一本化）
    """
    db = get_db()
    try:
        # Eager Loadで全リレーションを先読み（DetachedInstanceErrorを防ぐ）
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
            .order_by(Material.created_at.desc() if hasattr(Material, 'created_at') else Material.id.desc())
        )
        # SQLAlchemy 2.0のunique()で重複を除去
        result = db.execute(stmt)
        materials = result.unique().scalars().all()
        return materials
    finally:
        db.close()

def get_material_by_id(material_id: int):
    """IDで材料を取得（Eager Loadでリレーションも先読み・全リレーション網羅）"""
    db = get_db()
    try:
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
                                img = PILImage.open(filepath)
                                st.image(img, caption=filepath.name, width=150)
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


def main():
    # ビルド情報をサイドバーに表示
    sha = get_git_sha()
    current_time = datetime.now().isoformat(timespec="seconds")
    
    # デバッグ情報（UIが出る前に死ぬ問題を回避する保険）
    # 最低限の情報をprintで出力（Cloudログで確認可能）
    db_path = Path("materials.db")
    if db_path.exists():
        try:
            import sqlite3
            import hashlib
            conn = sqlite3.connect(str(db_path.absolute()))
            try:
                cursor = conn.cursor()
                # PRAGMA table_info(materials) の列名一覧
                cursor.execute("PRAGMA table_info(materials)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns[:20]]  # col[1] = column name
                print(f"[DEBUG] DB path: {db_path.absolute()}")
                print(f"[DEBUG] DB columns (first 20): {', '.join(column_names)}")
                
                # sha256取得（先頭16桁）
                with open(db_path, 'rb') as f:
                    db_content = f.read()
                    sha256_hash = hashlib.sha256(db_content).hexdigest()
                    sha256_prefix = sha256_hash[:16]
                    print(f"[DEBUG] DB sha256 (first 16): {sha256_prefix}")
            finally:
                conn.close()
        except Exception as e:
            import traceback
            print(f"[DEBUG] DB check failed: {e}\n{traceback.format_exc()}")
    
    with st.sidebar:
        st.caption(f"build: {sha}")
        st.caption(f"time: {current_time}")
        
        # デバッグ情報（一時的）
        with st.expander("🔧 Debug (temporary)", expanded=False):
            # DBパスとスキーマ情報（UIが出る前に死ぬ問題を回避する保険）
            st.write("**DB初期診断:**")
            st.write(f"- **DB path:** {db_path.absolute()}")
            
            # PRAGMA table_info(materials) の列名一覧
            if db_path.exists():
                try:
                    import sqlite3
                    conn = sqlite3.connect(str(db_path.absolute()))
                    try:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(materials)")
                        columns = cursor.fetchall()
                        column_names = [row[1] for row in columns[:20]]  # 最初の20件
                        st.write(f"- **materials列名（先頭20件）:** {', '.join(column_names)}")
                        if len(columns) > 20:
                            st.write(f"  (他 {len(columns) - 20} 列)")
                    finally:
                        conn.close()
                except Exception as e:
                    st.write(f"- **列名取得エラー:** {str(e)}")
            else:
                st.write("- **DB path:** 見つかりませんでした")
            
            st.write("---")
            
            # materials.db の情報
            if db_path.exists():
                stat = db_path.stat()
                st.write("**materials.db 情報:**")
                st.write(f"- **path:** {db_path.absolute()}")
                st.write(f"- **mtime:** {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(f"- **size:** {stat.st_size:,} bytes ({stat.st_size / 1024:.2f} KB)")
                
                # DBのmaterials件数とsha256（sqlite3で直接取得）
                try:
                    import sqlite3
                    import hashlib
                    conn = sqlite3.connect(str(db_path.absolute()))
                    try:
                        cursor = conn.cursor()
                        # 件数取得
                        cursor.execute("SELECT COUNT(*) FROM materials")
                        material_count = cursor.fetchone()[0]
                        st.write(f"- **materials件数:** {material_count} 件 (sqlite3)")
                        
                        # sha256取得（先頭16桁）
                        with open(db_path, 'rb') as f:
                            db_content = f.read()
                            sha256_hash = hashlib.sha256(db_content).hexdigest()
                            sha256_prefix = sha256_hash[:16]
                            st.write(f"- **sha256 (先頭16桁):** {sha256_prefix}")
                        
                        # PRAGMA table_info(materials) の列名一覧（最初の20件）
                        cursor.execute("PRAGMA table_info(materials)")
                        columns = cursor.fetchall()
                        column_names = [col[1] for col in columns[:20]]  # col[1] = column name
                        st.write(f"- **columns (最初の20件):** {', '.join(column_names)}")
                        if len(columns) > 20:
                            st.write(f"  (他 {len(columns) - 20} 件)")
                        
                        # 先頭レコードの材料名取得（count>0の時）
                        if material_count > 0:
                            cursor.execute("SELECT name_official, name FROM materials LIMIT 1")
                            row = cursor.fetchone()
                            if row:
                                first_name = row[0] or row[1] or "N/A"
                                st.write(f"- **first material name:** {first_name}")
                            else:
                                st.write(f"- **first material name:** (取得失敗)")
                        else:
                            st.write(f"- **first material name:** (DBが空)")
                    finally:
                        conn.close()
                except Exception as e:
                    import traceback
                    st.write(f"- **materials件数:** エラー ({str(e)})")
                    st.write(f"- **詳細:** {traceback.format_exc()}")
            else:
                st.write("**materials.db:** 見つかりませんでした ❌")
            
            st.write("---")
            
            # card_generator/schemasのimportエラー情報
            if _card_generator_import_error:
                st.write("**card_generator/schemas import エラー:**")
                st.write(f"- **エラー:** {_card_generator_import_error}")
                with st.expander("詳細なトレースバック", expanded=False):
                    st.code(_card_generator_import_traceback, language="python")
            else:
                st.write("**card_generator/schemas import:** ✅ 成功")
            
            st.write("---")
            
            # 画像ファイルの情報（アルミニウム）
            st.write("**画像ファイル情報（アルミニウム）:**")
            material_slug = "アルミニウム"
            material_image_dir = Path("static/images/materials") / material_slug
            
            for image_type, filename in [("primary", "primary.jpg"), ("space", "space.jpg"), ("product", "product.jpg")]:
                if image_type == "primary":
                    image_path = material_image_dir / filename
                else:
                    image_path = material_image_dir / "uses" / filename
                
                if image_path.exists():
                    stat = image_path.stat()
                    st.write(f"**{image_type}:**")
                    st.write(f"  - **path:** {image_path.absolute()}")
                    st.write(f"  - **mtime:** {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                    st.write(f"  - **size:** {stat.st_size:,} bytes ({stat.st_size / 1024:.2f} KB)")
                else:
                    st.write(f"**{image_type}:** 見つかりませんでした ❌")
            
            st.write("---")
            
            # 画像パス探索の情報
            from utils.image_display import find_material_image_paths
            debug_info = {}
            image_paths = find_material_image_paths("アルミニウム", Path.cwd(), debug_info=debug_info)
            
            st.write("**画像パス探索（アルミニウム）:**")
            st.write("**材料名:**", debug_info.get('material_name'))
            st.write("**safe_slug:**", debug_info.get('safe_slug'))
            st.write("**material_dir:**", debug_info.get('material_dir'))
            st.write("**material_dir exists:**", Path(debug_info.get('material_dir', '')).exists())
            
            st.write("---")
            st.write("**試した候補パス:**")
            for key in ['primary', 'space', 'product']:
                st.write(f"**{key}:**")
                tried = debug_info.get('tried_paths', {}).get(key, [])
                if tried:
                    for path in tried:
                        exists = Path(path).exists() if path else False
                        st.write(f"  - {path} {'✅' if exists else '❌'}")
                else:
                    st.write("  (候補なし)")
            
            st.write("---")
            st.write("**最終採用パスと表示型:**")
            # APP_VERSIONを取得（表示用）
            try:
                from material_map_version import APP_VERSION
            except ImportError:
                APP_VERSION = get_git_sha()
            
            found = debug_info.get('found_paths', {})
            for key in ['primary', 'space', 'product']:
                path = found.get(key) or image_paths.get(key)
                if path:
                    # pathはPathオブジェクトまたは文字列の可能性がある
                    if isinstance(path, Path):
                        path_obj = path
                        path_str = str(path)
                    else:
                        path_str = str(path)
                        path_obj = Path(path_str)
                    
                    # 表示に渡した型を判定
                    if path_obj.exists() and path_obj.is_file():
                        display_type = "PIL (ローカルファイル)"
                    elif path_str.startswith(('http://', 'https://')):
                        display_type = f"URL (キャッシュバスター: ?v={APP_VERSION})"
                    elif path_str.startswith('data:'):
                        display_type = "data: URL"
                    else:
                        display_type = "不明"
                    st.write(f"**{key}:** {path_str} ✅")
                    st.write(f"  - 表示型: {display_type}")
                else:
                    st.write(f"**{key}:** (見つかりませんでした) ❌")
        
        # Assets Mode診断
        try:
            mode, url_count, total_count = get_assets_mode_stats()
            if total_count > 0:
                mode_label = {
                    "local": "🔵 local",
                    "url": "🟢 url",
                    "mixed": "🟡 mixed"
                }.get(mode, mode)
                st.markdown("---")
                st.markdown(f"**Assets Mode:** {mode_label}")
                st.caption(f"URL画像: {url_count}/{total_count} ({url_count/total_count*100:.1f}%)" if total_count > 0 else "URL画像: 0/0")
        except Exception as e:
            # エラー時は表示しない（無視）
            pass
    
    # アセット確保（生成物の自動生成）
    try:
        from utils.ensure_assets import ensure_all_assets
        asset_stats = ensure_all_assets()
    except Exception as e:
        print(f"アセット確保エラー: {e}")
        import traceback
        traceback.print_exc()
        asset_stats = {}
    
    # サンプルデータの自動投入（INIT_SAMPLE_DATA=1 かつ DBが空の時だけ実行）
    # init_db()の後に実行（スキーマ補完完了後）
    # 例外が出てもアプリ起動を殺さない
    try:
        ensure_sample_data()
    except Exception as e:
        import traceback
        print(f"ERROR: ensure_sample_data() failed: {e}\n{traceback.format_exc()}")
        # アプリ起動は続行
    
    # 画像の自動修復（環境変数フラグがある場合のみ、かつDBが空の時だけ）
    # init_db()の後に実行（スキーマ補完完了後）
    if should_init_sample_data():
        try:
            from utils.ensure_images import ensure_images
            ensure_images(Path.cwd())
        except Exception as e:
            import traceback
            print(f"ERROR: 画像自動修復エラー: {e}\n{traceback.format_exc()}")
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
        st.warning("デバッグモード: CSSが無効化されています。表示が正常な場合、CSSが原因です。")
    
    # ヘッダー - WOTA風シンプル
    st.markdown('<h1 class="main-header">Material Map</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: left; color: #666; font-size: 0.95rem; margin-bottom: 3rem; font-weight: 400; letter-spacing: 0.01em;">素材の可能性を探索するデータベース</p>', unsafe_allow_html=True)
    
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
        
        # ページ選択（詳細ページ表示中は選択を変更しない）
        if st.session_state.selected_material_id:
            # 詳細ページ表示中は、ページ選択を一時的に無効化
            st.session_state.page = "材料一覧"
            page = "材料一覧"
        else:
            page = st.radio(
                "ページを選択",
                ["ホーム", "材料一覧", "材料登録", "ダッシュボード", "検索", "素材カード", "元素周期表"],
                index=["ホーム", "材料一覧", "材料登録", "ダッシュボード", "検索", "素材カード", "元素周期表"].index(st.session_state.page) if st.session_state.page in ["ホーム", "材料一覧", "材料登録", "ダッシュボード", "検索", "素材カード", "元素周期表"] else 0,
                label_visibility="collapsed"
            )
            st.session_state.page = page
        
        st.markdown("---")
        
        # 統計情報（画面左下に小さく表示）
        materials = get_all_materials()
        
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
    
    # ページルーティング
    if page == "ホーム":
        show_home()
    elif page == "材料一覧":
        show_materials_list()
    elif page == "材料登録":
        show_detailed_material_form()
    elif page == "ダッシュボード":
        show_dashboard()
    elif page == "検索":
        show_search()
    elif page == "素材カード":
        show_material_cards()
    elif page == "元素周期表":
        show_periodic_table()

def show_home():
    """ホームページ"""
    materials = get_all_materials()
    
    # サブ画像を装飾として表示
    sub_img_path = get_image_path("サブ.webp")
    if sub_img_path:
        try:
            sub_img = PILImage.open(sub_img_path)
            # 画像をリサイズ
            sub_img.thumbnail((300, 300), PILImage.Resampling.LANCZOS)
            
            # 装飾として配置
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                st.image(sub_img, width=200, use_container_width=False)
            with col2:
                st.markdown("""
                <div class="hero-section">
                    <h2 style="color: #1a1a1a; margin-bottom: 20px; font-size: 2rem; font-weight: 600; letter-spacing: -0.01em;">ようこそ</h2>
                    <p style="font-size: 1.2rem; color: #555; line-height: 1.8; max-width: 800px; margin: 0 auto; font-weight: 500;">
                        素材カード形式でマテリアル情報を管理する、美しく使いやすいデータベースシステムです。<br>
                        デザイナーやエンジニアが、材料の可能性を探索するためのツールです。
                    </p>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.image(sub_img, width=200, use_container_width=False)
        except Exception as e:
            # 画像読み込み失敗時は通常のヒーローセクション
            st.markdown("""
            <div class="hero-section">
                <h2 style="color: #2c3e50; margin-bottom: 20px; font-size: 2.5rem; font-weight: 800;">✨ ようこそ！</h2>
                <p style="font-size: 1.2rem; color: #555; line-height: 1.8; max-width: 800px; margin: 0 auto; font-weight: 500;">
                    素材カード形式でマテリアル情報を管理する、美しく使いやすいデータベースシステムです。<br>
                    デザイナーやエンジニアが、材料の可能性を探索するためのツールです。
                </p>
            </div>
            """, unsafe_allow_html=True)
    else:
        # 画像がない場合の通常表示
        st.markdown("""
        <div class="hero-section">
            <h2 style="color: #1a1a1a; margin-bottom: 20px; font-size: 2rem; font-weight: 600; letter-spacing: -0.01em;">ようこそ</h2>
            <p style="font-size: 1rem; color: #666; line-height: 1.8; max-width: 800px; margin: 0 auto; font-weight: 400;">
                素材カード形式でマテリアル情報を管理するデータベースシステムです。<br>
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
                    from utils.image_display import get_display_image_source, display_image_unified
                    import hashlib
                    import time
                    
                    # 材料の主画像を取得（Imageテーブルから）
                    image_source = None
                    if material.images:
                        image_source = get_display_image_source(material.images[0], Path.cwd())
                    
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
                                st.image(pil_img, width=120, use_container_width=False)
                            else:
                                display_image_unified(None, width=120, placeholder_size=(120, 120))
                        elif isinstance(image_source, str) and image_source.startswith(('http://', 'https://')):
                            # http/https URLの場合はキャッシュバスターを追加
                            try:
                                from material_map_version import APP_VERSION
                            except ImportError:
                                APP_VERSION = get_git_sha()
                            separator = "&" if "?" in image_source else "?"
                            st.image(f"{image_source}{separator}v={APP_VERSION}", width=120, use_container_width=False)
                        else:
                            # PILImageの場合はBase64エンコードして直接表示（キャッシュ回避）
                            thumb_size = (120, 120)
                            image_source.thumbnail(thumb_size, PILImage.Resampling.LANCZOS)
                            buffer = BytesIO()
                            image_source.save(buffer, format='PNG')
                            img_base64 = base64.b64encode(buffer.getvalue()).decode()
                            # 画像のハッシュをキーとして使用（キャッシュ対策）
                            img_hash = hashlib.md5(buffer.getvalue()).hexdigest()[:8]
                            st.image(f"data:image/png;base64,{img_base64}", width=120, use_container_width=False)
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

def show_materials_list():
    """材料一覧ページ"""
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
            
            # 3タブ構造で詳細表示（eager load済みのmaterialを渡す）
            # 念のため、再度取得してeager loadを保証
            material = get_material_by_id(material.id)
            if material:
                show_material_detail_tabs(material)
            return
        else:
            st.error("材料が見つかりませんでした。")
            st.session_state.selected_material_id = None
    
    materials = get_all_materials()
    
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
                from utils.image_display import get_display_image_source, display_image_unified
                import hashlib
                import time
                
                image_source = None
                if material.images:
                    image_source = get_display_image_source(material.images[0], Path.cwd())
                
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
                    else:
                        # PILImageの場合はBase64エンコード（キャッシュ回避）
                        from io import BytesIO
                        import base64
                        buffer = BytesIO()
                        image_source.save(buffer, format='PNG')
                        img_base64 = base64.b64encode(buffer.getvalue()).decode()
                        img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material_name}" />'
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
                    <div style="margin-top: 20px;">
                        <small style="color: #999;">ID: {material.id}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # ボタンのスタイルを明示的に設定（白文字を確実に表示）
                button_key = f"detail_{material.id}"
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
                
                if st.button(f"詳細を見る", key=button_key, use_container_width=True):
                    st.session_state.selected_material_id = material.id
                    st.session_state.page = "材料一覧"  # 一覧ページの詳細表示モード
                    st.rerun()

def show_dashboard():
    """ダッシュボードページ"""
    st.markdown('<h2 class="section-title">ダッシュボード</h2>', unsafe_allow_html=True)
    
    materials = get_all_materials()
    
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
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_timeline_chart(materials)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    
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
    st.markdown('<h2 class="section-title">材料検索</h2>', unsafe_allow_html=True)
    
    search_query = st.text_input("検索キーワード", placeholder="材料名、カテゴリ、説明などで検索...", key="search_input")
    
    if search_query:
        materials = get_all_materials()
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
                        from utils.image_display import get_display_image_source
                        image_source = None
                        if material.images:
                            image_source = get_display_image_source(material.images[0], Path.cwd())
                        
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
                                            img_html = f'<img src="data:{mime_type};base64,{img_base64}" class="material-hero-image" alt="{material.name}" />'
                                    else:
                                        img_html = f'<div class="material-hero-image" style="display: flex; align-items: center; justify-content: center; color: #999; font-size: 14px;">画像なし</div>'
                            else:
                                # PILImageの場合はBase64エンコード
                                from io import BytesIO
                                import base64
                                buffer = BytesIO()
                                image_source.save(buffer, format='PNG')
                                img_base64 = base64.b64encode(buffer.getvalue()).decode()
                                img_html = f'<img src="data:image/png;base64,{img_base64}" class="material-hero-image" alt="{material.name}" />'
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
                        
                        if st.button(f"詳細を見る", key=button_key, use_container_width=True):
                            st.session_state.selected_material_id = material.id
                            st.session_state.page = "材料一覧"  # 一覧ページの詳細表示モードに遷移
                            st.rerun()
        else:
            st.info("検索結果が見つかりませんでした。別のキーワードで検索してみてください。")

def show_material_cards():
    """素材カード表示ページ（3タブ構造）"""
    st.markdown('<h2 class="section-title">素材カード</h2>', unsafe_allow_html=True)
    
    materials = get_all_materials()
    
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
        
        # MaterialCard用のDTOを作成（ValidationErrorを防ぐ）
        from schemas import MaterialCardPayload, MaterialCard, PropertyDTO
        
        card_html = None
        error_message = None
        
        try:
            # 主要画像を取得（安全に）
            primary_image = None
            primary_image_path = None
            primary_image_type = None
            primary_image_description = None
            
            try:
                if hasattr(material, 'images') and material.images and len(material.images) > 0:
                    primary_image = material.images[0]
                    primary_image_path = getattr(primary_image, 'file_path', None) if primary_image else None
                    primary_image_type = getattr(primary_image, 'image_type', None) if primary_image else None
                    primary_image_description = getattr(primary_image, 'description', None) if primary_image else None
            except Exception as img_e:
                print(f"画像取得エラー（続行）: {img_e}")
            
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
            card_html = generate_material_card(card_data)
            
        except Exception as e:
            # エラーメッセージを保存
            error_message = str(e)
            import traceback
            error_traceback = traceback.format_exc()
            print(f"カード生成エラー: {error_message}")
            print(error_traceback)
            
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
        
        # エラーメッセージを表示
        if error_message:
            st.error(f"カード生成時にエラーが発生しました: {error_message}")
            with st.expander("エラー詳細（開発者向け）"):
                st.code(error_traceback if 'error_traceback' in locals() else error_message)
        
        # HTMLを表示
        try:
            st.components.v1.html(card_html, height=800, scrolling=True)
        except:
            st.markdown(card_html, unsafe_allow_html=True)
        
        # ダウンロードボタン
        st.download_button(
            label="📥 カードをHTMLとしてダウンロード",
            data=card_html,
            file_name=f"material_card_{material.id}.html",
            mime="text/html",
            use_container_width=True
        )

if __name__ == "__main__":
    main()
