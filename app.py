"""
StreamlitベースのWebアプリケーション
リッチなUIを持つマテリアルデータベース
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

# リッチなカスタムCSS
st.markdown("""
<style>
    /* メインスタイル */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        background-attachment: fixed;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* ヘッダー */
    .main-header {
        font-size: 4rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        margin-bottom: 1rem;
        text-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        animation: fadeInDown 0.8s ease-out;
    }
    
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* カードスタイル */
    .material-card-container {
        background: white;
        border-radius: 20px;
        padding: 30px;
        margin: 20px 0;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    
    .material-card-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 60px rgba(102, 126, 234, 0.2);
    }
    
    .category-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 8px 20px;
        border-radius: 25px;
        font-size: 13px;
        font-weight: 600;
        margin: 5px 5px 0 0;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    /* 統計カード */
    .stat-card {
        background: white;
        border-radius: 15px;
        padding: 25px;
        text-align: center;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08);
        transition: all 0.3s ease;
        border-left: 4px solid #667eea;
    }
    
    .stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.2);
    }
    
    .stat-value {
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 10px 0;
    }
    
    .stat-label {
        color: #666;
        font-size: 0.9rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* ボタンスタイル */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* サイドバー */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8f9ff 100%);
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #333;
    }
    
    /* 入力フィールド */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>select {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        transition: all 0.3s ease;
    }
    
    .stTextInput>div>div>input:focus,
    .stTextArea>div>div>textarea:focus,
    .stSelectbox>div>div>select:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* メトリクス */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 900;
    }
    
    /* アニメーション */
    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    
    /* グラデーションテキスト */
    .gradient-text {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }
    
    /* カードグリッド */
    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 20px;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

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
    # ヘッダー
    st.markdown('<h1 class="main-header">🔬 マテリアルデータベース</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: white; font-size: 1.2rem; margin-bottom: 3rem;">素材の可能性を探索する、美しいデータベース</p>', unsafe_allow_html=True)
    
    # サイドバー
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h2 style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                       -webkit-background-clip: text;
                       -webkit-text-fill-color: transparent;
                       margin: 0;">📋 メニュー</h2>
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
    
    # ヒーローセクション
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="background: white; border-radius: 20px; padding: 40px; text-align: center; 
                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1); margin: 20px 0;">
            <h2 style="color: #333; margin-bottom: 20px;">✨ ようこそ！</h2>
            <p style="font-size: 1.1rem; color: #666; line-height: 1.8;">
                素材カード形式でマテリアル情報を管理する、美しく使いやすいデータベースシステムです。<br>
                デザイナーやエンジニアが、材料の可能性を探索するためのツールです。
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # 機能紹介カード
    st.markdown("### 🎯 主な機能")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size: 3rem; margin-bottom: 10px;">📝</div>
            <h3 style="color: #333;">材料登録</h3>
            <p style="color: #666;">簡単に材料情報を登録・管理</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size: 3rem; margin-bottom: 10px;">📊</div>
            <h3 style="color: #333;">データ可視化</h3>
            <p style="color: #666;">グラフで材料データを分析</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stat-card">
            <div style="font-size: 3rem; margin-bottom: 10px;">🎨</div>
            <h3 style="color: #333;">素材カード</h3>
            <p style="color: #666;">美しい素材カードを自動生成</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 最近登録された材料
    if materials:
        st.markdown("### ⭐ 最近登録された材料")
        recent_materials = sorted(materials, key=lambda x: x.created_at if x.created_at else datetime.min, reverse=True)[:6]
        
        cols = st.columns(3)
        for idx, material in enumerate(recent_materials):
            with cols[idx % 3]:
                with st.container():
                    st.markdown(f"""
                    <div class="material-card-container">
                        <h3 style="color: #667eea; margin-top: 0;">{material.name}</h3>
                        <span class="category-badge">{material.category or '未分類'}</span>
                        <p style="color: #666; margin-top: 15px;">{material.description[:100] if material.description else '説明なし'}...</p>
                        <div style="margin-top: 15px;">
                            <small style="color: #999;">登録日: {material.created_at.strftime('%Y/%m/%d') if material.created_at else 'N/A'}</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # 将来の機能
    st.markdown("---")
    st.markdown("### 🚀 将来の機能（LLM統合予定）")
    
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
            <div style="background: white; border-radius: 15px; padding: 20px; 
                        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.08); height: 100%;">
                <div style="font-size: 2.5rem; margin-bottom: 10px;">{icon}</div>
                <h4 style="color: #333; margin: 10px 0;">{title}</h4>
                <p style="color: #666; font-size: 0.9rem; margin: 0;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

def show_materials_list():
    """材料一覧ページ"""
    st.markdown('<h2 class="gradient-text">📦 材料一覧</h2>', unsafe_allow_html=True)
    
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
                        f"<small>• {p.property_name}: <strong>{p.value} {p.unit or ''}</strong></small>"
                        for p in props
                    ])
                
                st.markdown(f"""
                <div class="material-card-container">
                    <h3 style="color: #667eea; margin-top: 0; font-size: 1.3rem;">{material.name}</h3>
                    <span class="category-badge">{material.category or '未分類'}</span>
                    <p style="color: #666; margin: 15px 0; font-size: 0.95rem;">
                        {material.description[:80] if material.description else '説明なし'}...
                    </p>
                    <div style="margin: 15px 0;">
                        {properties_text}
                    </div>
                    <div style="margin-top: 15px;">
                        <small style="color: #999;">ID: {material.id}</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"詳細を見る", key=f"detail_{material.id}", use_container_width=True):
                    st.session_state['selected_material_id'] = material.id
                    st.rerun()

