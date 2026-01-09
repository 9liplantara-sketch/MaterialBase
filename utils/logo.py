"""
ロゴ表示ユーティリティ
SVGロゴをHTML inline SVGとして描画する
Unicode正規化（NFKC）でファイル名の表記ゆれに対応
"""
from pathlib import Path
from typing import Optional, Dict
import streamlit as st
import unicodedata
import os


def get_logo_paths() -> Dict[str, Path]:
    """
    ロゴファイルのパスを取得（Unicode正規化対応）
    
    Returns:
        dict: {"type_logo": Path, "mark": Path}
        ファイルが見つからない場合は、存在しないPathを返す
    """
    # プロジェクトルートを取得（utils/logo.py から見て ../）
    project_root = Path(__file__).resolve().parent.parent
    
    # ロゴディレクトリ
    logo_dir = project_root / "logo"
    
    # 期待するファイル名（NFKC正規化済み）
    expected_names = {
        "type_logo": unicodedata.normalize("NFKC", "タイプロゴ.svg"),
        "mark": unicodedata.normalize("NFKC", "ロゴマーク.svg")
    }
    
    # 結果辞書
    result = {
        "type_logo": logo_dir / expected_names["type_logo"],
        "mark": logo_dir / expected_names["mark"]
    }
    
    # logo_dirが存在する場合、実ファイル一覧を読み込んで正規化マッチング
    if logo_dir.exists() and logo_dir.is_dir():
        # 実ファイル一覧を取得
        actual_files = {}
        for file_path in logo_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == ".svg":
                # NFKC正規化したファイル名をキーに
                normalized_name = unicodedata.normalize("NFKC", file_path.name)
                actual_files[normalized_name] = file_path
        
        # 期待するファイル名とマッチング
        for key, expected_name in expected_names.items():
            if expected_name in actual_files:
                result[key] = actual_files[expected_name]
    
    return result


@st.cache_data
def read_svg(path: Path, mtime: float) -> Optional[str]:
    """
    SVGファイルをUTF-8で読み込む（キャッシュキーにmtimeを含める）
    
    Args:
        path: SVGファイルのパス
        mtime: ファイルの更新時刻（stat().st_mtime）
    
    Returns:
        SVGコンテンツ（文字列）、見つからなければNone
    """
    try:
        if path.exists() and path.is_file():
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"Warning: Failed to read SVG {path}: {e}")
    return None


def render_svg_inline(svg: str, height_px: int, class_name: str = "") -> str:
    """
    SVGをHTML inline SVGとして描画するためのHTMLを生成
    サイズはinline styleで確実に指定（CSSに依存しない）
    
    Args:
        svg: SVGコンテンツ（文字列、<svg>タグを含む可能性がある）
        height_px: 高さ（ピクセル）- この値が確実に適用される
        class_name: CSSクラス名（任意、余白や整列用）
    
    Returns:
        HTML文字列
    """
    # SVGが既に<svg>タグを含んでいる場合は、そのまま使用
    if "<svg" in svg.lower():
        # 既存の<svg>タグを使用し、style属性を追加/更新
        import re
        # style属性を追加または更新（既存のheight指定を上書き）
        if re.search(r'style\s*=', svg, re.IGNORECASE):
            # 既存のstyle属性からheightを削除してから追加（確実に指定値を適用）
            height_pattern = r'height\s*:\s*[^;]+;?'
            def replace_style(m):
                old_style = m.group(1)
                # heightを削除
                cleaned_style = re.sub(height_pattern, "", old_style, flags=re.IGNORECASE).strip()
                # セミコロンで区切って整理
                if cleaned_style and not cleaned_style.endswith(';'):
                    cleaned_style += ';'
                return f'style="{cleaned_style} height: {height_px}px !important; width: auto; max-width: 100%; vertical-align: middle;"'
            svg = re.sub(
                r'style\s*=\s*["\']([^"\']*)["\']',
                replace_style,
                svg,
                flags=re.IGNORECASE
            )
        else:
            # style属性がない場合は追加
            svg = re.sub(
                r'<svg([^>]*)>',
                f'<svg\\1 style="height: {height_px}px !important; width: auto; max-width: 100%; vertical-align: middle;">',
                svg,
                flags=re.IGNORECASE
            )
        
        class_attr = f' class="{class_name}"' if class_name else ""
        return f'<div{class_attr} style="display: inline-block; line-height: 0;">{svg}</div>'
    else:
        # <svg>タグがない場合は追加（通常は発生しない）
        class_attr = f' class="{class_name}"' if class_name else ""
        return f"""
        <div{class_attr} style="display: inline-block; line-height: 0;">
            <svg style="height: {height_px}px !important; width: auto; max-width: 100%; vertical-align: middle;" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
                {svg}
            </svg>
        </div>
        """


