"""
材料データアクセスサービス層
DBアクセスを集約し、UI層からDB層を分離
"""
import os
import logging
from typing import List, Dict, Any, Optional
from utils.db import get_session, DBUnavailableError
from database import Material, Property, Image
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, noload, load_only

logger = logging.getLogger(__name__)

# DEBUG_ENV=1 の時のみDBアクセスログを出力
DEBUG_ENV = os.getenv("DEBUG_ENV", "0") == "1"

# 重いクエリガード: 一覧取得の上限（Neon節約のため）
MAX_LIST_LIMIT = 200


def _log_db_call(kind: str, **kwargs):
    """
    DBアクセスログを出力（DEBUG_ENV=1時のみ）
    
    Args:
        kind: DB呼び出し種別（count/page/list/detail/statistics）
        **kwargs: メタ情報（limit, offset等）
    """
    if DEBUG_ENV:
        # メタ情報をdict形式で出力（UI層でのパースは不要）
        meta = {k: v for k, v in kwargs.items()}
        logger.info(f"[DB_CALL] kind={kind} meta={meta}")


def get_material_count(
    include_unpublished: bool = False,
    include_deleted: bool = False
) -> int:
    """
    材料件数を取得
    
    Args:
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
    
    Returns:
        材料件数
    
    Raises:
        DBUnavailableError: DB接続エラー時
    """
    _log_db_call("count", include_unpublished=include_unpublished, include_deleted=include_deleted)
    
    try:
        with get_session() as db:
            stmt = select(func.count()).select_from(Material)
            
            if not include_deleted:
                if hasattr(Material, 'is_deleted'):
                    stmt = stmt.filter(Material.is_deleted == 0)
            
            if not include_unpublished:
                if hasattr(Material, 'is_published'):
                    stmt = stmt.filter(Material.is_published == 1)
            
            count = db.execute(stmt).scalar_one()
            return count
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'connect', 'network', 'timeout', 'refused', 'closed']):
            raise DBUnavailableError(f"データベース接続エラー: {e}") from e
        raise


