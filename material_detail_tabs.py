"""
材料詳細表示（3タブ構造）
"""
import streamlit as st
import json
from pathlib import Path
from typing import Optional, List, Dict
from PIL import Image as PILImage
from io import BytesIO
import base64


def get_image_path(filename: str) -> Optional[str]:
    """画像パスを取得"""
    possible_paths = [
        Path("static/images") / filename,
        Path("写真") / filename,
        Path("uploads") / filename,
        Path(filename)
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    return None


def get_base64_image(image_path: str) -> Optional[str]:
    """画像をBase64エンコード"""
    if image_path and Path(image_path).exists():
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        except Exception:
            return None
    return None


def parse_json_field(field_value: Optional[str]) -> List[str]:
    """JSON文字列フィールドをパース"""
    if not field_value:
        return []
    try:
        data = json.loads(field_value)
        if isinstance(data, list):
            return data
        elif isinstance(data, str):
            return [data]
        return []
    except:
        # JSONとしてパースできない場合は、そのままリストとして返す
        if isinstance(field_value, str):
            return [field_value]
        return []


def show_material_detail_tabs(material):
    """
    材料詳細を3タブ構造で表示
    
    Args:
        material: Materialオブジェクト
    """
    # タブの選択状態をセッションステートで管理
    if 'material_detail_tab' not in st.session_state:
        st.session_state.material_detail_tab = 'properties'
    
    # タブUI（Streamlitのタブ機能を使用）
    tab1, tab2, tab3 = st.tabs(["材料物性", "入手先・用途", "歴史・物語"])
    
    with tab1:
        show_properties_tab(material)
    
    with tab2:
        show_procurement_uses_tab(material)
    
    with tab3:
        show_history_story_tab(material)


def show_properties_tab(material):
    """タブ1: 材料物性"""
    st.markdown("### 基本特性")
    
    # 基本情報をグリッド表示
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if material.color_tags:
            colors = parse_json_field(material.color_tags)
            if colors:
                st.markdown(f"**色**: {', '.join(colors)}")
        if material.transparency:
            st.markdown(f"**透明性**: {material.transparency}")
        if material.hardness_qualitative:
            st.markdown(f"**硬さ（定性）**: {material.hardness_qualitative}")
            if material.hardness_value:
                st.markdown(f"**硬さ（数値）**: {material.hardness_value}")
    
    with col2:
        if material.weight_qualitative:
            st.markdown(f"**重さ感**: {material.weight_qualitative}")
        if material.specific_gravity:
            st.markdown(f"**比重**: {material.specific_gravity}")
        if material.water_resistance:
            st.markdown(f"**耐水性**: {material.water_resistance}")
    
    with col3:
        if material.heat_resistance_temp:
            st.markdown(f"**耐熱温度**: {material.heat_resistance_temp}℃")
        if material.heat_resistance_range:
            st.markdown(f"**耐熱範囲**: {material.heat_resistance_range}")
        if material.weather_resistance:
            st.markdown(f"**耐候性**: {material.weather_resistance}")
    
    st.markdown("---")
    
    # 物性データテーブル（数値・単位中心）
    if material.properties:
        st.markdown("### 物性データ")
        
        # データフレーム形式で表示
        import pandas as pd
        prop_data = {
            '物性名': [p.property_name for p in material.properties],
            '値': [p.value for p in material.properties],
            '単位': [p.unit or '' for p in material.properties]
        }
        df = pd.DataFrame(prop_data)
        st.dataframe(df, use_container_width=True, height=400)
        
        # カード形式でも表示（視覚的に見やすく）
        st.markdown("#### 物性データ（カード表示）")
        cols = st.columns(3)
        for idx, prop in enumerate(material.properties):
            with cols[idx % 3]:
                st.markdown(f"""
                <div style="
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                    margin-bottom: 10px;
                ">
                    <div style="font-size: 12px; color: #666; margin-bottom: 5px;">{prop.property_name}</div>
                    <div style="font-size: 20px; font-weight: 700; color: #1a1a1a;">
                        {prop.value} <span style="font-size: 14px; color: #666;">{prop.unit or ''}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("物性データが登録されていません。")
    
    st.markdown("---")
    
    # 加工・実装条件
    st.markdown("### 加工・実装条件")
    col1, col2 = st.columns(2)
    
    with col1:
        if material.processing_methods:
            methods = parse_json_field(material.processing_methods)
            if methods:
                st.markdown(f"**加工方法**: {', '.join(methods)}")
        if material.equipment_level:
            st.markdown(f"**必要設備レベル**: {material.equipment_level}")
    
    with col2:
        # 試作難易度（フィールド名のバリエーションに対応）
        difficulty = getattr(material, 'prototyping_difficulty', None) or getattr(material, 'prototype_difficulty', None)
        if difficulty:
            st.markdown(f"**試作難易度**: {difficulty}")
        if material.processing_other:
            st.markdown(f"**その他加工情報**: {material.processing_other}")


def show_procurement_uses_tab(material):
    """タブ2: 入手先・用途"""
    st.markdown("### 入手先情報")
    
    # 供給元・開発主体
    col1, col2 = st.columns(2)
    
    with col1:
        if material.supplier_org:
            st.markdown(f"**供給元・開発主体**: {material.supplier_org}")
        if material.supplier_type:
            st.markdown(f"**供給元種別**: {material.supplier_type}")
        if material.supplier_other:
            st.markdown(f"**その他**: {material.supplier_other}")
    
    with col2:
        if material.procurement_status:
            st.markdown(f"**調達性**: {material.procurement_status}")
        if material.cost_level:
            st.markdown(f"**コスト帯**: {material.cost_level}")
        if material.cost_value and material.cost_unit:
            st.markdown(f"**価格**: {material.cost_value} {material.cost_unit}")
    
    # 参照URL（入手先URL）- DetachedInstanceError対策
    try:
        # eager load済みのreference_urlsにアクセス
        if hasattr(material, 'reference_urls') and material.reference_urls:
            st.markdown("---")
            st.markdown("### 参照URL")
            for ref_url in material.reference_urls:
                st.markdown(f"- [{ref_url.url or 'URL'}]({ref_url.url})")
                if ref_url.description:
                    st.markdown(f"  *{ref_url.description}*")
        else:
            # データベースから直接取得を試みる（フォールバック）
            from database import SessionLocal, ReferenceURL
            db = SessionLocal()
            try:
                ref_urls = db.query(ReferenceURL).filter(ReferenceURL.material_id == material.id).all()
                if ref_urls:
                    st.markdown("---")
                    st.markdown("### 参照URL")
                    for ref_url in ref_urls:
                        st.markdown(f"- [{ref_url.url or 'URL'}]({ref_url.url})")
                        if ref_url.description:
                            st.markdown(f"  *{ref_url.description}*")
            finally:
                db.close()
    except Exception as e:
        # DetachedInstanceError等の例外をキャッチ（アプリを落とさない）
        import traceback
        print(f"参照URL取得エラー: {e}")
        traceback.print_exc()
    
    st.markdown("---")
    
    # 主な用途
    st.markdown("### 主な用途")
    
    if material.use_categories:
        use_cats = parse_json_field(material.use_categories)
        if use_cats:
            # カテゴリをバッジ形式で表示
            cols = st.columns(4)
            for idx, cat in enumerate(use_cats):
                with cols[idx % 4]:
                    st.markdown(f"""
                    <div style="
                        background: #667eea;
                        color: white;
                        padding: 8px 12px;
                        border-radius: 4px;
                        text-align: center;
                        font-size: 13px;
                        margin-bottom: 8px;
                    ">{cat}</div>
                    """, unsafe_allow_html=True)
    
    # 用途例（UseExample）- DetachedInstanceError対策
    try:
        # eager load済みのuse_examplesにアクセス
        if hasattr(material, 'use_examples') and material.use_examples:
            st.markdown("#### 用途例")
            for use_ex in material.use_examples:
                st.markdown(f"- **{use_ex.example_name or '用途例'}**")
                if use_ex.description:
                    st.markdown(f"  {use_ex.description}")
                if use_ex.url:
                    st.markdown(f"  [詳細リンク]({use_ex.url})")
        else:
            # データベースから直接取得を試みる（フォールバック）
            from database import SessionLocal, UseExample
            db = SessionLocal()
            try:
                use_examples = db.query(UseExample).filter(UseExample.material_id == material.id).all()
                if use_examples:
                    st.markdown("#### 用途例")
                    for use_ex in use_examples:
                        st.markdown(f"- **{use_ex.example_name or '用途例'}**")
                        if use_ex.description:
                            st.markdown(f"  {use_ex.description}")
                        if use_ex.url:
                            st.markdown(f"  [詳細リンク]({use_ex.url})")
            finally:
                db.close()
    except Exception as e:
        # DetachedInstanceError等の例外をキャッチ（アプリを落とさない）
        import traceback
        print(f"用途例取得エラー: {e}")
        traceback.print_exc()
    
    # 用途イメージ画像（画像表示の1本化）
    st.markdown("---")
    st.markdown("### 用途イメージ画像")
    
    # 材料の画像を表示（健康状態チェック付き）
    from utils.image_display import display_material_image
    
    if material.images:
        cols = st.columns(min(3, len(material.images)))
        for idx, img in enumerate(material.images):
            with cols[idx % 3]:
                # 各画像レコードに対して表示（簡易版：最初の画像のみ詳細チェック）
                if idx == 0:
                    # 最初の画像は詳細チェック付きで表示
                    display_material_image(
                        material,
                        caption=img.description or f"画像 {idx+1}",
                        use_container_width=True
                    )
                else:
                    # 2枚目以降は従来の方法（後で改善可能）
                    img_path = get_image_path(img.file_path)
                    if img_path:
                        try:
                            pil_img = PILImage.open(img_path)
                            # RGBモードに変換
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
                            st.image(pil_img, caption=img.description or f"画像 {idx+1}", use_container_width=True)
                        except Exception as e:
                            st.warning(f"画像の読み込みに失敗: {e}")
                    else:
                        st.info(f"画像が見つかりません: {img.file_path}")
    else:
        # 画像がない場合は自動生成を試みる
        display_material_image(
            material,
            caption="自動生成画像",
            use_container_width=True
        )


def show_history_story_tab(material):
    """タブ3: 歴史・物語"""
    st.markdown("### 開発背景・ストーリー")
    
    # 開発動機
    if material.development_motives:
        motives = parse_json_field(material.development_motives)
        if motives:
            st.markdown("#### 開発動機")
            for motive in motives:
                st.markdown(f"- {motive}")
    
    if material.development_motive_other:
        st.markdown(f"**その他動機**: {material.development_motive_other}")
    
    # 開発背景（短文）
    if material.development_background_short:
        st.markdown("---")
        st.markdown("#### 開発背景")
        st.markdown(material.development_background_short)
    
    # 開発ストーリー（長文）
    if material.development_story:
        st.markdown("---")
        st.markdown("#### 開発ストーリー")
        st.markdown(material.development_story)
    
    st.markdown("---")
    
    # デザイン視点での特徴
    st.markdown("### デザイン視点での特徴")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 触感
        if material.tactile_tags:
            tactile = parse_json_field(material.tactile_tags)
            if tactile:
                st.markdown("#### 触感")
                for tag in tactile:
                    st.markdown(f"- {tag}")
        if material.tactile_other:
            st.markdown(f"**その他触感**: {material.tactile_other}")
        
        # 視覚
        if material.visual_tags:
            visual = parse_json_field(material.visual_tags)
            if visual:
                st.markdown("#### 視覚的特徴")
                for tag in visual:
                    st.markdown(f"- {tag}")
        if material.visual_other:
            st.markdown(f"**その他視覚**: {material.visual_other}")
    
    with col2:
        # 音・匂い
        if material.sound_smell:
            st.markdown("#### 音・匂い")
            st.markdown(material.sound_smell)
        
        # 経年変化（データベースに該当フィールドがない場合はスキップ）
        if hasattr(material, 'aging_characteristics') and material.aging_characteristics:
            st.markdown("#### 経年変化")
            st.markdown(material.aging_characteristics)
        
        # 加工性（processing_knowhowフィールドを使用）
        if material.processing_knowhow:
            st.markdown("#### 加工性・加工ノウハウ")
            st.markdown(material.processing_knowhow)
    
    # 関連材料
    if material.related_materials:
        st.markdown("---")
        st.markdown("### 関連材料")
        related = parse_json_field(material.related_materials)
        if related:
            for rel in related:
                st.markdown(f"- {rel}")
    
    # NG用途（使われなかった可能性）
    if material.ng_uses:
        st.markdown("---")
        st.markdown("### 使われなかった可能性")
        ng_uses = parse_json_field(material.ng_uses)
        if ng_uses:
            st.markdown("#### NG用途")
            for ng in ng_uses:
                st.markdown(f"- {ng}")
    
    if material.ng_uses_other:
        st.markdown(f"**その他NG用途**: {material.ng_uses_other}")