def render_type_logo(height_px: int = 36, fallback_text: str = "Material Map", debug: bool = False) -> str:
    """
    タイプロゴを描画（全ページ共通のヘッダー用）
    
    Args:
        height_px: ロゴの高さ（デフォルト36px）
        fallback_text: SVGが見つからない場合のフォールバックテキスト
        debug: デバッグ情報を表示するか
    
    Returns:
        HTML文字列（SVGまたはフォールバックテキスト）
    """
    paths = get_logo_paths()
    type_logo_path = paths["type_logo"]
    
    # ファイルの存在確認とmtime取得
    if type_logo_path.exists() and type_logo_path.is_file():
        mtime = type_logo_path.stat().st_mtime
        svg_content = read_svg(type_logo_path, mtime)
        
        if svg_content:
            return render_svg_inline(svg_content, height_px, "site-logo")
    
    # フォールバック：テキスト表示
    if debug:
        st.warning(f"⚠️ タイプロゴが見つかりません: {type_logo_path}")
        with st.expander("🔍 デバッグ情報", expanded=False):
            st.write(f"**探したパス**: `{type_logo_path}`")
            st.write(f"**存在**: {type_logo_path.exists()}")
            if type_logo_path.parent.exists():
                st.write(f"**logoディレクトリ内のファイル**:")
                logo_dir = type_logo_path.parent
                svg_files = [f.name for f in logo_dir.iterdir() if f.is_file() and f.suffix.lower() == ".svg"]
                for svg_file in svg_files[:20]:  # 先頭20件
                    st.write(f"- {svg_file}")
    
    return f'<div class="site-logo-fallback" style="font-size: {height_px}px; font-weight: 600; color: #1a1a1a;">{fallback_text}</div>'


def render_logo_mark(height_px: int = 72, debug: bool = False) -> Optional[str]:
    """
    ロゴマークを描画（ホーム画面専用）
    
    Args:
        height_px: ロゴの高さ（デフォルト72px、3/4サイズ）
        debug: デバッグ情報を表示するか
    
    Returns:
        HTML文字列（SVGが見つからない場合はNone）
    """
    paths = get_logo_paths()
    mark_path = paths["mark"]
    
    # ファイルの存在確認とmtime取得
    if mark_path.exists() and mark_path.is_file():
        mtime = mark_path.stat().st_mtime
        svg_content = read_svg(mark_path, mtime)
        
        if svg_content:
            return render_svg_inline(svg_content, height_px, "site-mark")
    
    # 見つからない場合
    if debug:
        with st.expander("🔍 ロゴマークが見つかりません", expanded=False):
            st.write(f"**探したパス**: `{mark_path}`")
            st.write(f"**存在**: {mark_path.exists()}")
            if mark_path.parent.exists():
                st.write(f"**logoディレクトリ内のファイル**:")
                logo_dir = mark_path.parent
                svg_files = [f.name for f in logo_dir.iterdir() if f.is_file() and f.suffix.lower() == ".svg"]
                for svg_file in svg_files[:20]:  # 先頭20件
                    st.write(f"- {svg_file}")
    
    return None


def render_site_header(subtitle: Optional[str] = None, debug: bool = False) -> str:
    """
    サイトヘッダーを描画（タイプロゴ + サブタイトル）
    サブタイトルはタイプロゴの下に配置（縦並び）
    
    Args:
        subtitle: サブタイトル（任意、例：「素材の可能性を探索するデータベース」）
        debug: デバッグ情報を表示するか
    
    Returns:
        HTML文字列
    """
    logo_html = render_type_logo(height_px=36, debug=debug)
    
    if subtitle:
        return f"""
        <div class="site-header">
            <div class="site-title-block">
                {logo_html}
                <div class="site-subtitle">
                    {subtitle}
                </div>
            </div>
        </div>
        """
    else:
        return f"""
        <div class="site-header">
            <div class="site-title-block">
                {logo_html}
            </div>
        </div>
        """


def show_logo_debug_info():
    """
    ロゴファイルのデバッグ情報を表示（DEBUG=1の時のみ）
    """
    if os.getenv("DEBUG", "0") != "1":
        return
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 ロゴファイル実在確認")
    
    # プロジェクトルートとlogoディレクトリ
    project_root = Path(__file__).resolve().parent.parent
    logo_dir = project_root / "logo"
    
    st.sidebar.write(f"**logoディレクトリ**: `{logo_dir}`")
    st.sidebar.write(f"**存在**: {logo_dir.exists()}")
    
    if logo_dir.exists() and logo_dir.is_dir():
        # ファイル一覧を取得
        svg_files = [f for f in logo_dir.iterdir() if f.is_file() and f.suffix.lower() == ".svg"]
        st.sidebar.write(f"**検出したSVGファイル数**: {len(svg_files)}")
        
        with st.sidebar.expander("検出したファイル一覧（先頭20件）", expanded=False):
            for svg_file in svg_files[:20]:
                st.write(f"- `{svg_file.name}`")
                if svg_file.exists():
                    st.write(f"  - サイズ: {svg_file.stat().st_size} bytes")
                    st.write(f"  - mtime: {svg_file.stat().st_mtime}")
        
        # 解決されたパス
        paths = get_logo_paths()
        st.sidebar.markdown("---")
        st.sidebar.write("**解決されたパス**:")
        
        for key, path in paths.items():
            st.sidebar.write(f"**{key}**:")
            st.sidebar.write(f"- パス: `{path}`")
            st.sidebar.write(f"- 存在: {path.exists()}")
            if path.exists():
                st.sidebar.write(f"- サイズ: {path.stat().st_size} bytes")
                st.sidebar.write(f"- mtime: {path.stat().st_mtime}")
            else:
                st.sidebar.warning(f"⚠️ {key}が見つかりません")
    else:
        st.sidebar.error("❌ logoディレクトリが存在しません")
