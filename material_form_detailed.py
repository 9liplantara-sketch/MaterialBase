"""
詳細仕様対応の材料登録フォーム
レイヤー①（必須）とレイヤー②（任意）を含む包括的なフォーム
"""
import streamlit as st
import uuid
import json
import os
import re
import inspect
import logging
from database import Material, Property, Image, MaterialMetadata, ReferenceURL, UseExample, MaterialSubmission, init_db
# Phase 2.5: SessionLocal()は使用禁止。読み取りはget_session()、書き込みはsession_scope()を使用

# ロガーを設定（Cloudで確実に追えるように）
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(name)s] %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def normalize_uploaded_files(v) -> list:
    """
    UploadedFile のリストを正規化（型揺れに強い）
    
    Args:
        v: None, 単一の UploadedFile, または list[UploadedFile]
    
    Returns:
        list[UploadedFile]: name属性を持つもののみを含むリスト
    """
    if v is None:
        return []
    items = v if isinstance(v, list) else [v]
    return [x for x in items if x is not None and getattr(x, "name", None) is not None]


# 選択肢の定義
SUPPLIER_TYPES = [
    "企業", "大学/研究機関", "スタートアップ", "個人/アーティスト",
    "産学連携/コンソーシアム", "公的機関", "その他（自由記述）", "不明"
]

MATERIAL_CATEGORIES = [
    "高分子（樹脂・エラストマー等）", "金属・合金", "セラミックス・ガラス",
    "木材・紙・セルロース系", "繊維（天然/合成）", "ゴム",
    "複合材（FRP等）", "バイオマテリアル（菌糸・発酵・生体由来）",
    "ゲル・ハイドロゲル", "多孔質（フォーム・スポンジ・エアロゲル等）",
    "コーティング・表面処理材", "インク・塗料・顔料", "粉体・粒材",
    "電子/機能材料（電池・半導体・導電材等）", "その他（自由記述）", "不明"
]

MATERIAL_FORMS = [
    "シート/板材", "フィルム", "ロッド/棒材", "粒（ペレット）", "粉末",
    "繊維/糸", "フェルト/不織布", "液体（樹脂/溶液）", "ペースト/スラリー",
    "ゲル", "フォーム/スポンジ", "ブロック/バルク",
    "3Dプリント用フィラメント", "3Dプリント用レジン", "コーティング剤",
    "その他（自由記述）", "不明"
]

ORIGIN_TYPES = [
    "化石資源由来（石油等）", "植物由来", "動物由来", "鉱物由来",
    "微生物/発酵由来", "廃材/リサイクル由来", "混合/複合由来",
    "その他（自由記述）", "不明"
]

COLOR_OPTIONS = [
    "無色", "白系", "黒系", "グレー系", "透明", "半透明",
    "着色可能（任意色）", "その他（自由記述）", "不明"
]

TRANSPARENCY_OPTIONS = ["透明", "半透明", "不透明", "不明"]

HARDNESS_OPTIONS = ["とても柔らかい", "柔らかい", "中間", "硬い", "とても硬い", "不明"]

WEIGHT_OPTIONS = ["とても軽い", "軽い", "中間", "重い", "とても重い", "不明"]

WATER_RESISTANCE_OPTIONS = ["高い（屋外・水回りOK）", "中（条件付き）", "低い（水に弱い）", "不明"]

HEAT_RANGE_OPTIONS = ["低温域（〜60℃）", "中温域（60〜120℃）", "高温域（120℃〜）", "不明"]

WEATHER_RESISTANCE_OPTIONS = ["高い", "中", "低い", "不明"]

PROCESSING_METHODS = [
    "切削", "レーザー加工", "熱成形", "射出成形", "圧縮成形",
    "3Dプリント（FDM）", "3Dプリント（SLA/DLP）", "3Dプリント（SLS等粉体系）",
    "接着", "溶着/熱溶着", "縫製/編み", "積層/ラミネート",
    "塗装/コーティング", "焼成", "発泡", "鋳造", "その他（自由記述）", "不明"
]

EQUIPMENT_LEVELS = [
    "家庭/工房レベル", "ファブ施設レベル（FabLab等）",
    "工場設備が必要", "研究設備が必要", "不明"
]

DIFFICULTY_OPTIONS = ["低", "中", "高", "不明"]

USE_CATEGORIES = [
    "建築・内装", "家具", "生活用品/雑貨", "家電/機器筐体",
    "パッケージ/包装", "繊維/アパレル", "医療/ヘルスケア", "食品関連",
    "モビリティ", "エネルギー/電気電子", "教育/ホビー",
    "アート/展示", "その他（自由記述）", "不明",
    "産業設備・プラント",
    "インフラ・土木",
    "エネルギー（発電・蓄電・配電）",
    "防災・安全",
    "輸送・モビリティ",
    "海洋・港湾",
    "極環境",
    "研究・実験",
    "その他専門領域"
]

USE_ENVIRONMENT_OPTIONS = [
    "屋内", "屋外", "高温", "低温", "薬品", "塩害", "摩耗",
    "紫外線", "湿気", "乾燥", "振動", "衝撃", "圧力", "真空",
    "放射線", "電磁波", "静電気", "その他（自由記述）", "不明"
]

PROCUREMENT_OPTIONS = [
    "一般購入可", "法人のみ", "サンプル提供のみ",
    "共同研究/契約が必要", "入手困難", "不明"
]

COST_LEVELS = ["低", "中", "高", "変動大", "非公開", "不明"]

SAFETY_TAGS = [
    "食品接触OK", "食品接触不可", "皮膚接触OK", "皮膚接触注意",
    "揮発/臭気注意", "粉塵注意", "可燃性注意", "毒性/有害性懸念",
    "規制対象（要確認）", "不明", "その他（自由記述）"
]

VISIBILITY_OPTIONS = ["公開（誰でも閲覧可）", "限定公開（ログインユーザーのみ）", "非公開（登録者/管理者のみ）", "不明"]


# 必須フィールドのデフォルト値
REQUIRED_DEFAULTS = {
    "prototyping_difficulty": "中",
    "equipment_level": "家庭/工房レベル",
    "visibility": "公開（誰でも閲覧可）",
    "is_published": 1,
}


def _normalize_required(form_data: dict, existing=None) -> dict:
    """
    必須フィールドの補完（None/空文字列をデフォルト値で埋める）
    更新時は、既存値が埋まっているなら None/空文字で上書きしない
    """
    d = dict(form_data)

    for key, default in REQUIRED_DEFAULTS.items():
        v = d.get(key)

        # 未入力(None / 空文字)なら補完対象
        if v is None or (isinstance(v, str) and v.strip() == ""):
            # 更新時: 既存値が埋まっていれば維持（上書きしない）
            if existing is not None:
                cur = getattr(existing, key, None)
                if cur is not None:
                    if isinstance(cur, str):
                        if cur.strip() != "":
                            d.pop(key, None)
                            continue
                    else:
                        # int/float/bool などは None でなければ有効（0もOK）
                        d.pop(key, None)
                        continue

            # 新規 or 既存も空ならデフォルトを入れる
            d[key] = default

    if os.getenv("DEBUG", "0") == "1":
        print(f"[DEBUG] _normalize_required: {d}")

    return d


