"""
材料詳細表示（3タブ構造）
"""
import streamlit as st
import json
import os
from pathlib import Path
from typing import Optional, List, Dict
from PIL import Image as PILImage
from io import BytesIO
import base64
from urllib.parse import urlsplit, urlunsplit, quote


def safe_url(url: str) -> str:
    """
    URLのpath部分をエンコード（日本語ファイル名対応）
    
    Args:
        url: 元のURL
    
    Returns:
        エンコードされたURL
    """
    if not url:
        return url
    try:
        p = urlsplit(url)
        # path部分をエンコード（/と%はそのまま）
        encoded_path = quote(p.path, safe="/%")
        return urlunsplit((p.scheme, p.netloc, encoded_path, p.query, p.fragment))
    except Exception:
        # エンコードに失敗した場合は元のURLを返す
        return url


def get_images_by_kind(material) -> Dict[str, str]:
    """
    imagesテーブルから画像を取得して {kind: public_url} のdictを返す
    
    Args:
        material: Materialオブジェクト
    
    Returns:
        {kind: public_url} の辞書（例: {"primary": "https://...", "space": "https://...", "product": "https://..."}）
    """
    from database import SessionLocal, Image
    from sqlalchemy import or_
    
    # imagesテーブルから画像を取得
    images = []
    if hasattr(material, 'images') and material.images:
        images = list(material.images)
    else:
        # データベースから直接取得（kind/image_typeの両方に対応）
        db_images = SessionLocal()
        try:
            # kind列またはimage_type列でprimary/space/productを検索
            try:
                images = db_images.query(Image).filter(
                    Image.material_id == material.id,
                    or_(
                        Image.kind.in_(['primary', 'space', 'product']),
                        Image.image_type.in_(['primary', 'space', 'product'])
                    )
                ).all()
            except Exception:
                # image_type列が存在しない場合はkind列のみで検索
                try:
                    images = db_images.query(Image).filter(
                        Image.material_id == material.id,
                        Image.kind.in_(['primary', 'space', 'product'])
                    ).all()
                except Exception:
                    # どちらも失敗した場合は全画像を取得して後でフィルタ
                    all_images = db_images.query(Image).filter(
                        Image.material_id == material.id
                    ).all()
                    images = []
                    for img in all_images:
                        k = getattr(img, "kind", None) or getattr(img, "image_type", None)
                        if k in ('primary', 'space', 'product'):
                            images.append(img)
        finally:
            db_images.close()
    
    # images を {kind: public_url} にする（kind名やurl列名の揺れを吸収）
    images_by_kind: Dict[str, str] = {}
    
    for img in images:  # material.images でも DBクエリ結果でもOK
        k = getattr(img, "kind", None) or getattr(img, "image_type", None) or getattr(img, "type", None)
        u = getattr(img, "public_url", None) or getattr(img, "url", None)
        if k and u:
            images_by_kind[str(k)] = str(u)
    
    return images_by_kind


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
    st.markdown("---")
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
        st.dataframe(df, width='stretch', height=400)
        
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
                # 文字化け防止：改行を適切に処理し、Markdownエスケープ
                # リスト形式で表示（読みやすく）
                st.markdown("**加工方法**:")
                for method in methods:
                    # 括弧や記号をエスケープせず、そのまま表示（st.writeを使用）
                    st.write(f"  • {method}")
        if material.equipment_level:
            # 文字化け防止：st.writeを使用（Markdown解釈を避ける）
            st.write(f"**必要設備レベル**: {material.equipment_level}")
    
    with col2:
        # 試作難易度（フィールド名のバリエーションに対応）
        difficulty = getattr(material, 'prototyping_difficulty', None) or getattr(material, 'prototype_difficulty', None)
        if difficulty:
            # 文字化け防止：st.writeを使用
            st.write(f"**試作難易度**: {difficulty}")
        if material.processing_other:
            # 文字化け防止：st.writeを使用
            st.write(f"**その他加工情報**: {material.processing_other}")
    
    # 加工例画像セクション（材料別の生成画像を優先）
    if material.processing_methods:
        methods = parse_json_field(material.processing_methods)
        if methods:
            st.markdown("---")
            st.markdown("### 加工例")
            
            # データベースから材料別の加工例画像を取得
            from database import SessionLocal, ProcessExampleImage
            from utils.paths import resolve_path
            
            db = SessionLocal()
            try:
                process_images = db.query(ProcessExampleImage).filter(
                    ProcessExampleImage.material_id == material.id
                ).all()
                
                # 加工方法と画像のマッピング
                process_image_map = {p.process_method: p.image_path for p in process_images if p.image_path}
            finally:
                db.close()
            
            # 加工方法ごとに画像を表示（最大3列）
            cols = st.columns(min(3, len(methods)))
            for idx, method in enumerate(methods):
                with cols[idx % 3]:
                    try:
                        # 材料別の生成画像を優先
                        image_path = None
                        if method in process_image_map:
                            image_path = process_image_map[method]
                        
                        # 材料別画像がない場合、汎用画像を試す
                        if not image_path:
                            from utils.process_image_generator import get_process_example_image
                            image_path = get_process_example_image(method, output_dir="static/generated/process_examples")
                        
                        if image_path:
                            # パスを解決
                            resolved_path = resolve_path(image_path) if not Path(image_path).is_absolute() else Path(image_path)
                            
                            if resolved_path.exists():
                                # Pathを直接display_image_unifiedに渡す
                                from utils.image_display import display_image_unified
                                display_image_unified(resolved_path, caption=method, width=280)
                            else:
                                st.caption(f"{method} (画像ファイルが見つかりません)")
                        else:
                            st.caption(f"{method} (画像準備中)")
                    except Exception as e:
                        import traceback
                        st.caption(f"{method} (エラー: {str(e)[:50]})")
                        if os.getenv("DEBUG", "false").lower() == "true":
                            st.code(traceback.format_exc())


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
    
    # 代表的な使用例（UseExample）
    st.markdown("---")
    st.markdown("### 代表的な使用例")
    
    # DBから取得したUseExampleを表示
    try:
        # eager load済みのuse_examplesにアクセス
        use_examples_list = []
        if hasattr(material, 'use_examples') and material.use_examples:
            use_examples_list = material.use_examples
        else:
            # データベースから直接取得を試みる（フォールバック）
            from database import SessionLocal, UseExample
            from utils.paths import resolve_path
            db = SessionLocal()
            try:
                use_examples_list = db.query(UseExample).filter(UseExample.material_id == material.id).all()
            finally:
                db.close()
        
        if use_examples_list:
            # domainごとにグループ化（オプション）
            from collections import defaultdict
            by_domain = defaultdict(list)
            for use_ex in use_examples_list:
                domain = getattr(use_ex, 'domain', None) or "その他"
                by_domain[domain].append(use_ex)
            
            # 各用途例を表示（画像付き）
            from utils.use_example_display import display_use_example_image
            
            for domain, examples in by_domain.items():
                if len(by_domain) > 1:
                    st.markdown(f"#### {domain}")
                
                # 用途例をグリッド表示（画像 + 情報）
                cols = st.columns(min(3, len(examples)))
                for idx, use_ex in enumerate(examples):
                    with cols[idx % 3]:
                        # 画像を表示（生成された用途写真を優先）
                        from utils.paths import resolve_path
                        image_displayed = False
                        
                        # 画像を表示（get_material_image_refを使用しない、UseExampleは別処理）
                        from utils.image_display import display_image_unified
                        if use_ex.image_path:
                            try:
                                img_path = resolve_path(use_ex.image_path)
                                if img_path.exists():
                                    display_image_unified(img_path, caption=use_ex.example_name, width=280)
                                    image_displayed = True
                            except Exception as e:
                                if os.getenv("DEBUG", "0") == "1":
                                    st.caption(f"用途写真読み込みエラー: {e}")
                        
                        # 画像がない場合は既存の表示関数を使用
                        if not image_displayed:
                            display_use_example_image(use_ex, width=280)
                        
                        # タイトル
                        st.markdown(f"**{use_ex.example_name or '用途例'}**")
                        
                        # 説明
                        if use_ex.description:
                            st.markdown(f"<p style='font-size: 0.85rem; color: #666; margin-top: 4px;'>{use_ex.description}</p>", unsafe_allow_html=True)
                        
                        # 出典情報（権利的に安全な表示）
                        source_name = getattr(use_ex, 'source_name', None)
                        source_url = getattr(use_ex, 'source_url', None)
                        license_note = getattr(use_ex, 'license_note', None)
                        
                        if source_name or source_url or license_note:
                            source_parts = []
                            if source_name:
                                if source_url:
                                    source_parts.append(f"[{source_name}]({source_url})")
                                else:
                                    source_parts.append(source_name)
                            if license_note:
                                source_parts.append(f"({license_note})")
                            
                            if source_parts:
                                st.markdown(f"<small style='color: #999;'>**出典**: {' '.join(source_parts)}</small>", unsafe_allow_html=True)
                        
                        # リンク（後方互換）
                        if use_ex.example_url:
                            st.markdown(f"<small>[詳細リンク]({use_ex.example_url})</small>", unsafe_allow_html=True)
        else:
            st.info("用途例が未登録です。")
    except Exception as e:
        # DetachedInstanceError等の例外をキャッチ（アプリを落とさない）
        import traceback
        print(f"用途例取得エラー: {e}")
        traceback.print_exc()
        st.warning("用途例の取得に失敗しました。")


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
    
    # その他動機（安全にアクセス）
    development_motive_other = getattr(material, 'development_motive_other', None)
    if development_motive_other:
        st.markdown(f"**その他動機**: {development_motive_other}")
    
    # 開発背景（短文）（安全にアクセス）
    development_background_short = getattr(material, 'development_background_short', None)
    if development_background_short:
        st.markdown("---")
        st.markdown("#### 開発背景")
        st.markdown(development_background_short)
    
    # 開発ストーリー（長文）（安全にアクセス）
    development_story = getattr(material, 'development_story', None)
    if development_story:
        st.markdown("---")
        st.markdown("#### 開発ストーリー")
        st.markdown(development_story)
    
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
        # その他触感（安全にアクセス）
        tactile_other = getattr(material, 'tactile_other', None)
        if tactile_other:
            st.markdown(f"**その他触感**: {tactile_other}")
        
        # 視覚
        if material.visual_tags:
            visual = parse_json_field(material.visual_tags)
            if visual:
                st.markdown("#### 視覚的特徴")
                for tag in visual:
                    st.markdown(f"- {tag}")
        # その他視覚（安全にアクセス）
        visual_other = getattr(material, 'visual_other', None)
        if visual_other:
            st.markdown(f"**その他視覚**: {visual_other}")
    
    with col2:
        # 音・匂い（安全にアクセス）
        sound_smell = getattr(material, 'sound_smell', None)
        if sound_smell:
            st.markdown("#### 音・匂い")
            st.markdown(sound_smell)
        
        # 経年変化（データベースに該当フィールドがない場合はスキップ）
        aging_characteristics = getattr(material, 'aging_characteristics', None)
        if aging_characteristics:
            st.markdown("#### 経年変化")
            st.markdown(aging_characteristics)
        
        # 加工性（processing_knowhowフィールドを使用）（安全にアクセス）
        processing_knowhow = getattr(material, 'processing_knowhow', None)
        if processing_knowhow:
            st.markdown("#### 加工性・加工ノウハウ")
            st.markdown(processing_knowhow)
    
    # 関連材料
    if material.related_materials:
        st.markdown("---")
        st.markdown("### 関連材料")
        related = parse_json_field(material.related_materials)
        if related:
            for rel in related:
                st.markdown(f"- {rel}")
    
    # NG用途（使われなかった可能性）
    # NG用途（安全にアクセス）
    ng_uses = getattr(material, 'ng_uses', None)
    if ng_uses:
        st.markdown("---")
        st.markdown("### 使われなかった可能性")
        ng_uses_list = parse_json_field(ng_uses)
        if ng_uses_list:
            st.markdown("#### NG用途")
            for ng in ng_uses_list:
                st.markdown(f"- {ng}")
    
    # その他NG用途（安全にアクセス）
    ng_uses_other = getattr(material, 'ng_uses_other', None)
    if ng_uses_other:
        st.markdown(f"**その他NG用途**: {ng_uses_other}")

