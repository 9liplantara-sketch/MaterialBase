"""
周期表UIモジュール（実データ実装版）
JSONファイルから元素データを読み込み
"""
import streamlit as st
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from image_generator import ensure_element_image

# 周期表のレイアウト定義
# 構造: {周期: {族: 原子番号}}
PERIODIC_TABLE_LAYOUT = {
    1: {1: 1, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 2},
    2: {1: 3, 2: 4, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 5, 14: 6, 15: 7, 16: 8, 17: 9, 18: 10},
    3: {1: 11, 2: 12, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 13, 14: 14, 15: 15, 16: 16, 17: 17, 18: 18},
    4: {1: 19, 2: 20, 3: 21, 4: 22, 5: 23, 6: 24, 7: 25, 8: 26, 9: 27, 10: 28, 11: 29, 12: 30, 13: 31, 14: 32, 15: 33, 16: 34, 17: 35, 18: 36},
    5: {1: 37, 2: 38, 3: 39, 4: 40, 5: 41, 6: 42, 7: 43, 8: 44, 9: 45, 10: 46, 11: 47, 12: 48, 13: 49, 14: 50, 15: 51, 16: 52, 17: 53, 18: 54},
    6: {1: 55, 2: 56, 3: 57, 4: 72, 5: 73, 6: 74, 7: 75, 8: 76, 9: 77, 10: 78, 11: 79, 12: 80, 13: 81, 14: 82, 15: 83, 16: 84, 17: 85, 18: 86},
    7: {1: 87, 2: 88, 3: 89, 4: 104, 5: 105, 6: 106, 7: 107, 8: 108, 9: 109, 10: 110, 11: 111, 12: 112, 13: 113, 14: 114, 15: 115, 16: 116, 17: 117, 18: 118},
}

# ランタノイド（fブロック、周期6）
LANTHANIDES = [57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71]

# アクチノイド（fブロック、周期7）
ACTINIDES = [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103]

# 元素データの読み込み（キャッシュ）
@st.cache_data
def load_elements_data() -> Dict[int, Dict]:
    """元素データをJSONファイルから読み込む"""
    elements_file = Path("data/elements.json")
    
    if not elements_file.exists():
        st.error(f"元素データファイルが見つかりません: {elements_file}")
        return {}
    
    try:
        with open(elements_file, "r", encoding="utf-8") as f:
            elements_list = json.load(f)
        
        # 原子番号をキーとする辞書に変換
        elements_dict = {elem["atomic_number"]: elem for elem in elements_list}
        return elements_dict
    except Exception as e:
        st.error(f"元素データの読み込みエラー: {e}")
        return {}


def get_element_by_atomic_number(atomic_num: int) -> Optional[Dict]:
    """原子番号から元素データを取得"""
    elements = load_elements_data()
    return elements.get(atomic_num)


def get_element_by_symbol(symbol: str) -> Optional[Dict]:
    """元素記号から元素データを取得"""
    symbol_upper = symbol.upper().strip()
    elements = load_elements_data()
    for element in elements.values():
        if element.get("symbol", "").upper() == symbol_upper:
            return element
    return None


def get_element_by_name(name: str) -> Optional[Dict]:
    """元素名から元素データを取得（日本語・英語両方対応）"""
    name_lower = name.lower().strip()
    elements = load_elements_data()
    for element in elements.values():
        name_ja = element.get("name_ja", "").lower()
        name_en = element.get("name_en", "").lower()
        if name_lower in name_ja or name_lower in name_en:
            return element
    return None


