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
from database import SessionLocal, Material, Property, Image, MaterialMetadata, ReferenceURL, UseExample, MaterialSubmission, init_db


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
    "アート/展示", "その他（自由記述）", "不明"
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
    
    if is_edit_mode:
        # 編集モード：既存材料を取得
        db = SessionLocal()
        try:
            existing_material = db.query(Material).filter(Material.id == material_id).first()
            if not existing_material:
                st.error(f"❌ 材料ID {material_id} が見つかりません")
                return
            st.markdown('<h2 class="gradient-text">✏️ 材料編集</h2>', unsafe_allow_html=True)
            st.info(f"📝 **編集対象**: {existing_material.name_official}")
        finally:
            db.close()
    else:
        st.markdown('<h2 class="gradient-text">➕ 材料登録（詳細版）</h2>', unsafe_allow_html=True)
        st.info("📝 **レイヤー①（必須）**: 約10分で入力可能な基本情報\n\n**レイヤー②（任意）**: 後から追記できる詳細情報")
    
    # 編集モードの場合は既存値をform_dataに初期化
    if existing_material:
        # 既存値からform_dataを初期化（主要フィールドのみ）
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
        # 参照URLと使用例も取得
        if existing_material.reference_urls:
            form_data['reference_urls'] = [
                {'url': ref.url, 'type': ref.url_type, 'desc': ref.description}
                for ref in existing_material.reference_urls
            ]
        else:
            form_data['reference_urls'] = []
        if existing_material.use_examples:
            form_data['use_examples'] = [
                {'name': ex.example_name, 'url': ex.example_url, 'desc': ex.description}
                for ex in existing_material.use_examples
            ]
        else:
            form_data['use_examples'] = []
    else:
        form_data = {}
    
    # タブでレイヤー①とレイヤー②を分ける
    tab1, tab2 = st.tabs(["📋 レイヤー①：必須情報", "✨ レイヤー②：任意情報"])
    
    with tab1:
        layer1_data = show_layer1_form(existing_material=existing_material)
        if layer1_data:
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
    
    # フォーム送信
    if is_edit_mode or is_admin:
        # 管理者モードまたは編集モード：直接materialsに保存
        button_text = "✅ 材料を更新" if is_edit_mode else "✅ 材料を登録"
        if form_data and st.button(button_text, type="primary", width='stretch'):
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
                        # 編集ページから一覧に戻る
                        if st.button("← 一覧に戻る", key="back_after_edit"):
                            st.session_state.edit_material_id = None
                            st.session_state.page = "材料一覧"
                            st.rerun()
            else:
                # 失敗時：st.error(result["error"])とst.expanderでtraceback表示
                st.error(f"❌ エラーが発生しました: {result.get('error', '不明なエラー')}")
                if result.get("traceback"):
                    with st.expander("🔍 エラー詳細（デバッグ用）", expanded=False):
                        st.code(result["traceback"], language="python")
    else:
        # 一般ユーザーモード：submissionsに保存
        if form_data and st.button("📤 投稿を送信（承認待ち）", type="primary", width='stretch'):
            result = save_material_submission(form_data, submitted_by=submitted_by)
            
            # 防御的にresult.get("ok")で分岐
            if result.get("ok"):
                submission_id = result.get("submission_id")
                submission_uuid = result.get("uuid")
                st.success("✅ 投稿を送信しました！管理者の承認をお待ちください。")
                st.info("📝 承認後、材料一覧に表示されます。")
                st.markdown("---")
                st.markdown("### 📋 投稿控え")
                st.code(f"投稿ID: {submission_id}\nUUID: {submission_uuid}", language="text")
                st.info("💡 このIDを控えておくと、後で投稿ステータスを確認できます。")
            else:
                # 失敗時：st.error(result["error"])とst.expanderでtraceback表示
                st.error(f"❌ エラーが発生しました: {result.get('error', '不明なエラー')}")
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
    
    st.markdown("### 1. 基本識別情報")
    
    col1, col2 = st.columns(2)
    with col1:
        # 編集モードの場合は既存値を初期値に
        default_name = getattr(existing_material, 'name_official', '') if existing_material else ''
        form_data['name_official'] = st.text_input(
            "1-1 材料名（正式）*",
            value=default_name,
            key=f"name_official_{existing_material.id if existing_material else 'new'}",
            help="材料の正式名称を入力してください"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("材料IDは自動採番されます")
    
    # 材料名（通称・略称）複数
    st.markdown("**1-2 材料名（通称・略称）**")
    if 'aliases' not in st.session_state:
        st.session_state.aliases = [""]
    
    aliases = []
    for i, alias in enumerate(st.session_state.aliases):
        col1, col2 = st.columns([5, 1])
        with col1:
            alias_val = st.text_input(f"通称 {i+1}", value=alias, key=f"alias_{i}")
            if alias_val:
                aliases.append(alias_val)
        with col2:
            if st.button("削除", key=f"del_alias_{i}"):
                st.session_state.aliases.pop(i)
                st.rerun()
    
    if st.button("➕ 通称を追加"):
        st.session_state.aliases.append("")
        st.rerun()
    
    form_data['name_aliases'] = [a for a in aliases if a]
    
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
    
    # 参照URL（複数）
    st.markdown("**1-4 参照URL（公式/製品/論文/プレス等）**")
    if 'ref_urls' not in st.session_state:
        st.session_state.ref_urls = [{"url": "", "type": "", "desc": ""}]
    
    ref_urls = []
    for i, ref in enumerate(st.session_state.ref_urls):
        with st.expander(f"URL {i+1}", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                url_val = st.text_input("URL", value=ref['url'], key=f"ref_url_{i}")
            with col2:
                url_type = st.selectbox("種別", ["公式", "製品", "論文", "プレス", "その他"], key=f"ref_type_{i}")
            desc = st.text_input("メモ", value=ref.get('desc', ''), key=f"ref_desc_{i}")
            if url_val:
                ref_urls.append({"url": url_val, "type": url_type, "desc": desc})
            if st.button("削除", key=f"del_ref_{i}"):
                st.session_state.ref_urls.pop(i)
                st.rerun()
    
    if st.button("➕ URLを追加"):
        st.session_state.ref_urls.append({"url": "", "type": "", "desc": ""})
        st.rerun()
    
    form_data['reference_urls'] = ref_urls
    
    # 画像アップロード
    st.markdown("**1-5 画像（材料/サンプル/用途例）**")
    uploaded_files = st.file_uploader(
        "画像をアップロード（複数可）",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        help="ドラッグ&ドロップで複数ファイルをアップロードできます"
    )
    form_data['images'] = uploaded_files
    
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
    
    form_data['use_categories'] = st.multiselect(
        "6-1 主用途カテゴリ*",
        USE_CATEGORIES,
        key="use_categories"
    )
    if "その他（自由記述）" in form_data['use_categories']:
        form_data['use_other'] = st.text_input("その他（詳細）", key="use_other")
    
    # 代表的使用例（複数）
    st.markdown("**6-2 代表的使用例**")
    if 'use_examples' not in st.session_state:
        st.session_state.use_examples = [{"name": "", "url": "", "desc": ""}]
    
    use_examples = []
    for i, ex in enumerate(st.session_state.use_examples):
        with st.expander(f"使用例 {i+1}", expanded=False):
            name = st.text_input("製品名/事例名", value=ex.get('name', ''), key=f"ex_name_{i}")
            url = st.text_input("リンク", value=ex.get('url', ''), key=f"ex_url_{i}")
            desc = st.text_area("説明", value=ex.get('desc', ''), key=f"ex_desc_{i}")
            if name:
                use_examples.append({"name": name, "url": url, "desc": desc})
            if st.button("削除", key=f"del_ex_{i}"):
                st.session_state.use_examples.pop(i)
                st.rerun()
    
    if st.button("➕ 使用例を追加"):
        st.session_state.use_examples.append({"name": "", "url": "", "desc": ""})
        st.rerun()
    
    form_data['use_examples'] = use_examples
    
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


def save_material(form_data):
    """材料データを保存（upsert対応）"""
    db = SessionLocal()
    try:
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
        
        if existing_material:
            # UPDATE（既存レコードを更新）
            material = existing_material
            material_uuid = material.uuid  # UUIDは保持
            
            # 更新時：None は絶対に入れない（既存データを破壊しない）
            for k, v in form_data.items():
                if v is None:
                    continue  # None はスキップ（既存値を維持）
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
        
        db.flush()
        
        # 参照URL保存（既存のものは削除してから再作成）
        if existing_material:
            db.query(ReferenceURL).filter(ReferenceURL.material_id == material.id).delete()
        for ref in form_data.get('reference_urls', []):
            if ref.get('url'):
                ref_url = ReferenceURL(
                    material_id=material.id,
                    url=ref['url'],
                    url_type=ref.get('type'),
                    description=ref.get('desc')
                )
                db.add(ref_url)
        
        # 使用例保存（既存のものは削除してから再作成）
        if existing_material:
            db.query(UseExample).filter(UseExample.material_id == material.id).delete()
        for ex in form_data.get('use_examples', []):
            if ex.get('name'):
                use_ex = UseExample(
                    material_id=material.id,
                    example_name=ex['name'],
                    example_url=ex.get('url'),
                    description=ex.get('desc')
                )
                db.add(use_ex)
        
        db.commit()
        
        # R2 アップロード処理（material.id 確定後）
        uploaded_files = form_data.get('images', [])
        if uploaded_files and material.id:
            from utils.settings import get_flag
            from utils.r2_storage import upload_uploadedfile
            from utils.image_repo import upsert_image
            
            # 画像アップロードはフラグで制御
            enable_r2_upload = get_flag("ENABLE_R2_UPLOAD", True)
            # INIT_SAMPLE_DATA / SEED_SKIP_IMAGES の時は必ず False 扱い（安全）
            if get_flag("INIT_SAMPLE_DATA", False) or get_flag("SEED_SKIP_IMAGES", False):
                enable_r2_upload = False
            
            if enable_r2_upload:
                try:
                    # 最初のファイルを primary として扱う
                    if len(uploaded_files) > 0:
                        primary_file = uploaded_files[0]
                        r2_result = upload_uploadedfile(primary_file, material.id, "primary")
                        upsert_image(
                            db=db,
                            material_id=material.id,
                            kind="primary",
                            r2_key=r2_result["r2_key"],
                            public_url=r2_result["public_url"],
                            bytes=r2_result["bytes"],
                            mime=r2_result["mime"],
                            sha256=r2_result["sha256"],
                        )
                        db.commit()
                except Exception as e:
                    # R2 アップロード失敗はログだけ（材料保存は成功させる）
                    if os.getenv("DEBUG", "0") == "1":
                        import traceback
                        print(f"[R2] Upload failed (material_id={material.id}): {e}")
                        traceback.print_exc()
        
        # 成功時はdictを返す
        return {
            "ok": True,
            "action": action,
            "material_id": material.id,
            "uuid": material.uuid,
        }
        
    except Exception as e:
        db.rollback()
        import traceback
        # 失敗時はdictを返す（例外を再発生させない）
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        db.close()


def save_material_submission(form_data: dict, submitted_by: str = None):
    """
    材料投稿をmaterial_submissionsテーブルに保存（承認フロー用）
    
    Args:
        form_data: フォーム入力データ（_normalize_requiredで正規化済み）
        submitted_by: 投稿者情報（任意）
    
    Returns:
        dict: {"ok": True/False, "submission_id": int, "uuid": str, "error": str, "traceback": str}
    """
    db = SessionLocal()
    try:
        # 必須フィールドの補完（None/空文字列をデフォルト値で埋める）
        form_data = _normalize_required(form_data, existing=None)
        
        # payload_jsonにform_dataをJSON文字列として保存
        payload_json = json.dumps(form_data, ensure_ascii=False, default=str)
        
        # UUIDを生成
        submission_uuid = str(uuid.uuid4())
        
        # MaterialSubmissionを作成
        submission = MaterialSubmission(
            uuid=submission_uuid,
            status="pending",
            payload_json=payload_json,
            submitted_by=submitted_by if submitted_by and submitted_by.strip() else None
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)
        
        # 成功時はdictを返す
        return {
            "ok": True,
            "submission_id": submission.id,
            "uuid": submission.uuid,
        }
        
    except Exception as e:
        db.rollback()
        import traceback
        # 失敗時はdictを返す（例外を再発生させない）
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        db.close()


