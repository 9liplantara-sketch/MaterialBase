"""
Cloudflare R2 ストレージ統合モジュール
画像を R2 にアップロードし、公開URLを取得する
"""
import os
import hashlib
import logging
from typing import Optional, Dict, Any
from pathlib import Path

# バージョン文字列（実行確認用）
R2_STORAGE_VERSION = "2026-01-15T14:40:00"

# ロガーを設定（Cloudで確実に追えるように）
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(name)s] %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# boto3 を安全に import
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = None
    BotoCoreError = None

# Streamlit のインポートを安全に行う
try:
    import streamlit as st
except Exception:
    st = None

# utils.settings を安全に import
try:
    import utils.settings as settings
except Exception:
    # フォールバック: os.getenv のみで動作（settings が無い場合）
    class _FallbackSettings:
        @staticmethod
        def get_flag(key: str, default: bool = False) -> bool:
            # os.getenv のみで判定（安全側に倒さない）
            value = os.getenv(key)
            if value is None:
                return default
            value_str = str(value).lower().strip()
            return value_str in ("1", "true", "yes", "y", "on")
        
        @staticmethod
        def get_secret_str(key: str, default: str = "") -> str:
            return os.getenv(key, default)
    
    settings = _FallbackSettings()


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
    
    # Secrets から R2 設定を取得（get_secret_str が無い場合に備えた二重化）
    secret_str_fn = getattr(settings, "get_secret_str", None)
    if not callable(secret_str_fn):
        # フォールバック: os.getenv のみで取得
        def secret_str_fn(key, default=""):
            return os.getenv(key, default)
    
    account_id = secret_str_fn("R2_ACCOUNT_ID", "")
    access_key_id = secret_str_fn("R2_ACCESS_KEY_ID", "")
    secret_access_key = secret_str_fn("R2_SECRET_ACCESS_KEY", "")
    
    # 必須キーのチェック（不足キー名を明確に表示）
    missing_keys = []
    if not account_id:
        missing_keys.append("R2_ACCOUNT_ID")
    if not access_key_id:
        missing_keys.append("R2_ACCESS_KEY_ID")
    if not secret_access_key:
        missing_keys.append("R2_SECRET_ACCESS_KEY")
    
    if missing_keys:
        error_msg = f"R2 credentials are not set. Missing keys: {', '.join(missing_keys)}"
        logger.warning(f"[R2] Configuration error: {error_msg}")
        # Streamlit が利用可能な場合は警告を表示
        try:
            import streamlit as st
            st.warning(f"⚠️ R2 upload skipped: Missing secrets ({', '.join(missing_keys)})")
        except Exception:
            pass
        raise RuntimeError(
            f"{error_msg} "
            "Please set them in Streamlit Secrets."
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
    # get_secret_str が無い場合に備えた二重化
    secret_str_fn = getattr(settings, "get_secret_str", None)
    if not callable(secret_str_fn):
        # フォールバック: os.getenv のみで取得
        def secret_str_fn(key, default=""):
            return os.getenv(key, default)
    
    base_url = secret_str_fn("R2_PUBLIC_BASE_URL", "").rstrip("/")
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
        # get_secret_str が無い場合に備えた二重化
        secret_str_fn = getattr(settings, "get_secret_str", None)
        if not callable(secret_str_fn):
            # フォールバック: os.getenv のみで取得
            def secret_str_fn(key, default=""):
                return os.getenv(key, default)
        bucket = secret_str_fn("R2_BUCKET", "")
        if not bucket:
            error_msg = "R2_BUCKET is not set in Streamlit Secrets."
            logger.warning(f"[R2] Configuration error: {error_msg}")
            # Streamlit が利用可能な場合は警告を表示
            try:
                import streamlit as st
                st.warning("⚠️ R2 upload skipped: R2_BUCKET secret is missing")
            except Exception:
                pass
            raise RuntimeError(error_msg)
    
    client = get_r2_client()
    
    file_size = len(body)
    logger.info(f"[R2] version={R2_STORAGE_VERSION} Upload start: key={key}, size={file_size} bytes, content_type={content_type}, bucket={bucket}")
    
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        logger.info(f"[R2] Upload success: key={key}")
    except Exception as e:
        # ClientError, BotoCoreError が None の場合も含めて全ての例外をキャッチ
        error_msg = f"Failed to upload to R2: {e}"
        logger.exception(f"[R2] Upload failed: key={key}, error={error_msg}")
        # Streamlit が利用可能な場合は警告を表示
        try:
            import streamlit as st
            st.warning(f"⚠️ R2 upload failed: {str(e)[:100]}")
        except Exception:
            pass
        raise RuntimeError(error_msg)


def calculate_sha256(data: bytes) -> str:
    """SHA256ハッシュを計算"""
    return hashlib.sha256(data).hexdigest()


def upload_uploadedfile_to_prefix(
    uploaded_file,
    prefix: str,
    kind: str = "primary"
) -> Dict[str, Any]:
    """
    Streamlit の UploadedFile を R2 にアップロード（material_id 不要版、submission用）
    
    Args:
        uploaded_file: Streamlit の UploadedFile オブジェクト
        prefix: R2 キーのプレフィックス（例: "submissions/<uuid>/"）
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
    # get_flag が無い場合に備えた二重化
    flag_fn = getattr(settings, "get_flag", None)
    if not callable(flag_fn):
        # フォールバック: os.getenv のみで判定
        def flag_fn(key, default=False):
            value = os.getenv(key)
            if value is None:
                return default
            value_str = str(value).lower().strip()
            return value_str in ("1", "true", "yes", "y", "on")
    
    # ENABLE_R2_UPLOAD のチェック（統一された判定）
    enable_r2_upload = flag_fn("ENABLE_R2_UPLOAD", True)
    init_sample_data = flag_fn("INIT_SAMPLE_DATA", False)
    # 注意: SEED_SKIP_IMAGES は seed処理（init_sample_data.py等）のみで使用し、通常登録では参照しない
    
    # フラグ実値をログに出す（Cloudで確実に追える、バージョンも含める）
    logger.info(f"[R2] version={R2_STORAGE_VERSION} flags: INIT_SAMPLE_DATA={init_sample_data}, ENABLE_R2_UPLOAD={enable_r2_upload}")
    
    if init_sample_data or not enable_r2_upload:
        skip_reason = []
        if init_sample_data:
            skip_reason.append("INIT_SAMPLE_DATA=1 (seed mode)")
        if not enable_r2_upload:
            skip_reason.append("ENABLE_R2_UPLOAD=0")
        reason_msg = ", ".join(skip_reason)
        logger.warning(f"[R2] Upload disabled: {reason_msg}")
        # Streamlit が利用可能な場合は警告を表示
        try:
            import streamlit as st
            st.warning(f"⚠️ R2 upload disabled: {reason_msg}")
        except Exception:
            pass
        raise RuntimeError(f"R2 upload disabled: {reason_msg}")
    
    # ファイルデータを読み込む
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    data = uploaded_file.read() if hasattr(uploaded_file, "read") else uploaded_file.getvalue()
    body = data
    file_size = len(data)
    
    # SHA256ハッシュを計算
    sha256_hash = calculate_sha256(data)
    
    # ファイル名から拡張子を取得
    filename = getattr(uploaded_file, "name", "upload")
    import os as os_module
    _, ext = os_module.path.splitext(filename)
    if not ext or ext == ".":
        # MIMEタイプから拡張子を推定
        mime_type = getattr(uploaded_file, "type", None) or "image/jpeg"
        if mime_type == "image/png":
            ext = ".png"
        elif mime_type == "image/webp":
            ext = ".webp"
        elif mime_type == "image/gif":
            ext = ".gif"
        else:
            ext = ".jpg"
    else:
        mime_type = getattr(uploaded_file, "type", None) or "image/jpeg"
    
    # UUID を生成してユニーク化
    import uuid
    unique_id = uuid.uuid4().hex
    
    # R2 キーを生成（prefix ベース）
    # 形式: {prefix}/{kind}/{unique_id}{ext}
    prefix = prefix.rstrip("/")
    r2_key = f"{prefix}/{kind}/{unique_id}{ext}"
    
    file_name = getattr(uploaded_file, 'name', 'unknown')
    logger.info(f"[R2] version={R2_STORAGE_VERSION} Starting upload: prefix={prefix}, kind={kind}, file_size={file_size} bytes, file_name={file_name}")
    
    # R2 にアップロード（upload_bytes_to_r2 の引数名は body）
    upload_bytes_to_r2(key=r2_key, body=body, content_type=mime_type)
    
    # 公開URLを生成（make_public_url が存在するかチェック）
    make_url_fn = globals().get("make_public_url", None)
    if callable(make_url_fn):
        public_url = make_url_fn(r2_key)
    else:
        # make_public_url が無い場合は R2_PUBLIC_BASE_URL から合成
        secret_str_fn = getattr(settings, "get_secret_str", None)
        if callable(secret_str_fn):
            base = secret_str_fn("R2_PUBLIC_BASE_URL", "").rstrip("/")
        else:
            base = os.getenv("R2_PUBLIC_BASE_URL", "").rstrip("/")
        public_url = f"{base}/{r2_key}" if base else ""
    
    logger.info(f"[R2] Upload completed: r2_key={r2_key}, public_url={public_url}")
    
    return {
        "r2_key": r2_key,
        "public_url": public_url,
        "bytes": file_size,
        "mime": mime_type,
        "sha256": sha256_hash,
    }


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
    # get_flag が無い場合に備えた二重化
    flag_fn = getattr(settings, "get_flag", None)
    if not callable(flag_fn):
        # フォールバック: os.getenv のみで判定
        def flag_fn(key, default=False):
            value = os.getenv(key)
            if value is None:
                return default
            value_str = str(value).lower().strip()
            return value_str in ("1", "true", "yes", "y", "on")
    
    # ENABLE_R2_UPLOAD のチェック（統一された判定）
    enable_r2_upload = flag_fn("ENABLE_R2_UPLOAD", True)
    init_sample_data = flag_fn("INIT_SAMPLE_DATA", False)
    # 注意: SEED_SKIP_IMAGES は seed処理（init_sample_data.py等）のみで使用し、通常登録では参照しない
    
    # フラグ実値をログに出す（Cloudで確実に追える、バージョンも含める）
    logger.info(f"[R2] version={R2_STORAGE_VERSION} flags: INIT_SAMPLE_DATA={init_sample_data}, ENABLE_R2_UPLOAD={enable_r2_upload}")
    
    if init_sample_data or not enable_r2_upload:
        skip_reason = []
        if init_sample_data:
            skip_reason.append("INIT_SAMPLE_DATA=1 (seed mode)")
        if not enable_r2_upload:
            skip_reason.append("ENABLE_R2_UPLOAD=0")
        reason_msg = ", ".join(skip_reason)
        logger.warning(f"[R2] Upload disabled: {reason_msg}")
        # Streamlit が利用可能な場合は警告を表示
        try:
            import streamlit as st
            st.warning(f"⚠️ R2 upload disabled: {reason_msg}")
        except Exception:
            pass
        raise RuntimeError(f"R2 upload disabled: {reason_msg}")
    
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
    
    file_name = getattr(uploaded_file, 'name', 'unknown')
    logger.info(f"[R2] version={R2_STORAGE_VERSION} Starting upload: material_id={material_id}, kind={kind}, file_size={file_size} bytes, file_name={file_name}")
    
    # R2 にアップロード
    upload_bytes_to_r2(r2_key, body, mime_type)
    
    # 公開URLを生成
    public_url = make_public_url(r2_key)
    
    logger.info(f"[R2] Upload completed: material_id={material_id}, r2_key={r2_key}, public_url={public_url}")
    
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
    # フラグチェック（seed中はアップロードしない、統一された判定）
    # 注意: SEED_SKIP_IMAGES は seed処理（init_sample_data.py等）のみで使用し、通常登録では参照しない
    flag_fn = getattr(settings, "get_flag", None)
    if not callable(flag_fn):
        # フォールバック: os.getenv のみで判定
        def flag_fn(key, default=False):
            value = os.getenv(key)
            if value is None:
                return default
            value_str = str(value).lower().strip()
            return value_str in ("1", "true", "yes", "y", "on")
    
    enable_r2_upload = flag_fn("ENABLE_R2_UPLOAD", True)
    init_sample_data = flag_fn("INIT_SAMPLE_DATA", False)
    
    # フラグ実値をログに出す（Cloudで確実に追える、バージョンも含める）
    logger.info(f"[R2] version={R2_STORAGE_VERSION} flags: INIT_SAMPLE_DATA={init_sample_data}, ENABLE_R2_UPLOAD={enable_r2_upload}")
    
    if init_sample_data or not enable_r2_upload:
        skip_reason = []
        if init_sample_data:
            skip_reason.append("INIT_SAMPLE_DATA=1 (seed mode)")
        if not enable_r2_upload:
            skip_reason.append("ENABLE_R2_UPLOAD=0")
        reason_msg = ", ".join(skip_reason)
        logger.warning(f"[R2] Upload disabled: {reason_msg}")
        raise RuntimeError(f"R2 upload disabled: {reason_msg}")
    
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
