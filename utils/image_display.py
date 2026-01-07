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
import unicodedata
import re
from utils.paths import resolve_path

try:
    from material_map_version import APP_VERSION
except ImportError:
    # フォールバック: git SHAを直接取得
    import subprocess
    try:
        APP_VERSION = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        APP_VERSION = "no-git"


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
    
    # URLがある場合はそれを返す（http/https URLのみ）
    if url:
        # http/https URLの場合はそのまま返す（キャッシュバスターはdisplay_image_unifiedで追加）
        if url.startswith(('http://', 'https://')):
            return url
        # ローカルパス文字列の可能性がある場合は、後続の処理で判定
        # （ここではURLとして扱わない）
    
    # まず、staticのjpgを最優先で探索（DBパスより優先）
    # image_recordがMaterialオブジェクトの場合、材料名から統一構成のパスを探索
    material_name = None
    try:
        if hasattr(image_record, 'material_id') and image_record.material_id:
            # Imageオブジェクトの場合、material_idから材料名を取得
            from database import SessionLocal, Material
            db = SessionLocal()
            try:
                material = db.query(Material).filter(Material.id == image_record.material_id).first()
                if material:
                    material_name = material.name_official or material.name
            finally:
                db.close()
        elif hasattr(image_record, 'name_official'):
            material_name = image_record.name_official
        elif hasattr(image_record, 'name'):
            material_name = image_record.name
    except Exception:
        pass
    
    # 材料名がある場合、統一構成のパスを最優先で探索（正仕様: primary.jpgを最優先）
    if material_name:
        image_paths = find_material_image_paths(material_name, project_root)
        if image_paths.get('primary'):
            try:
                with open(image_paths['primary'], 'rb') as f:
                    pil_img = PILImage.open(f)
                    pil_img.load()
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
                if os.getenv("DEBUG_IMAGE", "false").lower() == "true":
                    print(f"統一構成画像読み込みエラー: {image_paths['primary']} - {e}")
                pass
    
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
    # staticのjpgを最優先、DBパスはフォールバック
    # 優先順位: staticのjpgを最優先、DBパスはフォールバック
    if file_path:
        try:
            # パスを解決（複数の可能性を試す）
            resolved_paths = []
            
            # 1. 絶対パスの場合
            if Path(file_path).is_absolute():
                resolved_paths.append(Path(file_path))
            else:
                # 2. 相対パスの場合、staticのjpgを最優先
                # static/images/materials/ からの相対パス（統一構成対応、最優先）
                # file_pathが "1_image.jpg" のような形式の場合、材料名から推測
                if "_" in file_path and file_path[0].isdigit():
                    # material_id_filename 形式の場合、DBから材料名を取得してパスを構築
                    try:
                        from database import SessionLocal, Material
                        db = SessionLocal()
                        try:
                            parts = file_path.split("_", 1)
                            if len(parts) == 2:
                                material_id = int(parts[0])
                                material = db.query(Material).filter(Material.id == material_id).first()
                                if material:
                                    material_name = material.name_official or material.name
                                    if material_name:
                                        # 統一構成のパスを最優先で追加
                                        import re
                                        safe_slug = material_name.strip()
                                        forbidden_chars = r'[/\\:*?"<>|]'
                                        safe_slug = re.sub(forbidden_chars, '_', safe_slug)
                                        # 正仕様: static/images/materials/{safe_slug}/primary.jpg (最優先)
                                        primary_jpg = project_root / "static" / "images" / "materials" / safe_slug / "primary.jpg"
                                        if primary_jpg.exists():
                                            resolved_paths.insert(0, primary_jpg)  # 最優先で追加
                                        # フォールバック: primary.png
                                        primary_png = project_root / "static" / "images" / "materials" / safe_slug / "primary.png"
                                        if primary_png.exists():
                                            resolved_paths.append(primary_png)
                                        # 旧仕様: primary/primary.* (最後のフォールバック)
                                        old_primary_jpg = project_root / "static" / "images" / "materials" / safe_slug / "primary" / "primary.jpg"
                                        if old_primary_jpg.exists():
                                            resolved_paths.append(old_primary_jpg)
                                        old_primary_png = project_root / "static" / "images" / "materials" / safe_slug / "primary" / "primary.png"
                                        if old_primary_png.exists():
                                            resolved_paths.append(old_primary_png)
                        finally:
                            db.close()
                    except Exception:
                        pass
                
                # static/images/materials/ からの相対パス（統一構成対応）
                resolved_paths.append(project_root / "static" / "images" / "materials" / file_path)
                # static/images/ からの相対パス
                resolved_paths.append(project_root / "static" / "images" / file_path)
                # uploads/ からの相対パス（フォールバック）
                resolved_paths.append(project_root / "uploads" / file_path)
                # プロジェクトルートからの相対パス
                resolved_paths.append(project_root / file_path)
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


