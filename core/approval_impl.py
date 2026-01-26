"""
承認処理の実装（トランザクション分離版）
app.py から分離した実装関数群
"""
import json
import logging
from database import Material, MaterialSubmission, ReferenceURL, UseExample

logger = logging.getLogger(__name__)


def _tx1_upsert_material_core(submission: MaterialSubmission, form_data: dict, update_existing: bool = True) -> tuple[int, str]:
    """
    Tx1: materials本体のみ。副作用（images/properties/embeddings/submission更新）は禁止。
    
    Args:
        submission: MaterialSubmissionオブジェクト
        form_data: フォームデータの辞書（payload_jsonからパース済み）
        update_existing: True なら同名素材（is_deleted=0）があれば更新、False なら常に新規作成
    
    Returns:
        material_id: 作成/更新されたMaterialのID
    
    Raises:
        Exception: Tx1失敗時（呼び出し元でcatchして即return）
    
    Note:
        - NOT NULL補完を flush前に行う
        - commit成功後、material_idを返す
        - 副作用（images/properties/embeddings/submission更新）は絶対に含めない
    """
    from utils.db import session_scope
    from sqlalchemy import select
    import uuid
    
    with session_scope() as db:
        # name_official の必須チェック
        name_official = form_data.get("name_official", "").strip()
        if not name_official:
            raise ValueError("材料名（正式）が空です。承認できません。")
        
        # Phase 4: NOT NULL補完を最初に実行（flush前）
        from utils.material_defaults import apply_material_defaults
        form_data = apply_material_defaults(form_data)
        
        # payload をサニタイズ：Material カラムだけに絞る（補完済みform_dataから）
        allowed_columns = {c.name for c in Material.__table__.columns}
        relationship_keys = {"images", "uploaded_images", "reference_urls", "use_examples", "properties", "metadata_items", "process_example_images"}
        system_keys = {"id", "created_at", "updated_at", "deleted_at", "uuid"}
        payload_for_material = {
            k: v for k, v in form_data.items()
            if k in allowed_columns 
            and k not in relationship_keys 
            and k not in system_keys
            and v is not None
        }
        
        # 既存Materialを検索（update_existing=True の場合のみ、is_deleted=0 のみ対象）
        material = None
        action = None
        
        if update_existing and name_official:
            existing_stmt = (
                select(Material)
                .where(Material.name_official == name_official)
                .where(Material.is_deleted == 0)
            )
            existing = db.execute(existing_stmt).scalar_one_or_none()
            
            if existing is not None:
                material = existing
                action = "updated"
                logger.info(f"[APPROVE][Tx1] Updating existing material (id={material.id}, name_official='{name_official}')")
        
        if material is None:
            # 新規作成前に、同名の active があるかチェック
            if name_official:
                active_check_stmt = (
                    select(Material.id)
                    .where(Material.name_official == name_official)
                    .where(Material.is_deleted == 0)
                    .limit(1)
                )
                active_existing = db.execute(active_check_stmt).scalar_one_or_none()
                if active_existing is not None:
                    if update_existing:
                        raise ValueError(f"同名の材料が既に存在します（ID: {active_existing}）。「既存へ反映」モードで承認してください。")
                    else:
                        raise ValueError(f"同名の材料が既に存在します（ID: {active_existing}）。材料名を変更して再投稿してください。")
            
            # 新規作成
            material_uuid = str(uuid.uuid4())
            material = Material(uuid=material_uuid)
            db.add(material)
            action = 'created'
            logger.info(f"[APPROVE][Tx1] Creating new material (name_official='{name_official}')")
        
        # 補完済みのpayload_for_materialをMaterialオブジェクトに設定（システム列は除外）
        for field, value in payload_for_material.items():
            if hasattr(material, field) and field not in system_keys:
                if value is not None:
                    setattr(material, field, value)
        
        # JSON配列フィールドの処理（補完後に上書き、リストの場合はJSON文字列に変換）
        json_fields = ['name_aliases', 'material_forms', 'color_tags', 'processing_methods',
                      'use_categories', 'safety_tags', 'question_templates', 'main_elements']
        for field in json_fields:
            if field in form_data and form_data[field]:
                if isinstance(form_data[field], list):
                    material.__setattr__(field, json.dumps(form_data[field], ensure_ascii=False))
                elif isinstance(form_data[field], str) and not form_data[field].startswith('['):
                    # 文字列の場合はそのまま（既にJSON文字列の可能性）
                    material.__setattr__(field, form_data[field])
        
        # 後方互換フィールド
        if form_data.get('name_official'):
            material.name = form_data.get('name_official')
        if form_data.get('category_main'):
            material.category = form_data.get('category_main')
        
        # search_textを生成して設定
        from utils.search import generate_search_text
        material.search_text = generate_search_text(material)
        
        db.flush()
        
        # 参照URL保存（更新モードの場合は既存を削除して置き換え）
        if action == "updated":
            db.query(ReferenceURL).filter(ReferenceURL.material_id == material.id).delete()
            db.query(UseExample).filter(UseExample.material_id == material.id).delete()
            db.flush()
        
        # 参照URL保存
        for ref in form_data.get('reference_urls', []):
            if ref.get('url'):
                ref_url = ReferenceURL(
                    material_id=material.id,
                    url=ref['url'],
                    url_type=ref.get('type'),
                    description=ref.get('desc')
                )
                db.add(ref_url)
        
        # 使用例保存
        for ex in form_data.get('use_examples', []):
            if ex.get('name'):
                use_ex = UseExample(
                    material_id=material.id,
                    example_name=ex['name'],
                    example_url=ex.get('url'),
                    description=ex.get('desc')
                )
                db.add(use_ex)
        
        # material.id を確定（flush してから取得）
        db.flush()
        material_id = material.id
        if not material_id:
            raise ValueError("material.id is None after flush")
        
        # session_scopeが自動commit（例外時は自動rollback）
        logger.info(f"[APPROVE][Tx1] commit success: material_id={material_id}, action={action}, uuid={material.uuid}")
        return material_id, action


