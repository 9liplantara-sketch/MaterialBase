"""
マテリアル画像生成モジュール
材料のイメージ画像を生成します
"""
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont
import numpy as np
import os
from pathlib import Path
from typing import Optional, Tuple


def generate_wood_texture(name, color_base=(139, 90, 43), size=(800, 600)):
    """木材テクスチャを生成"""
    img = Image.new('RGB', size, color_base)
    draw = ImageDraw.Draw(img)
    
    # 木目を描画
    width, height = size
    for i in range(0, height, 20):
        # 木目の線
        y = i + np.random.randint(-5, 5)
        color = tuple(max(0, min(255, c + np.random.randint(-20, 20))) for c in color_base)
        draw.line([(0, y), (width, y)], fill=color, width=2)
    
    # ノイズを追加
    noise = np.random.randint(-10, 10, (height, width, 3), dtype=np.int16)
    img_array = np.array(img).astype(np.int16)
    img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(img_array)
    
    # ぼかしで自然な質感に
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    
    return img


def generate_metal_texture(name, color_base=(192, 192, 192), size=(800, 600)):
    """金属テクスチャを生成"""
    img = Image.new('RGB', size, color_base)
    draw = ImageDraw.Draw(img)
    
    width, height = size
    
    # 金属の反射を模擬
    for i in range(0, width, 30):
        x = i
        gradient = Image.new('L', (1, height))
        for y in range(height):
            value = int(128 + 127 * np.sin(y / 50))
            gradient.putpixel((0, y), value)
        
        mask = gradient.resize((30, height))
        overlay = Image.new('RGB', (30, height), (255, 255, 255))
        img.paste(overlay, (x, 0), mask)
    
    # 微細なテクスチャ
    noise = np.random.randint(-15, 15, (height, width, 3), dtype=np.int16)
    img_array = np.array(img).astype(np.int16)
    img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(img_array)
    
    return img


def generate_plastic_texture(name, color_base=(200, 200, 200), size=(800, 600)):
    """プラスチックテクスチャを生成"""
    img = Image.new('RGB', size, color_base)
    
    # 滑らかなプラスチック感
    noise = np.random.randint(-5, 5, (size[1], size[0], 3), dtype=np.int16)
    img_array = np.array(img).astype(np.int16)
    img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(img_array)
    
    # 滑らかに
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    
    # 光沢を追加
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.1)
    
    return img


