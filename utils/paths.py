"""
パス解決ユーティリティ
プロジェクトルート基準の相対パスを解決（どこから実行しても同じパス）
"""
import os
from pathlib import Path
from typing import Optional


def project_root() -> Path:
    """
    プロジェクトルートディレクトリを取得
    
    Returns:
        プロジェクトルートのPathオブジェクト
    """
    # このファイル（utils/paths.py）の位置からプロジェクトルートを推定
    current_file = Path(__file__).resolve()
    # utils/paths.py なので、2階層上がプロジェクトルート
    root = current_file.parent.parent
    return root


def resolve_path(rel_path: str) -> Path:
    """
    プロジェクトルート基準の相対パスを絶対パスに解決
    
    Args:
        rel_path: プロジェクトルートからの相対パス（例: "static/generated/elements"）
    
    Returns:
        解決された絶対Pathオブジェクト
    """
    root = project_root()
    resolved = root / rel_path
    return resolved


def ensure_dir(path: Path) -> None:
    """
    ディレクトリが存在しない場合は作成
    
    Args:
        path: 作成するディレクトリのPath
    """
    path.mkdir(parents=True, exist_ok=True)


def get_generated_dir(subdir: Optional[str] = None) -> Path:
    """
    生成物ディレクトリのパスを取得（存在しない場合は作成）
    
    Args:
        subdir: サブディレクトリ名（例: "elements", "categories"）
    
    Returns:
        生成物ディレクトリのPath
    """
    if subdir:
        gen_dir = resolve_path(f"static/generated/{subdir}")
    else:
        gen_dir = resolve_path("static/generated")
    ensure_dir(gen_dir)
    return gen_dir

