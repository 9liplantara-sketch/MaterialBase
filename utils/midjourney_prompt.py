"""
Midjourney用プロンプト生成機能
"""
import json
from typing import Optional
from database import Material


def generate_midjourney_prompt(material: Material) -> str:
    """
    材料のDB値からMidjourney用プロンプトを生成
    
    Args:
        material: Materialオブジェクト
    
    Returns:
        Midjourney用プロンプト文字列
    """
    parts = []
    
    # 材料名
    if material.name_official:
        parts.append(material.name_official)
    
    # カテゴリ
    if material.category_main:
        parts.append(material.category_main)
    
    # 色
    if material.color_tags:
        try:
            colors = json.loads(material.color_tags)
            if isinstance(colors, list) and colors:
                parts.append(", ".join(colors))
        except (json.JSONDecodeError, TypeError):
            if isinstance(material.color_tags, str):
                parts.append(material.color_tags)
    
    # 透明性
    if material.transparency:
        transparency_map = {
            "透明": "transparent",
            "半透明": "translucent",
            "不透明": "opaque"
        }
        transparency_en = transparency_map.get(material.transparency, material.transparency)
        parts.append(transparency_en)
    
    # 質感・触感
    if material.tactile_tags:
        try:
            tactile = json.loads(material.tactile_tags)
            if isinstance(tactile, list) and tactile:
                parts.append(", ".join(tactile))
        except (json.JSONDecodeError, TypeError):
            if isinstance(material.tactile_tags, str):
                parts.append(material.tactile_tags)
    
    # 視覚的特徴
    if material.visual_tags:
        try:
            visual = json.loads(material.visual_tags)
            if isinstance(visual, list) and visual:
                parts.append(", ".join(visual))
        except (json.JSONDecodeError, TypeError):
            if isinstance(material.visual_tags, str):
                parts.append(material.visual_tags)
    
    # 加工方法（質感に関連）
    if material.processing_methods:
        try:
            methods = json.loads(material.processing_methods)
            if isinstance(methods, list) and methods:
                # 加工方法を英語化（必要に応じて）
                parts.append(f"processed by {', '.join(methods[:2])}")
        except (json.JSONDecodeError, TypeError):
            pass
    
    # 用途（文脈として）
    if material.use_categories:
        try:
            uses = json.loads(material.use_categories)
            if isinstance(uses, list) and uses:
                parts.append(f"for {', '.join(uses[:2])}")
        except (json.JSONDecodeError, TypeError):
            pass
    
    # プロンプトを組み立て
    prompt = ", ".join([p for p in parts if p])
    
    # スタイル指定を追加（オプション）
    style_suffix = ", high quality, detailed, material texture"
    prompt += style_suffix
    
    return prompt
