"""
材料データのキャッシュ用ユーティリティ
ORMオブジェクトをdict化してキャッシュすることでDetachedInstanceErrorを防ぐ
"""
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database import Material


def freeze_material_row(material: Material) -> Dict[str, Any]:
    """
    Material ORMオブジェクトをdictに変換（表示に必要な最小限の項目のみ）
    
    Args:
        material: Material ORMオブジェクト
    
    Returns:
        材料データのdict（表示用）
    """
    return {
        "id": material.id,
        "uuid": material.uuid,
        "name_official": material.name_official,
        "name": getattr(material, "name", material.name_official),  # 後方互換
        "category_main": material.category_main,
        "category": getattr(material, "category", material.category_main),  # 後方互換
        "is_published": getattr(material, "is_published", 1),
        "is_deleted": getattr(material, "is_deleted", 0),
        "created_at": material.created_at.isoformat() if material.created_at else None,
        "updated_at": material.updated_at.isoformat() if material.updated_at else None,
        # 画像情報（一覧ではロードしないため常にNone）
        "primary_image_url": None,
        "primary_image_path": None,
    }


def freeze_material_full(material: Material) -> Dict[str, Any]:
    """
    Material ORMオブジェクトを完全なdictに変換（編集画面用）
    
    Args:
        material: Material ORMオブジェクト
    
    Returns:
        材料データの完全なdict（編集用）
    """
    data = {
        "id": material.id,
        "uuid": material.uuid,
        "name_official": material.name_official,
        "name_aliases": json.loads(material.name_aliases) if material.name_aliases else [],
        "supplier_org": material.supplier_org,
        "supplier_type": material.supplier_type,
        "supplier_other": material.supplier_other,
        "category_main": material.category_main,
        "category_other": material.category_other,
        "material_forms": json.loads(material.material_forms) if material.material_forms else [],
        "material_forms_other": material.material_forms_other,
        "origin_type": material.origin_type,
        "origin_other": material.origin_other,
        "origin_detail": material.origin_detail,
        "recycle_bio_rate": material.recycle_bio_rate,
        "recycle_bio_basis": material.recycle_bio_basis,
        "color_tags": json.loads(material.color_tags) if material.color_tags else [],
        "transparency": material.transparency,
        "hardness_qualitative": material.hardness_qualitative,
        "hardness_value": material.hardness_value,
        "weight_qualitative": material.weight_qualitative,
        "specific_gravity": material.specific_gravity,
        "water_resistance": material.water_resistance,
        "heat_resistance_temp": material.heat_resistance_temp,
        "heat_resistance_range": material.heat_resistance_range,
        "weather_resistance": material.weather_resistance,
        "processing_methods": json.loads(material.processing_methods) if material.processing_methods else [],
        "processing_other": material.processing_other,
        "equipment_level": material.equipment_level,
        "prototyping_difficulty": material.prototyping_difficulty,
        "use_categories": json.loads(material.use_categories) if material.use_categories else [],
        "use_other": material.use_other,
        "procurement_status": material.procurement_status,
        "cost_level": material.cost_level,
        "cost_value": material.cost_value,
        "cost_unit": material.cost_unit,
        "safety_tags": json.loads(material.safety_tags) if material.safety_tags else [],
        "safety_other": material.safety_other,
        "restrictions": material.restrictions,
        "visibility": material.visibility,
        "is_published": getattr(material, "is_published", 1),
        "is_deleted": getattr(material, "is_deleted", 0),
        "created_at": material.created_at.isoformat() if material.created_at else None,
        "updated_at": material.updated_at.isoformat() if material.updated_at else None,
    }
    
    # リレーション（eager load済みの場合のみ）
    if hasattr(material, "reference_urls") and material.reference_urls:
        data["reference_urls"] = [
            {
                "url": ref.url,
                "type": ref.url_type,
                "desc": ref.description,
            }
            for ref in material.reference_urls
        ]
    else:
        data["reference_urls"] = []
    
    if hasattr(material, "use_examples") and material.use_examples:
        data["use_examples"] = [
            {
                "name": ex.example_name,
                "url": ex.example_url,
                "desc": ex.description,
                "domain": ex.domain,
                "image_path": ex.image_path,
                "image_url": ex.image_url,
            }
            for ex in material.use_examples
        ]
    else:
        data["use_examples"] = []
    
    # 画像情報（eager load済みの場合のみ）
    if hasattr(material, "images") and material.images:
        primary_image = next((img for img in material.images if img.kind == "primary"), None)
        if primary_image:
            data["primary_image_url"] = primary_image.public_url or primary_image.url
            data["primary_image_path"] = primary_image.file_path
    else:
        data["primary_image_url"] = None
        data["primary_image_path"] = None
    
    return data
