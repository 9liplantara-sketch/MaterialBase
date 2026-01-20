"""
全文検索機能（Postgres全文検索 + pgvector埋め込み検索）
"""
import json
import hashlib
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from database import Material, MaterialEmbedding


def generate_search_text(material: Material) -> str:
    """
    材料から検索用テキストを生成（欠損に強い実装）
    
    Args:
        material: Materialオブジェクト（MaterialProxy等でも可）
    
    Returns:
        検索用テキスト（スペース区切り、空の場合は空文字列）
    """
    parts = []
    
    # ヘルパー関数：安全に属性を取得
    def safe_get(attr_name: str, default=None):
        return getattr(material, attr_name, default)
    
    # ヘルパー関数：JSON文字列を安全にパース
    def safe_json_parse(value, default=None):
        if not value:
            return default
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return default
        except (json.JSONDecodeError, TypeError, AttributeError):
            if isinstance(value, str):
                return [value]  # 文字列の場合はリストとして扱う
            return default
    
    # 基本識別情報
    name_official = safe_get("name_official")
    if name_official:
        parts.append(str(name_official))
    
    name_aliases = safe_get("name_aliases")
    if name_aliases:
        aliases = safe_json_parse(name_aliases)
        if aliases:
            parts.extend([str(a) for a in aliases if a])
    
    name = safe_get("name")  # 後方互換
    if name:
        parts.append(str(name))
    
    # 分類
    category_main = safe_get("category_main")
    if category_main:
        parts.append(str(category_main))
    
    category_other = safe_get("category_other")
    if category_other:
        parts.append(str(category_other))
    
    category = safe_get("category")  # 後方互換
    if category:
        parts.append(str(category))
    
    material_forms = safe_get("material_forms")
    if material_forms:
        forms = safe_json_parse(material_forms)
        if forms:
            parts.extend([str(f) for f in forms if f])
    
    material_forms_other = safe_get("material_forms_other")
    if material_forms_other:
        parts.append(str(material_forms_other))
    
    # 由来・原料
    origin_type = safe_get("origin_type")
    if origin_type:
        parts.append(str(origin_type))
    
    origin_detail = safe_get("origin_detail")
    if origin_detail:
        parts.append(str(origin_detail))
    
    origin_other = safe_get("origin_other")
    if origin_other:
        parts.append(str(origin_other))
    
    # 基本特性
    color_tags = safe_get("color_tags")
    if color_tags:
        colors = safe_json_parse(color_tags)
        if colors:
            parts.extend([str(c) for c in colors if c])
    
    transparency = safe_get("transparency")
    if transparency:
        parts.append(str(transparency))
    
    hardness_qualitative = safe_get("hardness_qualitative")
    if hardness_qualitative:
        parts.append(str(hardness_qualitative))
    
    weight_qualitative = safe_get("weight_qualitative")
    if weight_qualitative:
        parts.append(str(weight_qualitative))
    
    water_resistance = safe_get("water_resistance")
    if water_resistance:
        parts.append(str(water_resistance))
    
    heat_resistance_range = safe_get("heat_resistance_range")
    if heat_resistance_range:
        parts.append(str(heat_resistance_range))
    
    weather_resistance = safe_get("weather_resistance")
    if weather_resistance:
        parts.append(str(weather_resistance))
    
    # 加工・実装条件
    processing_methods = safe_get("processing_methods")
    if processing_methods:
        methods = safe_json_parse(processing_methods)
        if methods:
            parts.extend([str(m) for m in methods if m])
    
    processing_other = safe_get("processing_other")
    if processing_other:
        parts.append(str(processing_other))
    
    equipment_level = safe_get("equipment_level")
    if equipment_level:
        parts.append(str(equipment_level))
    
    prototyping_difficulty = safe_get("prototyping_difficulty")
    if prototyping_difficulty:
        parts.append(str(prototyping_difficulty))
    
    # 用途
    use_categories = safe_get("use_categories")
    if use_categories:
        uses = safe_json_parse(use_categories)
        if uses:
            parts.extend([str(u) for u in uses if u])
    
    use_other = safe_get("use_other")
    if use_other:
        parts.append(str(use_other))
    
    # 安全・制約
    safety_tags = safe_get("safety_tags")
    if safety_tags:
        safety = safe_json_parse(safety_tags)
        if safety:
            parts.extend([str(s) for s in safety if s])
    
    safety_other = safe_get("safety_other")
    if safety_other:
        parts.append(str(safety_other))
    
    restrictions = safe_get("restrictions")
    if restrictions:
        parts.append(str(restrictions))
    
    # 説明（後方互換）
    description = safe_get("description")
    if description:
        parts.append(str(description))
    
    # 空白を除去して結合
    try:
        search_text = " ".join([p.strip() for p in parts if p and p.strip()])
    except Exception:
        # 万が一エラーが発生した場合は空文字列を返す
        search_text = ""
    
    return search_text