def _normalize_key(s: str) -> str:
    """
    文字列をNFKC正規化して、全角スペース等も潰す
    
    Args:
        s: 正規化する文字列
    
    Returns:
        正規化された文字列
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("\u3000", " ")  # 全角スペース→半角
    return s.strip()


def _dir_map(base_dir: Path) -> dict[str, str]:
    """
    static/images/materials/* のフォルダ一覧を取得し、正規化キー→実フォルダ名の辞書を作る
    
    Args:
        base_dir: static/images/materials のパス
    
    Returns:
        正規化キー→実フォルダ名の辞書
    """
    m = {}
    if not base_dir.exists():
        return m
    for p in base_dir.iterdir():
        if p.is_dir():
            m[_normalize_key(p.name)] = p.name
    return m


def resolve_material_dir_name(material, base_dir: Path, safe_slug: str) -> tuple[str, dict]:
    """
    材料オブジェクトから実フォルダ名を解決（候補名×正規化×実フォルダ照合）
    
    Args:
        material: Materialオブジェクト
        base_dir: static/images/materials のパス
        safe_slug: 既存のsafe_slug（フォールバック用）
    
    Returns:
        (dir_name, debug_info) のタプル
        - dir_name: 解決されたフォルダ名
        - debug_info: デバッグ情報の辞書
    """
    dm = _dir_map(base_dir)
    
    candidates = []
    # できるだけ多めに候補を集める（存在しない属性は getattr で回避）
    for key in ["name_official", "name"]:
        v = getattr(material, key, None)
        if v:
            candidates.append(str(v))
    
    # safe_slugも候補に追加（現状互換）
    if safe_slug and safe_slug not in candidates:
        candidates.append(safe_slug)
    
    # name_aliases を分解したもの（カンマ区切り等）
    aliases = getattr(material, "name_aliases", None)
    if aliases:
        # listでもstrでもOKに
        if isinstance(aliases, list):
            candidates.extend([str(x) for x in aliases if x])
        else:
            # "A,B,C" などを想定
            candidates.extend([x.strip() for x in str(aliases).split(",") if x.strip()])
    
    chosen = None
    tried = []
    for c in candidates:
        nk = _normalize_key(c)
        tried.append((c, nk))
        if nk in dm:
            chosen = dm[nk]
            break
    
    if not chosen:
        chosen = safe_slug  # fallback
    
    debug = {
        "base_dir": str(base_dir),
        "candidates": candidates,
        "tried": tried,
        "dir_map_sample": list(dm.items())[:30],
        "chosen": chosen,
        "chosen_exists": (base_dir / chosen).exists() if chosen else False,
    }
    return chosen, debug


def find_material_image_paths(
    material_name: str,
    project_root: Optional[Path] = None,
    debug_info: Optional[Dict] = None,
    material_obj: Optional[object] = None
) -> Dict[str, Optional[Path]]:
    """
    材料の画像パスを探索（統一構成対応、表記ゆれ対応）
    
    探索順序（正仕様を最優先）:
    1. static/images/materials/{resolved_dir}/primary.jpg (最優先)
    2. static/images/materials/{resolved_dir}/primary.png (フォールバック)
    3. static/images/materials/{resolved_dir}/primary.webp (フォールバック)
    4. static/images/materials/{resolved_dir}/uses/space.jpg (最優先)
    5. static/images/materials/{resolved_dir}/uses/space.png (フォールバック)
    6. static/images/materials/{resolved_dir}/uses/product.jpg (最優先)
    7. static/images/materials/{resolved_dir}/uses/product.png (フォールバック)
    8. 旧仕様（primary/primary.*）は最後のフォールバック
    
    Args:
        material_name: 材料名
        project_root: プロジェクトルートのパス
        debug_info: デバッグ情報を格納する辞書（オプション）
        material_obj: Materialオブジェクト（表記ゆれ対応のため、指定推奨）
    
    Returns:
        {
            'primary': Path or None,
            'space': Path or None,
            'product': Path or None
        }
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    base_dir = project_root / 'static' / 'images' / 'materials'
    
    # 安全なスラッグに変換（フォールバック用）
    import re
    safe_slug = material_name.strip()
    forbidden_chars = r'[/\\:*?"<>|]'
    safe_slug = re.sub(forbidden_chars, '_', safe_slug)
    
    # material_objがある場合は表記ゆれ対応のフォルダ名解決を使用
    if material_obj is not None:
        dir_name, _ = resolve_material_dir_name(material_obj, base_dir, safe_slug)
        material_dir = base_dir / dir_name
    else:
        # material_objがない場合は従来通りsafe_slugを使用
        material_dir = base_dir / safe_slug
    
    result = {
        'primary': None,
        'space': None,
        'product': None
    }
    
    # デバッグ情報用
    if debug_info is not None:
        debug_info['material_name'] = material_name
        debug_info['safe_slug'] = safe_slug
        debug_info['material_dir'] = str(material_dir)
        debug_info['tried_paths'] = {'primary': [], 'space': [], 'product': []}
        debug_info['found_paths'] = {}
    
    # primary画像を探索（正仕様を最優先）
    # 1. static/images/materials/{safe_slug}/primary.jpg (最優先)
    primary_jpg = material_dir / 'primary.jpg'
    if primary_jpg.exists():
        result['primary'] = primary_jpg
        if debug_info is not None:
            debug_info['found_paths']['primary'] = str(primary_jpg)
    else:
        if debug_info is not None:
            debug_info['tried_paths']['primary'].append(str(primary_jpg))
        
        # 2. static/images/materials/{safe_slug}/primary.png (フォールバック)
        primary_png = material_dir / 'primary.png'
        if primary_png.exists():
            result['primary'] = primary_png
            if debug_info is not None:
                debug_info['found_paths']['primary'] = str(primary_png)
        else:
            if debug_info is not None:
                debug_info['tried_paths']['primary'].append(str(primary_png))
            
            # 3. static/images/materials/{safe_slug}/primary.webp (フォールバック)
            primary_webp = material_dir / 'primary.webp'
            if primary_webp.exists():
                result['primary'] = primary_webp
                if debug_info is not None:
                    debug_info['found_paths']['primary'] = str(primary_webp)
            else:
                if debug_info is not None:
                    debug_info['tried_paths']['primary'].append(str(primary_webp))
                
                # 8. 旧仕様: static/images/materials/{safe_slug}/primary/primary.* (最後のフォールバック)
                primary_dir = material_dir / 'primary'
                if primary_dir.exists():
                    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        old_primary_path = primary_dir / f'primary{ext}'
                        if old_primary_path.exists():
                            result['primary'] = old_primary_path
                            if debug_info is not None:
                                debug_info['found_paths']['primary'] = str(old_primary_path)
                            break
                        else:
                            if debug_info is not None:
                                debug_info['tried_paths']['primary'].append(str(old_primary_path))
    
    # uses画像を探索（正仕様を最優先）
    uses_dir = material_dir / 'uses'
    if uses_dir.exists():
        # space画像を探索
        # 4. static/images/materials/{safe_slug}/uses/space.jpg (最優先)
        space_jpg = uses_dir / 'space.jpg'
        if space_jpg.exists():
            result['space'] = space_jpg
            if debug_info is not None:
                debug_info['found_paths']['space'] = str(space_jpg)
        else:
            if debug_info is not None:
                debug_info['tried_paths']['space'].append(str(space_jpg))
            
            # 5. static/images/materials/{safe_slug}/uses/space.png (フォールバック)
            space_png = uses_dir / 'space.png'
            if space_png.exists():
                result['space'] = space_png
                if debug_info is not None:
                    debug_info['found_paths']['space'] = str(space_png)
            else:
                if debug_info is not None:
                    debug_info['tried_paths']['space'].append(str(space_png))
        
        # product画像を探索
        # 6. static/images/materials/{safe_slug}/uses/product.jpg (最優先)
        product_jpg = uses_dir / 'product.jpg'
        if product_jpg.exists():
            result['product'] = product_jpg
            if debug_info is not None:
                debug_info['found_paths']['product'] = str(product_jpg)
        else:
            if debug_info is not None:
                debug_info['tried_paths']['product'].append(str(product_jpg))
            
            # 7. static/images/materials/{safe_slug}/uses/product.png (フォールバック)
            product_png = uses_dir / 'product.png'
            if product_png.exists():
                result['product'] = product_png
                if debug_info is not None:
                    debug_info['found_paths']['product'] = str(product_png)
            else:
                if debug_info is not None:
                    debug_info['tried_paths']['product'].append(str(product_png))
    
    return result


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
                # ローカルパス（Pathまたはstrでファイルがexists）の場合はPILImageとして扱う
                # 重要: ローカルファイルパスには?v=を付けない（存在しないパスになるため）
                if isinstance(image_source, Path):
                    # Pathオブジェクトの場合は直接開く
                    if image_source.exists() and image_source.is_file():
                        pil_img = PILImage.open(image_source)
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
                        st.image(pil_img, caption=caption, width=width, use_container_width=use_container_width)
                    else:
                        image_source = None
                elif isinstance(image_source, str):
                    # 文字列の場合、http/https/data:で始まるか、ローカルファイルかを判定
                    if image_source.startswith(('http://', 'https://')):
                        # http/https URLの場合はキャッシュバスターを追加
                        separator = "&" if "?" in image_source else "?"
                        image_source_with_cache = f"{image_source}{separator}v={APP_VERSION}"
                        st.image(image_source_with_cache, caption=caption, width=width, use_container_width=use_container_width)
                    elif image_source.startswith('data:'):
                        # data:URLの場合はそのまま
                        st.image(image_source, caption=caption, width=width, use_container_width=use_container_width)
                    else:
                        # ローカルファイルパスの可能性がある場合
                        path = Path(image_source)
                        if path.exists() and path.is_file():
                            # PILImageとして開いて表示（キャッシュバスター不要）
                            pil_img = PILImage.open(path)
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
                            st.image(pil_img, caption=caption, width=width, use_container_width=use_container_width)
                        else:
                            # ファイルが存在しない場合はエラー
                            image_source = None
                else:
                    # PILImageの場合はそのまま
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