def get_materials_page(
    include_unpublished: bool = False,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    search_query: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    材料一覧をページングで取得（dict化して返す）
    
    Args:
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
        limit: 取得件数（MAX_LIST_LIMIT=200で上限適用）
        offset: オフセット
        search_query: 検索クエリ（材料名）
    
    Returns:
        材料のdictリスト
    
    Raises:
        DBUnavailableError: DB接続エラー時
    """
    # 重いクエリガード: limitを上限でclamp
    limit = min(limit, MAX_LIST_LIMIT)
    
    _log_db_call("page", limit=limit, offset=offset, include_unpublished=include_unpublished, include_deleted=include_deleted)
    
    try:
        from utils.material_cache import freeze_material_row
        
        with get_session() as db:
            # 一覧表示用：必要な列だけをロードし、リレーションは全てnoload（高速化）
            stmt = (
                select(Material)
                .options(
                    # 必要な列だけをロード（パフォーマンス向上）
                    load_only(
                        Material.id,
                        Material.uuid,
                        Material.name_official,
                        Material.name,  # 後方互換
                        Material.category_main,
                        Material.category,  # 後方互換
                        Material.is_published,
                        Material.is_deleted,
                        Material.created_at,
                        Material.updated_at,
                    ),
                    # リレーションは全てnoload（一覧では不要）
                    noload(Material.properties),
                    noload(Material.images),
                    noload(Material.reference_urls),
                    noload(Material.use_examples),
                    noload(Material.metadata_items),
                    noload(Material.process_example_images),
                )
            )
            
            # フィルタ
            if not include_deleted:
                if hasattr(Material, 'is_deleted'):
                    stmt = stmt.filter(Material.is_deleted == 0)
            
            if not include_unpublished:
                if hasattr(Material, 'is_published'):
                    stmt = stmt.filter(Material.is_published == 1)
            
            # 検索クエリ
            if search_query and search_query.strip():
                stmt = stmt.filter(Material.name_official.ilike(f"%{search_query.strip()}%"))
            
            # ソート
            stmt = stmt.order_by(
                Material.created_at.desc() if hasattr(Material, 'created_at') else Material.id.desc()
            )
            
            # ページング
            stmt = stmt.limit(limit).offset(offset)
            
            # 実行
            result = db.execute(stmt)
            materials = result.unique().scalars().all()
            
            # material_idsを取得して画像情報とpropertiesを一括取得（N+1問題を回避）
            material_ids = [m.id for m in materials]
            primary_images_dict = {}  # {material_id: public_url}
            properties_dict = {}  # {material_id: [Property, ...]}
            
            if material_ids:
                # primary画像を一括取得
                images_stmt = select(Image).filter(
                    Image.material_id.in_(material_ids),
                    Image.kind == "primary"
                )
                images_result = db.execute(images_stmt)
                images = images_result.scalars().all()
                for img in images:
                    if img.public_url:
                        primary_images_dict[img.material_id] = img.public_url
                
                # propertiesを一括取得（表示用、最大3件まで）
                properties_stmt = select(Property).filter(
                    Property.material_id.in_(material_ids)
                )
                properties_result = db.execute(properties_stmt)
                properties_list = properties_result.scalars().all()
                for prop in properties_list:
                    if prop.material_id not in properties_dict:
                        properties_dict[prop.material_id] = []
                    # Propertyオブジェクトをdict化（DetachedInstanceErrorを防ぐ）
                    prop_dict = {
                        "property_name": prop.property_name,
                        "value": prop.value,
                        "unit": prop.unit,
                    }
                    properties_dict[prop.material_id].append(prop_dict)
            
            # dict化（DetachedInstanceErrorを防ぐ、scalar列のみ参照、画像URLとpropertiesも含める）
            material_dicts = []
            for m in materials:
                d = freeze_material_row(m)
                # primary画像のpublic_urlを追加
                d["primary_image_url"] = primary_images_dict.get(m.id)
                # propertiesを追加（表示用、最大3件まで）
                d["properties"] = properties_dict.get(m.id, [])[:3]
                material_dicts.append(d)
            
            return material_dicts
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'connect', 'network', 'timeout', 'refused', 'closed']):
            raise DBUnavailableError(f"データベース接続エラー: {e}") from e
        raise


def get_all_materials(
    include_unpublished: bool = False,
    include_deleted: bool = False
) -> List[Material]:
    """
    全材料を取得（Eager Loadでリレーションも先読み）
    
    Args:
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
    
    Returns:
        Materialオブジェクトのリスト（MAX_LIST_LIMIT=200件まで）
    
    Raises:
        DBUnavailableError: DB接続エラー時
    
    Note:
        - 重いクエリガード: 内部的にMAX_LIST_LIMIT=200を適用（無制限禁止）
    """
    _log_db_call("list", include_unpublished=include_unpublished, include_deleted=include_deleted)
    
    try:
        with get_session() as db:
            stmt = (
                select(Material)
                .options(
                    selectinload(Material.properties),
                    selectinload(Material.images),
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.metadata_items),
                    selectinload(Material.process_example_images),
                )
            )
            
            if not include_deleted:
                if hasattr(Material, 'is_deleted'):
                    stmt = stmt.filter(Material.is_deleted == 0)
            
            if not include_unpublished:
                if hasattr(Material, 'is_published'):
                    stmt = stmt.filter(Material.is_published == 1)
            
            stmt = stmt.order_by(
                Material.created_at.desc() if hasattr(Material, 'created_at') else Material.id.desc()
            )
            
            # 重いクエリガード: MAX_LIST_LIMITを適用
            stmt = stmt.limit(MAX_LIST_LIMIT)
            
            result = db.execute(stmt)
            materials = result.unique().scalars().all()
            return materials
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'connect', 'network', 'timeout', 'refused', 'closed']):
            raise DBUnavailableError(f"データベース接続エラー: {e}") from e
        raise


def get_material_by_id(material_id: int) -> Optional[Material]:
    """
    材料IDで取得
    
    Args:
        material_id: 材料ID
    
    Returns:
        Materialオブジェクト（見つからない場合はNone）
    
    Raises:
        DBUnavailableError: DB接続エラー時
    """
    _log_db_call("detail", material_id=material_id)
    
    try:
        with get_session() as db:
            stmt = (
                select(Material)
                .options(
                    selectinload(Material.properties),
                    selectinload(Material.images),
                    selectinload(Material.reference_urls),
                    selectinload(Material.use_examples),
                    selectinload(Material.metadata_items),
                    selectinload(Material.process_example_images),
                )
                .filter(Material.id == material_id)
            )
            
            result = db.execute(stmt)
            material = result.unique().scalar_one_or_none()
            return material
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'connect', 'network', 'timeout', 'refused', 'closed']):
            raise DBUnavailableError(f"データベース接続エラー: {e}") from e
        raise


def get_statistics(
    include_unpublished: bool = False,
    include_deleted: bool = False
) -> Dict[str, Any]:
    """
    統計情報を取得
    
    Args:
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
    
    Returns:
        統計情報のdict（material_count, categories, total_properties, avg_properties）
    
    Raises:
        DBUnavailableError: DB接続エラー時
    """
    _log_db_call("statistics", include_unpublished=include_unpublished, include_deleted=include_deleted)
    
    try:
        with get_session() as db:
            # 材料件数
            stmt_count = select(func.count()).select_from(Material)
            if not include_deleted:
                if hasattr(Material, 'is_deleted'):
                    stmt_count = stmt_count.filter(Material.is_deleted == 0)
            if not include_unpublished:
                if hasattr(Material, 'is_published'):
                    stmt_count = stmt_count.filter(Material.is_published == 1)
            material_count = db.execute(stmt_count).scalar_one()
            
            # カテゴリ数（重複除去）
            stmt_categories = select(Material.category_main).distinct()
            if not include_deleted:
                if hasattr(Material, 'is_deleted'):
                    stmt_categories = stmt_categories.filter(Material.is_deleted == 0)
            if not include_unpublished:
                if hasattr(Material, 'is_published'):
                    stmt_categories = stmt_categories.filter(Material.is_published == 1)
            categories_result = db.execute(stmt_categories).scalars().all()
            categories = len([c for c in categories_result if c])
            
            # 物性数
            total_properties = db.execute(select(func.count(Property.id))).scalar() or 0
            
            # 平均物性数
            avg_properties = total_properties / material_count if material_count > 0 else 0.0
            
            return {
                "material_count": material_count,
                "categories": categories,
                "total_properties": total_properties,
                "avg_properties": avg_properties,
            }
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'connect', 'network', 'timeout', 'refused', 'closed']):
            raise DBUnavailableError(f"データベース接続エラー: {e}") from e
        raise