def search_materials_fulltext(
    db: Session,
    query: str = "",
    filters: Optional[dict] = None,
    limit: int = 20,
    include_unpublished: bool = False,
    include_deleted: bool = False
) -> Tuple[List[Material], dict]:
    """
    Postgres全文検索で材料を検索（フィルタ対応）
    
    Args:
        db: データベースセッション
        query: 検索クエリ（自然言語、空文字列の場合はフィルタのみ）
        filters: フィルタ辞書 {
            'use_categories': List[str],  # 用途
            'transparency': str,  # 透明性
            'weather_resistance': str,  # 耐候性
            'water_resistance': str,  # 耐水性
            'equipment_level': str,  # 設備レベル
            'cost_level': str,  # コスト帯
        }
        limit: 取得件数上限
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
    
    Returns:
        (検索結果のMaterialリスト（関連度順）, 検索情報辞書)
    """
    filters = filters or {}
    
    # データベースの種類を確認
    dialect_name = db.bind.dialect.name if hasattr(db, 'bind') and db.bind else None
    
    # WHERE条件を構築
    where_conditions = []
    
    # 基本フィルタ
    if not include_deleted:
        where_conditions.append(Material.is_deleted == 0)
    
    if not include_unpublished:
        where_conditions.append(Material.is_published == 1)
    
    # フィルタ条件を追加
    if filters.get('use_categories'):
        # JSON配列に含まれるかチェック
        use_conditions = []
        for use_cat in filters['use_categories']:
            use_conditions.append(
                Material.use_categories.contains(f'"{use_cat}"')
            )
        if use_conditions:
            from sqlalchemy import or_
            where_conditions.append(or_(*use_conditions))
    
    if filters.get('transparency'):
        where_conditions.append(Material.transparency == filters['transparency'])
    
    if filters.get('weather_resistance'):
        where_conditions.append(Material.weather_resistance == filters['weather_resistance'])
    
    if filters.get('water_resistance'):
        where_conditions.append(Material.water_resistance == filters['water_resistance'])
    
    if filters.get('equipment_level'):
        where_conditions.append(Material.equipment_level == filters['equipment_level'])
    
    if filters.get('cost_level'):
        where_conditions.append(Material.cost_level == filters['cost_level'])
    
    # Postgresの全文検索を使用
    if dialect_name == 'postgresql':
        try:
            # WHERE条件を適用
            if where_conditions:
                from sqlalchemy import and_
                stmt = select(Material).where(and_(*where_conditions))
            else:
                stmt = select(Material)
            
            # 全文検索条件を追加（クエリがある場合）
            if query and query.strip():
                stmt = stmt.where(
                    text("to_tsvector('simple', COALESCE(search_text, '')) @@ plainto_tsquery('simple', :query)")
                ).params(query=query.strip())
                
                # 関連度でソート（ts_rankを使用）
                stmt = stmt.order_by(
                    text("ts_rank(to_tsvector('simple', COALESCE(search_text, '')), plainto_tsquery('simple', :query)) DESC")
                ).params(query=query.strip())
            else:
                # クエリがない場合はID順
                stmt = stmt.order_by(Material.id.desc())
            
            # 件数制限
            stmt = stmt.limit(limit)
            
            # 実行
            results = db.execute(stmt).unique().scalars().all()
            
            # 検索情報を構築
            search_info = {
                'query': query,
                'filters': filters,
                'count': len(results),
                'where_conditions': str(where_conditions) if where_conditions else "なし"
            }
            
            return list(results), search_info
        except Exception as e:
            # Postgres全文検索が失敗した場合はフォールバック
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Postgres全文検索が失敗しました（フォールバック）: {e}")
            # フォールバック処理に進む
    
    # フォールバック: search_textに部分一致検索
    stmt = select(Material)
    
    # WHERE条件を適用
    if where_conditions:
        from sqlalchemy import and_
        stmt = stmt.where(and_(*where_conditions))
    
    # 全文検索条件を追加（クエリがある場合）
    if query and query.strip():
        query_lower = query.strip().lower()
        query_terms = query_lower.split()
        
        if query_terms:
            conditions = []
            for term in query_terms:
                if term:
                    conditions.append(
                        func.lower(Material.search_text).contains(term)
                    )
            
            if conditions:
                from sqlalchemy import or_
                stmt = stmt.where(or_(*conditions))
            else:
                return [], {'query': query, 'filters': filters, 'count': 0, 'where_conditions': str(where_conditions)}
    
    # 件数制限
    stmt = stmt.limit(limit)
    
    # 実行
    results = db.execute(stmt).unique().scalars().all()
    
    # 検索情報を構築
    search_info = {
        'query': query,
        'filters': filters,
        'count': len(results),
        'where_conditions': str(where_conditions) if where_conditions else "なし"
    }
    
    return list(results), search_info


