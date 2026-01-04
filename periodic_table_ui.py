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


def show_periodic_table():
    """周期表ページを表示（UI先行実装）"""
    st.markdown('<h2 class="section-title">元素周期表</h2>', unsafe_allow_html=True)
    
    # セッションステートの初期化
    if "selected_element_atomic_number" not in st.session_state:
        st.session_state.selected_element_atomic_number = None
    
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
    
    # 選択された元素を取得
    selected_element = None
    if st.session_state.selected_element_atomic_number:
        selected_element = get_element_by_atomic_number(st.session_state.selected_element_atomic_number)
    
    # メインレイアウト：周期表（左）と詳細パネル（右）
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 周期表")
        
        # 周期表の表示
        render_periodic_table(st.session_state.selected_element_atomic_number)
    
    with col_right:
        st.markdown("### 元素詳細")
        if selected_element:
            render_element_detail_panel(selected_element)
        else:
            st.info("周期表から元素をクリックするか、検索フィルタを使用してください。")


def render_periodic_table(selected_atomic_number: Optional[int] = None):
    """周期表をレンダリング"""
    # 周期表のヘッダー（族番号）
    header_cols = st.columns(18)
    for i, col in enumerate(header_cols, 1):
        with col:
            st.markdown(f"<div style='text-align: center; font-size: 10px; color: #666; padding: 4px 0;'>{i}</div>", unsafe_allow_html=True)
    
    # 周期1-7の表示
    for period in range(1, 8):
        render_period_row(period, selected_atomic_number)
    
    # ランタノイド（fブロック）
    st.markdown("---")
    st.markdown("#### ランタノイド（fブロック）")
    render_f_block(LANTHANIDES, selected_atomic_number)
    
    # アクチノイド（fブロック）
    st.markdown("---")
    st.markdown("#### アクチノイド（fブロック）")
    render_f_block(ACTINIDES, selected_atomic_number)


def render_period_row(period: int, selected_atomic_number: Optional[int] = None):
    """周期の行をレンダリング"""
    cols = st.columns(18)
    
    layout = PERIODIC_TABLE_LAYOUT.get(period, {})
    
    for group in range(1, 19):
        with cols[group - 1]:
            atomic_num = layout.get(group, 0)
            
            if atomic_num == 0:
                # 空セル
                st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
            else:
                element = get_element_by_atomic_number(atomic_num)
                if element:
                    render_element_cell(element, selected_atomic_number == atomic_num)


def render_f_block(atomic_numbers: List[int], selected_atomic_number: Optional[int] = None):
    """fブロック（ランタノイド・アクチノイド）をレンダリング"""
    cols = st.columns(15)
    
    for idx, atomic_num in enumerate(atomic_numbers):
        with cols[idx]:
            element = get_element_by_atomic_number(atomic_num)
            if element:
                render_element_cell(element, selected_atomic_number == atomic_num)


def render_element_cell(element: Dict, is_selected: bool = False):
    """元素セルをレンダリング（クリック可能）"""
    atomic_num = element["atomic_number"]
    symbol = element.get("symbol", f"E{atomic_num}")
    group = element.get("group", "未分類")
    bg_color = get_element_category_color(group)
    
    # 選択状態のスタイル
    border_style = "3px solid #1a1a1a" if is_selected else "1px solid #ccc"
    bg_color_selected = "#FFD700" if is_selected else bg_color
    
    # ボタンとして表示（クリック可能）
    button_key = f"element_{atomic_num}"
    
    # 元素名を取得（日本語優先）
    name = element.get("name_ja") or element.get("name_en") or f"Element {atomic_num}"
    
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
        use_container_width=True,
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
            from PIL import Image as PILImage
            img = PILImage.open(image_path)
            st.image(img, caption=f"{display_name} ({element.get('symbol', '')})", width=200)
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