def _tx2_upsert_images(material_id: int, uploaded_images: list, payload_dict: dict, *, submission_id: int = None) -> None:
    """
    Tx2: images upsert。失敗しても承認は継続。
    
    Args:
        material_id: MaterialのID
        uploaded_images: アップロード済み画像情報のリスト
        payload_dict: submissionのpayload_json（images_info取得用）
        submission_id: オプション（ログ用）
    
    Note:
        - R2 upload は DB Tx の外で行う（ネットワークI/OでTxを長引かせない）
        - DB upsert のみ session_scope() を使う
        - 失敗しても承認は継続（ログは残す）
    """
    from utils.db import session_scope
    import base64
    import hashlib
    
    # 一括登録の承認待ち送信で保存した images_info を処理（R2 upload）
    images_info = payload_dict.get("images_info", [])
    if isinstance(images_info, list) and len(images_info) > 0:
        from utils.bulk_import import upload_image_to_r2
        
        for img_info in images_info:
            if not isinstance(img_info, dict):
                continue
            
            kind = img_info.get('kind', 'primary')
            file_name = img_info.get('file_name', '')
            data_base64 = img_info.get('data_base64', '')
            
            if not data_base64:
                continue
            
            try:
                # base64デコード
                image_data = base64.b64decode(data_base64)
                
                # R2にアップロード（DB Txの外）
                r2_result = upload_image_to_r2(material_id, image_data, kind, file_name)
                
                if r2_result:
                    uploaded_images.append({
                        'kind': kind,
                        'r2_key': r2_result['r2_key'],
                        'public_url': r2_result['public_url'],
                        'mime': r2_result.get('mime', 'image/jpeg'),
                        'sha256': hashlib.sha256(image_data).hexdigest(),
                        'bytes': len(image_data)
                    })
                    logger.info(f"[APPROVE][Tx2] Uploaded image from images_info: kind={kind}, file_name={file_name}")
            except Exception as e:
                logger.warning(f"[APPROVE][Tx2] Failed to process image from images_info: {e}")
    
    uploaded_images_count = len(uploaded_images)
    if uploaded_images_count == 0:
        logger.info(f"[APPROVE][Tx2] No images to upsert (uploaded_images_count=0), skipping Tx2")
        return
    
    # DB upsert（session_scope内）
    with session_scope() as db:
        from utils.image_repo import upsert_image
        
        for idx, img_info in enumerate(uploaded_images):
            if not isinstance(img_info, dict):
                logger.warning(f"[APPROVE][Tx2] Image {idx+1} is not a dict: type={type(img_info)}, skipping")
                continue
            
            kind = img_info.get('kind', 'primary')
            r2_key = img_info.get('r2_key')
            public_url = img_info.get('public_url')
            mime = img_info.get('mime')
            sha256 = img_info.get('sha256')
            bytes_value = img_info.get('bytes')
            
            # bytes が None でない場合は int に変換（bigint対応）
            if bytes_value is not None:
                try:
                    bytes_value = int(bytes_value)
                except (ValueError, TypeError):
                    logger.warning(f"[APPROVE][Tx2] Image {idx+1} bytes value is not int-convertible: {bytes_value}, using None")
                    bytes_value = None
            
            logger.info(f"[APPROVE][Tx2] Upserting image {idx+1}/{uploaded_images_count}: kind={kind}, r2_key={r2_key}, public_url={public_url}, mime={mime}, sha256={sha256[:16] if sha256 else None}...")
            
            upsert_image(
                db=db,
                material_id=material_id,
                kind=kind,
                r2_key=r2_key,
                public_url=public_url,
                bytes=bytes_value,
                mime=mime,
                sha256=sha256,
            )
                
        # session_scopeが自動commit（例外時は自動rollback）
        logger.info(f"[APPROVE][Tx2] success: images upserted for material_id={material_id} (count={uploaded_images_count})")