def generate_material_image(material_name, category, output_dir="uploads"):
    """材料のイメージ画像を生成"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # カテゴリに応じたテクスチャ生成
    if "木材" in category or "木" in category:
        # 木材の色を材料名に応じて変更
        wood_colors = {
            "カリン": (180, 140, 100),
            "栗": (139, 90, 43),
            "樫": (101, 67, 33),
        }
        color = wood_colors.get(material_name.split()[0] if " " in material_name else material_name, (139, 90, 43))
        img = generate_wood_texture(material_name, color)
    elif "金属" in category or "アルミ" in material_name or "ステンレス" in material_name or "真鍮" in material_name:
        # 金属の色を材料名に応じて変更
        metal_colors = {
            "アルミ": (192, 192, 192),
            "ステンレス": (220, 220, 220),
            "真鍮": (181, 166, 66),
        }
        color = metal_colors.get(material_name.split()[0] if " " in material_name else material_name, (192, 192, 192))
        img = generate_metal_texture(material_name, color)
    elif "プラスチック" in category or "PP" in material_name or "PE" in material_name or "PVC" in material_name:
        # プラスチックの色
        plastic_colors = {
            "PP": (255, 255, 200),
            "PE": (240, 240, 240),
            "PVC": (255, 255, 255),
        }
        color = plastic_colors.get(material_name.split()[0] if " " in material_name else material_name, (200, 200, 200))
        img = generate_plastic_texture(material_name, color)
    else:
        # デフォルト
        img = Image.new('RGB', (800, 600), (200, 200, 200))
    
    # ファイル名を生成（安全な形式）
    safe_name = "".join(c for c in material_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"{safe_name.replace(' ', '_')}.webp"
    filepath = output_path / filename
    
    # WebP形式で保存
    img.save(filepath, 'WEBP', quality=85)
    
    return str(filepath)


def ensure_material_image(material_name, category, material_id, db):
    """材料の画像が存在しない場合、生成してデータベースに登録"""
    from database import Image as ImageModel
    
    # 既存の画像をチェック
    existing = db.query(ImageModel).filter(ImageModel.material_id == material_id).first()
    if existing:
        return existing.file_path
    
    # 画像を生成
    try:
        image_path = generate_material_image(material_name, category)
        if not image_path:
            return None
            
        file_name = Path(image_path).name
        
        # データベースに登録
        db_image = ImageModel(
            material_id=material_id,
            file_path=file_name,
            image_type="generated",
            description=f"{material_name}の生成画像"
        )
        db.add(db_image)
        db.flush()
        
        print(f"  ✓ 画像生成: {file_name}")
        return file_name
    except Exception as e:
        print(f"  ✗ 画像生成エラー ({material_name}): {e}")
        import traceback
        traceback.print_exc()
        return None


# ========== 元素画像生成機能 ==========

def get_element_group_color(group: str) -> Tuple[int, int, int]:
    """元素分類に応じた色を返す（RGB）"""
    color_map = {
        "非金属": (144, 238, 144),      # ライトグリーン
        "金属": (255, 182, 193),        # ライトピンク
        "半金属": (221, 160, 221),      # プラム
        "ハロゲン": (255, 215, 0),      # ゴールド
        "貴ガス": (135, 206, 235),      # スカイブルー
        "アルカリ金属": (255, 99, 71),   # トマトレッド
        "アルカリ土類金属": (255, 165, 0), # オレンジ
        "遷移金属": (192, 192, 192),    # シルバー
        "ランタノイド": (173, 216, 230), # ライトブルー
        "アクチノイド": (70, 130, 180),  # スチールブルー
    }
    return color_map.get(group, (224, 224, 224))  # デフォルト: ライトグレー


def generate_element_image(
    symbol: str,
    atomic_number: int,
    group: str,
    size: Tuple[int, int] = (400, 400),
    output_dir: str = "static/images/elements"
) -> Optional[str]:
    """
    元素画像を生成（抽象的・図形的表現）
    
    Args:
        symbol: 元素記号（例: "H", "Fe"）
        atomic_number: 原子番号
        group: 元素分類
        size: 画像サイズ
        output_dir: 出力ディレクトリ
    
    Returns:
        生成された画像ファイルのパス（相対パス）
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 背景色を取得
    bg_color = get_element_group_color(group)
    
    # 画像を作成
    img = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(img)
    
    width, height = size
    center_x, center_y = width // 2, height // 2
    
    # 抽象的・図形的な装飾を追加
    # 1. 円形のグラデーション（中心から外側へ）
    for i in range(0, min(width, height) // 2, 10):
        # 色を整数のタプルに変換
        color = tuple(int(min(255, c + (255 - c) * (1 - i / (min(width, height) // 2)))) for c in bg_color)
        draw.ellipse(
            [center_x - i, center_y - i, center_x + i, center_y + i],
            outline=color,
            width=2
        )
    
    # 2. 幾何学的な線（対角線）
    line_color = tuple(int(min(255, c + 30)) for c in bg_color)
    draw.line([(0, 0), (width, height)], fill=line_color, width=2)
    draw.line([(width, 0), (0, height)], fill=line_color, width=2)
    
    # 3. 元素記号を中心に配置
    # フォントサイズを計算（画像サイズに応じて）
    font_size = min(width, height) // 4
    
    try:
        # システムフォントを試す
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
        except:
            # デフォルトフォント
            font = ImageFont.load_default()
    
    # テキストのサイズを取得
    bbox = draw.textbbox((0, 0), symbol, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 中心に配置
    text_x = center_x - text_width // 2
    text_y = center_y - text_height // 2
    
    # テキストを描画（白または黒、背景に応じて）
    # bg_colorが整数のタプルであることを確認
    bg_sum = sum(int(c) for c in bg_color)
    text_color = (255, 255, 255) if bg_sum < 400 else (0, 0, 0)
    draw.text((text_x, text_y), symbol, fill=text_color, font=font)
    
    # 原子番号を小さく表示（左上）
    atomic_font_size = font_size // 3
    try:
        atomic_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", atomic_font_size)
    except:
        try:
            atomic_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", atomic_font_size)
        except:
            atomic_font = ImageFont.load_default()
    
    atomic_text = str(atomic_number)
    atomic_bbox = draw.textbbox((0, 0), atomic_text, font=atomic_font)
    atomic_text_width = atomic_bbox[2] - atomic_bbox[0]
    draw.text((10, 10), atomic_text, fill=text_color, font=atomic_font)
    
    # ファイル名を生成
    filename = f"element_{atomic_number}_{symbol}.webp"
    filepath = output_path / filename
    
    # WebP形式で保存
    img.save(filepath, 'WEBP', quality=90)
    
    # 相対パスを返す
    try:
        return str(filepath.relative_to(Path.cwd()))
    except ValueError:
        # 相対パスに変換できない場合は、相対パス文字列を返す
        return str(Path(output_dir) / filename)


def ensure_element_image(
    symbol: str,
    atomic_number: int,
    group: str,
    output_dir: str = "static/images/elements"
) -> Optional[str]:
    """
    元素画像が存在しない場合、生成する
    
    Args:
        symbol: 元素記号
        atomic_number: 原子番号
        group: 元素分類
        output_dir: 出力ディレクトリ
    
    Returns:
        画像ファイルのパス（相対パス）、生成失敗時はNone
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 既存の画像をチェック
    filename = f"element_{atomic_number}_{symbol}.webp"
    filepath = output_path / filename
    
    if filepath.exists():
        try:
            return str(filepath.relative_to(Path.cwd()))
        except ValueError:
            return str(Path(output_dir) / filename)
    
    # 画像を生成
    try:
        generated_path = generate_element_image(symbol, atomic_number, group, output_dir=output_dir)
        return generated_path
    except Exception as e:
        print(f"  ✗ 元素画像生成エラー ({symbol}, {atomic_number}): {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_all_element_images(output_dir: str = "static/images/elements"):
    """
    118元素すべての画像を生成
    
    Args:
        output_dir: 出力ディレクトリ
    """
    import json
    
    # 元素データを読み込み
    elements_file = Path("data/elements.json")
    if not elements_file.exists():
        print(f"エラー: 元素データファイルが見つかりません: {elements_file}")
        return
    
    with open(elements_file, "r", encoding="utf-8") as f:
        elements = json.load(f)
    
    print(f"118元素すべての画像を生成します...")
    print("=" * 60)
    
    success_count = 0
    for element in elements:
        symbol = element.get("symbol", "")
        atomic_number = element.get("atomic_number", 0)
        group = element.get("group", "未分類")
        
        if not symbol or atomic_number == 0:
            continue
        
        try:
            image_path = ensure_element_image(symbol, atomic_number, group, output_dir)
            if image_path:
                success_count += 1
                print(f"  ✓ {atomic_number:3d} {symbol:3s} ({group})")
            else:
                print(f"  ✗ {atomic_number:3d} {symbol:3s} - 生成失敗")
        except Exception as e:
            print(f"  ✗ {atomic_number:3d} {symbol:3s} - エラー: {e}")
    
    print("=" * 60)
    print(f"✅ 画像生成完了: {success_count}/{len(elements)} 元素")