def get_element_category_color(category: str) -> str:
    """元素カテゴリに応じた色を返す（HTMLカラーコード）"""
    from image_generator import get_element_group_color
    # RGBからHTMLカラーコードに変換
    rgb = get_element_group_color(category)
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def get_element_image_path(element: Dict) -> Optional[str]:
    """元素の画像パスを取得（存在しない場合は生成）"""
    from utils.paths import resolve_path, get_generated_dir
    
    if not element:
        return None
    
    atomic_number = element.get("atomic_number")
    symbol = element.get("symbol", "").upper()
    if not atomic_number or not symbol:
        return None
    
    # 統一された生成物ディレクトリを優先
    generated_dir = get_generated_dir("elements")
    
    # PNG形式を優先（次にWebP）
    filenames = [
        f"element_{atomic_number}_{symbol}.png",
        f"element_{atomic_number}_{symbol}.webp",
    ]
    
    # 画像パスを確認（生成物ディレクトリを優先）
    for filename in filenames:
        image_paths = [
            generated_dir / filename,
            resolve_path(f"static/images/elements/{filename}"),
            resolve_path(f"static/images/{filename}"),
            Path("static/images/elements") / filename,
            Path("static/images") / filename,
        ]
        
        for img_path in image_paths:
            if img_path.exists() and img_path.stat().st_size > 0:
                return str(img_path)
    
    # 画像が存在しない場合は生成を試みる
    try:
        from image_generator import generate_element_image
        group = element.get("group", "未分類")
        
        # PNG形式で生成
        generated_path = generate_element_image(
            symbol=symbol,
            atomic_number=atomic_number,
            group=group,
            size=(400, 400),
            output_dir=str(generated_dir)
        )
        
        if generated_path:
            gen_path = Path(generated_path)
            if not gen_path.is_absolute():
                gen_path = generated_dir / Path(generated_path).name
            
            # WebPからPNGに変換
            if gen_path.exists() and gen_path.suffix == ".webp":
                from PIL import Image as PILImage
                with PILImage.open(gen_path) as img:
                    if img.mode != 'RGB':
                        rgb_img = PILImage.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'RGBA':
                            rgb_img.paste(img, mask=img.split()[3])
                        else:
                            rgb_img = img.convert('RGB')
                        img = rgb_img
                    
                    png_path = generated_dir / f"element_{atomic_number}_{symbol}.png"
                    img.save(png_path, 'PNG', quality=95)
                    return str(png_path)
            
            if gen_path.exists():
                return str(gen_path)
    except Exception as e:
        print(f"元素画像生成エラー (原子番号 {atomic_number}): {e}")
        import traceback
        traceback.print_exc()
    
    return None


def show_periodic_table():
    """周期表ページを表示（材料×元素マッピング対応）"""
    st.markdown('<h2 class="section-title">元素周期表</h2>', unsafe_allow_html=True)
    
    # セッションステートの初期化
    if "selected_element_atomic_number" not in st.session_state:
        st.session_state.selected_element_atomic_number = None
    if "selected_material_id_for_elements" not in st.session_state:
        st.session_state.selected_material_id_for_elements = None
    
    # 材料選択セクション
    st.markdown("### 材料を選んで元素をハイライト")
    
    # 材料一覧を取得
    try:
        from app import get_all_materials
        materials = get_all_materials()
        
        if materials:
            material_options = {
                "材料を選択...": None
            }
            for m in materials:
                material_name = m.name_official or m.name or f"材料ID: {m.id}"
                material_options[material_name] = m.id
            
            selected_material_name = st.selectbox(
                "材料を選択",
                list(material_options.keys()),
                index=0,
                key="material_selector_periodic_table"
            )
            
            if selected_material_name and selected_material_name != "材料を選択...":
                st.session_state.selected_material_id_for_elements = material_options[selected_material_name]
            else:
                st.session_state.selected_material_id_for_elements = None
        else:
            st.info("材料が登録されていません。")
            st.session_state.selected_material_id_for_elements = None
    except Exception as e:
        st.warning(f"材料データの読み込みエラー: {e}")
        st.session_state.selected_material_id_for_elements = None
    
    st.markdown("---")
    
    # 検索フィルタ
    col1, col2, col3 = st.columns(3)
    with col1:
        search_atomic_number = st.number_input(
            "原子番号で検索",
            min_value=1,
            max_value=118,
            value=None,
            step=1,
            help="1-118の範囲で入力"
        )
    with col2:
        search_symbol = st.text_input(
            "元素記号で検索",
            placeholder="例: H, He, Li",
            help="元素記号を入力"
        )
    with col3:
        search_name = st.text_input(
            "元素名で検索",
            placeholder="例: 水素, ヘリウム",
            help="元素名を入力"
        )
    
    # 検索結果の処理（検索フィルタが入力された場合、セッションステートを更新）
    if search_atomic_number:
        st.session_state.selected_element_atomic_number = int(search_atomic_number)
    elif search_symbol:
        element = get_element_by_symbol(search_symbol)
        if element:
            st.session_state.selected_element_atomic_number = element["atomic_number"]
    elif search_name:
        element = get_element_by_name(search_name)
        if element:
            st.session_state.selected_element_atomic_number = element["atomic_number"]
    
    # 選択された材料の主要元素リストを取得
    highlighted_elements = set()
    selected_material = None
    if st.session_state.selected_material_id_for_elements:
        try:
            from app import get_material_by_id
            selected_material = get_material_by_id(st.session_state.selected_material_id_for_elements)
            if selected_material and selected_material.main_elements:
                import json
                try:
                    elements_list = json.loads(selected_material.main_elements)
                    if isinstance(elements_list, list):
                        highlighted_elements = set(int(e) for e in elements_list if isinstance(e, (int, str)) and str(e).isdigit())
                except:
                    pass
        except Exception as e:
            st.warning(f"材料データの取得エラー: {e}")
    
    # 選択された元素を取得
    selected_element = None
    if st.session_state.selected_element_atomic_number:
        selected_element = get_element_by_atomic_number(st.session_state.selected_element_atomic_number)
    
    # メインレイアウト：周期表（左）と詳細パネル（右）
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 周期表")
        
        # 選択された材料の情報を表示
        if selected_material and highlighted_elements:
            material_name = selected_material.name_official or selected_material.name or f"材料ID: {selected_material.id}"
            st.info(f"📌 **{material_name}** に含まれる元素をハイライト表示中（{len(highlighted_elements)}元素）")
        
        # 周期表の表示（ハイライト対応）
        render_periodic_table(
            selected_atomic_number=st.session_state.selected_element_atomic_number,
            highlighted_elements=highlighted_elements
        )
    
    with col_right:
        st.markdown("### 元素詳細")
        if selected_element:
            render_element_detail_panel(selected_element)
        elif selected_material and highlighted_elements:
            st.markdown(f"#### 選択中の材料: {material_name}")
            st.markdown(f"**含まれる主要元素**: {len(highlighted_elements)}元素")
            if highlighted_elements:
                elements_info = []
                for atomic_num in sorted(highlighted_elements):
                    element = get_element_by_atomic_number(atomic_num)
                    if element:
                        symbol = element.get("symbol", "")
                        name_ja = element.get("name_ja", "")
                        elements_info.append(f"{symbol} ({name_ja})")
                st.markdown(", ".join(elements_info))
        else:
            st.info("周期表から元素をクリックするか、検索フィルタを使用してください。")