def _txsub_mark_submission_approved(submission_id: int, material_id: int, editor_note: str = None) -> None:
    """
    TxSub: submissionsを approved にし、approved_material_id を設定する。Tx1成功後にのみ呼ぶ。
    
    Args:
        submission_id: MaterialSubmissionのID
        material_id: 承認されたMaterialのID（FK整合性のため必須）
        editor_note: 承認メモ（任意）
    
    Raises:
        Exception: TxSub失敗時（呼び出し元でcatchして承認失敗扱い）
    
    Note:
        - material_idの存在確認は呼び出し元で済んでいる前提
        - status='approved', approved_material_id=material_id を設定
        - このTxは必須（失敗時は承認全体を失敗扱い）
    """
    from utils.db import session_scope
    from datetime import datetime
    
    from utils.db import normalize_submission_key
    
    with session_scope() as db:
        kind, normalized_key = normalize_submission_key(submission_id)
        if kind is None or normalized_key is None:
            raise ValueError(f"Submission {submission_id} not found in TxSub")
        
        # 型ガード：kind=="id" でも normalized_key が int でなければ uuid検索にフォールバック
        if kind == "id" and isinstance(normalized_key, int):
            submission = db.query(MaterialSubmission).filter(MaterialSubmission.id == normalized_key).first()
        else:
            # kind=="uuid" または kind=="id" だが normalized_key が int でない場合
            if not isinstance(normalized_key, str):
                normalized_key = str(normalized_key)
            submission = db.query(MaterialSubmission).filter(MaterialSubmission.uuid == normalized_key).first()
            
        if not submission:
            raise ValueError(f"Submission {submission_id} not found in TxSub")
        
        # statusがpendingのままか確認
        if submission.status != "pending":
            raise ValueError(f"Submission {submission_id} status is '{submission.status}', not 'pending'. Cannot approve.")
        
        submission.status = "approved"
        submission.approved_material_id = material_id
        if editor_note and editor_note.strip():
            submission.editor_note = editor_note.strip()
        
        # session_scopeが自動commit（例外時は自動rollback）
        logger.info(f"[APPROVE][TxSub] success: submission_id={submission_id}, approved_material_id={material_id}")
