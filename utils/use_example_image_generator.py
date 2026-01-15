"""
用途例画像生成モジュール
内装/プロダクト/建築などの用途イメージを生成
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

# get_flag を安全に import（ImportError でも落ちないようにする）
try:
    import utils.settings as settings
except Exception:
    # フォールバック: 安全側に倒す実装（画像処理を止める方向）
    def get_flag(key: str, default: bool = False) -> bool:
        # INIT_SAMPLE_DATA / SEED_SKIP_IMAGES は True を返す（画像処理を止める）
        if key in ("INIT_SAMPLE_DATA", "SEED_SKIP_IMAGES"):
            return True
        # ENABLE_IMAGE_DB_WRITE は False を返す（DB書き込みを止める）
        if key == "ENABLE_IMAGE_DB_WRITE":
            return False
        # その他は default を返す
        return default


def generate_use_example_image(
    material_name: str,
    use_title: str,
    domain: str,
    size: Tuple[int, int] = (400, 300),
    output_dir: str = "static/uses"
) -> Optional[str]:
    """
    用途例の画像を生成（抽象的・シンプルな表現）
    
    Args:
        material_name: 材料名
        use_title: 用途タイトル（例: "アルミ鍋"）
        domain: 領域（例: "キッチン", "建築", "内装"）
        size: 画像サイズ
        output_dir: 出力ディレクトリ
    
    Returns:
        生成された画像ファイルのパス（相対パス）
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 領域に応じた背景色
    domain_colors = {
        "キッチン": (255, 240, 230),  # ベージュ系
        "建築": (240, 240, 250),      # ライトブルー系
        "内装": (250, 250, 240),      # ライトイエロー系
        "プロダクト": (240, 250, 240), # ライトグリーン系
        "生活": (250, 240, 250),      # ライトピンク系
    }
    bg_color = domain_colors.get(domain, (245, 245, 245))
    
    # 画像を作成
    img = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(img)
    
    width, height = size
    
    # シンプルな図形的表現
    # 1. 中央に大きな円（用途のイメージ）
    center_x, center_y = width // 2, height // 2
    circle_radius = min(width, height) // 4
    
    # 円の色（材料に応じて）
    if "アルミ" in material_name:
        circle_color = (200, 200, 200)  # シルバー
    elif "ステンレス" in material_name:
        circle_color = (220, 220, 220)  # 白っぽい
    elif "真鍮" in material_name or "黄銅" in material_name:
        circle_color = (218, 165, 32)  # ゴールド
    elif "PP" in material_name or "PE" in material_name or "PVC" in material_name:
        circle_color = (200, 230, 255)  # ライトブルー
    else:
        circle_color = (180, 180, 180)  # グレー
    
    draw.ellipse(
        [center_x - circle_radius, center_y - circle_radius,
         center_x + circle_radius, center_y + circle_radius],
        fill=circle_color,
        outline=(150, 150, 150),
        width=2
    )
    
    # 2. テキストを配置
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # 用途タイトル（中央下）
    text_y = center_y + circle_radius + 20
    bbox = draw.textbbox((0, 0), use_title, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_x = center_x - text_width // 2
    draw.text((text_x, text_y), use_title, fill=(50, 50, 50), font=font_large)
    
    # 領域（左上）
    draw.text((10, 10), domain, fill=(100, 100, 100), font=font_small)
    
    # ファイル名を生成
    safe_title = "".join(c for c in use_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    filename = f"{material_name.replace(' ', '_')}_{safe_title}.png"
    filepath = output_path / filename
    
    # PNG形式で保存
    img.save(filepath, 'PNG', quality=95)
    
    # 相対パスを返す
    try:
        return str(filepath.relative_to(Path.cwd()))
    except ValueError:
        return str(Path(output_dir) / filename)


def ensure_use_example_image(
    material_name: str,
    use_title: str,
    domain: str,
    output_dir: str = "static/uses"
) -> Optional[str]:
    """
    用途例画像が存在しない場合、生成する
    
    Args:
        material_name: 材料名
        use_title: 用途タイトル
        domain: 領域
        output_dir: 出力ディレクトリ
    
    Returns:
        画像ファイルのパス（相対パス）、生成失敗時はNone
    """
    # DB書き込み許可フラグ（デフォルト False = Cloud/seedでは絶対書かない）
    # SEED_SKIP_IMAGES または INIT_SAMPLE_DATA が True の場合もスキップ
    # get_flag が無い場合に備えた二重化
    flag_fn = getattr(settings, "get_flag", None)
    if not callable(flag_fn):
        # フォールバック: os.getenv のみで判定
        import os
        def flag_fn(key, default=False):
            value = os.getenv(key)
            if value is None:
                return default
            value_str = str(value).lower().strip()
            return value_str in ("1", "true", "yes", "y", "on")
    
    if (flag_fn("SEED_SKIP_IMAGES", False) or 
        flag_fn("INIT_SAMPLE_DATA", False) or 
        not flag_fn("ENABLE_IMAGE_DB_WRITE", False)):
        print(f"[IMAGE] skip DB write: flags disabled (material: {material_name}, use: {use_title})")
        return None
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 既存の画像をチェック
    safe_title = "".join(c for c in use_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    filename = f"{material_name.replace(' ', '_')}_{safe_title}.png"
    filepath = output_path / filename
    
    if filepath.exists():
        try:
            return str(filepath.relative_to(Path.cwd()))
        except ValueError:
            return str(Path(output_dir) / filename)
    
    # 画像を生成
    try:
        generated_path = generate_use_example_image(material_name, use_title, domain, output_dir=output_dir)
        return generated_path
    except Exception as e:
        print(f"  ✗ 用途例画像生成エラー ({material_name}, {use_title}): {e}")
        import traceback
        traceback.print_exc()
        return None