def update_material_search_text(db: Session, material: Material) -> None:
    """
    材料のsearch_textを更新
    
    Args:
        db: データベースセッション
        material: Materialオブジェクト
    """
    search_text = generate_search_text(material)
    material.search_text = search_text
    db.commit()


def calculate_content_hash(material: Material) -> str:
    """
    材料の内容からハッシュを計算（差分更新用）
    
    Args:
        material: Materialオブジェクト
    
    Returns:
        SHA256ハッシュ（16進数文字列）
    """
    # search_textをベースにハッシュを計算
    search_text = generate_search_text(material)
    hash_obj = hashlib.sha256(search_text.encode('utf-8'))
    return hash_obj.hexdigest()


def generate_embedding(text: str) -> List[float]:
    """
    テキストから埋め込みベクトルを生成（ダミー実装）
    
    Args:
        text: 埋め込み対象のテキスト
    
    Returns:
        埋め込みベクトル（1536次元のリスト）
    
    Note:
        実際の実装では、OpenAI APIや他の埋め込みAPIを使用する
        現時点ではダミーベクトルを返す（後でAPI接続する）
    """
    # ダミー実装：テキストのハッシュから疑似ランダムベクトルを生成
    import hashlib
    import struct
    
    hash_obj = hashlib.sha256(text.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # 1536次元のベクトルを生成（ハッシュから疑似ランダムに）
    embedding = []
    for i in range(1536):
        # ハッシュバイトを循環して使用
        byte_val = hash_bytes[i % len(hash_bytes)]
        # -1.0 から 1.0 の範囲に正規化
        val = (byte_val / 255.0) * 2.0 - 1.0
        embedding.append(val)
    
    # L2正規化（コサイン類似度を使うため）
    norm = sum(x * x for x in embedding) ** 0.5
    if norm > 0:
        embedding = [x / norm for x in embedding]
    
    return embedding


def update_material_embedding(db: Session, material: Material) -> bool:
    """
    材料の埋め込みを更新（content_hashが変わった場合のみ）
    
    Args:
        db: データベースセッション
        material: Materialオブジェクト
    
    Returns:
        更新が行われた場合 True、スキップされた場合 False
    """
    # データベースの種類を確認
    dialect_name = db.bind.dialect.name if hasattr(db, 'bind') and db.bind else None
    
    if dialect_name != 'postgresql':
        # Postgres以外ではスキップ
        return False
    
    # 現在のcontent_hashを計算
    current_hash = calculate_content_hash(material)
    
    # 既存のembeddingを取得
    existing_embedding = db.query(MaterialEmbedding).filter(
        MaterialEmbedding.material_id == material.id
    ).first()
    
    # content_hashが変わっていない場合はスキップ
    if existing_embedding and existing_embedding.content_hash == current_hash:
        return False
    
    # search_textから埋め込みを生成
    search_text = generate_search_text(material)
    if not search_text:
        # search_textが空の場合はスキップ
        return False
    
    embedding_vector = generate_embedding(search_text)
    
    # pgvector.sqlalchemy.Vectorを使う場合とそうでない場合で処理を分ける
    try:
        from pgvector.sqlalchemy import Vector
        # Vector型を使う場合：リストをそのまま設定
        if existing_embedding:
            existing_embedding.content_hash = current_hash
            existing_embedding.embedding = embedding_vector
            existing_embedding.updated_at = datetime.utcnow()
        else:
            new_embedding = MaterialEmbedding(
                material_id=material.id,
                content_hash=current_hash,
                embedding=embedding_vector,
                updated_at=datetime.utcnow()
            )
            db.add(new_embedding)
    except ImportError:
        # pgvectorがインストールされていない場合は生のSQLで保存
        embedding_str = '[' + ','.join(str(x) for x in embedding_vector) + ']'
        
        if existing_embedding:
            db.execute(
                text("""
                    UPDATE material_embeddings
                    SET content_hash = :content_hash,
                        embedding = :embedding::vector,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE material_id = :material_id
                """),
                {
                    "material_id": material.id,
                    "content_hash": current_hash,
                    "embedding": embedding_str
                }
            )
        else:
            db.execute(
                text("""
                    INSERT INTO material_embeddings (material_id, content_hash, embedding, updated_at)
                    VALUES (:material_id, :content_hash, :embedding::vector, CURRENT_TIMESTAMP)
                """),
                {
                    "material_id": material.id,
                    "content_hash": current_hash,
                    "embedding": embedding_str
                }
            )
    
    db.commit()
    return True


def search_materials_vector(
    db: Session,
    query: str,
    limit: int = 20,
    include_unpublished: bool = False,
    include_deleted: bool = False
) -> List[Tuple[Material, float]]:
    """
    ベクトル検索で材料を検索（コサイン類似度）
    
    Args:
        db: データベースセッション
        query: 検索クエリ（自然言語）
        limit: 取得件数上限
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
    
    Returns:
        (Material, 類似度スコア) のタプルのリスト（類似度順）
    """
    if not query or not query.strip():
        return []
    
    # データベースの種類を確認
    dialect_name = db.bind.dialect.name if hasattr(db, 'bind') and db.bind else None
    
    if dialect_name != 'postgresql':
        # Postgres以外では空リストを返す
        return []
    
    # クエリテキストから埋め込みを生成
    query_embedding = generate_embedding(query.strip())
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
    
    # ベクトル検索クエリ（コサイン類似度）
    # 1 - (embedding <=> query_embedding) がコサイン類似度
    conditions = []
    if not include_deleted:
        conditions.append("m.is_deleted = 0")
    if not include_unpublished:
        conditions.append("m.is_published = 1")
    
    where_clause = " AND " + " AND ".join(conditions) if conditions else ""
    
    stmt = text(f"""
        SELECT 
            m.id,
            1 - (me.embedding <=> :query_embedding::vector) as similarity
        FROM materials m
        INNER JOIN material_embeddings me ON m.id = me.material_id
        WHERE me.embedding IS NOT NULL{where_clause}
        ORDER BY similarity DESC
        LIMIT :limit
    """)
    
    # 実行
    result = db.execute(stmt, {
        "query_embedding": embedding_str,
        "limit": limit
    })
    
    # Materialオブジェクトを取得
    results = []
    for row in result:
        material_id, similarity = row
        material = db.query(Material).filter(Material.id == material_id).first()
        if material:
            results.append((material, float(similarity)))
    
    return results


def search_materials_hybrid(
    db: Session,
    query: str = "",
    filters: Optional[dict] = None,
    limit: int = 20,
    include_unpublished: bool = False,
    include_deleted: bool = False,
    text_weight: float = 0.5,
    vector_weight: float = 0.5
) -> Tuple[List[Material], dict]:
    """
    テキスト検索とベクトル検索のハイブリッド検索（フィルタ対応）
    
    Args:
        db: データベースセッション
        query: 検索クエリ（自然言語、空文字列の場合はフィルタのみ）
        filters: フィルタ辞書 {
            'use_categories': List[str],  # 用途
            'transparency': str,  # 透明性
            'weather_resistance': str,  # 耐候性
            'water_resistance': str,  # 耐水性
            'equipment_level': str,  # 設備レベル
            'cost_level': str,  # コスト帯
        }
        limit: 取得件数上限
        include_unpublished: 非公開も含める
        include_deleted: 削除済みも含める
        text_weight: テキスト検索の重み（デフォルト: 0.5）
        vector_weight: ベクトル検索の重み（デフォルト: 0.5）
    
    Returns:
        (検索結果のMaterialリスト（統合スコア順）, 検索情報辞書)
    """
    filters = filters or {}
    
    # データベースの種類を確認
    dialect_name = db.bind.dialect.name if hasattr(db, 'bind') and db.bind else None
    
    if dialect_name != 'postgresql':
        # Postgres以外では全文検索のみを使用
        results, search_info = search_materials_fulltext(
            db=db,
            query=query,
            filters=filters,
            limit=limit,
            include_unpublished=include_unpublished,
            include_deleted=include_deleted
        )
        return results, search_info
    
    # フィルタで候補集合を絞る（WHERE条件を構築）
    where_conditions = []
    
    # 基本フィルタ
    if not include_deleted:
        where_conditions.append(Material.is_deleted == 0)
    
    if not include_unpublished:
        where_conditions.append(Material.is_published == 1)
    
    # フィルタ条件を追加
    if filters.get('use_categories'):
        from sqlalchemy import or_
        use_conditions = []
        for use_cat in filters['use_categories']:
            use_conditions.append(
                Material.use_categories.contains(f'"{use_cat}"')
            )
        if use_conditions:
            where_conditions.append(or_(*use_conditions))
    
    if filters.get('transparency'):
        where_conditions.append(Material.transparency == filters['transparency'])
    
    if filters.get('weather_resistance'):
        where_conditions.append(Material.weather_resistance == filters['weather_resistance'])
    
    if filters.get('water_resistance'):
        where_conditions.append(Material.water_resistance == filters['water_resistance'])
    
    if filters.get('equipment_level'):
        where_conditions.append(Material.equipment_level == filters['equipment_level'])
    
    if filters.get('cost_level'):
        where_conditions.append(Material.cost_level == filters['cost_level'])
    
    # WHERE条件を適用したベースクエリ
    if where_conditions:
        from sqlalchemy import and_
        base_stmt = select(Material).where(and_(*where_conditions))
    else:
        base_stmt = select(Material)
    
    # クエリがある場合のみハイブリッド検索を実行
    if query and query.strip():
        # 全文検索スコアとベクトル類似度を取得するSQL
        query_embedding = generate_embedding(query.strip())
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'
        
        # WHERE条件を構築（SQLインジェクション対策のためパラメータ化、:name形式）
        where_parts = []
        params = {
            "query": query.strip(),
            "query_embedding": embedding_str,  # pgvector形式: '[0.0,0.1,...]'
            "text_weight": text_weight,
            "vector_weight": vector_weight,
            "limit": limit
        }
        
        if not include_deleted:
            where_parts.append("m.is_deleted = 0")
        if not include_unpublished:
            where_parts.append("m.is_published = 1")
        
        # フィルタ条件を追加（パラメータ化、:name形式）
        if filters.get('use_categories'):
            use_conditions = []
            for i, uc in enumerate(filters['use_categories']):
                param_name = f"use_cat_{i}"
                use_conditions.append(f"m.use_categories LIKE :{param_name}")
                params[param_name] = f'%"{uc}"%'
            where_parts.append(f"({' OR '.join(use_conditions)})")
        
        if filters.get('transparency'):
            where_parts.append("m.transparency = :transparency")
            params['transparency'] = filters['transparency']
        
        if filters.get('weather_resistance'):
            where_parts.append("m.weather_resistance = :weather_resistance")
            params['weather_resistance'] = filters['weather_resistance']
        
        if filters.get('water_resistance'):
            where_parts.append("m.water_resistance = :water_resistance")
            params['water_resistance'] = filters['water_resistance']
        
        if filters.get('equipment_level'):
            where_parts.append("m.equipment_level = :equipment_level")
            params['equipment_level'] = filters['equipment_level']
        
        if filters.get('cost_level'):
            where_parts.append("m.cost_level = :cost_level")
            params['cost_level'] = filters['cost_level']
        
        where_clause = " AND " + " AND ".join(where_parts) if where_parts else ""
        
        # ベクトル検索が使えるかチェック（material_embeddingsテーブルとpgvector拡張の存在確認）
        use_vector_search = False
        try:
            # material_embeddingsテーブルの存在確認
            check_stmt = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'material_embeddings'
                )
            """)
            has_embeddings_table = db.execute(check_stmt).scalar()
            
            if has_embeddings_table:
                # pgvector拡張の存在確認
                check_vector_stmt = text("""
                    SELECT EXISTS (
                        SELECT FROM pg_extension 
                        WHERE extname = 'vector'
                    )
                """)
                has_vector_ext = db.execute(check_vector_stmt).scalar()
                use_vector_search = has_vector_ext and vector_weight > 0
        except Exception:
            use_vector_search = False
        
        # ハイブリッド検索クエリ（全文rank + ベクトル類似度）
        if use_vector_search:
            # ベクトル検索を含むハイブリッド検索
            hybrid_stmt = text(f"""
                SELECT 
                    m.id,
                    COALESCE(
                        ts_rank(to_tsvector('simple', COALESCE(m.search_text, '')), plainto_tsquery('simple', :query)),
                        0
                    ) as text_rank,
                    COALESCE(
                        1 - (me.embedding <=> :query_embedding::vector),
                        0
                    ) as vector_similarity,
                    (COALESCE(
                        ts_rank(to_tsvector('simple', COALESCE(m.search_text, '')), plainto_tsquery('simple', :query)),
                        0
                    ) * :text_weight + COALESCE(
                        1 - (me.embedding <=> :query_embedding::vector),
                        0
                    ) * :vector_weight) as combined_score
                FROM materials m
                LEFT JOIN material_embeddings me ON m.id = me.material_id
                WHERE (
                    (m.search_text IS NOT NULL AND m.search_text != '' AND 
                     to_tsvector('simple', COALESCE(m.search_text, '')) @@ plainto_tsquery('simple', :query))
                    OR
                    (me.embedding IS NOT NULL)
                ){where_clause}
                ORDER BY combined_score DESC
                LIMIT :limit
            """)
        else:
            # ベクトル検索なし（全文検索のみ）
            hybrid_stmt = text(f"""
                SELECT 
                    m.id,
                    COALESCE(
                        ts_rank(to_tsvector('simple', COALESCE(m.search_text, '')), plainto_tsquery('simple', :query)),
                        0
                    ) as text_rank,
                    0 as vector_similarity,
                    (COALESCE(
                        ts_rank(to_tsvector('simple', COALESCE(m.search_text, '')), plainto_tsquery('simple', :query)),
                        0
                    ) * :text_weight) as combined_score
                FROM materials m
                WHERE (
                    m.search_text IS NOT NULL AND m.search_text != '' AND 
                    to_tsvector('simple', COALESCE(m.search_text, '')) @@ plainto_tsquery('simple', :query)
                ){where_clause}
                ORDER BY combined_score DESC
                LIMIT :limit
            """)
            # ベクトル検索を使わない場合はquery_embeddingを削除
            params.pop('query_embedding', None)
        
        # 実行（エラーハンドリング付き）
        try:
            result = db.execute(hybrid_stmt, params)
            
            # Materialオブジェクトを取得
            material_ids = [row[0] for row in result]
            materials_dict = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()}
            
            # ID順序を保持
            results = [materials_dict[mid] for mid in material_ids if mid in materials_dict]
            
            # 検索情報を構築
            search_info = {
                'query': query,
                'filters': filters,
                'count': len(results),
                'method': 'hybrid' if use_vector_search else 'fulltext_only',
                'text_weight': text_weight,
                'vector_weight': vector_weight if use_vector_search else 0
            }
            
            return results, search_info
        
        except Exception as e:
            # ベクトル検索が失敗した場合は全文検索にフォールバック
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Hybrid search failed, falling back to fulltext search: {e}")
            
            # 全文検索にフォールバック
            results, search_info = search_materials_fulltext(
                db=db,
                query=query,
                filters=filters,
                limit=limit,
                include_unpublished=include_unpublished,
                include_deleted=include_deleted
            )
            search_info['method'] = 'fulltext_fallback'
            search_info['fallback_reason'] = str(e)
            return results, search_info
    else:
        # クエリがない場合はフィルタのみで全文検索を使用
        results, search_info = search_materials_fulltext(
            db=db,
            query="",
            filters=filters,
            limit=limit,
            include_unpublished=include_unpublished,
            include_deleted=include_deleted
        )
        search_info['method'] = 'filter_only'
        return results, search_info
