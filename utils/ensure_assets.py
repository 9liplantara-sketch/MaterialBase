"""
アセット確保モジュール
起動時に必要な生成物（画像など）が存在するかチェックし、不足分のみ生成
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
import os

from utils.paths import resolve_path, get_generated_dir


def check_image_file(filepath: Path) -> bool:
    """
    画像ファイルが有効かチェック（存在・サイズ・形式）
    
    Args:
        filepath: チェックするファイルのPath
    
    Returns:
        有効な画像ファイルならTrue
    """
    if not filepath.exists():
        return False
    
    # ファイルサイズが0バイトでないか
    if filepath.stat().st_size == 0:
        return False
    
    # 画像として読み込めるか
    try:
        with Image.open(filepath) as img:
            # RGBモードに変換可能か（RGBA等もOK）
            img.verify()
        return True
    except Exception:
        return False


def ensure_element_images() -> Dict[str, int]:
    """
    元素画像を確保（不足分のみ生成）
    
    Returns:
        統計情報の辞書: {"total": 総数, "existing": 存在数, "generated": 生成数, "failed": 失敗数}
    """
    from image_generator import ensure_element_image
    
    stats = {
        "total": 0,
        "existing": 0,
        "generated": 0,
        "failed": 0,
        "missing_files": []
    }
    
    try:
        # 元素データを読み込み
        elements_file = resolve_path("data/elements.json")
        if not elements_file.exists():
            print(f"警告: 元素データファイルが見つかりません: {elements_file}")
            return stats
        
        with open(elements_file, "r", encoding="utf-8") as f:
            elements = json.load(f)
        
        stats["total"] = len(elements)
        
        # 出力ディレクトリ（統一された場所）
        output_dir = get_generated_dir("elements")
        
        for element in elements:
            symbol = element.get("symbol", "")
            atomic_number = element.get("atomic_number", 0)
            group = element.get("group", "未分類")
            
            if not symbol or atomic_number == 0:
                continue
            
            # ファイル名（一意性確保）
            filename = f"element_{atomic_number}_{symbol}.png"
            filepath = output_dir / filename
            
            # 既存ファイルをチェック
            if check_image_file(filepath):
                stats["existing"] += 1
                continue
            
            # 画像を生成
            try:
                # 既存の生成関数を使用（直接PNG形式で生成）
                from image_generator import generate_element_image
                
                # PNG形式で直接生成
                generated_path = generate_element_image(
                    symbol=symbol,
                    atomic_number=atomic_number,
                    group=group,
                    size=(400, 400),
                    output_dir=str(output_dir)
                )
                
                # 生成されたパスを確認
                if generated_path:
                    gen_path = Path(generated_path)
                    if not gen_path.is_absolute():
                        # 相対パスの場合、複数の可能性を試す
                        possible_paths = [
                            output_dir / gen_path.name,
                            resolve_path(str(gen_path)),
                            gen_path
                        ]
                        gen_path = None
                        for pp in possible_paths:
                            if pp.exists():
                                gen_path = pp
                                break
                        
                        if gen_path is None:
                            # ファイル名から直接探す
                            gen_path = output_dir / f"element_{atomic_number}_{symbol}.webp"
                    
                    # WebPからPNGに変換（既存関数がWebPを生成する場合）
                    if gen_path.exists():
                        try:
                            with Image.open(gen_path) as img:
                                # RGBモードに変換（透明は白背景に合成）
                                if img.mode != 'RGB':
                                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                    if img.mode == 'RGBA':
                                        rgb_img.paste(img, mask=img.split()[3])
                                    else:
                                        rgb_img = img.convert('RGB')
                                    img = rgb_img
                                
                                # PNGとして保存
                                png_path = output_dir / filename
                                img.save(png_path, 'PNG', quality=95)
                            
                            # WebPファイルを削除（オプション、PNGが成功した場合のみ）
                            if filepath.exists() and gen_path.suffix == ".webp" and gen_path != filepath:
                                try:
                                    gen_path.unlink()
                                except:
                                    pass
                        except Exception as conv_e:
                            print(f"画像変換エラー ({symbol}, {atomic_number}): {conv_e}")
                    
                    # 最終的なPNGファイルをチェック
                    if check_image_file(filepath):
                        stats["generated"] += 1
                    else:
                        stats["failed"] += 1
                        stats["missing_files"].append(filename)
                else:
                    stats["failed"] += 1
                    stats["missing_files"].append(filename)
            except Exception as e:
                print(f"元素画像生成エラー ({symbol}, {atomic_number}): {e}")
                import traceback
                traceback.print_exc()
                stats["failed"] += 1
                stats["missing_files"].append(filename)
        
    except Exception as e:
        print(f"元素画像確保エラー: {e}")
        import traceback
        traceback.print_exc()
    
    return stats


def ensure_category_images() -> Dict[str, int]:
    """
    カテゴリ画像を確保（必要に応じて実装）
    
    Returns:
        統計情報の辞書
    """
    stats = {
        "total": 0,
        "existing": 0,
        "generated": 0,
        "failed": 0,
        "missing_files": []
    }
    
    # カテゴリ画像の生成が必要な場合、ここに実装
    # 現時点では空実装
    
    return stats


def ensure_process_example_images() -> Dict[str, int]:
    """
    加工例画像を確保（不足分のみ生成）
    
    Returns:
        統計情報の辞書
    """
    from utils.process_image_generator import get_process_example_image
    
    stats = {
        "total": 0,
        "existing": 0,
        "generated": 0,
        "failed": 0,
        "missing_files": []
    }
    
    # 主要な加工方法のリスト
    process_methods = [
        "射出成形",
        "圧縮成形",
        "3Dプリント（FDM）",
        "熱成形",
        "接着",
        "レーザー加工",
        "切削",
        "鋳造",
        "溶接",
        "塗装/コーティング"
    ]
    
    stats["total"] = len(process_methods)
    output_dir = get_generated_dir("process_examples")
    
    for method in process_methods:
        try:
            # 既存の関数を使用（内部で生成も行う）
            img_path = get_process_example_image(method, str(output_dir))
            
            if img_path:
                filepath = Path(img_path)
                if not filepath.is_absolute():
                    filepath = output_dir / Path(img_path).name
                
                if check_image_file(filepath):
                    stats["existing"] += 1
                else:
                    stats["generated"] += 1
            else:
                stats["failed"] += 1
                stats["missing_files"].append(f"{method}.png")
        except Exception as e:
            print(f"加工例画像生成エラー ({method}): {e}")
            stats["failed"] += 1
            stats["missing_files"].append(f"{method}.png")
    
    return stats


def ensure_all_assets() -> Dict[str, Dict[str, int]]:
    """
    すべてのアセットを確保
    
    Returns:
        各アセットタイプの統計情報を含む辞書
    """
    results = {}
    
    try:
        results["elements"] = ensure_element_images()
    except Exception as e:
        print(f"元素画像確保エラー: {e}")
        results["elements"] = {"error": str(e)}
    
    try:
        results["categories"] = ensure_category_images()
    except Exception as e:
        print(f"カテゴリ画像確保エラー: {e}")
        results["categories"] = {"error": str(e)}
    
    try:
        results["process_examples"] = ensure_process_example_images()
    except Exception as e:
        print(f"加工例画像確保エラー: {e}")
        results["process_examples"] = {"error": str(e)}
    
    return results