def show_detailed_material_form(material_id: int = None):
    """
    詳細仕様対応の材料登録フォーム（新規登録・編集対応）
    
    Args:
        material_id: 編集モードの場合、既存材料のID
    """
    # 編集モードかどうか判定
    is_edit_mode = material_id is not None
    existing_material = None
    existing_data = {}  # session 内で dict に変換したデータを保存
    
    # material_id が変更されたらフォーム関連stateを掃除
    prev = st.session_state.get("active_edit_material_id")
    if is_edit_mode and material_id and prev and prev != material_id:
        # このフォームで使うキーだけを削除（雑に全部消さない）
        for k in list(st.session_state.keys()):
            if k.endswith(f"_{prev}") and (
                k.startswith("name_") or k.startswith("description_") or k.startswith("images_") or
                k.startswith("existing_images_") or k.startswith("reference_urls_") or k.startswith("use_examples_") or
                k.startswith("approval_") or k.startswith("editor_")
            ):
                del st.session_state[k]
    st.session_state["active_edit_material_id"] = material_id
    
    if is_edit_mode:
        # 編集モード：既存材料を取得（eager load でリレーションを事前ロード）
        from utils.db import get_session
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        
        with get_session() as db:
            # selectinload で必要なリレーションを事前ロード
            stmt = (
                select(Material)
                .where(Material.id == material_id)
                .options(
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.images),
                )
            )
            existing_material = db.execute(stmt).scalar_one_or_none()
            
            if not existing_material:
                st.error(f"❌ 材料ID {material_id} が見つかりません")
                return
            
            st.markdown('<h2 class="gradient-text">✏️ 材料編集</h2>', unsafe_allow_html=True)
            st.info(f"📝 **編集対象**: {existing_material.name_official}")
            
            # session を閉じる前に、必要なリレーションにアクセスして dict に変換（DetachedInstanceError 防止）
            # ここでアクセスすることで、リレーションが確実にロードされる
            reference_urls_list = list(existing_material.reference_urls or [])
            use_examples_list = list(existing_material.use_examples or [])
            images_list = list(existing_material.images or [])
            
            # session 内で dict に変換して保存（session を閉じた後でもアクセス可能にする）
            existing_data = {
                'reference_urls': [
                    {'url': ref.url, 'type': ref.url_type, 'desc': ref.description}
                    for ref in reference_urls_list
                ],
                'use_examples': [
                    {'name': ex.example_name, 'url': ex.example_url, 'desc': ex.description}
                    for ex in use_examples_list
                ],
            }
            # get_session()が自動でcloseするため、finallyは不要
            # existing_material は detached になるが、必要なデータは既に dict に変換済み
            
            # st.session_state に既存値を設定（既に値がある場合は上書きしない）
            def seed(key, value):
                if key not in st.session_state:
                    st.session_state[key] = value
            
            # 主要フィールドを session_state に設定
            seed(f"name_official_cached", getattr(existing_material, 'name_official', '') or "")
            seed(f"supplier_org_{material_id}", getattr(existing_material, 'supplier_org', '') or "")
            seed(f"supplier_type_{material_id}", getattr(existing_material, 'supplier_type', '') or "")
            seed(f"supplier_other_{material_id}", getattr(existing_material, 'supplier_other', '') or "")
            seed(f"category_main_{material_id}", getattr(existing_material, 'category_main', '') or "")
            seed(f"category_other_{material_id}", getattr(existing_material, 'category_other', '') or "")
            seed(f"material_forms_other_{material_id}", getattr(existing_material, 'material_forms_other', '') or "")
            seed(f"origin_type_{material_id}", getattr(existing_material, 'origin_type', '') or "")
            seed(f"origin_other_{material_id}", getattr(existing_material, 'origin_other', '') or "")
            seed(f"origin_detail_{material_id}", getattr(existing_material, 'origin_detail', '') or "")
            seed(f"recycle_bio_rate_{material_id}", getattr(existing_material, 'recycle_bio_rate', None))
            seed(f"recycle_bio_basis_{material_id}", getattr(existing_material, 'recycle_bio_basis', '') or "")
            seed(f"transparency_{material_id}", getattr(existing_material, 'transparency', '') or "")
            seed(f"hardness_qualitative_{material_id}", getattr(existing_material, 'hardness_qualitative', '') or "")
            seed(f"hardness_value_{material_id}", getattr(existing_material, 'hardness_value', None))
            seed(f"weight_qualitative_{material_id}", getattr(existing_material, 'weight_qualitative', '') or "")
            seed(f"specific_gravity_{material_id}", getattr(existing_material, 'specific_gravity', None))
            seed(f"water_resistance_{material_id}", getattr(existing_material, 'water_resistance', '') or "")
            seed(f"heat_resistance_temp_{material_id}", getattr(existing_material, 'heat_resistance_temp', None))
            seed(f"heat_resistance_range_{material_id}", getattr(existing_material, 'heat_resistance_range', '') or "")
            seed(f"weather_resistance_{material_id}", getattr(existing_material, 'weather_resistance', '') or "")
            seed(f"processing_other_{material_id}", getattr(existing_material, 'processing_other', '') or "")
            seed(f"equipment_level_{material_id}", getattr(existing_material, 'equipment_level', '') or "")
            seed(f"prototyping_difficulty_{material_id}", getattr(existing_material, 'prototyping_difficulty', '') or "")
            seed(f"use_other_{material_id}", getattr(existing_material, 'use_other', '') or "")
            seed(f"procurement_status_{material_id}", getattr(existing_material, 'procurement_status', '') or "")
            seed(f"cost_level_{material_id}", getattr(existing_material, 'cost_level', '') or "")
            seed(f"cost_value_{material_id}", getattr(existing_material, 'cost_value', None))
            seed(f"cost_unit_{material_id}", getattr(existing_material, 'cost_unit', '') or "")
            seed(f"safety_other_{material_id}", getattr(existing_material, 'safety_other', '') or "")
            seed(f"restrictions_{material_id}", getattr(existing_material, 'restrictions', '') or "")
            seed(f"visibility_{material_id}", getattr(existing_material, 'visibility', '') or "")
            seed(f"is_published_{material_id}", getattr(existing_material, 'is_published', 1))
            
            # JSON配列フィールド
            name_aliases = json.loads(getattr(existing_material, 'name_aliases', '[]')) if getattr(existing_material, 'name_aliases', None) else []
            seed("aliases", name_aliases)
            
            material_forms = json.loads(getattr(existing_material, 'material_forms', '[]')) if getattr(existing_material, 'material_forms', None) else []
            seed(f"material_forms_{material_id}", material_forms)
            
            color_tags = json.loads(getattr(existing_material, 'color_tags', '[]')) if getattr(existing_material, 'color_tags', None) else []
            seed(f"color_tags_{material_id}", color_tags)
            
            processing_methods = json.loads(getattr(existing_material, 'processing_methods', '[]')) if getattr(existing_material, 'processing_methods', None) else []
            seed(f"processing_methods_{material_id}", processing_methods)
            
            use_categories = json.loads(getattr(existing_material, 'use_categories', '[]')) if getattr(existing_material, 'use_categories', None) else []
            seed(f"use_categories_{material_id}", use_categories)
            
            safety_tags = json.loads(getattr(existing_material, 'safety_tags', '[]')) if getattr(existing_material, 'safety_tags', None) else []
            seed(f"safety_tags_{material_id}", safety_tags)
            
            # リレーション
            seed("ref_urls", existing_data.get('reference_urls', []))
            seed("use_examples", existing_data.get('use_examples', []))
            
            # 画像（既存画像一覧を表示用に保存）
            seed(f"existing_images_{material_id}", [
                {'kind': img.kind, 'public_url': img.public_url, 'r2_key': img.r2_key}
                for img in images_list
            ])
    else:
        st.markdown('<h2 class="gradient-text">➕ 材料登録（詳細版）</h2>', unsafe_allow_html=True)
        st.info("📝 **レイヤー①（必須）**: 約10分で入力可能な基本情報\n\n**レイヤー②（任意）**: 後から追記できる詳細情報")
        
        # 一括登録モードのチェック
        if st.session_state.get('bulk_import_mode', False):
            # 一括登録UIを表示
            from app import show_bulk_import
            show_bulk_import(embedded=True)
            return
    
    # 一括登録ボタン（編集モードでない場合のみ表示）
    if not existing_material:
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("📦 材料一括登録", key="bulk_import_button", use_container_width=True):
                st.session_state.bulk_import_mode = True
                st.rerun()
    
    # 編集モードの場合は既存値をform_dataに初期化
    if existing_material:
        # 既存値からform_dataを初期化（主要フィールドのみ）
        # existing_material は detached になる可能性があるため、スカラー属性のみを使用
        form_data = {
            'name_official': getattr(existing_material, 'name_official', ''),
            'name_aliases': json.loads(getattr(existing_material, 'name_aliases', '[]')) if getattr(existing_material, 'name_aliases', None) else [],
            'supplier_org': getattr(existing_material, 'supplier_org', ''),
            'supplier_type': getattr(existing_material, 'supplier_type', ''),
            'supplier_other': getattr(existing_material, 'supplier_other', ''),
            'category_main': getattr(existing_material, 'category_main', ''),
            'category_other': getattr(existing_material, 'category_other', ''),
            'material_forms': json.loads(getattr(existing_material, 'material_forms', '[]')) if getattr(existing_material, 'material_forms', None) else [],
            'material_forms_other': getattr(existing_material, 'material_forms_other', ''),
            'origin_type': getattr(existing_material, 'origin_type', ''),
            'origin_other': getattr(existing_material, 'origin_other', ''),
            'origin_detail': getattr(existing_material, 'origin_detail', ''),
            'recycle_bio_rate': getattr(existing_material, 'recycle_bio_rate', None),
            'recycle_bio_basis': getattr(existing_material, 'recycle_bio_basis', ''),
            'color_tags': json.loads(getattr(existing_material, 'color_tags', '[]')) if getattr(existing_material, 'color_tags', None) else [],
            'transparency': getattr(existing_material, 'transparency', ''),
            'hardness_qualitative': getattr(existing_material, 'hardness_qualitative', ''),
            'hardness_value': getattr(existing_material, 'hardness_value', ''),
            'weight_qualitative': getattr(existing_material, 'weight_qualitative', ''),
            'specific_gravity': getattr(existing_material, 'specific_gravity', None),
            'water_resistance': getattr(existing_material, 'water_resistance', ''),
            'heat_resistance_temp': getattr(existing_material, 'heat_resistance_temp', None),
            'heat_resistance_range': getattr(existing_material, 'heat_resistance_range', ''),
            'weather_resistance': getattr(existing_material, 'weather_resistance', ''),
            'processing_methods': json.loads(getattr(existing_material, 'processing_methods', '[]')) if getattr(existing_material, 'processing_methods', None) else [],
            'processing_other': getattr(existing_material, 'processing_other', ''),
            'equipment_level': getattr(existing_material, 'equipment_level', ''),
            'prototyping_difficulty': getattr(existing_material, 'prototyping_difficulty', ''),
            # 'use_environment': json.loads(getattr(existing_material, 'use_environment', '[]')) if getattr(existing_material, 'use_environment', None) else [],  # 一時的にコメントアウト（DBにカラムが存在しない）
            'use_categories': json.loads(getattr(existing_material, 'use_categories', '[]')) if getattr(existing_material, 'use_categories', None) else [],
            'use_other': getattr(existing_material, 'use_other', ''),
            'procurement_status': getattr(existing_material, 'procurement_status', ''),
            'cost_level': getattr(existing_material, 'cost_level', ''),
            'cost_value': getattr(existing_material, 'cost_value', None),
            'cost_unit': getattr(existing_material, 'cost_unit', ''),
            'safety_tags': json.loads(getattr(existing_material, 'safety_tags', '[]')) if getattr(existing_material, 'safety_tags', None) else [],
            'safety_other': getattr(existing_material, 'safety_other', ''),
            'restrictions': getattr(existing_material, 'restrictions', ''),
            'visibility': getattr(existing_material, 'visibility', ''),
            'is_published': getattr(existing_material, 'is_published', 1),
        }
        # 参照URLと使用例は session 内で dict に変換済み（DetachedInstanceError 防止）
        form_data['reference_urls'] = existing_data.get('reference_urls', [])
        form_data['use_examples'] = existing_data.get('use_examples', [])
    else:
        form_data = {}
    
    # 材料名（正式）を st.form の外に配置して、submit時に値が消えないようにする
    NAME_KEY = "name_official_input"
    NAME_CACHE = "name_official_cached"
    
    st.markdown("### 1. 基本識別情報")
    col1, col2 = st.columns(2)
    with col1:
        # default_name は分岐OK（input自体は分岐させない）
        default_name = ""
        if existing_material:
            default_name = (getattr(existing_material, "name_official", "") or "").strip()
        else:
            default_name = (st.session_state.get(NAME_CACHE, "") or "").strip()
        
        # ★ text_input は必ず毎回呼ぶ
        name_val = st.text_input(
            "1-1 材料名（正式）*",
            value=default_name,
            key=NAME_KEY,
            help="材料の正式名称を入力してください",
        )
        
        # ★ 空でキャッシュを上書きしない
        if name_val and name_val.strip():
            st.session_state[NAME_CACHE] = name_val.strip()
        elif NAME_CACHE not in st.session_state:
            st.session_state[NAME_CACHE] = ""
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("材料IDは自動採番されます")
    
    # 画像アップロード（st.form の外に配置して、submit時に値が消えないようにする）
    PRIMARY_KEY = "primary_image"
    CACHE_KEY = "primary_image_cached"
    
    st.markdown("**1-5 画像（材料/サンプル/用途例）**")
    
    if is_edit_mode:
        # 編集モード：既存画像を表示
        existing_images = st.session_state.get(f"existing_images_{material_id}", [])
        
        if existing_images:
            st.markdown("**既存画像:**")
            for idx, img_info in enumerate(existing_images):
                if isinstance(img_info, dict):
                    kind = img_info.get('kind', 'primary')
                    public_url = img_info.get('public_url')
                    r2_key = img_info.get('r2_key')
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if public_url:
                            st.image(public_url, caption=f"{kind}画像", use_container_width=True)
                            st.markdown(f"URL: {public_url}")
                        elif r2_key:
                            st.write(f"**{kind}画像**: {r2_key}")
                        else:
                            st.write(f"**{kind}画像**: 情報なし")
                    with col2:
                        delete_key = f"delete_image_{material_id}_{idx}"
                        if st.checkbox("削除", key=delete_key, help="チェックして保存すると削除されます"):
                            # 削除フラグを session_state に保存
                            if f"deleted_images_{material_id}" not in st.session_state:
                                st.session_state[f"deleted_images_{material_id}"] = []
                            if idx not in st.session_state[f"deleted_images_{material_id}"]:
                                st.session_state[f"deleted_images_{material_id}"].append(idx)
            st.info("💡 既存画像は維持されます。新しい画像をアップロードする場合は下記から追加してください。")
        else:
            st.info("ℹ️ 既存画像はありません。")
        
        # 新規アップロード（任意）
        uploaded_files = st.file_uploader(
            "新しい画像をアップロード（任意・複数可）",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True,
            key=f"images_upload_{material_id}",
            help="既存画像に追加する新しい画像をアップロードできます（空でも既存画像が維持されます）"
        )
    else:
        # 新規作成モード：通常のアップロード
        uploaded_files = st.file_uploader(
            "画像をアップロード（複数可）",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True,
            key=PRIMARY_KEY,
            help="ドラッグ&ドロップで複数ファイルをアップロードできます"
        )
    
    # session_state にキャッシュ（submit時に値が消えないように）
    if uploaded_files:
        st.session_state[CACHE_KEY] = uploaded_files
    elif CACHE_KEY not in st.session_state:
        st.session_state[CACHE_KEY] = []
    
    # フォーム全体を st.form で囲む
    with st.form("material_form", clear_on_submit=False):
        # タブでレイヤー①とレイヤー②を分ける
        tab1, tab2 = st.tabs(["📋 レイヤー①：必須情報", "✨ レイヤー②：任意情報"])
        
        with tab1:
            layer1_data = show_layer1_form(existing_material=existing_material)
            if layer1_data:
                # name_official/name が混ざるなら除去して上書きを防ぐ
                layer1_data.pop("name_official", None)
                layer1_data.pop("name", None)
                form_data.update(layer1_data)
        
        with tab2:
            # show_layer2_form のシグネチャを実行時に確認して互換呼び出しに切り替える
            def _call_layer2(existing_material):
                """show_layer2_form を実行時にチェックして呼び出す互換性シム"""
                try:
                    sig = inspect.signature(show_layer2_form)
                    params = sig.parameters
                    
                    if "existing_material" in params:
                        # existing_material パラメータが存在する場合
                        return show_layer2_form(existing_material=existing_material)
                    else:
                        # existing_material パラメータが存在しない場合（古い実装）
                        if os.getenv("DEBUG", "0") == "1":
                            st.warning("⚠️ show_layer2_form が existing_material パラメータを受け取りません（古い実装）")
                            st.json({
                                "show_layer2_form.module": getattr(show_layer2_form, "__module__", None),
                                "show_layer2_form.file": inspect.getsourcefile(show_layer2_form),
                                "show_layer2_form.signature": str(sig),
                                "has_existing_material": False,
                                "parameters": list(params.keys()),
                            })
                        return show_layer2_form()
                except TypeError as e:
                    # 念のため最終フォールバック（古い関数でも落ちない）
                    if os.getenv("DEBUG", "0") == "1":
                        try:
                            sig = inspect.signature(show_layer2_form)
                            params = sig.parameters
                            st.error(f"⚠️ Layer2呼び出しでTypeError: {e}")
                            st.json({
                                "show_layer2_form.module": getattr(show_layer2_form, "__module__", None),
                                "show_layer2_form.file": inspect.getsourcefile(show_layer2_form),
                                "show_layer2_form.signature": str(sig),
                                "has_existing_material": "existing_material" in params,
                                "parameters": list(params.keys()),
                                "error": str(e),
                            })
                        except Exception as diag_error:
                            st.error(f"⚠️ Layer2呼び出しでTypeError: {e}（診断情報の取得も失敗: {diag_error}）")
                    # フォールバック: existing_material なしで呼び出す
                    try:
                        return show_layer2_form()
                    except Exception as fallback_error:
                        # それでも失敗する場合は空のdictを返す（クラッシュを防ぐ）
                        if os.getenv("DEBUG", "0") == "1":
                            st.error(f"⚠️ show_layer2_form() の呼び出しに失敗しました: {fallback_error}")
                        return {}
                except Exception as e:
                    # その他の予期しない例外
                    if os.getenv("DEBUG", "0") == "1":
                        st.error(f"⚠️ show_layer2_form の呼び出しで予期しないエラー: {e}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")
                    return {}
            
            layer2_data = _call_layer2(existing_material)
            if layer2_data:
                # name_official/name が混ざるなら除去して上書きを防ぐ
                layer2_data.pop("name_official", None)
                layer2_data.pop("name", None)
                form_data.update(layer2_data)
        
        # 掲載可否の設定
        st.markdown("---")
        st.markdown("### 📢 掲載設定")
        # 編集モードの場合は既存値を初期値に
        default_published_index = 0
        if existing_material:
            default_published_index = 0 if getattr(existing_material, 'is_published', 1) == 1 else 1
        is_published = st.radio(
            "掲載:",
            ["公開", "非公開"],
            index=default_published_index,  # デフォルトは公開（編集時は既存値）
            horizontal=True,
            key=f"is_published_{material_id if material_id else 'new'}"
        )
        form_data['is_published'] = 1 if is_published == "公開" else 0
        
        # 管理者モードかどうかを判定
        is_admin = os.getenv("DEBUG", "0") == "1" or os.getenv("ADMIN", "0") == "1"
        
        # 投稿者情報（一般ユーザー用、任意）
        submitted_by = None
        if not is_admin and not is_edit_mode:
            st.markdown("---")
            st.markdown("### 📝 投稿者情報（任意）")
            submitted_by = st.text_input(
                "ニックネーム / メールアドレス（任意）",
                key=f"submitted_by_{material_id if material_id else 'new'}",
                help="承認連絡が必要な場合に使用します（任意入力）"
            )
            if submitted_by and submitted_by.strip() == "":
                submitted_by = None
        
        # フォーム送信ボタン
        submitted = False
        if is_edit_mode or is_admin:
            # 管理者モードまたは編集モード：直接materialsに保存
            button_text = "✅ 材料を更新" if is_edit_mode else "✅ 材料を登録"
            submitted = st.form_submit_button(button_text, type="primary", use_container_width=True)
        else:
            # 一般ユーザーモード：submissionsに保存
            submitted = st.form_submit_button("📤 投稿を送信（承認待ち）", type="primary", use_container_width=True)
    
    # submitted 時は、必ず st.session_state から画像を取得（rerunで消えるのを防ぐ）
    if submitted:
        # 通称の削除/追加処理（submitted 時に実行）
        if '_alias_del_flags' in form_data:
            # 削除フラグが True のものを除外
            aliases_filtered = []
            for i, alias in enumerate(form_data.get('name_aliases', [])):
                if not form_data['_alias_del_flags'].get(i, False):
                    aliases_filtered.append(alias)
            form_data['name_aliases'] = aliases_filtered
            
            # 新しい通称を追加（重複チェック）
            new_alias = form_data.get('_new_alias', '').strip()
            if new_alias and new_alias not in form_data['name_aliases']:
                form_data['name_aliases'].append(new_alias)
            
            # 一時的なキーを削除
            form_data.pop('_alias_del_flags', None)
            form_data.pop('_new_alias', None)
        
        # 参照URLの削除/追加処理（同様）
        if '_ref_del_flags' in form_data:
            ref_urls_filtered = []
            for i, ref in enumerate(form_data.get('reference_urls', [])):
                if not form_data['_ref_del_flags'].get(i, False):
                    ref_urls_filtered.append(ref)
            form_data['reference_urls'] = ref_urls_filtered
            form_data.pop('_ref_del_flags', None)
        
        # 使用例の削除/追加処理（同様）
        if '_ex_del_flags' in form_data:
            use_examples_filtered = []
            for i, ex in enumerate(form_data.get('use_examples', [])):
                if not form_data['_ex_del_flags'].get(i, False):
                    use_examples_filtered.append(ex)
            form_data['use_examples'] = use_examples_filtered
            form_data.pop('_ex_del_flags', None)
        
        # 参照URLの追加処理
        if '_new_ref_url' in form_data and form_data['_new_ref_url']:
            new_ref = {
                "url": form_data['_new_ref_url'],
                "type": form_data.get('_new_ref_type', ''),
                "desc": form_data.get('_new_ref_desc', '')
            }
            if new_ref['url'] not in [r.get('url', '') for r in form_data.get('reference_urls', [])]:
                form_data['reference_urls'].append(new_ref)
            form_data.pop('_new_ref_url', None)
            form_data.pop('_new_ref_type', None)
            form_data.pop('_new_ref_desc', None)
        
        # 使用例の追加処理
        if '_new_ex_name' in form_data and form_data['_new_ex_name']:
            new_ex = {
                "name": form_data['_new_ex_name'],
                "url": form_data.get('_new_ex_url', ''),
                "desc": form_data.get('_new_ex_desc', '')
            }
            if new_ex['name'] not in [e.get('name', '') for e in form_data.get('use_examples', [])]:
                form_data['use_examples'].append(new_ex)
            form_data.pop('_new_ex_name', None)
            form_data.pop('_new_ex_url', None)
            form_data.pop('_new_ex_desc', None)
        
        # name_official を session_state のキャッシュから取得（submit時に確実に保持される）
        NAME_CACHE = "name_official_cached"
        name_official = st.session_state.get(NAME_CACHE, "").strip()
        name_official_raw = st.session_state.get("name_official_input", "")
        
        # ログ出力（送信時の値を確認）
        logger.info(f"[FORM] name_official_cached='{name_official}'")
        logger.info(f"[FORM] name_official_raw='{name_official_raw}'")
        
        # DEBUG=1 のときは UI にも表示
        if os.getenv("DEBUG", "0") == "1":
            st.info(f"🧾 材料名（送信値）: {name_official or '(EMPTY)'}")
        
        # form_data の name_official を設定（確実に取得）
        form_data['name_official'] = name_official
        
        # 画像を session_state のキャッシュから取得（submit時に確実に保持される）
        CACHE_KEY = "primary_image_cached"
        cached_files = st.session_state.get(CACHE_KEY, [])
        uploaded_files = normalize_uploaded_files(cached_files)
        
        # 編集モード時の既存画像処理
        if is_edit_mode and material_id:
            # 既存画像を維持するフラグを設定
            form_data['keep_existing_images'] = True
            
            # 削除フラグを取得
            deleted_indices = st.session_state.get(f"deleted_images_{material_id}", [])
            if deleted_indices:
                form_data['deleted_image_indices'] = deleted_indices
        
        # 画像枚数をログ出力
        cached_image_count = len(uploaded_files)
        logger.info(f"[MATERIAL FORM] cached_image_count={cached_image_count}, is_edit_mode={is_edit_mode}")
        
        # DEBUG=1 のときは UI にも表示
        if os.getenv("DEBUG", "0") == "1":
            st.info(f"📸 キャッシュ画像: {cached_image_count} 枚")
            for idx, img in enumerate(uploaded_files):
                if hasattr(img, 'name'):
                    logger.info(f"[MATERIAL FORM] Cached image {idx+1}: {img.name}")
        
        # form_data の images を設定（確実に取得）
        # 編集モードで新規アップロードが空の場合は None を設定（既存画像を維持）
        if is_edit_mode and material_id and not uploaded_files:
            form_data['images'] = None  # 既存画像を維持
        else:
            form_data['images'] = uploaded_files
        
        # 画像枚数をログ出力
        image_count = len(form_data.get('images', [])) if form_data.get('images') else 0
        logger.info(f"[MATERIAL FORM] Submitted: image_count={image_count}, is_edit_mode={is_edit_mode}")
        if image_count > 0:
            st.info(f"📸 選択された画像: {image_count} 枚")
            for idx, img in enumerate(form_data['images']):
                if hasattr(img, 'name'):
                    logger.info(f"[MATERIAL FORM] Image {idx+1}: {img.name}")
        else:
            if is_edit_mode:
                st.info("ℹ️ 新しい画像はアップロードされませんでした（既存画像が維持されます）")
            else:
                st.info("ℹ️ 画像は選択されていません")
            logger.info(f"[MATERIAL FORM] No images selected (is_edit_mode={is_edit_mode})")
        
        # 最後の最後に name_official をキャッシュから確実に採用（上書きを防ぐ）
        NAME_CACHE = "name_official_cached"
        NAME_INPUT_KEY = "name_official_input"
        name_official_final = st.session_state.get(NAME_CACHE, "").strip()
        name_official_raw = st.session_state.get(NAME_INPUT_KEY, "")
        
        form_data["name_official"] = name_official_final
        form_data["name"] = name_official_final  # 画面表示の安定化
        
        # save_material_submission() の直前に "最終値" をログに出す（DEBUG=0でも1行出す）
        logger.info(f"[SUBMIT] final name_official='{form_data.get('name_official')}' raw='{name_official_raw}' cached='{st.session_state.get(NAME_CACHE, '')}'")
        
        # フォーム送信処理
        if is_edit_mode or is_admin:
            # 管理者モードまたは編集モード：直接materialsに保存
            result = save_material(form_data)
            
            # 防御的にresult.get("ok")で分岐
            if result.get("ok"):
                # 成功時：result["action"]でcreated/updatedを判定してメッセージ表示
                if result.get("action") == 'created':
                    st.success("✅ 材料を新規登録しました！")
                else:
                    st.success("✅ 材料を更新しました！")
                    # 編集モードの場合は編集完了フラグを設定
                    if is_edit_mode:
                        st.session_state.edit_completed = True
                        # 編集ページから一覧に戻る（フォーム外なので st.button を使用可能）
                        if st.button("← 一覧に戻る", key="back_after_edit"):
                            st.session_state.edit_material_id = None
                            st.session_state.page = "材料一覧"
                            st.rerun()
            else:
                # 失敗時：st.error(result["error"])とst.expanderでtraceback表示
                error_msg = result.get('error', '不明なエラー')
                st.error(f"❌ エラーが発生しました: {error_msg}")
                # name_official が空の場合は特別なメッセージを表示
                if result.get("error_code") == "name_official_empty":
                    st.info("💡 材料名（正式）を入力してから再度送信してください。")
                if result.get("traceback"):
                    with st.expander("🔍 エラー詳細（デバッグ用）", expanded=False):
                        st.code(result["traceback"], language="python")
    else:
        # 一般ユーザーモード：submissionsに保存
        if form_data and st.button("📤 投稿を送信（承認待ち）", type="primary", use_container_width=True):
            # save_material_submission() を呼ぶ "直前" に必ずこれを実行
            NAME_CACHE = "name_official_cached"
            NAME_INPUT_KEY = "name_official_input"
            name = st.session_state.get(NAME_CACHE, "").strip()
            form_data["name_official"] = name
            form_data["name"] = name
            
            # その直後に、空なら必ず return（INSERTしない）
            if not form_data["name_official"]:
                st.error("❌ 材料名（正式）が空です。送信できません。")
                logger.warning(f"[SUBMIT] blocked: name_official empty, raw='{st.session_state.get(NAME_INPUT_KEY, '')}' cached='{st.session_state.get(NAME_CACHE, '')}'")
                return
            
            # その場でログに必ず出す（DEBUG=0でも1行は残す）
            logger.info(f"[SUBMIT] final name_official='{form_data['name_official']}' raw='{st.session_state.get(NAME_INPUT_KEY, '')}' cached='{st.session_state.get(NAME_CACHE, '')}'")
            
            result = save_material_submission(form_data, submitted_by=submitted_by)
            
            # 防御的にresult.get("ok")で分岐
            if result.get("ok"):
                submission_id = result.get("submission_id")
                submission_uuid = result.get("uuid")
                uploaded_images = result.get("uploaded_images", [])
                
                st.success("✅ 投稿を送信しました！管理者の承認をお待ちください。")
                st.info("📝 承認後、材料一覧に表示されます。")
                st.markdown("---")
                st.markdown("### 📋 投稿控え")
                st.code(f"投稿ID: {submission_id}\nUUID: {submission_uuid}", language="text")
                st.info("💡 このIDを控えておくと、後で投稿ステータスを確認できます。")
                
                # アップロードされた画像のプレビュー
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
            else:
                # 失敗時：st.error(result["error"])とst.expanderでtraceback表示
                error_msg = result.get('error', '不明なエラー')
                st.error(f"❌ エラーが発生しました: {error_msg}")
                # name_official が空の場合は特別なメッセージを表示
                if result.get("error_code") == "name_official_empty":
                    st.info("💡 材料名（正式）を入力してから再度送信してください。")
                if result.get("traceback"):
                    with st.expander("🔍 エラー詳細（デバッグ用）", expanded=False):
                        st.code(result["traceback"], language="python")