def show_material_form():
    """材料登録フォーム"""
    st.markdown('<h2 class="gradient-text">➕ 材料登録</h2>', unsafe_allow_html=True)
    
    with st.form("material_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("材料名 *", placeholder="例: ステンレス鋼 SUS304", help="材料の正式名称を入力してください")
            category = st.selectbox(
                "カテゴリ",
                ["", "金属", "プラスチック", "セラミック", "複合材料", "その他"],
                help="材料のカテゴリを選択"
            )
        
        with col2:
            description = st.text_area("説明", placeholder="材料の特徴、用途、説明を入力してください", height=100)
        
        st.markdown("### 📊 物性データ")
        
        # 動的な物性入力フィールド
        if 'properties' not in st.session_state:
            st.session_state.properties = [{'name': '', 'value': '', 'unit': ''}]
        
        properties = []
        for i, prop in enumerate(st.session_state.properties):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                prop_name = st.text_input(f"物性名 {i+1}", value=prop['name'], key=f"prop_name_{i}", placeholder="例: 密度")
            with col2:
                prop_value = st.number_input(f"値 {i+1}", value=float(prop['value']) if prop['value'] else 0.0, key=f"prop_value_{i}", step=0.01)
            with col3:
                prop_unit = st.text_input(f"単位 {i+1}", value=prop['unit'], key=f"prop_unit_{i}", placeholder="例: g/cm³")
            
            properties.append({
                'name': prop_name,
                'value': prop_value,
                'unit': prop_unit
            })
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.form_submit_button("➕ 物性を追加", use_container_width=True):
                st.session_state.properties.append({'name': '', 'value': '', 'unit': ''})
                st.rerun()
        
        submitted = st.form_submit_button("✅ 材料を登録", use_container_width=True, type="primary")
        
        if submitted:
            if not name:
                st.error("❌ 材料名は必須です")
            else:
                try:
                    material = create_material(name, category if category else None, description, properties)
                    st.success(f"✅ 材料「{material.name}」を登録しました！")
                    st.balloons()
                    st.session_state.properties = [{'name': '', 'value': '', 'unit': ''}]
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ エラーが発生しました: {str(e)}")

def show_dashboard():
    """ダッシュボードページ"""
    st.markdown('<h2 class="gradient-text">📊 ダッシュボード</h2>', unsafe_allow_html=True)
    
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
    st.markdown('<h2 class="gradient-text">🔍 材料検索</h2>', unsafe_allow_html=True)
    
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
                        <div class="material-card-container">
                            <h3 style="color: #667eea; margin-top: 0;">{material.name}</h3>
                            <span class="category-badge">{material.category or '未分類'}</span>
                            <p style="color: #666; margin: 15px 0;">{material.description or '説明なし'}</p>
                            {f'<p><strong>物性データ:</strong> {len(material.properties)}個</p>' if material.properties else ''}
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("検索結果が見つかりませんでした。別のキーワードで検索してみてください。")

def show_material_cards():
    """素材カード表示ページ"""
    st.markdown('<h2 class="gradient-text">📄 素材カード</h2>', unsafe_allow_html=True)
    
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
