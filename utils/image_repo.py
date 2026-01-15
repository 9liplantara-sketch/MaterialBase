"""
画像リポジトリモジュール
DB の images テーブルへの upsert 操作を提供
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import Image


def upsert_image(
    db: Session,
    material_id: int,
    kind: str,
    r2_key: Optional[str] = None,
    public_url: Optional[str] = None,
    bytes: Optional[int] = None,
    mime: Optional[str] = None,
    sha256: Optional[str] = None,
    file_path: Optional[str] = None,  # 後方互換
    url: Optional[str] = None,  # 後方互換
    description: Optional[str] = None,
) -> Image:
    """
    images テーブルに画像情報を upsert（既存があれば UPDATE、無ければ INSERT）
    
    Args:
        db: データベースセッション
        material_id: 材料ID（必須）
        kind: 画像種別（primary/space/product）（必須）
        r2_key: R2 内のキー（パス）
        public_url: R2 公開URL（優先）
        bytes: ファイルサイズ（バイト）（Phase1: 使用しない、常にNone）
        mime: MIMEタイプ
        sha256: SHA256ハッシュ
        file_path: ローカルパス（後方互換）
        url: S3 URL（後方互換）
        description: 説明
    
    Returns:
        Image オブジェクト
    
    Raises:
        ValueError: material_id が None の場合
    
    Note:
        Phase1: bytes列には書かない（BYTEA型の可能性があるため）
        ファイルサイズを保存したい場合は size_bytes(BIGINT)列を新設予定
    """
    # material_id が None の時は絶対にINSERTしない（即return）
    if not material_id:
        raise ValueError("material_id must be provided (cannot be None)")
    
    # 既存の画像を検索（material_id + kind で一意）
    existing = db.query(Image).filter(
        Image.material_id == material_id,
        Image.kind == kind
    ).first()
    
    if existing:
        # 既存レコードを更新
        if r2_key is not None:
            existing.r2_key = r2_key
        if public_url is not None:
            existing.public_url = public_url
        # Phase1: bytes列には書かない（BYTEA型の可能性があるため）
        # if bytes is not None:
        #     existing.bytes = bytes
        if mime is not None:
            existing.mime = mime
        if sha256 is not None:
            existing.sha256 = sha256
        if file_path is not None:
            existing.file_path = file_path
        if url is not None:
            existing.url = url
        if description is not None:
            existing.description = description
        existing.updated_at = datetime.utcnow()
        
        db.flush()
        return existing
    else:
        # 新規レコードを作成
        new_image = Image(
            material_id=material_id,
            kind=kind,
            r2_key=r2_key,
            public_url=public_url,
            bytes=None,  # Phase1: bytes列には書かない（常にNone）
            mime=mime,
            sha256=sha256,
            file_path=file_path,
            url=url,
            description=description,
        )
        db.add(new_image)
        db.flush()
        return new_image