def render_periodic_table(
    selected_atomic_number: Optional[int] = None,
    highlighted_elements: Optional[set] = None
):
    """周期表をレンダリング（材料×元素マッピング対応）"""
    if highlighted_elements is None:
        highlighted_elements = set()
    
    # 周期表のヘッダー（族番号）
    header_cols = st.columns(18)
    for i, col in enumerate(header_cols, 1):
        with col:
            st.markdown(f"<div style='text-align: center; font-size: 10px; color: #666; padding: 4px 0;'>{i}</div>", unsafe_allow_html=True)
    
    # 周期1-7の表示
    for period in range(1, 8):
        render_period_row(period, selected_atomic_number, highlighted_elements)
    
    # ランタノイド（fブロック）
    st.markdown("---")
    st.markdown("#### ランタノイド（fブロック）")
    render_f_block(LANTHANIDES, selected_atomic_number, highlighted_elements, section="lanthanides")
    
    # アクチノイド（fブロック）
    st.markdown("---")
    st.markdown("#### アクチノイド（fブロック）")
    render_f_block(ACTINIDES, selected_atomic_number, highlighted_elements, section="actinides")


def render_period_row(
    period: int,
    selected_atomic_number: Optional[int] = None,
    highlighted_elements: Optional[set] = None
):
    """周期の行をレンダリング（材料×元素マッピング対応）"""
    if highlighted_elements is None:
        highlighted_elements = set()
    
    cols = st.columns(18)
    
    layout = PERIODIC_TABLE_LAYOUT.get(period, {})
    
    for group in range(1, 19):
        with cols[group - 1]:
            atomic_num = layout.get(group, 0)
            
            if atomic_num == 0:
                # 空セル（keyは不要）
                st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
            else:
                element = get_element_by_atomic_number(atomic_num)
                if element:
                    is_selected = selected_atomic_number == atomic_num
                    is_highlighted = atomic_num in highlighted_elements
                    # keyを一意化: block="main", section="periodic", row=period, col=group
                    render_element_cell(
                        element, 
                        is_selected, 
                        is_highlighted,
                        block="main",
                        section="periodic",
                        row=period,
                        col=group
                    )


def render_f_block(
    atomic_numbers: List[int],
    selected_atomic_number: Optional[int] = None,
    highlighted_elements: Optional[set] = None,
    section: str = "fblock"
):
    """fブロック（ランタノイド・アクチノイド）をレンダリング（材料×元素マッピング対応）"""
    if highlighted_elements is None:
        highlighted_elements = set()
    
    cols = st.columns(15)
    
    for idx, atomic_num in enumerate(atomic_numbers):
        with cols[idx]:
            element = get_element_by_atomic_number(atomic_num)
            if element:
                is_selected = selected_atomic_number == atomic_num
                is_highlighted = atomic_num in highlighted_elements
                # keyを一意化: block="fblock", section=section, row=0, col=idx
                render_element_cell(
                    element, 
                    is_selected, 
                    is_highlighted,
                    block="fblock",
                    section=section,
                    row=0,
                    col=idx
                )


