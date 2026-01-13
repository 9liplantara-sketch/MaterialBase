"""
Cloudflare R2 ストレージ統合モジュール
画像を R2 にアップロードし、公開URLを取得する
"""
import os
import hashlib
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

# boto3 を安全に import
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None

# Streamlit のインポートを安全に行う
try:
    import streamlit as st
except Exception:
    st = None

# utils.settings を安全に import
try:
    from utils.settings import get_flag, get_secret_str
except Exception:
    # フォールバック
    def get_flag(key: str, default: bool = False) -> bool:
        # 安全側に倒す
        if key in ("INIT_SAMPLE_DATA", "SEED_SKIP_IMAGES"):
            return True
        if key == "ENABLE_R2_UPLOAD":
            return False
        return default
    
    def get_secret_str(key: str, default: str = "") -> str:
        return os.getenv(key, default)


def get_r2_client():
    """
    Cloudflare R2 クライアントを取得
    
    Returns:
        boto3.client("s3") インスタンス（R2用に設定済み）
    
    Raises:
        RuntimeError: Secrets が設定されていない場合
    """
    if not BOTO3_AVAILABLE:
        raise RuntimeError("boto3 is not installed. Please install it: pip install boto3")
    
    # Secrets から R2 設定を取得
    account_id = get_secret_str("R2_ACCOUNT_ID", "")
    access_key_id = get_secret_str("R2_ACCESS_KEY_ID", "")
    secret_access_key = get_secret_str("R2_SECRET_ACCESS_KEY", "")
    
    if not account_id or not access_key_id or not secret_access_key:
        if os.getenv("DEBUG", "0") == "1":
            print("[R2] WARNING: R2 credentials not found. R2 upload will be skipped.")
        raise RuntimeError(
            "R2 credentials are not set. "
            "Please set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY in Streamlit Secrets."
        )
    
    # R2 エンドポイントURL
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    
    # boto3 クライアントを作成
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )
    
    return client


def make_public_url(key: str) -> str:
    """
    R2 の公開URLを生成
    
    Args:
        key: R2 内のキー（パス）
    
    Returns:
        公開URL
    """
    base_url = get_secret_str("R2_PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("R2_PUBLIC_BASE_URL is not set in Streamlit Secrets.")
    
    # key の先頭の / を除去
    key = key.lstrip("/")
    
    return f"{base_url}/{key}"


def upload_bytes_to_r2(key: str, body: bytes, content_type: str, bucket: Optional[str] = None) -> None:
    """
    R2 にバイトデータをアップロード
    
    Args:
        key: R2 内のキー（パス）
        body: アップロードするバイトデータ
        content_type: MIMEタイプ（例: "image/jpeg"）
        bucket: バケット名（None の場合は Secrets から取得）
    
    Raises:
        RuntimeError: アップロードに失敗した場合
    """
    if not bucket:
        bucket = get_secret_str("R2_BUCKET", "")
        if not bucket:
            raise RuntimeError("R2_BUCKET is not set in Streamlit Secrets.")
    
    client = get_r2_client()
    
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"Failed to upload to R2: {e}")


def calculate_sha256(data: bytes) -> str:
    """SHA256ハッシュを計算"""
    return hashlib.sha256(data).hexdigest()


def upload_uploadedfile(
    uploaded_file,
    material_id: int,
    kind: str = "primary"
) -> Dict[str, Any]:
    """
    Streamlit の UploadedFile を R2 にアップロード
    
    Args:
        uploaded_file: Streamlit の UploadedFile オブジェクト
        material_id: 材料ID
        kind: 画像種別（primary/space/product）
    
    Returns:
        {
            "r2_key": str,
            "public_url": str,
            "bytes": int,
            "mime": str,
            "sha256": str
        }
    
    Raises:
        RuntimeError: アップロードに失敗した場合
    """
    # フラグチェック（seed中はアップロードしない）
    if (get_flag("INIT_SAMPLE_DATA", False) or 
        get_flag("SEED_SKIP_IMAGES", False) or 
        not get_flag("ENABLE_R2_UPLOAD", True)):
        raise RuntimeError("R2 upload is disabled by flags (INIT_SAMPLE_DATA/SEED_SKIP_IMAGES or ENABLE_R2_UPLOAD=False)")
    
    # material_id が None の場合はエラー
    if not material_id:
        raise ValueError("material_id must be provided")
    
    # ファイルデータを読み込む
    body = uploaded_file.read()
    file_size = len(body)
    
    # SHA256ハッシュを計算
    sha256_hash = calculate_sha256(body)
    
    # MIMEタイプを取得
    mime_type = uploaded_file.type or "image/jpeg"
    
    # 拡張子を推定
    ext = "jpg"
    if mime_type == "image/png":
        ext = "png"
    elif mime_type == "image/webp":
        ext = "webp"
    elif mime_type == "image/gif":
        ext = "gif"
    
    # R2 キーを生成（material_id ベース、ユニーク化のため sha256 の先頭8文字を使用）
    # 形式: materials/<material_id>/<kind>/<sha256_prefix>.<ext>
    sha256_prefix = sha256_hash[:8]
    r2_key = f"materials/{material_id}/{kind}/{sha256_prefix}.{ext}"
    
    # R2 にアップロード
    upload_bytes_to_r2(r2_key, body, mime_type)
    
    # 公開URLを生成
    public_url = make_public_url(r2_key)
    
    return {
        "r2_key": r2_key,
        "public_url": public_url,
        "bytes": file_size,
        "mime": mime_type,
        "sha256": sha256_hash,
    }


def upload_local_file(
    file_path: Path,
    material_id: int,
    kind: str = "primary"
) -> Dict[str, Any]:
    """
    ローカルファイルを R2 にアップロード
    
    Args:
        file_path: ローカルファイルパス
        material_id: 材料ID
        kind: 画像種別（primary/space/product）
    
    Returns:
        {
            "r2_key": str,
            "public_url": str,
            "bytes": int,
            "mime": str,
            "sha256": str
        }
    
    Raises:
        RuntimeError: アップロードに失敗した場合
    """
    # フラグチェック（seed中はアップロードしない）
    if (get_flag("INIT_SAMPLE_DATA", False) or 
        get_flag("SEED_SKIP_IMAGES", False) or 
        not get_flag("ENABLE_R2_UPLOAD", True)):
        raise RuntimeError("R2 upload is disabled by flags")
    
    # material_id が None の場合はエラー
    if not material_id:
        raise ValueError("material_id must be provided")
    
    # ファイルを読み込む
    with open(file_path, "rb") as f:
        body = f.read()
    
    file_size = len(body)
    
    # SHA256ハッシュを計算
    sha256_hash = calculate_sha256(body)
    
    # MIMEタイプを推定
    ext = file_path.suffix.lower().lstrip(".")
    mime_type = "image/jpeg"
    if ext == "png":
        mime_type = "image/png"
    elif ext == "webp":
        mime_type = "image/webp"
    elif ext == "gif":
        mime_type = "image/gif"
    
    # R2 キーを生成
    sha256_prefix = sha256_hash[:8]
    r2_key = f"materials/{material_id}/{kind}/{sha256_prefix}.{ext}"
    
    # R2 にアップロード
    upload_bytes_to_r2(r2_key, body, mime_type)
    
    # 公開URLを生成
    public_url = make_public_url(r2_key)
    
    return {
        "r2_key": r2_key,
        "public_url": public_url,
        "bytes": file_size,
        "mime": mime_type,
        "sha256": sha256_hash,
    }
