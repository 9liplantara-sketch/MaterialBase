"""
材料seed用のユーティリティ（べき等性を保証）
get-or-createパターンで重複投入を防ぐ
"""
import json
from typing import Optional, Dict, Any, Tuple
from database import SessionLocal, Material, Property, Image, UseExample, ProcessExampleImage
from sqlalchemy.orm import Session


def get_or_create_material(
    db: Session,
    name_official: str,
    name: Optional[str] = None,
    **kwargs
) -> Tuple[Material, bool]:
    """
    材料を取得または作成（get-or-createパターン）
    
    Args:
        db: データベースセッション
        name_official: 正式名称（一意キーとして使用）
        name: 旧name（後方互換）
        **kwargs: Materialのその他の属性
    
    Returns:
        (Material, created) のタプル
        - Material: 取得または作成されたMaterialオブジェクト
        - created: True=新規作成, False=既存取得
    """
    # 既存の材料を検索（name_official優先、なければname）
    existing = db.query(Material).filter(
        Material.name_official == name_official
    ).first()
    
    if not existing and name:
        # name_officialで見つからない場合、nameで検索（後方互換）
        existing = db.query(Material).filter(
            Material.name == name
        ).first()
    
    if existing:
        # 既存の材料が見つかった場合は更新（必要に応じて）
        # ここでは既存データを優先するため、更新は行わない
        return existing, False
    
    # 新規作成
    material = Material(
        name_official=name_official,
        name=name or name_official,  # 後方互換
        **kwargs
    )
    db.add(material)
    # flushは呼び出し側で行う（トランザクション管理のため）
    return material, True


def get_or_create_property(
    db: Session,
    material_id: int,
    property_name: str,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    measurement_condition: Optional[str] = None
) -> Tuple[Optional[Property], bool]:
    """
    物性データを取得または作成（get-or-createパターン）
    
    Args:
        db: データベースセッション
        material_id: 材料ID
        property_name: 物性名（一意キーの一部）
        value: 値
        unit: 単位
        measurement_condition: 測定条件
    
    Returns:
        (Property, created) のタプル
    """
    # material_id が None の場合は即 return（最終安全策）
    if not material_id:
        print(f"[SEED] skip property: material_id is None (property: {property_name})")
        return None, False
    
    # 既存の物性データを検索（material_id + property_nameで一意）
    existing = db.query(Property).filter(
        Property.material_id == material_id,
        Property.property_name == property_name
    ).first()
    
    if existing:
        return existing, False
    
    # 新規作成
    prop = Property(
        material_id=material_id,
        property_name=property_name,
        value=value,
        unit=unit,
        measurement_condition=measurement_condition
    )
    db.add(prop)
    return prop, True


def get_or_create_use_example(
    db: Session,
    material_id: int,
    example_name: str,
    domain: Optional[str] = None,
    description: Optional[str] = None,
    image_path: Optional[str] = None,
    **kwargs
) -> Tuple[UseExample, bool]:
    """
    用途例を取得または作成（get-or-createパターン）
    
    Args:
        db: データベースセッション
        material_id: 材料ID
        example_name: 用途例名（一意キーの一部）
        domain: 領域
        description: 説明
        image_path: 画像パス
        **kwargs: UseExampleのその他の属性
    
    Returns:
        (UseExample, created) のタプル
    """
    # 既存の用途例を検索（material_id + example_nameで一意）
    existing = db.query(UseExample).filter(
        UseExample.material_id == material_id,
        UseExample.example_name == example_name
    ).first()
    
    if existing:
        return existing, False
    
    # 新規作成
    use_example = UseExample(
        material_id=material_id,
        example_name=example_name,
        domain=domain,
        description=description,
        image_path=image_path or "",
        **kwargs
    )
    db.add(use_example)
    return use_example, True

