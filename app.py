"""
StreamlitベースのWebアプリケーション
オンラインで動くプロトタイプアプリ
"""
import streamlit as st
import sqlite3
import os
from pathlib import Path
from PIL import Image as PILImage
import qrcode
from io import BytesIO
import base64

from database import SessionLocal, Material, Property, Image, Metadata, init_db
from card_generator import generate_material_card
from models import MaterialCard

# クラウド環境でのポート設定
if 'PORT' in os.environ:
    port = int(os.environ.get("PORT", 8501))

# ページ設定
st.set_page_config(
    page_title="マテリアルデータベース",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .material-card {
        border: 2px solid #667eea;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        background: white;
    }
    .property-item {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #e0e0e0;
    }
    .stButton>button {
        width: 100%;
        background-color: #667eea;
        color: white;
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

# メインアプリケーション
def main():
    st.markdown('<h1 class="main-header">🔬 マテリアルデータベース</h1>', unsafe_allow_html=True)
    
    # サイドバー
    with st.sidebar:
        st.title("📋 メニュー")
        page = st.radio(
            "ページを選択",
            ["🏠 ホーム", "📦 材料一覧", "➕ 材料登録", "🔍 検索", "📄 素材カード"]
        )
        
        st.markdown("---")
        st.markdown("### 統計情報")
        materials = get_all_materials()
        st.metric("登録材料数", len(materials))
        if materials:
            categories = set([m.category for m in materials if m.category])
            st.metric("カテゴリ数", len(categories))
    
    # ページルーティング
    if page == "🏠 ホーム":
        show_home()
    elif page == "📦 材料一覧":
        show_materials_list()
    elif page == "➕ 材料登録":
        show_material_form()
    elif page == "🔍 検索":
        show_search()
    elif page == "📄 素材カード":
        show_material_cards()

def show_home():
    """ホームページ"""
    st.markdown("""
    ## ようこそ！マテリアルデータベースへ
    
    このシステムは、素材カード形式でマテリアル情報を管理するデータベースです。
    
    ### 主な機能
    
    - ✅ **材料情報の登録・管理**
    - ✅ **物性データの管理**
    - ✅ **画像のアップロード**
    - ✅ **素材カードの自動生成**
    - ✅ **検索・フィルタリング機能**
    
    ### 使い方
    
    1. **材料登録**: サイドバーから「材料登録」を選択して新しい材料を追加
    2. **材料一覧**: 登録された材料を一覧で確認
    3. **素材カード**: 材料情報を視覚的なカード形式で表示・印刷
    
    ### 将来の機能（LLM統合予定）
    
    - 🤖 自然言語での材料検索
    - 🎯 要件に基づく材料推奨
    - 📊 物性データの予測
    - 🔗 材料の類似度分析
    """)
    
    # 最近登録された材料
    materials = get_all_materials()
    if materials:
        st.markdown("### 最近登録された材料")
        recent_materials = sorted(materials, key=lambda x: x.created_at, reverse=True)[:5]
        for material in recent_materials:
            with st.expander(f"🔹 {material.name} ({material.category or 'カテゴリ未設定'})"):
                st.write(f"**説明**: {material.description or '説明なし'}")
                st.write(f"**登録日**: {material.created_at.strftime('%Y年%m月%d日') if material.created_at else 'N/A'}")
                if material.properties:
                    st.write("**主要物性**:")
                    for prop in material.properties[:3]:
                        st.write(f"- {prop.property_name}: {prop.value} {prop.unit or ''}")

def show_materials_list():
    """材料一覧ページ"""
    st.title("📦 材料一覧")
    
    materials = get_all_materials()
    
    if not materials:
        st.info("まだ材料が登録されていません。「材料登録」から材料を追加してください。")
        return
    
    # フィルタリング
    col1, col2 = st.columns(2)
    with col1:
        categories = [None] + list(set([m.category for m in materials if m.category]))
        selected_category = st.selectbox("カテゴリでフィルタ", categories)
    with col2:
        search_term = st.text_input("材料名で検索")
    
    # フィルタリング適用
    filtered_materials = materials
    if selected_category:
        filtered_materials = [m for m in filtered_materials if m.category == selected_category]
    if search_term:
        filtered_materials = [m for m in filtered_materials if search_term.lower() in m.name.lower()]
    
    st.write(f"**{len(filtered_materials)}件**の材料が見つかりました")
    
    # 材料カード表示
    for material in filtered_materials:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"### {material.name}")
                if material.category:
                    st.markdown(f"🏷️ **カテゴリ**: {material.category}")
                if material.description:
                    st.write(material.description)
            
            with col2:
                if material.properties:
                    st.markdown("**主要物性**")
                    for prop in material.properties[:3]:
                        st.write(f"- {prop.property_name}: {prop.value} {prop.unit or ''}")
            
            with col3:
                st.write(f"**ID**: {material.id}")
                if st.button(f"詳細", key=f"detail_{material.id}"):
                    st.session_state['selected_material_id'] = material.id
                    st.rerun()
            
            st.markdown("---")

def show_material_form():
    """材料登録フォーム"""
    st.title("➕ 材料登録")
    
    with st.form("material_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("材料名 *", placeholder="例: ステンレス鋼 SUS304")
            category = st.selectbox(
                "カテゴリ",
                ["", "金属", "プラスチック", "セラミック", "複合材料", "その他"]
            )
        
        with col2:
            description = st.text_area("説明", placeholder="材料の説明を入力してください")
        
        st.markdown("### 物性データ")
        
        # 動的な物性入力フィールド
        if 'properties' not in st.session_state:
            st.session_state.properties = [{'name': '', 'value': '', 'unit': ''}]
        
        properties = []
        for i, prop in enumerate(st.session_state.properties):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                prop_name = st.text_input(f"物性名 {i+1}", value=prop['name'], key=f"prop_name_{i}")
            with col2:
                prop_value = st.number_input(f"値 {i+1}", value=float(prop['value']) if prop['value'] else 0.0, key=f"prop_value_{i}")
            with col3:
                prop_unit = st.text_input(f"単位 {i+1}", value=prop['unit'], key=f"prop_unit_{i}")
            
            properties.append({
                'name': prop_name,
                'value': prop_value,
                'unit': prop_unit
            })
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("➕ 物性を追加"):
                st.session_state.properties.append({'name': '', 'value': '', 'unit': ''})
                st.rerun()
        
        submitted = st.form_submit_button("✅ 材料を登録")
        
        if submitted:
            if not name:
                st.error("材料名は必須です")
            else:
                try:
                    material = create_material(name, category if category else None, description, properties)
                    st.success(f"✅ 材料「{material.name}」を登録しました！")
                    st.session_state.properties = [{'name': '', 'value': '', 'unit': ''}]
                    st.rerun()
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")

def show_search():
    """検索ページ"""
    st.title("🔍 材料検索")
    
    search_query = st.text_input("検索キーワード", placeholder="材料名、カテゴリ、説明などで検索")
    
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
            st.write(f"**{len(results)}件**の結果が見つかりました")
            for material in results:
                with st.expander(f"🔹 {material.name}"):
                    st.write(f"**カテゴリ**: {material.category or '未設定'}")
                    st.write(f"**説明**: {material.description or '説明なし'}")
                    if material.properties:
                        st.write("**物性データ**:")
                        for prop in material.properties:
                            st.write(f"- {prop.property_name}: {prop.value} {prop.unit or ''}")
        else:
            st.info("検索結果が見つかりませんでした。")

def show_material_cards():
    """素材カード表示ページ"""
    st.title("📄 素材カード")
    
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
        st.markdown(f"## {material.name}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
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
            import pandas as pd
            prop_data = {
                '物性名': [p.property_name for p in material.properties],
                '値': [p.value for p in material.properties],
                '単位': [p.unit or '' for p in material.properties]
            }
            df = pd.DataFrame(prop_data)
            st.dataframe(df, use_container_width=True)
        
        # カードのHTML生成と表示
        primary_image = material.images[0] if material.images else None
        card_data = MaterialCard(material=material, primary_image=primary_image)
        card_html = generate_material_card(card_data)
        
        st.markdown("---")
        st.markdown("### 素材カード（印刷用）")
        
        # HTMLを表示（クラウド環境でも動作するように）
        try:
            st.components.v1.html(card_html, height=800, scrolling=True)
        except:
            # フォールバック: HTMLを直接表示
            st.markdown(card_html, unsafe_allow_html=True)
        
        # ダウンロードボタン
        st.download_button(
            label="📥 カードをHTMLとしてダウンロード",
            data=card_html,
            file_name=f"material_card_{material.id}.html",
            mime="text/html"
        )

if __name__ == "__main__":
    main()

