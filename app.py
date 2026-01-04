"""
StreamlitベースのWebアプリケーション
マテリアル感のあるリッチなUI
"""
import streamlit as st
import os
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

from database import SessionLocal, Material, Property, Image, MaterialMetadata, ReferenceURL, UseExample, init_db
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func
from card_generator import generate_material_card
from models import MaterialCard
from material_form_detailed import show_detailed_material_form
from periodic_table_ui import show_periodic_table
from material_detail_tabs import show_material_detail_tabs

# クラウド環境でのポート設定
if 'PORT' in os.environ:
    port = int(os.environ.get("PORT", 8501))

# ページ設定
st.set_page_config(
    page_title="マテリアルデータベース | Material Database",
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

# WOTA風シンプルなカスタムCSS（視認性重視）
def get_custom_css():
    """カスタムCSSを生成（WOTA風シンプルデザイン）"""
    return f"""
<style>
    /* ベースフォント - シンプルなサンセリフ（WOTA風） */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
    }}
    
    /* ベース文字色を確保（視認性向上） */
    html, body, [class*="st-"], p, span, div, h1, h2, h3, h4, h5, h6 {{
        color: #1a1a1a !important;
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
    
    /* ボタンスタイル - WOTA風シンプル */
    .stButton>button {{
        background: #1a1a1a;
        color: #ffffff;
        border: 1px solid #1a1a1a;
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
    
    .stButton>button:hover {{
        background: #333333;
        border-color: #333333;
        transform: none;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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
if not os.path.exists("materials.db"):
    init_db()

def ensure_sample_data():
    """サンプルデータが存在しない場合、自動投入"""
    db = get_db()
    try:
        # 材料数をカウント
        count = db.execute(select(func.count(Material.id))).scalar() or 0
        if count == 0:
            # サンプルデータを投入
            from init_sample_data import init_sample_data
            init_sample_data()
            st.info("サンプルデータを自動投入しました。ページをリロードしてください。")
    except Exception as e:
        st.error(f"サンプルデータの投入中にエラーが発生しました: {e}")
    finally:
        db.close()

def get_db():
    """データベースセッションを取得"""
    return SessionLocal()

def get_all_materials():
    """全材料を取得（Eager Loadでリレーションも先読み）"""
    db = get_db()
    try:
        # Eager Loadでproperties, images, metadata_itemsを先読み
        stmt = (
            select(Material)
            .options(
                selectinload(Material.properties),
                selectinload(Material.images),
                selectinload(Material.metadata_items),
            )
            .order_by(Material.created_at.desc() if hasattr(Material, 'created_at') else Material.id.desc())
        )
        materials = db.execute(stmt).scalars().all()
        return materials
    finally:
        db.close()

def get_material_by_id(material_id: int):
    """IDで材料を取得（Eager Loadでリレーションも先読み）"""
    db = get_db()
    try:
        stmt = (
            select(Material)
            .options(
                selectinload(Material.properties),
                selectinload(Material.images),
                selectinload(Material.metadata_items),
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

# メインアプリケーション
def main():
    # サンプルデータの自動投入（初回起動時のみ）
    ensure_sample_data()
    
    # 画像の自動修復（起動時）
    from utils.ensure_images import ensure_images
    ensure_images(Path.cwd())
    
    # デバッグスイッチ（サイドバーでCSSを無効化可能）
    debug_no_css = st.sidebar.checkbox("Debug: CSSを無効化", value=False, help="白飛びが発生している場合、このチェックをONにするとCSSを無効化して表示を確認できます")
    
    # 画像診断モード（開発用）
    debug_images = st.sidebar.checkbox("🔍 画像診断モード", value=False, help="画像の健康状態を診断します（原因切り分け用）")
    
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
    st.markdown('<h1 class="main-header">マテリアルデータベース</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: left; color: #666; font-size: 0.95rem; margin-bottom: 3rem; font-weight: 400; letter-spacing: 0.01em;">素材の可能性を探索するデータベース</p>', unsafe_allow_html=True)
    
    # サイドバー - WOTA風シンプル
    with st.sidebar:
        st.markdown("""
        <div style="text-align: left; padding: 20px 0 24px 0; border-bottom: 1px solid rgba(0,0,0,0.08);">
            <h2 style="color: #1a1a1a; margin: 0; font-weight: 600; font-size: 18px; letter-spacing: -0.01em;">メニュー</h2>
        </div>
        """, unsafe_allow_html=True)
        
        page = st.radio(
            "ページを選択",
            ["ホーム", "材料一覧", "材料登録", "ダッシュボード", "検索", "素材カード", "元素周期表"],
            label_visibility="collapsed"
        )
        
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
            <small>Material Database v1.0</small>
        </div>
        """, unsafe_allow_html=True)
    
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
        
        cols = st.columns(3)
        for idx, material in enumerate(recent_materials):
            with cols[idx % 3]:
                with st.container():
                    # サブ画像をカード内に装飾として追加
                    sub_img_html = ""
                    sub_img_path = get_image_path("サブ.webp")
                    if sub_img_path:
                        try:
                            sub_img_small = PILImage.open(sub_img_path)
                            sub_img_small.thumbnail((100, 100), PILImage.Resampling.LANCZOS)
                            buffer = BytesIO()
                            sub_img_small.save(buffer, format='WEBP')
                            img_base64 = base64.b64encode(buffer.getvalue()).decode()
                            sub_img_html = f'<div style="position: absolute; top: 10px; right: 10px; opacity: 0.1; width: 80px; height: 80px; background: url(\"data:image/webp;base64,{img_base64}\"); background-size: contain; background-repeat: no-repeat;"></div>'
                        except:
                            pass
                    
                    st.markdown(f"""
                    <div class="material-card-container material-texture" style="position: relative;">
                        {sub_img_html}
                        <h3 style="color: #667eea; margin-top: 0; font-size: 1.4rem; font-weight: 700; position: relative; z-index: 1;">{material.name}</h3>
                        <span class="category-badge" style="position: relative; z-index: 1;">{material.category or '未分類'}</span>
                        <p style="color: #666; margin-top: 20px; line-height: 1.6; position: relative; z-index: 1;">{material.description[:100] if material.description else '説明なし'}...</p>
                        <div style="margin-top: 20px; position: relative; z-index: 1;">
                            <small style="color: #999;">登録日: {material.created_at.strftime('%Y/%m/%d') if material.created_at else 'N/A'}</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
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
    if 'selected_material_id' in st.session_state and st.session_state['selected_material_id']:
        material_id = st.session_state['selected_material_id']
        material = get_material_by_id(material_id)
        
        if material:
            # 戻るボタン
            if st.button("← 一覧に戻る", key="back_to_list"):
                st.session_state['selected_material_id'] = None
                st.rerun()
            
            st.markdown("---")
            st.markdown(f"# {material.name_official or material.name}")
            
            # 3タブ構造で詳細表示
            show_material_detail_tabs(material)
            return
        else:
            st.error("材料が見つかりませんでした。")
            st.session_state['selected_material_id'] = None
    
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
                
                # 素材画像を取得（主役として表示）
                from utils.image_display import get_material_image
                pil_img, img_status, img_message = get_material_image(material, Path.cwd(), auto_regenerate=True)
                
                # 画像HTML（プレースホルダー含む）
                if pil_img and img_status == "ok":
                    from io import BytesIO
                    import base64
                    buffer = BytesIO()
                    pil_img.save(buffer, format='PNG')
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
                
                if st.button(f"詳細を見る", key=f"detail_{material.id}", use_container_width=True):
                    st.session_state['selected_material_id'] = material.id
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
                        
                        # 素材画像を取得（主役として表示）
                        from utils.image_display import get_material_image
                        pil_img, img_status, img_message = get_material_image(material, Path.cwd(), auto_regenerate=True)
                        
                        # 画像HTML（プレースホルダー含む）
                        if pil_img and img_status == "ok":
                            from io import BytesIO
                            import base64
                            buffer = BytesIO()
                            pil_img.save(buffer, format='PNG')
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
        
        primary_image = material.images[0] if material.images else None
        card_data = MaterialCard(material=material, primary_image=primary_image)
        card_html = generate_material_card(card_data)
        
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
