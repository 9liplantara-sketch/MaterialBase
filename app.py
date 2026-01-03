"""
StreamlitベースのWebアプリケーション
マテリアル感のあるリッチなUI
"""
import streamlit as st
import os
from pathlib import Path
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
from card_generator import generate_material_card
from models import MaterialCard
from material_form_detailed import show_detailed_material_form

# クラウド環境でのポート設定
if 'PORT' in os.environ:
    port = int(os.environ.get("PORT", 8501))

# ページ設定
st.set_page_config(
    page_title="マテリアルデータベース | Material Database",
    page_icon="🔬",
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

# デバッグスイッチ（サイドバーでCSSを無効化可能）
# 注意: この変数はmain()関数内で設定されるため、ここでは定義のみ
debug_no_css = False

# マテリアル感のあるカスタムCSS（条件付き適用）
def get_custom_css():
    """カスタムCSSを生成（デバッグモード対応）"""
    return f"""
<style>
    /* ベース文字色を確保（白飛び防止） */
    html, body, [class*="st-"] {{
        color: #111 !important;
    }}
    
    /* メイン背景 - メイン.webpを使用 */
    .stApp {{
        background: {'url("data:image/webp;base64,' + main_bg_base64 + '")' if main_bg_base64 else 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)'};
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        background-repeat: no-repeat;
        position: relative;
        min-height: 100vh;
    }}
    
    .stApp::before {{
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255, 255, 255, 0.75);
        z-index: -1;
        pointer-events: none;
    }}
    
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        position: relative;
        z-index: 10;
        background: transparent;
    }}
    
    /* ヘッダー - マテリアル感のあるデザイン */
    .main-header {{
        font-size: 4.5rem;
        font-weight: 900;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 8px rgba(255, 255, 255, 0.8),
                     -1px -1px 2px rgba(0, 0, 0, 0.1);
        letter-spacing: 2px;
        position: relative;
        z-index: 2;
    }}
    
    .main-header::after {{
        content: '';
        display: block;
        width: 100px;
        height: 4px;
        background: linear-gradient(90deg, transparent, #667eea, transparent);
        margin: 20px auto;
        border-radius: 2px;
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
    
    /* カードスタイル - マテリアル感 */
    .material-card-container {{
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 24px;
        padding: 35px;
        margin: 25px 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12),
                    0 2px 8px rgba(0, 0, 0, 0.08),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(255, 255, 255, 0.8);
        position: relative;
        overflow: hidden;
    }}
    
    .material-card-container::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
        opacity: 0.6;
    }}
    
    .material-card-container:hover {{
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 16px 48px rgba(102, 126, 234, 0.25),
                    0 4px 16px rgba(0, 0, 0, 0.12),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9);
        border-color: rgba(102, 126, 234, 0.3);
    }}
    
    /* カテゴリバッジ - マテリアル感 */
    .category-badge {{
        display: inline-block;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.9) 0%, rgba(118, 75, 162, 0.9) 100%);
        color: white;
        padding: 10px 24px;
        border-radius: 30px;
        font-size: 13px;
        font-weight: 700;
        margin: 8px 8px 0 0;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4),
                    inset 0 1px 0 rgba(255, 255, 255, 0.3);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }}
    
    /* 統計カード - ガラスモーフィズム */
    .stat-card {{
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 30px;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9);
        transition: all 0.4s ease;
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-left: 5px solid #667eea;
        position: relative;
        overflow: hidden;
    }}
    
    .stat-card::before {{
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
        animation: rotate 20s linear infinite;
    }}
    
    @keyframes rotate {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}
    
    .stat-card:hover {{
        transform: translateY(-5px) scale(1.05);
        box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9);
    }}
    
    .stat-value {{
        font-size: 3rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 15px 0;
        position: relative;
        z-index: 1;
    }}
    
    .stat-label {{
        color: #555;
        font-size: 0.95rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        position: relative;
        z-index: 1;
    }}
    
    /* ボタンスタイル - マテリアル感 */
    .stButton>button {{
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.6rem 2.5rem;
        font-weight: 700;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4),
                    inset 0 1px 0 rgba(255, 255, 255, 0.3);
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 14px;
    }}
    
    .stButton>button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.5),
                    inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }}
    
    /* サイドバー - ガラスモーフィズム */
    [data-testid="stSidebar"] {{
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(0, 0, 0, 0.1);
    }}
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        color: #2c3e50;
    }}
    
    /* 入力フィールド - マテリアル感 */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>select {{
        border-radius: 12px;
        border: 2px solid rgba(0, 0, 0, 0.1);
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
    }}
    
    .stTextInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus,
    .stSelectbox>div>div>select:focus {{
        border-color: #667eea;
        box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15),
                    inset 0 2px 4px rgba(0, 0, 0, 0.05);
        background: rgba(255, 255, 255, 1);
    }}
    
    /* メトリクス */
    [data-testid="stMetricValue"] {{
        font-size: 2.2rem;
        font-weight: 900;
        color: #2c3e50;
    }}
    
    /* グラデーションテキスト */
    .gradient-text {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        letter-spacing: 1px;
    }}
    
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
    
    /* ヒーローセクション */
    .hero-section {{
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(20px);
        border-radius: 30px;
        padding: 60px 40px;
        text-align: center;
        margin: 40px 0;
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.8);
        position: relative;
        overflow: hidden;
    }}
    
    .hero-section::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: {'url("data:image/webp;base64,' + sub_bg_base64 + '")' if sub_bg_base64 else 'none'};
        background-size: 50%;
        opacity: 0.05;
        animation: float 30s ease-in-out infinite;
    }}
    
    @keyframes float {{
        0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
        50% {{ transform: translate(20px, 20px) rotate(5deg); }}
    }}
    
    /* セクションタイトル */
    .section-title {{
        font-size: 2.5rem;
        font-weight: 800;
        color: #2c3e50;
        margin: 40px 0 20px 0;
        text-align: center;
        position: relative;
        padding-bottom: 20px;
    }}
    
    .section-title::after {{
        content: '';
        display: block;
        width: 80px;
        height: 4px;
        background: linear-gradient(90deg, transparent, #667eea, transparent);
        margin: 15px auto 0;
        border-radius: 2px;
    }}
</style>
"""

# データベース初期化
if not os.path.exists("materials.db"):
    init_db()

def get_db():
    """データベースセッションを取得"""
    return SessionLocal()

def get_all_materials():
    """全材料を取得"""
    db = get_db()
    try:
        materials = db.query(Material).all()
        return materials
    finally:
        db.close()

def get_material_by_id(material_id: int):
    """IDで材料を取得"""
    db = get_db()
    try:
        material = db.query(Material).filter(Material.id == material_id).first()
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
    """QRコードを生成"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Material ID: {material_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    return qr_img

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
    # デバッグスイッチ（サイドバーでCSSを無効化可能）
    debug_no_css = st.sidebar.checkbox("🔧 Debug: CSSを無効化", value=False, help="白飛びが発生している場合、このチェックをONにするとCSSを無効化して表示を確認できます")
    
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
        st.warning("🔧 デバッグモード: CSSが無効化されています。表示が正常な場合、CSSが原因です。")
    
    # ヘッダー
    st.markdown('<h1 class="main-header">🔬 マテリアルデータベース</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #555; font-size: 1.3rem; margin-bottom: 3rem; font-weight: 500;">素材の可能性を探索する、美しいデータベース</p>', unsafe_allow_html=True)
    
    # サイドバー
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h2 style="color: #2c3e50; margin: 0; font-weight: 800;">📋 メニュー</h2>
        </div>
        """, unsafe_allow_html=True)
        
        page = st.radio(
            "ページを選択",
            ["🏠 ホーム", "📦 材料一覧", "➕ 材料登録", "📊 ダッシュボード", "🔍 検索", "📄 素材カード"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # 統計情報
        materials = get_all_materials()
        st.markdown("### 📈 統計情報")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("材料数", len(materials), delta=None)
        with col2:
            if materials:
                categories = len(set([m.category for m in materials if m.category]))
                st.metric("カテゴリ", categories)
        
        if materials:
            total_properties = sum(len(m.properties) for m in materials)
            st.metric("物性データ", total_properties)
        
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; padding: 20px 0; color: #666;">
            <small>Material Database v1.0</small>
        </div>
        """, unsafe_allow_html=True)
    
    # ページルーティング
    if page == "🏠 ホーム":
        show_home()
    elif page == "📦 材料一覧":
        show_materials_list()
    elif page == "➕ 材料登録":
        show_detailed_material_form()
    elif page == "📊 ダッシュボード":
        show_dashboard()
    elif page == "🔍 検索":
        show_search()
    elif page == "📄 素材カード":
        show_material_cards()

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
                    <h2 style="color: #2c3e50; margin-bottom: 20px; font-size: 2.5rem; font-weight: 800;">✨ ようこそ！</h2>
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
            <h2 style="color: #2c3e50; margin-bottom: 20px; font-size: 2.5rem; font-weight: 800;">✨ ようこそ！</h2>
            <p style="font-size: 1.2rem; color: #555; line-height: 1.8; max-width: 800px; margin: 0 auto; font-weight: 500;">
                素材カード形式でマテリアル情報を管理する、美しく使いやすいデータベースシステムです。<br>
                デザイナーやエンジニアが、材料の可能性を探索するためのツールです。
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # 機能紹介カード
    st.markdown('<h3 class="section-title">🎯 主な機能</h3>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size: 3.5rem; margin-bottom: 15px;">📝</div>
            <h3 style="color: #2c3e50; margin: 15px 0;">材料登録</h3>
            <p style="color: #666; margin: 0;">簡単に材料情報を登録・管理</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size: 3.5rem; margin-bottom: 15px;">📊</div>
            <h3 style="color: #2c3e50; margin: 15px 0;">データ可視化</h3>
            <p style="color: #666; margin: 0;">グラフで材料データを分析</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size: 3.5rem; margin-bottom: 15px;">🎨</div>
            <h3 style="color: #2c3e50; margin: 15px 0;">素材カード</h3>
            <p style="color: #666; margin: 0;">美しい素材カードを自動生成</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 最近登録された材料
    if materials:
        st.markdown('<h3 class="section-title">⭐ 最近登録された材料</h3>', unsafe_allow_html=True)
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
    
    # 将来の機能
    st.markdown("---")
    st.markdown('<h3 class="section-title">🚀 将来の機能（LLM統合予定）</h3>', unsafe_allow_html=True)
    
    future_features = [
        ("🤖", "自然言語検索", "「高強度で軽量な材料」など、自然な言葉で検索"),
        ("🎯", "材料推奨", "要件に基づいて最適な材料を自動推奨"),
        ("📊", "物性予測", "AIによる物性データの予測"),
        ("🔗", "類似度分析", "材料間の類似性を分析")
    ]
    
    cols = st.columns(4)
    for idx, (icon, title, desc) in enumerate(future_features):
        with cols[idx]:
            st.markdown(f"""
            <div class="material-card-container" style="padding: 25px; text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 15px;">{icon}</div>
                <h4 style="color: #2c3e50; margin: 15px 0; font-weight: 700;">{title}</h4>
                <p style="color: #666; font-size: 0.95rem; margin: 0; line-height: 1.6;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

def show_materials_list():
    """材料一覧ページ"""
    st.markdown('<h2 class="gradient-text section-title">📦 材料一覧</h2>', unsafe_allow_html=True)
    
    materials = get_all_materials()
    
    if not materials:
        st.info("まだ材料が登録されていません。「材料登録」から材料を追加してください。")
        return
    
    # フィルタリング
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        categories = ["すべて"] + list(set([m.category for m in materials if m.category]))
        selected_category = st.selectbox("カテゴリでフィルタ", categories)
    with col2:
        search_term = st.text_input("🔍 材料名で検索", placeholder="材料名を入力...")
    with col3:
        st.write("")  # スペーサー
        st.write("")  # スペーサー
    
    # フィルタリング適用
    filtered_materials = materials
    if selected_category and selected_category != "すべて":
        filtered_materials = [m for m in filtered_materials if m.category == selected_category]
    if search_term:
        filtered_materials = [m for m in filtered_materials if search_term.lower() in m.name.lower()]
    
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
                
                st.markdown(f"""
                <div class="material-card-container material-texture">
                    <h3 style="color: #667eea; margin-top: 0; font-size: 1.4rem; font-weight: 700;">{material.name}</h3>
                    <span class="category-badge">{material.category or '未分類'}</span>
                    <p style="color: #666; margin: 20px 0; font-size: 0.95rem; line-height: 1.6;">
                        {material.description[:80] if material.description else '説明なし'}...
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
    st.markdown('<h2 class="gradient-text section-title">📊 ダッシュボード</h2>', unsafe_allow_html=True)
    
    materials = get_all_materials()
    
    if not materials:
        st.info("ダッシュボードを表示するには、まず材料を登録してください。")
        return
    
    # 統計カード
    st.markdown("### 📈 統計情報")
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
        total_properties = sum(len(m.properties) for m in materials)
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
    st.markdown("### 📋 カテゴリ別詳細")
    category_data = {}
    for material in materials:
        cat = material.category or "未分類"
        if cat not in category_data:
            category_data[cat] = []
        category_data[cat].append(material)
    
    for category, mats in category_data.items():
        with st.expander(f"📁 {category} ({len(mats)}件)", expanded=False):
            for mat in mats:
                st.write(f"• **{mat.name}** - {len(mat.properties)}個の物性データ")

def show_search():
    """検索ページ"""
    st.markdown('<h2 class="gradient-text section-title">🔍 材料検索</h2>', unsafe_allow_html=True)
    
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
                        st.markdown(f"""
                        <div class="material-card-container material-texture">
                            <h3 style="color: #667eea; margin-top: 0; font-size: 1.3rem; font-weight: 700;">{material.name}</h3>
                            <span class="category-badge">{material.category or '未分類'}</span>
                            <p style="color: #666; margin: 15px 0; line-height: 1.6;">{material.description or '説明なし'}</p>
                            {f'<p style="color: #555;"><strong>物性データ:</strong> {len(material.properties)}個</p>' if material.properties else ''}
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("検索結果が見つかりませんでした。別のキーワードで検索してみてください。")

def show_material_cards():
    """素材カード表示ページ"""
    st.markdown('<h2 class="gradient-text section-title">📄 素材カード</h2>', unsafe_allow_html=True)
    
    materials = get_all_materials()
    
    if not materials:
        st.info("材料が登録されていません。")
        return
    
    material_options = {f"{m.name} (ID: {m.id})": m.id for m in materials}
    selected_material_name = st.selectbox("材料を選択", list(material_options.keys()))
    material_id = material_options[selected_material_name]
    
    material = get_material_by_id(material_id)
    
    if material:
        # 素材カードの表示
        st.markdown("---")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"## {material.name}")
            if material.category:
                st.markdown(f"**カテゴリ**: {material.category}")
            if material.description:
                st.markdown(f"**説明**: {material.description}")
        
        with col2:
            qr_img = generate_qr_code(material.id)
            st.image(qr_img, caption="QRコード", width=150)
        
        # 物性データテーブル
        if material.properties:
            st.markdown("### 物性データ")
            prop_data = {
                '物性名': [p.property_name for p in material.properties],
                '値': [p.value for p in material.properties],
                '単位': [p.unit or '' for p in material.properties]
            }
            df = pd.DataFrame(prop_data)
            st.dataframe(df, use_container_width=True, height=300)
        
        # カードのHTML生成と表示
        primary_image = material.images[0] if material.images else None
        card_data = MaterialCard(material=material, primary_image=primary_image)
        card_html = generate_material_card(card_data)
        
        st.markdown("---")
        st.markdown("### 素材カード（印刷用）")
        
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
