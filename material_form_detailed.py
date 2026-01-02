"""
詳細仕様対応の材料登録フォーム
レイヤー①（必須）とレイヤー②（任意）を含む包括的なフォーム
"""
import streamlit as st
import uuid
import json
from database import SessionLocal, Material, Property, Image, MaterialMetadata, ReferenceURL, UseExample, init_db


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


def show_detailed_material_form():
    """詳細仕様対応の材料登録フォーム"""
    st.markdown('<h2 class="gradient-text">➕ 材料登録（詳細版）</h2>', unsafe_allow_html=True)
    
    st.info("📝 **レイヤー①（必須）**: 約10分で入力可能な基本情報\n\n**レイヤー②（任意）**: 後から追記できる詳細情報")
    
    # タブでレイヤー①とレイヤー②を分ける
    tab1, tab2 = st.tabs(["📋 レイヤー①：必須情報", "✨ レイヤー②：任意情報"])
    
    with tab1:
        form_data = show_layer1_form()
    
    with tab2:
        layer2_data = show_layer2_form()
        if form_data:
            form_data.update(layer2_data)
    
    # フォーム送信
    if form_data and st.button("✅ 材料を登録", type="primary", use_container_width=True):
        try:
            save_material(form_data)
            st.success("✅ 材料を登録しました！")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")


def show_layer1_form():
    """レイヤー①：必須情報フォーム"""
    form_data = {}
    
    st.markdown("### 1. 基本識別情報")
    
    col1, col2 = st.columns(2)
    with col1:
        form_data['name_official'] = st.text_input(
            "1-1 材料名（正式）*",
            key="name_official",
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
        form_data['supplier_org'] = st.text_input("組織名*", key="supplier_org")
    with col2:
        form_data['supplier_type'] = st.selectbox("種別*", SUPPLIER_TYPES, key="supplier_type")
        if form_data['supplier_type'] == "その他（自由記述）":
            form_data['supplier_other'] = st.text_input("その他（詳細）", key="supplier_other")
    
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
    
    form_data['origin_type'] = st.selectbox(
        "3-1 原料由来（一次分類）*",
        ORIGIN_TYPES,
        key="origin_type"
    )
    if form_data['origin_type'] == "その他（自由記述）":
        form_data['origin_other'] = st.text_input("その他（詳細）", key="origin_other")
    
    form_data['origin_detail'] = st.text_input(
        "3-2 原料詳細（具体名）*",
        placeholder="例：トウモロコシ由来PLA、木粉、ガラスカレット、菌糸体",
        key="origin_detail"
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
        key="equipment_level"
    )
    
    form_data['prototyping_difficulty'] = st.selectbox(
        "5-3 試作難易度*",
        DIFFICULTY_OPTIONS,
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
        key="visibility"
    )
    
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
    """材料データを保存"""
    db = SessionLocal()
    try:
        # UUID生成
        material_uuid = str(uuid.uuid4())
        
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
        
        # Material作成
        material = Material(
            uuid=material_uuid,
            name_official=form_data['name_official'],
            name_aliases=json.dumps(form_data.get('name_aliases', []), ensure_ascii=False),
            supplier_org=form_data['supplier_org'],
            supplier_type=form_data['supplier_type'],
            supplier_other=form_data.get('supplier_other'),
            category_main=form_data['category_main'],
            category_other=form_data.get('category_other'),
            material_forms=json.dumps(form_data['material_forms'], ensure_ascii=False),
            material_forms_other=form_data.get('material_forms_other'),
            origin_type=form_data['origin_type'],
            origin_other=form_data.get('origin_other'),
            origin_detail=form_data['origin_detail'],
            recycle_bio_rate=form_data.get('recycle_bio_rate'),
            recycle_bio_basis=form_data.get('recycle_bio_basis'),
            color_tags=json.dumps(form_data.get('color_tags', []), ensure_ascii=False),
            transparency=form_data['transparency'],
            hardness_qualitative=form_data['hardness_qualitative'],
            hardness_value=form_data.get('hardness_value'),
            weight_qualitative=form_data['weight_qualitative'],
            specific_gravity=form_data.get('specific_gravity'),
            water_resistance=form_data['water_resistance'],
            heat_resistance_temp=form_data.get('heat_resistance_temp'),
            heat_resistance_range=form_data['heat_resistance_range'],
            weather_resistance=form_data['weather_resistance'],
            processing_methods=json.dumps(form_data['processing_methods'], ensure_ascii=False),
            processing_other=form_data.get('processing_other'),
            equipment_level=form_data['equipment_level'],
            prototyping_difficulty=form_data['prototyping_difficulty'],
            use_categories=json.dumps(form_data['use_categories'], ensure_ascii=False),
            use_other=form_data.get('use_other'),
            procurement_status=form_data['procurement_status'],
            cost_level=form_data['cost_level'],
            cost_value=form_data.get('cost_value'),
            cost_unit=form_data.get('cost_unit'),
            safety_tags=json.dumps(form_data['safety_tags'], ensure_ascii=False),
            safety_other=form_data.get('safety_other'),
            restrictions=form_data.get('restrictions'),
            visibility=form_data['visibility'],
            # レイヤー②
            development_motives=json.dumps(form_data.get('development_motives', []), ensure_ascii=False),
            development_motive_other=form_data.get('development_motive_other'),
            development_background_short=form_data.get('development_background_short'),
            development_story=form_data.get('development_story'),
            tactile_tags=json.dumps(form_data.get('tactile_tags', []), ensure_ascii=False),
            tactile_other=form_data.get('tactile_other'),
            visual_tags=json.dumps(form_data.get('visual_tags', []), ensure_ascii=False),
            visual_other=form_data.get('visual_other'),
            sound_smell=form_data.get('sound_smell'),
            circularity=form_data.get('circularity'),
            certifications=json.dumps(form_data.get('certifications', []), ensure_ascii=False),
            certifications_other=form_data.get('certifications_other'),
            # 後方互換性
            name=form_data['name_official'],
            category=form_data['category_main']
        )
        
        db.add(material)
        db.flush()
        
        # 参照URL保存
        for ref in form_data.get('reference_urls', []):
            if ref.get('url'):
                ref_url = ReferenceURL(
                    material_id=material.id,
                    url=ref['url'],
                    url_type=ref.get('type'),
                    description=ref.get('desc')
                )
                db.add(ref_url)
        
        # 使用例保存
        for ex in form_data.get('use_examples', []):
            if ex.get('name'):
                use_ex = UseExample(
                    material_id=material.id,
                    example_name=ex['name'],
                    example_url=ex.get('url'),
                    description=ex.get('desc')
                )
                db.add(use_ex)
        
        # 画像保存（簡易版 - 実際にはファイル保存処理が必要）
        # TODO: 画像ファイルの保存処理を実装
        
        db.commit()
        return material
        
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

