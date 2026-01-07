"""
画像表示の1本化モジュール
すべての画像表示をこのモジュール経由で行う
safe_slug基準で統一、IMAGE_BASE_URL対応、差し替え運用対応
"""
import os
import streamlit as st
from pathlib import Path
from PIL import Image as PILImage
from typing import Optional, Tuple, Union, Dict, Literal
import re
import base64

try:
    from material_map_version import APP_VERSION
except ImportError:
    APP_VERSION = os.getenv("APP_VERSION", "dev")


def safe_slug_from_material(material) -> str:
    """
    材料オブジェクトからsafe_slugを生成（唯一のキー）
    
    Args:
        material: Materialオブジェクト
    
    Returns:
        safe_slug（パス安全な文字列）
    """
    material_name = getattr(material, 'name_official', None) or getattr(material, 'name', None) or ""
    slug = material_name.strip()
    forbidden_chars = r'[/\\:*?"<>|]'
    slug = re.sub(forbidden_chars, '_', slug)
    return slug


def get_material_image_ref(
    material,
    kind: Literal["primary", "space", "product"],
    project_root: Optional[Path] = None
) -> Tuple[Optional[Union[str, Path]], Dict]:
    """
    材料の画像参照を取得（safe_slug基準で統一、差し替え運用対応）
    
    優先順位:
    A. DBの明示URL（http/httpsのみ）
    B. IMAGE_BASE_URL が設定されていれば規約URLを組み立てて採用
    C. ローカルファイル fallback（リポジトリ内）
    D. 旧互換 fallback（日本語ディレクトリ）※ただし C が無い場合のみ
    
    Args:
        material: Materialオブジェクト
        kind: 画像の種類（"primary", "space", "product"）
        project_root: プロジェクトルートのパス
    
    Returns:
        (src, debug_info) のタプル
        - src: URL文字列、Pathオブジェクト、またはNone
        - debug_info: デバッグ情報の辞書
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    # safe_slugを生成（唯一のキー）
    safe_slug = safe_slug_from_material(material)
    
    # kindごとの相対パス
    if kind == "primary":
        relative_path = f"materials/{safe_slug}/primary.jpg"
    elif kind == "space":
        relative_path = f"materials/{safe_slug}/uses/space.jpg"
    elif kind == "product":
        relative_path = f"materials/{safe_slug}/uses/product.jpg"
    else:
        relative_path = None
    
    debug_info = {
        "kind": kind,
        "material_id": getattr(material, 'id', None),
        "material_name": getattr(material, 'name_official', None) or getattr(material, 'name', None),
        "safe_slug": safe_slug,
        "chosen_branch": None,
        "image_version_value": None,
        "candidate_urls": [],
        "candidate_paths": [],
        "failed_paths": [],
        "final_src_type": None,
        "final_url": None,
        "final_path": None,
        "final_path_exists": None,
        "size": None,
        "mtime": None,
    }
    
    # base_dirのディレクトリ一覧を取得（デバッグ用）
    base_dir = project_root / 'static' / 'images' / 'materials'
    if base_dir.exists():
        try:
            dirs = [d.name for d in base_dir.iterdir() if d.is_dir()]
            debug_info["base_dir_sample"] = sorted(dirs)[:20]  # 最初の20件
        except Exception as e:
            debug_info["base_dir_error"] = str(e)
    
    # A. DBの明示URL（http/httpsのみ）
    url = None
    
    if kind == "primary":
        url = getattr(material, 'texture_image_url', None)
    elif kind in ["space", "product"]:
        use_examples = getattr(material, 'use_examples', [])
        if use_examples:
            for use_ex in use_examples:
                use_domain = getattr(use_ex, 'domain', None) or ""
                # domainが"space"または"product"に一致するか、日本語で一致するか
                if (kind == "space" and ("space" in use_domain.lower() or "空間" in use_domain)) or \
                   (kind == "product" and ("product" in use_domain.lower() or "プロダクト" in use_domain)):
                    url = getattr(use_ex, 'image_url', None)
                    if url:
                        break
    
    if url and url.startswith(('http://', 'https://')):
        debug_info["candidate_urls"].append(url)
        separator = "&" if "?" in url else "?"
        image_version = os.getenv("IMAGE_VERSION") or APP_VERSION or "dev"
        url_with_cache = f"{url}{separator}v={image_version}"
        debug_info["chosen_branch"] = "db_url"
        debug_info["image_version_value"] = image_version
        debug_info["final_src_type"] = "url"
        debug_info["final_url"] = url_with_cache
        return url_with_cache, debug_info
    
    # B. IMAGE_BASE_URL が設定されていれば規約URLを組み立てて採用
    image_base_url = os.getenv("IMAGE_BASE_URL")
    if image_base_url and relative_path:
        base_url_clean = image_base_url.rstrip('/')
        base_url = f"{base_url_clean}/{relative_path}"
        debug_info["candidate_urls"].append(base_url)
        separator = "&" if "?" in base_url else "?"
        image_version = os.getenv("IMAGE_VERSION") or APP_VERSION or "dev"
        url_with_cache = f"{base_url}{separator}v={image_version}"
        debug_info["chosen_branch"] = "base_url"
        debug_info["image_version_value"] = image_version
        debug_info["final_src_type"] = "url"
        debug_info["final_url"] = url_with_cache
        return url_with_cache, debug_info
    
    # C. ローカルファイル fallback（リポジトリ内）
    if relative_path:
        local_path = project_root / "static" / "images" / relative_path
        
        abs_path = str(local_path.resolve())
        debug_info["candidate_paths"].append(abs_path)
        
        if local_path.exists() and local_path.is_file():
            debug_info["chosen_branch"] = "local"
            debug_info["final_src_type"] = "path"
            debug_info["final_path"] = abs_path
            debug_info["final_path_exists"] = True
            try:
                stat = local_path.stat()
                debug_info["size"] = stat.st_size
                debug_info["mtime"] = stat.st_mtime
            except Exception as e:
                debug_info["stat_error"] = str(e)
            return local_path, debug_info
        else:
            debug_info["failed_paths"].append({
                "path": abs_path,
                "exists": local_path.exists(),
                "is_file": local_path.is_file() if local_path.exists() else False
            })
    
    # D. 旧互換 fallback（日本語ディレクトリ）※ただし C が無い場合のみ
    if base_dir.exists():
        # material.name_official / material.name / aliases で一致するフォルダを探す
        candidates_raw = []
        material_name = getattr(material, 'name_official', None) or getattr(material, 'name', None) or ""
        if material_name:
            candidates_raw.append(material_name)
            # 注釈を除去
            name_without_annotation = re.sub(r'[（(].*?[）)]', '', material_name).strip()
            if name_without_annotation != material_name:
                candidates_raw.append(name_without_annotation)
        
        # name_aliases を分解
        aliases = getattr(material, "name_aliases", None)
        if aliases:
            if isinstance(aliases, list):
                candidates_raw.extend([str(x) for x in aliases if x])
            else:
                candidates_raw.extend([x.strip() for x in str(aliases).split(",") if x.strip()])
        
        # 実フォルダと照合
        for candidate_name in candidates_raw:
            if not candidate_name:
                continue
            old_safe_slug = candidate_name.strip()
            forbidden_chars = r'[/\\:*?"<>|]'
            old_safe_slug = re.sub(forbidden_chars, '_', old_safe_slug)
            
            old_material_dir = base_dir / old_safe_slug
            if old_material_dir.exists() and old_material_dir.is_dir():
                # kindに応じた画像パス
                if kind == "primary":
                    old_candidate = old_material_dir / "primary.jpg"
                elif kind == "space":
                    old_candidate = old_material_dir / "uses" / "space.jpg"
                elif kind == "product":
                    old_candidate = old_material_dir / "uses" / "product.jpg"
                else:
                    old_candidate = None
                
                if old_candidate:
                    abs_path = str(old_candidate.resolve())
                    debug_info["candidate_paths"].append(abs_path)
                    
                    if old_candidate.exists() and old_candidate.is_file():
                        debug_info["chosen_branch"] = "legacy_jp"
                        debug_info["final_src_type"] = "path"
                        debug_info["final_path"] = abs_path
                        debug_info["final_path_exists"] = True
                        debug_info["legacy_dir"] = old_safe_slug
                        try:
                            stat = old_candidate.stat()
                            debug_info["size"] = stat.st_size
                            debug_info["mtime"] = stat.st_mtime
                        except Exception as e:
                            debug_info["stat_error"] = str(e)
                        return old_candidate, debug_info
                    else:
                        debug_info["failed_paths"].append({
                            "path": abs_path,
                            "exists": old_candidate.exists(),
                            "is_file": old_candidate.is_file() if old_candidate.exists() else False
                        })
    
    # 見つからない場合
    debug_info["chosen_branch"] = "none"
    debug_info["final_src_type"] = None
    debug_info["final_path_exists"] = False
    return None, debug_info


def to_data_url(image_path: Path) -> Optional[str]:
    """
    画像ファイルをdata URLに変換
    
    Args:
        image_path: 画像ファイルのパス
    
    Returns:
        data URL文字列、またはNone
    """
    try:
        if not image_path.exists():
            return None
        
        with open(image_path, 'rb') as f:
            img_data = f.read()
        
        # 拡張子からMIMEタイプを判定
        ext = image_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
        }
        mime_type = mime_types.get(ext, 'image/jpeg')
        
        # base64エンコード
        base64_data = base64.b64encode(img_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    except Exception:
        return None


def display_image_unified(
    image_source: Optional[Union[str, Path, PILImage.Image]],
    caption: Optional[str] = None,
    width: Union[Literal["stretch", "content"], int, None] = "stretch",
    debug: Optional[Dict] = None
):
    """
    画像を統一的な方法で表示（URL/Path/PILImage対応）
    
    Args:
        image_source: URL文字列、Pathオブジェクト、またはPILImage
        caption: キャプション
        width: 幅（"stretch", "content", またはピクセル数）
        debug: デバッグ情報（DEBUG=1のときのみ表示）
    """
    if image_source is None:
        # プレースホルダーを表示
        st.markdown(
            f'<div style="width: 100%; height: 200px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; color: #666;">画像なし</div>',
            unsafe_allow_html=True
        )
        # DEBUG=1のときのみdebug情報を表示
        if debug and os.getenv("DEBUG", "0") == "1":
            with st.expander("🔍 デバッグ情報", expanded=False):
                st.json(debug)
        return
    
    try:
        if isinstance(image_source, str):
            # URLまたはdata URL
            if image_source.startswith(('http://', 'https://', 'data:')):
                # widthが"stretch"の場合はNoneに変換（Streamlitのデフォルト動作）
                width_param = None if width == "stretch" else width
                st.image(image_source, caption=caption, width=width_param)
            else:
                # ローカルパス文字列の場合はPathとして処理
                path = Path(image_source)
                if path.exists() and path.is_file():
                    img = PILImage.open(path)
                    if img.mode != 'RGB':
                        if img.mode in ('RGBA', 'LA', 'P'):
                            rgb_img = PILImage.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'RGBA':
                                rgb_img.paste(img, mask=img.split()[3])
                            elif img.mode == 'LA':
                                rgb_img.paste(img.convert('RGB'), mask=img.split()[1])
                            else:
                                rgb_img = img.convert('RGB')
                            img = rgb_img
                        else:
                            img = img.convert('RGB')
                    width_param = None if width == "stretch" else width
                    st.image(img, caption=caption, width=width_param)
                else:
                    display_image_unified(None, caption=caption, debug=debug)
        elif isinstance(image_source, Path):
            # Pathオブジェクト: PILで開いてst.imageに渡す
            if image_source.exists() and image_source.is_file():
                img = PILImage.open(image_source)
                if img.mode != 'RGB':
                    if img.mode in ('RGBA', 'LA', 'P'):
                        rgb_img = PILImage.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'RGBA':
                            rgb_img.paste(img, mask=img.split()[3])
                        elif img.mode == 'LA':
                            rgb_img.paste(img.convert('RGB'), mask=img.split()[1])
                        else:
                            rgb_img = img.convert('RGB')
                        img = rgb_img
                    else:
                        img = img.convert('RGB')
                width_param = None if width == "stretch" else width
                st.image(img, caption=caption, width=width_param)
            else:
                display_image_unified(None, caption=caption, debug=debug)
        elif isinstance(image_source, PILImage.Image):
            # PILImage
            width_param = None if width == "stretch" else width
            st.image(image_source, caption=caption, width=width_param)
        else:
            display_image_unified(None, caption=caption, debug=debug)
    except Exception as e:
        if os.getenv("DEBUG_IMAGE", "false").lower() == "true" or os.getenv("DEBUG", "0") == "1":
            st.error(f"画像表示エラー: {e}")
            if debug:
                with st.expander("🔍 デバッグ情報", expanded=False):
                    st.json(debug)
        display_image_unified(None, caption=caption, debug=debug)
