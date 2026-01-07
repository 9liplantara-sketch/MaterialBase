"""
画像表示の1本化モジュール
すべての画像表示をこのモジュール経由で行う
URL優先、フォールバックでローカルパス
Streamlit Cloud対応（キャッシュ対策含む）
"""
import os
import streamlit as st
from pathlib import Path
from PIL import Image as PILImage
from typing import Optional, Tuple, Union, Dict
from utils.paths import resolve_path


def get_display_image_source(
    image_record,
    project_root: Optional[Path] = None
) -> Optional[Union[str, PILImage.Image]]:
    """
    画像表示用のソースを取得（URL優先、フォールバックでローカルパス）
    
    Args:
        image_record: Image/UseExample/ProcessExampleImage/Materialオブジェクト
        project_root: プロジェクトルートのパス
    
    Returns:
        URL文字列、PILImage、またはNone
        - URLがある場合: URL文字列を返す（st.image()で直接使用可能）
        - URLがなくローカルパスがある場合: PILImageオブジェクトを返す
        - どちらもない場合: None
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    # URLを優先的にチェック
    url = None
    file_path = None
    
    # オブジェクトの種類に応じてURL/パスを取得（例外時もアプリは落ちない）
    try:
        if hasattr(image_record, 'url') and image_record.url:
            url = image_record.url
        elif hasattr(image_record, 'image_url') and image_record.image_url:
            url = image_record.image_url
        elif hasattr(image_record, 'texture_image_url') and image_record.texture_image_url:
            url = image_record.texture_image_url
    except Exception:
        # 例外時はurlをNoneのまま続行（アプリは落ちない）
        url = None
    
    # URLがある場合はそれを返す
    if url:
        return url
    
    # ローカルパスを取得（例外時もアプリは落ちない）
    try:
        if hasattr(image_record, 'file_path') and image_record.file_path:
            file_path = image_record.file_path
        elif hasattr(image_record, 'image_path') and image_record.image_path:
            file_path = image_record.image_path
        elif hasattr(image_record, 'texture_image_path') and image_record.texture_image_path:
            file_path = image_record.texture_image_path
        else:
            file_path = None
    except Exception:
        # 例外時はfile_pathをNoneのまま続行（アプリは落ちない）
        file_path = None
    
    # ローカルパスがある場合は画像を読み込んで返す（例外時もアプリは落ちない）
    if file_path:
        try:
            # パスを解決（複数の可能性を試す）
            resolved_paths = []
            
            # 1. 絶対パスの場合
            if Path(file_path).is_absolute():
                resolved_paths.append(Path(file_path))
            else:
                # 2. 相対パスの場合、複数の可能性を試す
                # uploads/ からの相対パス
                resolved_paths.append(project_root / "uploads" / file_path)
                # static/images/materials/ からの相対パス（統一構成対応）
                # file_pathが "1_image.jpg" のような形式の場合、材料名から推測
                if "_" in file_path and file_path[0].isdigit():
                    # material_id_filename 形式の場合
                    parts = file_path.split("_", 1)
                    if len(parts) == 2:
                        material_id = parts[0]
                        filename = parts[1]
                        # DBから材料名を取得してパスを構築（オプション）
                        # ここでは直接uploads/を試す
                        pass
                # プロジェクトルートからの相対パス
                resolved_paths.append(project_root / file_path)
                # static/images/ からの相対パス
                resolved_paths.append(project_root / "static" / "images" / file_path)
                # static/images/materials/ からの相対パス
                resolved_paths.append(project_root / "static" / "images" / "materials" / file_path)
                # そのまま
                resolved_paths.append(Path(file_path))
            
            # 最初に見つかったパスを使用（最新のファイルを優先）
            found_paths = []
            for resolved_path in resolved_paths:
                try:
                    if resolved_path.exists() and resolved_path.is_file():
                        # ファイルの更新日時を取得（最新のファイルを優先）
                        mtime = resolved_path.stat().st_mtime
                        found_paths.append((mtime, resolved_path))
                except Exception:
                    continue
            
            # 最新のファイルを選択（更新日時でソート）
            if found_paths:
                found_paths.sort(key=lambda x: x[0], reverse=True)
                resolved_path = found_paths[0][1]
                
                try:
                    # Streamlit Cloudでのキャッシュ対策: ファイルを強制的に再読み込み
                    # ファイルを開いてすぐにメモリに読み込む
                    with open(resolved_path, 'rb') as f:
                        pil_img = PILImage.open(f)
                        # 画像をメモリに読み込んでから閉じる（ファイルハンドルの問題を回避）
                        pil_img.load()
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
                        return pil_img
                except Exception as e:
                    # 読み込みエラーは無視してNoneを返す（アプリは落ちない）
                    if os.getenv("DEBUG_IMAGE", "false").lower() == "true":
                        print(f"画像読み込みエラー: {resolved_path} - {e}")
                    pass
        except Exception as e:
            # 読み込みエラーは無視してNoneを返す（アプリは落ちない）
            print(f"画像読み込みエラー: {file_path} - {e}")
            pass
    
    return None


def display_image_unified(
    image_source: Optional[Union[str, PILImage.Image]],
    caption: Optional[str] = None,
    width: Optional[int] = None,
    use_container_width: bool = False,
    placeholder_size: Tuple[int, int] = (400, 300)
):
    """
    統一画像表示関数（URLまたはPILImageを受け取り、st.image()で表示）
    画像が無い場合はプレースホルダーを表示（真っ白回避）
    例外時もアプリは落ちない（画像だけスキップ）
    
    Args:
        image_source: URL文字列、PILImage、またはNone
        caption: 画像キャプション
        width: 画像幅
        use_container_width: コンテナ幅を使用するか
        placeholder_size: プレースホルダーのサイズ（幅, 高さ）
    """
    try:
        if image_source:
            # URLまたはPILImageを表示（例外時もアプリは落ちない）
            try:
                st.image(image_source, caption=caption, width=width, use_container_width=use_container_width)
            except Exception:
                # 画像表示エラー時はプレースホルダーを表示（アプリは落ちない）
                image_source = None
        
        if not image_source:
            # プレースホルダーを表示（真っ白回避）
            try:
                placeholder = PILImage.new('RGB', placeholder_size, (240, 240, 240))
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(placeholder)
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
                except:
                    font = ImageFont.load_default()
                text = "画像なし"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw.text(
                    ((placeholder_size[0] - text_width) // 2, (placeholder_size[1] - text_height) // 2),
                    text,
                    fill=(150, 150, 150),
                    font=font
                )
                try:
                    st.image(placeholder, caption=caption or "プレースホルダー", width=width, use_container_width=use_container_width)
                except Exception:
                    # プレースホルダー表示も失敗した場合は何も表示しない（アプリは落ちない）
                    pass
            except Exception:
                # プレースホルダー生成も失敗した場合は何も表示しない（アプリは落ちない）
                pass
    except Exception:
        # 全体の例外時もアプリは落ちない（画像だけスキップ）
        pass

