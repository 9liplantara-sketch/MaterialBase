"""
画像表示の1本化モジュール
すべての画像表示をこのモジュール経由で行う
URL優先、フォールバックでローカルパス
"""
import streamlit as st
from pathlib import Path
from PIL import Image as PILImage
from typing import Optional, Tuple, Union, Dict
from utils.image_health import check_image_health, resolve_image_path, normalize_image_path
from utils.paths import resolve_path
from image_generator import ensure_material_image


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
            # パスを解決
            resolved_path = resolve_path(file_path) if not Path(file_path).is_absolute() else Path(file_path)
            
            if resolved_path.exists():
                pil_img = PILImage.open(resolved_path)
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
        except Exception:
            # 読み込みエラーは無視してNoneを返す（アプリは落ちない）
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


def get_material_image(
    material,
    project_root: Optional[Path] = None,
    auto_regenerate: bool = True
) -> Tuple[Optional[PILImage.Image], str, str]:
    """
    材料の画像を取得（健康状態チェック付き）
    
    Args:
        material: Materialオブジェクト
        project_root: プロジェクトルートのパス
        auto_regenerate: 画像が存在しない場合に自動再生成するか
    
    Returns:
        (PILImage, status, message) のタプル
        - PILImage: 画像オブジェクト（取得できない場合はNone）
        - status: "ok" | "missing" | "corrupt" | "blackout" | "regenerated" | "error"
        - message: ステータスメッセージ
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)
    
    # 材料に画像が登録されているか確認
    if not material.images:
        if auto_regenerate:
            # 自動再生成を試みる
            try:
                from database import SessionLocal
                db = SessionLocal()
                try:
                    image_path = ensure_material_image(
                        material.name_official or material.name,
                        material.category_main or material.category or "その他",
                        material.id,
                        db
                    )
                    db.commit()
                    if image_path:
                        # 再生成成功、再帰的に取得
                        return get_material_image(material, project_root, auto_regenerate=False)
                finally:
                    db.close()
            except Exception as e:
                return None, "error", f"画像再生成に失敗しました: {str(e)}"
        
        return None, "missing", "画像が登録されていません"
    
    # 最初の画像を使用
    img_record = material.images[0]
    
    # パスを正規化
    normalized_path = normalize_image_path(img_record.file_path, project_root)
    resolved_path = resolve_image_path(img_record.file_path, project_root)
    
    # 健康状態をチェック
    health = check_image_health(img_record.file_path, project_root)
    
    if health["status"] == "ok":
        # 正常な画像を読み込む
        try:
            pil_img = PILImage.open(resolved_path)
            # RGBモードに変換（表示時の問題を防ぐ）
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
            
            return pil_img, "ok", "画像は正常です"
        except Exception as e:
            return None, "error", f"画像の読み込みに失敗しました: {str(e)}"
    
    elif health["status"] == "blackout":
        # 黒画像の場合は再生成を試みる
        if auto_regenerate:
            try:
                from database import SessionLocal
                db = SessionLocal()
                try:
                    # 既存の画像レコードを削除
                    from database import Image as ImageModel
                    db.query(ImageModel).filter(ImageModel.id == img_record.id).delete()
                    
                    # 再生成
                    image_path = ensure_material_image(
                        material.name_official or material.name,
                        material.category_main or material.category or "その他",
                        material.id,
                        db
                    )
                    db.commit()
                    if image_path:
                        # 再生成成功、再帰的に取得
                        return get_material_image(material, project_root, auto_regenerate=False)
                finally:
                    db.close()
            except Exception as e:
                return None, "error", f"画像再生成に失敗しました: {str(e)}"
        
        return None, "blackout", f"画像が黒塗りです: {health['reason']}"
    
    elif health["status"] == "missing":
        # ファイル不存在の場合は再生成を試みる
        if auto_regenerate:
            try:
                from database import SessionLocal
                db = SessionLocal()
                try:
                    image_path = ensure_material_image(
                        material.name_official or material.name,
                        material.category_main or material.category or "その他",
                        material.id,
                        db
                    )
                    db.commit()
                    if image_path:
                        # 再生成成功、再帰的に取得
                        return get_material_image(material, project_root, auto_regenerate=False)
                finally:
                    db.close()
            except Exception as e:
                return None, "error", f"画像再生成に失敗しました: {str(e)}"
        
        return None, "missing", f"画像ファイルが存在しません: {health['reason']}"
    
    else:
        # その他のエラー
        return None, health["status"], health["reason"]


def display_material_image(
    material,
    caption: Optional[str] = None,
    width: Optional[int] = None,
    use_container_width: bool = False,
    project_root: Optional[Path] = None
):
    """
    材料の画像を表示（健康状態チェック付き、自動修復対応）
    
    Args:
        material: Materialオブジェクト
        caption: 画像キャプション
        width: 画像幅
        use_container_width: コンテナ幅を使用するか
        project_root: プロジェクトルートのパス
    """
    pil_img, status, message = get_material_image(material, project_root, auto_regenerate=True)
    
    if status == "ok" and pil_img:
        # 正常な画像を表示
        st.image(pil_img, caption=caption, width=width, use_container_width=use_container_width)
    elif status == "regenerated":
        # 再生成成功
        st.success(f"✅ 画像を再生成しました: {message}")
        # 再取得して表示
        pil_img, status, message = get_material_image(material, project_root, auto_regenerate=False)
        if status == "ok" and pil_img:
            st.image(pil_img, caption=caption, width=width, use_container_width=use_container_width)
    else:
        # エラー時はプレースホルダーを表示（決して黒画像は出さない）
        st.warning(f"⚠️ {message}")
        # プレースホルダー画像を生成
        placeholder = PILImage.new('RGB', (400, 300), (240, 240, 240))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(placeholder)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except:
            font = ImageFont.load_default()
        text = "画像なし"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            ((400 - text_width) // 2, (300 - text_height) // 2),
            text,
            fill=(150, 150, 150),
            font=font
        )
        st.image(placeholder, caption="プレースホルダー", width=width, use_container_width=use_container_width)


def find_material_image_paths(
    material_name_or_slug: str,
    project_root: Optional[Path] = None
) -> Dict[str, Optional[Path]]:
    """
    材料の画像パスを探索（統一構成に対応・命名規則100%対応）
    
    探索順序（拡張子優先順位: jpg > jpeg > png > webp）:
    1. static/images/materials/{safe_slug}/primary.jpg
    2. static/images/materials/{safe_slug}/primary.jpeg
    3. static/images/materials/{safe_slug}/primary.png
    4. static/images/materials/{safe_slug}/primary.webp
    5. static/images/materials/{safe_slug}/uses/space.jpg
    6. static/images/materials/{safe_slug}/uses/space.jpeg
    7. static/images/materials/{safe_slug}/uses/space.png
    8. static/images/materials/{safe_slug}/uses/space.webp
    9. static/images/materials/{safe_slug}/uses/product.jpg
    10. static/images/materials/{safe_slug}/uses/product.jpeg
    11. static/images/materials/{safe_slug}/uses/product.png
    12. static/images/materials/{safe_slug}/uses/product.webp
    
    旧仕様フォールバック（後方互換性）:
    - static/images/materials/{safe_slug}/primary/primary.*
    - static/images/materials/{safe_slug}/uses/{name}1.*
    - static/images/materials/{safe_slug}/uses/{name}2.*
    
    Args:
        material_name_or_slug: 材料名またはスラッグ
        project_root: プロジェクトルートのパス
    
    Returns:
        {
            'primary': Path or None,
            'space': Path or None,
            'product': Path or None
        }
    """
    if project_root is None:
        project_root = resolve_path('.')
    else:
        project_root = Path(project_root)
    
    # 安全なスラッグに変換
    import re
    safe_slug = material_name_or_slug.strip()
    forbidden_chars = r'[/\\:*?"<>|]'
    safe_slug = re.sub(forbidden_chars, '_', safe_slug)
    
    material_dir = project_root / 'static' / 'images' / 'materials' / safe_slug
    
    result = {
        'primary': None,
        'space': None,
        'product': None
    }
    
    # 拡張子優先順位: jpg > jpeg > png > webp
    ext_priority = ['.jpg', '.jpeg', '.png', '.webp']
    
    # primary画像を探索（新仕様: primary.{ext}）
    for ext in ext_priority:
        primary_path = material_dir / f'primary{ext}'
        if primary_path.exists():
            result['primary'] = primary_path
            break
    
    # 旧仕様フォールバック: primary/primary.*
    if result['primary'] is None:
        primary_dir = material_dir / 'primary'
        if primary_dir.exists():
            for ext in ext_priority:
                primary_path = primary_dir / f'primary{ext}'
                if primary_path.exists():
                    result['primary'] = primary_path
                    break
    
    # uses画像を探索
    uses_dir = material_dir / 'uses'
    if uses_dir.exists():
        # space画像を探索（新仕様: uses/space.{ext}）
        for ext in ext_priority:
            space_path = uses_dir / f'space{ext}'
            if space_path.exists():
                result['space'] = space_path
                break
        
        # 旧仕様フォールバック: uses/{name}1.*
        if result['space'] is None:
            for file_path in uses_dir.iterdir():
                if file_path.is_file() and re.match(rf'^{re.escape(material_name_or_slug)}1\..+$', file_path.name):
                    result['space'] = file_path
                    break
        
        # product画像を探索（新仕様: uses/product.{ext}）
        for ext in ext_priority:
            product_path = uses_dir / f'product{ext}'
            if product_path.exists():
                result['product'] = product_path
                break
        
        # 旧仕様フォールバック: uses/{name}2.*
        if result['product'] is None:
            for file_path in uses_dir.iterdir():
                if file_path.is_file() and re.match(rf'^{re.escape(material_name_or_slug)}2\..+$', file_path.name):
                    result['product'] = file_path
                    break
    
    return result


def display_material_image_paths(
    material_name_or_slug: str,
    caption_prefix: Optional[str] = None,
    project_root: Optional[Path] = None
):
    """
    材料の画像を表示（統一構成に対応、プレースホルダー対応）
    
    Args:
        material_name_or_slug: 材料名またはスラッグ
        caption_prefix: キャプションのプレフィックス（例: "材料: "）
        project_root: プロジェクトルートのパス
    """
    paths = find_material_image_paths(material_name_or_slug, project_root)
    
    # primary画像を表示
    if paths['primary']:
        caption = f"{caption_prefix or ''}メイン画像" if caption_prefix else "メイン画像"
        try:
            img = PILImage.open(paths['primary'])
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
            st.image(img, caption=caption, use_container_width=True)
        except Exception:
            display_image_unified(None, caption=caption)
    else:
        display_image_unified(None, caption=f"{caption_prefix or ''}メイン画像" if caption_prefix else "メイン画像")
    
    # uses画像を表示（space, product）
    if paths['space'] or paths['product']:
        col1, col2 = st.columns(2)
        
        with col1:
            if paths['space']:
                caption = f"{caption_prefix or ''}空間の使用例" if caption_prefix else "空間の使用例"
                try:
                    img = PILImage.open(paths['space'])
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
                    st.image(img, caption=caption, use_container_width=True)
                except Exception:
                    display_image_unified(None, caption=caption)
            else:
                display_image_unified(None, caption=f"{caption_prefix or ''}空間の使用例" if caption_prefix else "空間の使用例")
        
        with col2:
            if paths['product']:
                caption = f"{caption_prefix or ''}プロダクトの使用例" if caption_prefix else "プロダクトの使用例"
                try:
                    img = PILImage.open(paths['product'])
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
                    st.image(img, caption=caption, use_container_width=True)
                except Exception:
                    display_image_unified(None, caption=caption)
            else:
                display_image_unified(None, caption=f"{caption_prefix or ''}プロダクトの使用例" if caption_prefix else "プロダクトの使用例")