def render_element_cell(
    element: Dict, 
    is_selected: bool = False, 
    is_highlighted: bool = False,
    *,
    block: str = "main",
    section: str = "periodic",
    row: int = 0,
    col: int = 0
):
    """元素セルをレンダリング（クリック可能、材料×元素マッピング対応、key一意化対応）"""
    atomic_num = element["atomic_number"]
    symbol = element.get("symbol", f"E{atomic_num}")
    group = element.get("group", "未分類")
    bg_color = get_element_category_color(group)
    
    # 選択状態とハイライト状態のスタイル
    if is_selected:
        border_style = "3px solid #1a1a1a"
        bg_color_selected = "#FFD700"  # 選択時は金色
    elif is_highlighted:
        border_style = "2px solid #667eea"  # ハイライト時は青い枠
        bg_color_selected = bg_color  # 背景色はそのまま
    else:
        border_style = "1px solid #ccc"
        bg_color_selected = bg_color
    
    # ボタンkeyを一意化（block, section, row, colを含める）
    # これにより、周期表とfブロックで同じ原子番号でも重複しない
    button_key = f"ptbtn:{block}:{section}:{row}:{col}:{atomic_num}"
    
    # 開発時のみkey重複を検知（環境変数で制御）
    import os
    if os.getenv("DEBUG_KEYS") == "1":
        if not hasattr(st.session_state, '_button_keys'):
            st.session_state._button_keys = set()
        if button_key in st.session_state._button_keys:
            st.error(f"⚠️ Key重複検知: {button_key}")
        else:
            st.session_state._button_keys.add(button_key)
    
    # 元素名を取得（日本語優先）
    name = element.get("name_ja") or element.get("name_en") or f"Element {atomic_num}"
    
    # ハイライト時の追加スタイル
    highlight_style = ""
    if is_highlighted and not is_selected:
        # ハイライト時は背景色を少し明るく、影を追加
        highlight_style = f"""
        box-shadow: 0 0 8px 2px rgba(102, 126, 234, 0.6) !important;
        opacity: 1 !important;
        """
    
    # カスタムスタイルを先に適用
    st.markdown(
        f"""
        <style>
        button[key="{button_key}"] {{
            background-color: {bg_color_selected} !important;
            border: {border_style} !important;
            font-size: 11px !important;
            padding: 8px 4px !important;
            height: 60px !important;
            white-space: pre-line !important;
            line-height: 1.2 !important;
            {highlight_style}
        }}
        button[key="{button_key}"]:hover {{
            opacity: 0.8;
            transform: scale(1.05);
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
    
    if st.button(
        f"{atomic_num}\n{symbol}",
        key=button_key,
        width='stretch',
        help=f"{name} (原子番号: {atomic_num})"
    ):
        st.session_state.selected_element_atomic_number = atomic_num
        st.rerun()


def render_element_detail_panel(element: Dict):
    """元素詳細パネルをレンダリング（実データ）"""
    st.markdown("---")
    
    # 元素名（日本語優先）
    name_ja = element.get("name_ja", "")
    name_en = element.get("name_en", "")
    display_name = name_ja if name_ja else name_en
    
    # 元素画像を表示
    image_path = get_element_image_path(element)
    if image_path and Path(image_path).exists():
        try:
            from utils.image_display import display_image_unified
            display_image_unified(Path(image_path), caption=f"{display_name} ({element.get('symbol', '')})", width=200)
        except Exception as e:
            st.warning(f"画像の読み込みに失敗しました: {e}")
    
    st.markdown(f"### {display_name}")
    if name_ja and name_en:
        st.markdown(f"*{name_en}*")
    
    st.markdown(f"**元素記号**: {element.get('symbol', 'N/A')}")
    st.markdown(f"**原子番号**: {element.get('atomic_number', 'N/A')}")
    st.markdown(f"**周期**: {element.get('period', 'N/A')}")
    st.markdown(f"**分類**: {element.get('group', 'N/A')}")
    st.markdown(f"**状態**: {element.get('state', 'N/A')}")
    
    if element.get("notes"):
        st.markdown(f"**備考**: {element.get('notes')}")
    
    st.markdown("---")
    st.markdown("#### 出典")
    sources = element.get("sources", [])
    if sources:
        for source in sources:
            st.markdown(f"- **{source.get('name', 'N/A')}** ({source.get('license', 'N/A')})")
            if source.get("url"):
                st.markdown(f"  - {source.get('url')}")
    else:
        st.info("出典情報がありません。")