def show_layer1_form(existing_material=None):
    """
    レイヤー①：必須情報フォーム
    
    Args:
        existing_material: 編集モードの場合、既存のMaterialオブジェクト
    """
    form_data = {}
    
    # name_official は st.form の外で処理されるため、ここでは何もしない
    # （show_detailed_material_form で form_data に設定済み）
    
    # 材料名（通称・略称）複数（st.form内で完結）
    st.markdown("**1-2 材料名（通称・略称）**")
    
    # session_state の初期化（初回のみ）
    if 'aliases' not in st.session_state:
        if existing_material:
            # 編集モード：既存値を初期化
            existing_aliases = getattr(existing_material, 'name_aliases', None)
            if existing_aliases:
                try:
                    import json
                    st.session_state.aliases = json.loads(existing_aliases) if isinstance(existing_aliases, str) else existing_aliases
                except:
                    st.session_state.aliases = [""]
            else:
                st.session_state.aliases = [""]
        else:
            st.session_state.aliases = [""]
    
    # 既存の通称を表示（削除チェックボックス付き）
    aliases = []
    for i, alias in enumerate(st.session_state.aliases):
        col1, col2 = st.columns([5, 1])
        with col1:
            alias_val = st.text_input(f"通称 {i+1}", value=alias, key=f"alias_{i}")
            if alias_val:
                aliases.append(alias_val)
        with col2:
            # 削除チェックボックス（フォーム内で使用可能）
            del_flag = st.checkbox("削除", key=f"del_alias_{i}", help="チェックして保存すると削除されます")
            if del_flag:
                # チェックされたものは除外（送信時に処理）
                pass
    
    # 追加する通称の入力
    new_alias = st.text_input("➕ 追加する通称（入力して保存すると追加されます）", key="new_alias", placeholder="新しい通称を入力")
    
    # 送信時に処理（ここでは form_data に反映するだけ）
    # 実際の削除/追加処理は submitted 時に実行
    form_data['name_aliases'] = [a for a in aliases if a]
    form_data['_alias_del_flags'] = {i: st.session_state.get(f"del_alias_{i}", False) for i in range(len(st.session_state.aliases))}
    form_data['_new_alias'] = new_alias.strip() if new_alias else ""
    
    # 供給元・開発主体
    st.markdown("**1-3 供給元・開発主体***")
    col1, col2 = st.columns([2, 1])
    with col1:
        # 編集モードの場合は既存値を初期値に
        default_supplier_org = getattr(existing_material, 'supplier_org', '') if existing_material else ''
        form_data['supplier_org'] = st.text_input("組織名*", value=default_supplier_org, key=f"supplier_org_{existing_material.id if existing_material else 'new'}")
    with col2:
        # 編集モードの場合は既存値を初期値に
        default_supplier_type = getattr(existing_material, 'supplier_type', SUPPLIER_TYPES[0]) if existing_material else SUPPLIER_TYPES[0]
        supplier_type_index = SUPPLIER_TYPES.index(default_supplier_type) if default_supplier_type in SUPPLIER_TYPES else 0
        form_data['supplier_type'] = st.selectbox("種別*", SUPPLIER_TYPES, index=supplier_type_index, key=f"supplier_type_{existing_material.id if existing_material else 'new'}")
        if form_data['supplier_type'] == "その他（自由記述）":
            default_supplier_other = getattr(existing_material, 'supplier_other', '') if existing_material else ''
            form_data['supplier_other'] = st.text_input("その他（詳細）", value=default_supplier_other, key=f"supplier_other_{existing_material.id if existing_material else 'new'}")
    
    # 参照URL（複数）（st.form内で完結）
    st.markdown("**1-4 参照URL（公式/製品/論文/プレス等）**")
    
    # session_state の初期化（初回のみ）
    if 'ref_urls' not in st.session_state:
        if existing_material and form_data.get('reference_urls'):
            # 編集モード：既存値を初期化（dict から取得、DetachedInstanceError 防止）
            st.session_state.ref_urls = form_data.get('reference_urls', [])
        else:
            st.session_state.ref_urls = [{"url": "", "type": "", "desc": ""}]
    
    ref_urls = []
    for i, ref in enumerate(st.session_state.ref_urls):
        with st.expander(f"URL {i+1}", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                url_val = st.text_input("URL", value=ref['url'], key=f"ref_url_{i}")
            with col2:
                url_type = st.selectbox("種別", ["公式", "製品", "論文", "プレス", "その他"], 
                                       index=["公式", "製品", "論文", "プレス", "その他"].index(ref.get('type', '公式')) if ref.get('type') in ["公式", "製品", "論文", "プレス", "その他"] else 0,
                                       key=f"ref_type_{i}")
            desc = st.text_input("メモ", value=ref.get('desc', ''), key=f"ref_desc_{i}")
            if url_val:
                ref_urls.append({"url": url_val, "type": url_type, "desc": desc})
            # 削除チェックボックス（フォーム内で使用可能）
            del_flag = st.checkbox("削除", key=f"del_ref_{i}", help="チェックして保存すると削除されます")
    
    # 追加するURLの入力
    st.markdown("**➕ 新しいURLを追加**")
    new_url = st.text_input("URL", key="new_ref_url", placeholder="新しいURLを入力")
    new_url_type = st.selectbox("種別", ["公式", "製品", "論文", "プレス", "その他"], key="new_ref_type")
    new_url_desc = st.text_input("メモ", key="new_ref_desc", placeholder="メモ（任意）")
    
    # 送信時に処理（ここでは form_data に反映するだけ）
    form_data['reference_urls'] = ref_urls
    form_data['_ref_del_flags'] = {i: st.session_state.get(f"del_ref_{i}", False) for i in range(len(st.session_state.ref_urls))}
    form_data['_new_ref_url'] = new_url.strip() if new_url else ""
    form_data['_new_ref_type'] = new_url_type if new_url else ""
    form_data['_new_ref_desc'] = new_url_desc.strip() if new_url_desc else ""
    
    st.markdown("---")
    st.markdown("### 2. 分類")
    
    form_data['category_main'] = st.selectbox(
        "2-1 材料カテゴリ（大分類）*",
        MATERIAL_CATEGORIES,
        key="category_main"
    )
    if form_data['category_main'] == "その他（自由記述）":
        form_data['category_other'] = st.text_input("その他（詳細）", key="category_other")
    
    form_data['material_forms'] = st.multiselect(
        "2-2 材料形態（供給形状）*",
        MATERIAL_FORMS,
        key="material_forms"
    )
    if "その他（自由記述）" in form_data['material_forms']:
        form_data['material_forms_other'] = st.text_input("その他（詳細）", key="material_forms_other")
    
    st.markdown("---")
    st.markdown("### 3. 由来・原料")
    
    # 編集モードの場合は既存値を初期値に
    default_origin_type = getattr(existing_material, 'origin_type', ORIGIN_TYPES[0]) if existing_material else ORIGIN_TYPES[0]
    origin_type_index = ORIGIN_TYPES.index(default_origin_type) if default_origin_type in ORIGIN_TYPES else 0
    form_data['origin_type'] = st.selectbox(
        "3-1 原料由来（一次分類）*",
        ORIGIN_TYPES,
        index=origin_type_index,
        key=f"origin_type_{existing_material.id if existing_material else 'new'}"
    )
    if form_data['origin_type'] == "その他（自由記述）":
        default_origin_other = getattr(existing_material, 'origin_other', '') if existing_material else ''
        form_data['origin_other'] = st.text_input("その他（詳細）", value=default_origin_other, key=f"origin_other_{existing_material.id if existing_material else 'new'}")
    
    default_origin_detail = getattr(existing_material, 'origin_detail', '') if existing_material else ''
    form_data['origin_detail'] = st.text_input(
        "3-2 原料詳細（具体名）*",
        value=default_origin_detail,
        placeholder="例：トウモロコシ由来PLA、木粉、ガラスカレット、菌糸体",
        key=f"origin_detail_{existing_material.id if existing_material else 'new'}"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        form_data['recycle_bio_rate'] = st.number_input(
            "3-3 リサイクル/バイオ含有率（%）",
            min_value=0.0,
            max_value=100.0,
            value=None,
            key="recycle_bio_rate"
        )
    with col2:
        form_data['recycle_bio_basis'] = st.selectbox(
            "根拠",
            ["自己申告", "第三者認証", "文献", "不明"],
            key="recycle_bio_basis"
        )
    
    st.markdown("---")
    st.markdown("### 4. 基本特性")
    
    form_data['color_tags'] = st.multiselect(
        "4-1 色*",
        COLOR_OPTIONS,
        key="color_tags"
    )
    form_data['transparency'] = st.selectbox(
        "透明性*",
        TRANSPARENCY_OPTIONS,
        key="transparency"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        form_data['hardness_qualitative'] = st.selectbox(
            "4-2 硬さ（定性）*",
            HARDNESS_OPTIONS,
            key="hardness_qualitative"
        )
    with col2:
        form_data['hardness_value'] = st.text_input(
            "硬さ（数値）",
            placeholder="例：Shore A 50, Mohs 3",
            key="hardness_value"
        )
    
    col1, col2 = st.columns(2)
    with col1:
        form_data['weight_qualitative'] = st.selectbox(
            "4-3 重さ感（定性）*",
            WEIGHT_OPTIONS,
            key="weight_qualitative"
        )
    with col2:
        form_data['specific_gravity'] = st.number_input(
            "比重",
            min_value=0.0,
            value=None,
            key="specific_gravity"
        )
    
    form_data['water_resistance'] = st.selectbox(
        "4-4 耐水性・耐湿性*",
        WATER_RESISTANCE_OPTIONS,
        key="water_resistance"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        form_data['heat_resistance_temp'] = st.number_input(
            "4-5 耐熱性（温度℃）",
            min_value=-273.0,
            value=None,
            key="heat_resistance_temp"
        )
    with col2:
        form_data['heat_resistance_range'] = st.selectbox(
            "耐熱性（範囲）*",
            HEAT_RANGE_OPTIONS,
            key="heat_resistance_range"
        )
    
    form_data['weather_resistance'] = st.selectbox(
        "4-6 耐候性（屋外耐久）*",
        WEATHER_RESISTANCE_OPTIONS,
        key="weather_resistance"
    )
    
    st.markdown("---")
    st.markdown("### 5. 加工・実装条件")
    
    form_data['processing_methods'] = st.multiselect(
        "5-1 加工方法（可能なもの）*",
        PROCESSING_METHODS,
        key="processing_methods"
    )
    if "その他（自由記述）" in form_data['processing_methods']:
        form_data['processing_other'] = st.text_input("その他（詳細）", key="processing_other")
    
    form_data['equipment_level'] = st.selectbox(
        "5-2 必要設備レベル*",
        EQUIPMENT_LEVELS,
        index=0,  # デフォルトを "家庭/工房レベル"
        key="equipment_level"
    )
    
    form_data['prototyping_difficulty'] = st.selectbox(
        "5-3 試作難易度*",
        DIFFICULTY_OPTIONS,
        index=1,  # デフォルトを "中"
        key="prototyping_difficulty"
    )
    
    st.markdown("---")
    st.markdown("### 6. 用途・市場状態")
    
    # 使用環境（一時的にコメントアウト - DBにカラムが存在しない）
    # form_data['use_environment'] = st.multiselect(
    #     "6-1 使用環境",
    #     USE_ENVIRONMENT_OPTIONS,
    #     default=form_data.get('use_environment', []),
    #     key="use_environment"
    # )
    
    form_data['use_categories'] = st.multiselect(
        "6-2 主用途カテゴリ*",
        USE_CATEGORIES,
        default=form_data.get('use_categories', []),
        key="use_categories"
    )
    if "その他（自由記述）" in form_data['use_categories']:
        form_data['use_other'] = st.text_input("その他（詳細）", key="use_other")
    
    # 代表的使用例（複数）（st.form内で完結）
    st.markdown("**6-2 代表的使用例**")
    
    # session_state の初期化（初回のみ）
    if 'use_examples' not in st.session_state:
        if existing_material and form_data.get('use_examples'):
            # 編集モード：既存値を初期化（dict から取得、DetachedInstanceError 防止）
            st.session_state.use_examples = form_data.get('use_examples', [])
        else:
            st.session_state.use_examples = [{"name": "", "url": "", "desc": ""}]
    
    use_examples = []
    for i, ex in enumerate(st.session_state.use_examples):
        with st.expander(f"使用例 {i+1}", expanded=False):
            name = st.text_input("製品名/事例名", value=ex.get('name', ''), key=f"ex_name_{i}")
            url = st.text_input("リンク", value=ex.get('url', ''), key=f"ex_url_{i}")
            desc = st.text_area("説明", value=ex.get('desc', ''), key=f"ex_desc_{i}")
            if name:
                use_examples.append({"name": name, "url": url, "desc": desc})
            # 削除チェックボックス（フォーム内で使用可能）
            del_flag = st.checkbox("削除", key=f"del_ex_{i}", help="チェックして保存すると削除されます")
    
    # 追加する使用例の入力
    st.markdown("**➕ 新しい使用例を追加**")
    new_ex_name = st.text_input("製品名/事例名", key="new_ex_name", placeholder="新しい使用例名を入力")
    new_ex_url = st.text_input("リンク", key="new_ex_url", placeholder="リンク（任意）")
    new_ex_desc = st.text_area("説明", key="new_ex_desc", placeholder="説明（任意）")
    
    # 送信時に処理（ここでは form_data に反映するだけ）
    form_data['use_examples'] = use_examples
    form_data['_ex_del_flags'] = {i: st.session_state.get(f"del_ex_{i}", False) for i in range(len(st.session_state.use_examples))}
    form_data['_new_ex_name'] = new_ex_name.strip() if new_ex_name else ""
    form_data['_new_ex_url'] = new_ex_url.strip() if new_ex_url else ""
    form_data['_new_ex_desc'] = new_ex_desc.strip() if new_ex_desc else ""
    
    form_data['procurement_status'] = st.selectbox(
        "6-3 調達性（入手しやすさ）*",
        PROCUREMENT_OPTIONS,
        key="procurement_status"
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        form_data['cost_level'] = st.selectbox(
            "6-4 コスト帯（目安）*",
            COST_LEVELS,
            key="cost_level"
        )
    with col2:
        form_data['cost_value'] = st.number_input(
            "価格情報（数値）",
            min_value=0.0,
            value=None,
            key="cost_value"
        )
    with col3:
        form_data['cost_unit'] = st.text_input(
            "単位",
            placeholder="例：円/kg, 円/m²",
            key="cost_unit"
        )
    
    st.markdown("---")
    st.markdown("### 7. 制約・安全・法規")
    
    form_data['safety_tags'] = st.multiselect(
        "7-1 安全区分（用途制限）*",
        SAFETY_TAGS,
        key="safety_tags"
    )
    if "その他（自由記述）" in form_data['safety_tags']:
        form_data['safety_other'] = st.text_input("その他（詳細）", key="safety_other")
    
    form_data['restrictions'] = st.text_area(
        "7-2 禁止・注意事項（自由記述）",
        placeholder="使用上の注意点、禁止事項などを記入してください",
        key="restrictions"
    )
    
    st.markdown("---")
    st.markdown("### 8. 公開範囲")
    
    form_data['visibility'] = st.selectbox(
        "8-1 公開設定*",
        VISIBILITY_OPTIONS,
        index=0,  # デフォルトを "公開（誰でも閲覧可）"
        key="visibility"
    )
    
    st.markdown("---")
    st.markdown("### 9. 主要元素リスト（STEP 6: 材料×元素マッピング）")
    
    st.info("💡 **思考の補助**として、この材料に含まれる主要元素の原子番号を入力してください。\n\n例: 水 (H₂O) → `1, 8`、鉄 (Fe) → `26`、プラスチック (C, H, O) → `1, 6, 8`")
    
    main_elements_input = st.text_input(
        "主要元素の原子番号（カンマ区切り）",
        placeholder="例: 1, 6, 8 または 26",
        help="1-118の範囲で、カンマ区切りで入力してください",
        key="main_elements_input"
    )
    
    if main_elements_input:
        try:
            # カンマ区切りの文字列をパース
            elements_list = [int(e.strip()) for e in main_elements_input.split(",") if e.strip().isdigit()]
            # 1-118の範囲に制限
            elements_list = [e for e in elements_list if 1 <= e <= 118]
            if elements_list:
                form_data['main_elements'] = json.dumps(elements_list, ensure_ascii=False)
                st.success(f"✅ {len(elements_list)}個の元素を登録: {elements_list}")
            else:
                form_data['main_elements'] = None
                st.warning("⚠️ 有効な原子番号（1-118）が見つかりませんでした。")
        except Exception as e:
            form_data['main_elements'] = None
            st.warning(f"⚠️ 入力形式が正しくありません: {e}")
    else:
        form_data['main_elements'] = None
    
    return form_data


def show_layer2_form():
    """レイヤー②：任意情報フォーム"""
    form_data = {}
    
    st.markdown("### A. ストーリー・背景")
    
    DEVELOPMENT_MOTIVES = [
        "環境負荷低減", "コスト低減", "性能向上（強度/耐熱等）",
        "触感/意匠性の追求", "安全性向上", "地域資源活用",
        "廃棄物活用", "規制対応", "サプライチェーン事情",
        "研究的好奇心", "その他（自由記述）", "不明"
    ]
    
    form_data['development_motives'] = st.multiselect(
        "A-1 開発動機タイプ",
        DEVELOPMENT_MOTIVES,
        key="dev_motives"
    )
    if "その他（自由記述）" in form_data.get('development_motives', []):
        form_data['development_motive_other'] = st.text_input("その他（詳細）", key="dev_motive_other")
    
    form_data['development_background_short'] = st.text_input(
        "A-2 開発背景（短文）",
        key="dev_background_short"
    )
    
    form_data['development_story'] = st.text_area(
        "A-3 開発ストーリー（長文）",
        placeholder="課題、転機、学びなどを記入してください",
        height=150,
        key="dev_story"
    )
    
    st.markdown("---")
    st.markdown("### C. 感覚的特性")
    
    TACTILE_TAGS = [
        "さらさら", "しっとり", "ざらざら", "もちもち", "ねっとり",
        "ふわふわ", "つるつる", "べたつく", "ひんやり", "あたたかい",
        "かたい感触", "やわらかい感触", "その他（自由記述）"
    ]
    
    form_data['tactile_tags'] = st.multiselect(
        "C-1 触感タグ",
        TACTILE_TAGS,
        key="tactile_tags"
    )
    if "その他（自由記述）" in form_data.get('tactile_tags', []):
        form_data['tactile_other'] = st.text_input("その他（詳細）", key="tactile_other")
    
    VISUAL_TAGS = [
        "マット", "グロス", "パール/干渉", "透過散乱", "蛍光",
        "蓄光", "変色（温度/光）", "その他（自由記述）"
    ]
    
    form_data['visual_tags'] = st.multiselect(
        "C-2 視覚タグ（光の反応）",
        VISUAL_TAGS,
        key="visual_tags"
    )
    if "その他（自由記述）" in form_data.get('visual_tags', []):
        form_data['visual_other'] = st.text_input("その他（詳細）", key="visual_other")
    
    form_data['sound_smell'] = st.text_input(
        "C-3 音・匂い",
        placeholder="音や匂いの特徴を記入してください",
        key="sound_smell"
    )
    
    st.markdown("---")
    st.markdown("### D. 物性値（任意）")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        density_value = st.number_input(
            "密度 (g/cm³)",
            min_value=0.0,
            value=None,
            step=0.01,
            format="%.2f",
            key="density",
            help="材料の密度を入力してください（例: 1.38）"
        )
        if density_value is not None and density_value > 0:
            form_data['density'] = float(density_value)
    
    with col2:
        tensile_strength_value = st.number_input(
            "引張強度 (MPa)",
            min_value=0.0,
            value=None,
            step=0.1,
            format="%.1f",
            key="tensile_strength",
            help="引張強度を入力してください（例: 50.0）"
        )
        if tensile_strength_value is not None and tensile_strength_value > 0:
            form_data['tensile_strength'] = float(tensile_strength_value)
    
    with col3:
        yield_strength_value = st.number_input(
            "降伏強度 (MPa)",
            min_value=0.0,
            value=None,
            step=0.1,
            format="%.1f",
            key="yield_strength",
            help="降伏強度を入力してください（例: 45.0）"
        )
        if yield_strength_value is not None and yield_strength_value > 0:
            form_data['yield_strength'] = float(yield_strength_value)
    
    st.markdown("---")
    st.markdown("### F. 環境・倫理・未来")
    
    CIRCULARITY_OPTIONS = [
        "リサイクルしやすい", "条件付きで可能", "難しい",
        "生分解する", "焼却前提", "不明"
    ]
    
    form_data['circularity'] = st.selectbox(
        "F-1 循環性（ざっくり評価）",
        CIRCULARITY_OPTIONS,
        key="circularity"
    )
    
    CERTIFICATIONS = [
        "ISO系", "FSC/PEFC", "GRS 等リサイクル系", "生分解規格",
        "食品接触規格", "その他（自由記述）", "不明"
    ]
    
    form_data['certifications'] = st.multiselect(
        "F-2 認証・規格（あれば）",
        CERTIFICATIONS,
        key="certifications"
    )
    if "その他（自由記述）" in form_data.get('certifications', []):
        form_data['certifications_other'] = st.text_input("その他（詳細）", key="certifications_other")
    
    return form_data


def handle_primary_image(material_id: int, uploaded_files: list) -> None:
    """
    主画像をR2にアップロードし、imagesテーブルへupsertする共通関数
    
    Args:
        material_id: 材料ID（確定済み）
        uploaded_files: UploadedFile のリスト（空の場合はスキップ）
    
    Returns:
        None（例外時はログとUI警告のみ、材料保存は継続）
    """
    if not uploaded_files or len(uploaded_files) == 0:
        logger.info("[R2] skip: no uploaded file")
        st.info("ℹ️ 画像が選択されていないため、R2アップロードをスキップします")
        return
    
    # 最初のファイルを primary として扱う
    primary_file = uploaded_files[0]
    if primary_file is None:
        logger.warning("[R2] WARNING: primary_file is None, skipping upload")
        st.warning("⚠️ 画像ファイルが無効です。R2アップロードをスキップします。")
        return
    
    # R2設定のチェック
    import utils.settings as settings
    
    # get_flag が無い場合に備えた二重化
    flag_fn = getattr(settings, "get_flag", None)
    if not callable(flag_fn):
        # フォールバック: os.getenv のみで判定
        def flag_fn(key, default=False):
            value = os.getenv(key)
            if value is None:
                return default
            value_str = str(value).lower().strip()
            return value_str in ("1", "true", "yes", "y", "on")
    
    enable_r2_upload = flag_fn("ENABLE_R2_UPLOAD", True)
    # INIT_SAMPLE_DATA の時は必ず False 扱い（seed中はR2アップロードしない）
    # 注意: SEED_SKIP_IMAGES は seed処理（init_sample_data.py等）のみで使用し、通常登録では参照しない
    if flag_fn("INIT_SAMPLE_DATA", False):
        enable_r2_upload = False
        logger.info("[R2] skip: INIT_SAMPLE_DATA=True (seed mode)")
        st.info("ℹ️ サンプルデータ生成中はR2アップロードをスキップします")
        return
    
    if not enable_r2_upload:
        logger.info("[R2] skip: ENABLE_R2_UPLOAD is False")
        st.info("ℹ️ R2アップロードが無効化されています")
        return
    
    # R2 アップロード処理
    try:
        # importを安定化（循環/欠落に強い）
        import utils.r2_storage as r2_storage
        from utils.image_repo import upsert_image
        
        # R2設定の確認（Missing keys を理由付きでUIにも出す）
        try:
            # get_r2_client を呼んで設定不足を検知
            _ = r2_storage.get_r2_client()
        except RuntimeError as r2_config_error:
            error_msg = str(r2_config_error)
            logger.warning(f"[R2] Configuration error: {error_msg}")
            st.warning(f"⚠️ R2設定が不足しています: {error_msg}")
            return
        
        # ファイル名を取得
        file_name = getattr(primary_file, 'name', 'unknown')
        logger.info(f"[R2] Upload start: material_id={material_id}, file={file_name}")
        
        # R2 にアップロード
        r2_result = r2_storage.upload_uploadedfile(primary_file, material_id, "primary")
        
        logger.info(f"[R2] Upload success: material_id={material_id}, r2_key={r2_result.get('r2_key')}, public_url={r2_result.get('public_url')}")
        
        # images テーブルへ upsert
        from utils.db import session_scope
        with session_scope() as db:
            upsert_image(
                db=db,
                material_id=material_id,
                kind="primary",
                r2_key=r2_result["r2_key"],
                public_url=r2_result["public_url"],
                bytes=None,  # Phase1: bytes列には書かない（BYTEA型の可能性があるため）
                mime=r2_result["mime"],
                sha256=r2_result["sha256"],
            )
            # commitはsession_scopeが自動で行う
            logger.info(f"[R2] Image saved to DB: material_id={material_id}, public_url={r2_result['public_url']}")
            st.success(f"✅ 画像をR2にアップロードしました: {r2_result.get('public_url', 'N/A')}")
            
    except Exception as r2_error:
        # R2 アップロード失敗はログとUI警告のみ（材料保存は成功させる）
        logger.exception(f"[R2] Upload failed: material_id={material_id}, error={r2_error}")
        st.warning(f"⚠️ R2アップロードに失敗しました: {str(r2_error)[:100]}")


def save_material(form_data):
    """材料データを保存（upsert対応）"""
    from utils.db import session_scope
    try:
        with session_scope() as db:
            # name_officialで既存レコードを検索（upsert）
            existing_material = db.query(Material).filter(
            Material.name_official == form_data['name_official']
        ).first()
        
        # 必須フィールドの補完（None/空文字列をデフォルト値で埋める）
        form_data = _normalize_required(form_data, existing=existing_material)
        
        # 必須フィールドのバリデーション
        required_fields = [
            'name_official', 'supplier_org', 'supplier_type',
            'category_main', 'material_forms', 'origin_type', 'origin_detail',
            'transparency', 'hardness_qualitative', 'weight_qualitative',
            'water_resistance', 'heat_resistance_range', 'weather_resistance',
            'processing_methods', 'equipment_level', 'prototyping_difficulty',
            'use_categories', 'procurement_status', 'cost_level',
            'safety_tags', 'visibility'
        ]
        
        for field in required_fields:
            if field not in form_data or not form_data[field]:
                raise ValueError(f"必須フィールド '{field}' が入力されていません")
        
        action = 'updated' if existing_material else 'created'
        
        # relationship を form_data から pop（setattr で触らない）
        ref_urls_payload = form_data.pop("reference_urls", None)
        use_examples_payload = form_data.pop("use_examples", None)
        
        if existing_material:
            # UPDATE（既存レコードを更新）
            # --- ensure material is bound to this session ---
            material = db.merge(existing_material)
            material_uuid = material.uuid  # UUIDは保持
            
            # 差分更新：変更されたキーだけを updates に入れる
            updates = {}
            json_array_fields = ['name_aliases', 'material_forms', 'color_tags', 'processing_methods',
                                'use_categories', 'safety_tags', 'question_templates', 'main_elements',
                                'development_motives', 'tactile_tags', 'visual_tags', 'certifications']
            
            for k, v in form_data.items():
                # None や空文字列は既存値を維持（スキップ）
                if v is None:
                    continue
                if isinstance(v, str) and v.strip() == "":
                    continue
                
                # 既存値と比較して変更があった場合のみ updates に入れる
                existing_value = getattr(material, k, None)
                
                # JSON配列フィールドの場合は、既存値（JSON文字列）をパースして比較
                if k in json_array_fields:
                    if isinstance(v, list):
                        # form_data の値がリストの場合、JSON文字列に変換して比較
                        v_json = json.dumps(v, ensure_ascii=False, sort_keys=True)
                        if isinstance(existing_value, str):
                            try:
                                existing_list = json.loads(existing_value)
                                existing_json = json.dumps(existing_list, ensure_ascii=False, sort_keys=True)
                                if existing_json != v_json:
                                    updates[k] = json.dumps(v, ensure_ascii=False)
                            except (json.JSONDecodeError, TypeError):
                                # パース失敗時は更新する
                                updates[k] = json.dumps(v, ensure_ascii=False)
                        elif existing_value != v_json:
                            updates[k] = json.dumps(v, ensure_ascii=False)
                    elif existing_value != v:
                        updates[k] = v
                else:
                    # 通常フィールドは直接比較
                    if existing_value != v:
                        updates[k] = v
            
            # 変更されたキーだけを setattr で更新
            for k, v in updates.items():
                setattr(material, k, v)
        else:
            # INSERT（新規レコード）
            material_uuid = str(uuid.uuid4())
            material = Material(
                uuid=material_uuid,
                id=None  # 新規作成
            )
            db.add(material)
        
        # Materialデータを設定（新規/更新共通）
        # 注意：既存レコードの更新は上記のループで完了しているため、ここは新規のみ
        if not existing_material:
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
            material.prototyping_difficulty = form_data['prototyping_difficulty']  # typo修正
            # material.use_environment = json.dumps(form_data.get('use_environment', []), ensure_ascii=False)  # 一時的にコメントアウト（DBにカラムが存在しない）
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
            material.is_published = form_data.get('is_published', 1)  # デフォルトは公開
            # レイヤー②
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
            # STEP 6: 材料×元素マッピング
            material.main_elements = form_data.get('main_elements')
            # 後方互換性
            material.name = form_data['name_official']
            material.category = form_data['category_main']
        
        # search_textを生成して設定（新規/更新共通）
        from utils.search import generate_search_text, update_material_embedding
        material.search_text = generate_search_text(material)
        
        db.flush()
        
        # 埋め込みを更新（content_hashが変わった場合のみ）
        try:
            update_material_embedding(db, material)
        except Exception as e:
            # 埋め込み更新失敗は警告のみ（保存は継続）
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[SAVE MATERIAL] Failed to update embedding for material_id={material.id}: {e}")
        
        # 参照URL保存（既存のものは削除してから再作成）
        # 編集モードでは、payload が None でない場合のみ更新（変更があった場合のみ）
        if ref_urls_payload is not None:
            db.query(ReferenceURL).filter(ReferenceURL.material_id == material.id).delete()
            for ref in ref_urls_payload:
                if ref.get('url'):
                    ref_url = ReferenceURL(
                        material_id=material.id,
                        url=ref['url'],
                        url_type=ref.get('type'),
                        description=ref.get('desc')
                    )
                    db.add(ref_url)
        
        # 使用例保存（既存のものは削除してから再作成）
        # 編集モードでは、payload が None でない場合のみ更新（変更があった場合のみ）
        if use_examples_payload is not None:
            db.query(UseExample).filter(UseExample.material_id == material.id).delete()
            for ex in use_examples_payload:
                if ex.get('name'):
                    use_ex = UseExample(
                        material_id=material.id,
                        example_name=ex['name'],
                        example_url=ex.get('url'),
                        description=ex.get('desc')
                    )
                    db.add(use_ex)
        
        # commitはsession_scopeが自動で行う
        
        # R2 アップロード処理（material.id 確定後）
        # submitted 時は session_state のキャッシュから確実に取得
        CACHE_KEY = "primary_image_cached"
        cached_files = st.session_state.get(CACHE_KEY, [])
        uploaded_files = normalize_uploaded_files(cached_files)
        
        # form_data からも取得を試みる（フォールバック）
        if not uploaded_files:
            uploaded_files = normalize_uploaded_files(form_data.get('images', []))
        
        # 画像枚数をログ出力
        cached_image_count = len(uploaded_files)
        logger.info(f"[SAVE MATERIAL] cached_image_count={cached_image_count}, material_id={material.id if material else None}")
        
        if cached_image_count > 0:
            st.info(f"📸 保存する画像: {cached_image_count} 枚")
            for idx, img in enumerate(uploaded_files):
                if hasattr(img, 'name'):
                    logger.info(f"[SAVE MATERIAL] Image {idx+1}: {img.name}")
        else:
            logger.info(f"[SAVE MATERIAL] No images to upload (cached_image_count=0)")
            st.info("ℹ️ 画像が選択されていないため、R2アップロードをスキップします")
        
        # 共通関数でR2アップロード処理（material.id が確定している場合のみ）
        # 画像アップロードが空なら既存画像を維持する（再アップロード不要）
        if material.id and uploaded_files:
            handle_primary_image(material.id, uploaded_files)
        
        # 成功時はdictを返す
        return {
            "ok": True,
            "action": action,
            "material_id": material.id,
            "uuid": material.uuid,
        }
    except Exception as e:
        # rollbackはsession_scopeが自動で行う
        import traceback
        # 失敗時はdictを返す（例外を再発生させない）
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def save_material_submission(form_data: dict, submitted_by: str = None):
    """
    材料投稿をmaterial_submissionsテーブルに保存（承認フロー用）
    
    Args:
        form_data: フォーム入力データ（_normalize_requiredで正規化済み）
        submitted_by: 投稿者情報（任意）
    
    Returns:
        dict: {"ok": True/False, "submission_id": int, "uuid": str, "error": str, "traceback": str}
    """
    from utils.db import session_scope
    try:
        with session_scope() as db:
            # UUIDを生成（R2 プレフィックス用）
            submission_uuid = str(uuid.uuid4())
        
        # 画像を form_data から pop（UploadedFile は JSON 化できないため）
        # 防御的に複数回 pop して確実に除去（再発防止）
        form_data.pop('images', None)
        if 'images' in form_data:
            # 念のため再度除去（_normalize_required で再追加された可能性）
            form_data.pop('images', None)
        
        # submitted 時は session_state のキャッシュから確実に取得
        CACHE_KEY = "primary_image_cached"
        cached_files = st.session_state.get(CACHE_KEY, [])
        uploaded_files = normalize_uploaded_files(cached_files)
        
        # 画像枚数をログ出力
        cached_image_count = len(uploaded_files)
        logger.info(f"[SAVE SUBMISSION] cached_image_count={cached_image_count}, submission_uuid={submission_uuid}")
        
        if cached_image_count > 0:
            st.info(f"📸 保存する画像: {cached_image_count} 枚")
            for idx, img in enumerate(uploaded_files):
                if hasattr(img, 'name'):
                    logger.info(f"[SAVE SUBMISSION] Image {idx+1}: {img.name}")
        else:
            logger.info(f"[SAVE SUBMISSION] No images to upload (cached_image_count=0)")
            st.info("ℹ️ 画像が選択されていないため、R2アップロードをスキップします")
        
        uploaded_images = []
        
        # name_official を session_state キャッシュから最終確定（空なら送信停止）
        NAME_CACHE = "name_official_cached"
        name_official = st.session_state.get(NAME_CACHE, "").strip()
        form_data["name_official"] = name_official
        form_data["name"] = name_official
        
        if not name_official:
            error_msg = "材料名（正式）が入力されていません。必須項目です。"
            logger.warning(f"[SAVE SUBMISSION] name_official is empty (cached='{st.session_state.get(NAME_CACHE, '')}'), skipping submission (INSERTしない)")
            st.error(f"❌ {error_msg}")
            return {
                "ok": False,
                "error": error_msg,
                "error_code": "name_official_empty",
            }
        
        # 送信前に DB を問い合わせ：pending の同名チェック
        from sqlalchemy import select
        existing_pending = db.execute(
            select(MaterialSubmission.id)
            .where(MaterialSubmission.status == "pending")
            .where(MaterialSubmission.name_official == name_official)
            .limit(1)
        ).scalar_one_or_none()
        
        if existing_pending is not None:
            st.info(f"ℹ️ すでに承認待ちです（投稿ID: {existing_pending}）")
            logger.info(f"[SAVE SUBMISSION] Duplicate pending submission detected (id={existing_pending}, name_official='{name_official}'), skipping INSERT")
            return {
                "ok": False,
                "error": f"すでに承認待ちです（投稿ID: {existing_pending}）",
                "error_code": "duplicate_pending",
            }
        
        # ログ出力（送信時の値を確認）
        logger.info(f"[SAVE SUBMISSION] name_official='{name_official}' (length={len(name_official)})")
        
        # properties 配列を作成（値があるものだけ）
        properties_list = []
        property_mapping = {
            "density": ("density", "g/cm³"),
            "tensile_strength": ("tensile_strength", "MPa"),
            "yield_strength": ("yield_strength", "MPa"),
        }
        for form_key, (prop_key, unit) in property_mapping.items():
            value = form_data.get(form_key)
            if value is not None and value > 0:
                properties_list.append({
                    "key": prop_key,
                    "value": float(value),
                    "unit": unit
                })
        form_data["properties"] = properties_list
        logger.info(f"[SAVE SUBMISSION] properties={properties_list}")
        
        # 必須フィールドの補完（None/空文字列をデフォルト値で埋める）
        # images を除去した後に _normalize_required を呼ぶ（images が再追加されないように）
        form_data = _normalize_required(form_data, existing=None)
        
        # 再度 images を除去（念のため）
        if 'images' in form_data:
            form_data.pop('images', None)
        
        # R2 アップロード処理（フラグチェック）
        import utils.settings as settings
        
        # get_flag が無い場合に備えた二重化
        flag_fn = getattr(settings, "get_flag", None)
        if not callable(flag_fn):
            # フォールバック: os.getenv のみで判定
            def flag_fn(key, default=False):
                value = os.getenv(key)
                if value is None:
                    return default
                value_str = str(value).lower().strip()
                return value_str in ("1", "true", "yes", "y", "on")
        
        enable_r2_upload = flag_fn("ENABLE_R2_UPLOAD", True)
        # INIT_SAMPLE_DATA の時は必ず False 扱い（seed中はR2アップロードしない）
        # 注意: SEED_SKIP_IMAGES は seed処理（init_sample_data.py等）のみで使用し、通常登録では参照しない
        if flag_fn("INIT_SAMPLE_DATA", False):
            enable_r2_upload = False
            logger.info("[R2] skip: INIT_SAMPLE_DATA=True (seed mode)")
        
        if enable_r2_upload and uploaded_files and len(uploaded_files) > 0:
            try:
                # R2 関連の import を安定化（循環/欠落に強い）
                import utils.r2_storage as r2_storage
                
                # プレフィックスを決定
                prefix = f"submissions/{submission_uuid}"
                logger.info(f"[R2] Starting submission upload: prefix={prefix}, files={len(uploaded_files)}")
                
                # フォールバック関数（upload_uploadedfile_to_prefix が無い場合）
                def _fallback_upload_to_prefix(uploaded_file, prefix, kind):
                    """upload_uploadedfile_to_prefix が無い場合のフォールバック実装"""
                    import hashlib
                    
                    # ファイルデータを読み込む
                    uploaded_file.seek(0)  # ファイルポインタを先頭に戻す
                    data = uploaded_file.read()
                    file_size = len(data)
                    
                    # SHA256ハッシュを計算
                    sha256_hash = hashlib.sha256(data).hexdigest()
                    
                    # ファイル名から拡張子を取得
                    filename = getattr(uploaded_file, "name", "upload")
                    _, ext = os.path.splitext(filename)
                    if not ext or ext == ".":
                        # MIMEタイプから拡張子を推定
                        mime_type = getattr(uploaded_file, "type", None) or "image/jpeg"
                        if mime_type == "image/png":
                            ext = ".png"
                        elif mime_type == "image/webp":
                            ext = ".webp"
                        elif mime_type == "image/gif":
                            ext = ".gif"
                        else:
                            ext = ".jpg"
                    
                    # R2 キーを生成
                    prefix = prefix.rstrip("/")
                    unique_id = uuid.uuid4().hex[:8]
                    r2_key = f"{prefix}/{kind}/{unique_id}{ext}"
                    
                    # MIMEタイプを取得
                    content_type = getattr(uploaded_file, "type", None) or "image/jpeg"
                    
                    # upload_bytes_to_r2 を呼び出す
                    r2_storage.upload_bytes_to_r2(key=r2_key, body=data, content_type=content_type)
                    
                    # 公開URLを生成（make_public_url が存在するかチェック）
                    make_url_fn = getattr(r2_storage, "make_public_url", None)
                    if callable(make_url_fn):
                        public_url = make_url_fn(r2_key)
                    else:
                        # make_public_url が無い場合はエラー
                        raise RuntimeError("make_public_url is not available in r2_storage module")
                    
                    logger.info(f"[R2] Fallback upload completed: r2_key={r2_key}, public_url={public_url}")
                    
                    return {
                        "r2_key": r2_key,
                        "public_url": public_url,
                        "bytes": file_size,
                        "mime": content_type,
                        "sha256": sha256_hash,
                    }
                
                # 各ファイルをアップロード（最初を primary、2番目を space、3番目を product として扱う）
                kind_map = ["primary", "space", "product"]
                for idx, uploaded_file in enumerate(uploaded_files[:3]):  # 最大3ファイル
                    if uploaded_file is None:
                        logger.warning(f"[R2] uploaded_file[{idx}] is None, skipping")
                        continue
                    kind = kind_map[idx] if idx < len(kind_map) else "primary"
                    file_name = getattr(uploaded_file, 'name', 'unknown')
                    logger.info(f"[R2] Uploading file {idx+1}/{min(len(uploaded_files), 3)}: {file_name}, kind={kind}")
                    try:
                        # upload_uploadedfile_to_prefix が存在するかチェック
                        upload_fn = getattr(r2_storage, "upload_uploadedfile_to_prefix", None)
                        if callable(upload_fn):
                            logger.info(f"[R2] Using upload_uploadedfile_to_prefix for file {idx+1}")
                            r2_result = upload_fn(uploaded_file, prefix, kind)
                        else:
                            logger.info(f"[R2] Using fallback upload function for file {idx+1} (upload_uploadedfile_to_prefix not available)")
                            r2_result = _fallback_upload_to_prefix(uploaded_file, prefix, kind)
                        
                        uploaded_images.append({
                            "kind": kind,
                            "r2_key": r2_result["r2_key"],
                            "public_url": r2_result["public_url"],
                            "bytes": r2_result["bytes"],
                            "mime": r2_result["mime"],
                            "sha256": r2_result["sha256"],
                        })
                        logger.info(f"[R2] Upload success: r2_key={r2_result.get('r2_key')}, public_url={r2_result.get('public_url')}")
                    except Exception as r2_error:
                        logger.exception(f"[R2] Upload failed for file {idx+1}: {r2_error}")
                        st.warning(f"⚠️ 画像 {idx+1} のR2アップロードに失敗しました: {str(r2_error)[:100]}")
                
                logger.info(f"[R2] Submission upload completed: {len(uploaded_images)} files uploaded")
            except Exception as e:
                # R2 アップロード失敗はログとUI警告のみ（投稿保存は成功させる）
                logger.exception(f"[R2] Submission upload failed: {e}")
                st.warning(f"⚠️ R2アップロードに失敗しました: {str(e)[:100]}")
                # R2 アップロード失敗は警告のみ（submission は保存する）
        
        # payload_json に uploaded_images を追加
        if uploaded_images:
            form_data["uploaded_images"] = uploaded_images
        
        # payload_jsonにform_dataをJSON文字列として保存
        payload_json = json.dumps(form_data, ensure_ascii=False, default=str)
        
        # MaterialSubmissionを作成（name_official も保存）
        submission = MaterialSubmission(
            uuid=submission_uuid,
            status="pending",
            name_official=name_official,  # 重複チェック用
            payload_json=payload_json,
            submitted_by=submitted_by if submitted_by and submitted_by.strip() else None
        )
        
        db.add(submission)
        # commitはsession_scopeが自動で行う
        db.refresh(submission)
        
        # 成功時はdictを返す
        return {
            "ok": True,
            "submission_id": submission.id,
            "uuid": submission.uuid,
            "uploaded_images": uploaded_images,  # プレビュー用
        }
    except Exception as e:
        # rollbackはsession_scopeが自動で行う
        import traceback
        # 失敗時はdictを返す（例外を再発生させない）
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


