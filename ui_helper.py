"""
UIヘルパー関数 - 画像処理とマテリアル感のあるデザイン要素
"""
import os
from pathlib import Path
import base64
from PIL import Image as PILImage
import io


def get_image_path(filename):
    """画像パスを取得"""
    # 複数のパスを試す
    possible_paths = [
        Path("static/images") / filename,
        Path("写真") / filename,
        Path(filename)
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    return None


def get_base64_image(image_path):
    """画像をBase64エンコード"""
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        except Exception as e:
            print(f"画像読み込みエラー: {e}")
            return None
    return None


def get_image_css_background(image_path, opacity=1.0):
    """画像をCSS背景として使用するための文字列を生成"""
    base64_img = get_base64_image(image_path)
    if base64_img:
        return f'url("data:image/webp;base64,{base64_img}")'
    return None


def create_material_texture_css(sub_image_path):
    """マテリアルテクスチャ用のCSSを生成"""
    base64_img = get_base64_image(sub_image_path)
    if base64_img:
        return f"""
        background-image: url("data:image/webp;base64,{base64_img}");
        background-size: 200%;
        background-position: center;
        opacity: 0.05;
        mix-blend-mode: multiply;
        """
    return ""


def resize_image_for_web(image_path, max_width=800, quality=85):
    """Web表示用に画像をリサイズ"""
    if not image_path or not os.path.exists(image_path):
        return None
    
    try:
        img = PILImage.open(image_path)
        # WebP形式の場合はそのまま、それ以外は変換
        if img.format != 'WEBP':
            # RGBに変換（RGBAの場合は背景を白に）
            if img.mode == 'RGBA':
                background = PILImage.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
        
        # リサイズ
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), PILImage.Resampling.LANCZOS)
        
        # Base64エンコード
        buffer = io.BytesIO()
        img.save(buffer, format='WEBP', quality=quality)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode()
    except Exception as e:
        print(f"画像処理エラー: {e}")
        return None


