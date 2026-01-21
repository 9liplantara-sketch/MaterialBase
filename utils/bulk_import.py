"""
一括登録機能（CSV + 画像ZIP）
管理者用の材料一括登録・更新機能
"""
import csv
import io
import json
import re
import unicodedata
import zipfile
import tempfile
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from database import Material, Image
from utils.search import generate_search_text, update_material_search_text
from utils.image_repo import upsert_image

# ロガーを設定
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(name)s] %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def normalize_material_name(name: str) -> str:
    """
    材料名を正規化（NFKC、空白除去）
    
    Args:
        name: 材料名
    
    Returns:
        正規化された材料名
    """
    if not name:
        return ""
    # Unicode正規化（NFKC: 互換文字を正規化）
    name = unicodedata.normalize('NFKC', name)
    # 全角スペースを半角スペースに変換
    name = name.replace("　", " ")
    # 連続するスペースを1つに
    while "  " in name:
        name = name.replace("  ", " ")
    # 末尾の空白を除去
    name = name.strip()
    return name


def generate_material_name_candidates(material_name: str) -> List[str]:
    """
    材料名から候補名を複数生成（括弧揺れ吸収）
    
    例: "真鍮（黄銅）" の場合
    - "真鍮（黄銅）"（元の名前）
    - "真鍮"（括弧前のみ）
    - "黄銅"（括弧内のみ）
    
    Args:
        material_name: 材料名
    
    Returns:
        候補名のリスト
    """
    candidates = []
    normalized = normalize_material_name(material_name)
    
    if not normalized:
        return candidates
    
    # 元の名前を追加
    candidates.append(normalized)
    
    # 括弧パターンを抽出（全角・半角両対応）
    # 例: "真鍮（黄銅）" → ["真鍮", "黄銅"]
    bracket_patterns = [
        r'(.+?)（(.+?)）',  # 全角括弧
        r'(.+?)\((.+?)\)',  # 半角括弧
        r'(.+?)【(.+?)】',  # 二重括弧
    ]
    
    for pattern in bracket_patterns:
        match = re.match(pattern, normalized)
        if match:
            before = match.group(1).strip()
            inside = match.group(2).strip()
            if before:
                candidates.append(before)
            if inside:
                candidates.append(inside)
    
    # 重複を除去して返す
    seen = set()
    result = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    
    return result


def fix_zip_filename(name: str) -> str:
    """
    ZIP内の日本語ファイル名を復元（CP437→UTF-8変換を試す）
    
    Args:
        name: ZIP内のファイル名（文字化けしている可能性あり）
    
    Returns:
        復元されたファイル名（失敗した場合は元のname）
    """
    try:
        # CP437エンコーディングでエンコードしてからUTF-8でデコードを試す
        fixed = name.encode('cp437').decode('utf-8')
        return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        # 変換に失敗した場合は元の名前を返す
        return name


def find_image_files(
    material_name: str,
    image_files_dict: Dict[str, Tuple[str, bytes]],
    kind: str
) -> Optional[Tuple[str, bytes]]:
    """
    材料名から画像ファイルを検索（CSV側・ZIP側両方にNFKC正規化を適用）
    
    Args:
        material_name: 材料名（CSV側）
        image_files_dict: {正規化済みbasename（拡張子除外）: (完全なファイル名, ファイルデータ)} の辞書
        kind: 画像種別（primary/space/product）
    
    Returns:
        (完全なファイル名, ファイルデータ) のタプル、見つからない場合はNone
    """
    # CSV側の材料名を正規化（NFKC）
    material_name_normalized = unicodedata.normalize('NFKC', material_name.strip())
    
    # 候補名を生成（正規化済み）
    candidates_raw = generate_material_name_candidates(material_name)
    candidates = [unicodedata.normalize('NFKC', c.strip()) for c in candidates_raw]
    
    # kindに応じたbasenameパターンを生成（拡張子なし）
    if kind == 'primary':
        patterns = candidates
    elif kind == 'space':
        patterns = [f"{name}1" for name in candidates]
    elif kind == 'product':
        patterns = [f"{name}2" for name in candidates]
    else:
        return None
    
    # ZIP側のキーも正規化済みなので、そのまま比較
    # 大文字小文字を区別しない検索
    # image_files_dictの値は (full_filename, file_data) のタプル
    image_files_lower = {k.lower(): v for k, v in image_files_dict.items()}
    
    for pattern in patterns:
        pattern_normalized = unicodedata.normalize('NFKC', pattern.strip())
        pattern_lower = pattern_normalized.lower()
        if pattern_lower in image_files_lower:
            # 見つかった場合は、値のタプル(完全なファイル名, ファイルデータ)を返す
            full_filename, file_data = image_files_lower[pattern_lower]
            return (full_filename, file_data)
    
    return None


def extract_zip_images(zip_file) -> Tuple[Dict[str, Tuple[str, bytes]], Dict[str, int]]:
    """
    ZIPファイルから画像ファイルを展開（macOSメタファイルを除外）
    
    Args:
        zip_file: ZIPファイル（Streamlit UploadedFileまたはファイルパス）
    
    Returns:
        ({正規化basename（拡張子除外）: (完全なファイル名, ファイルデータ)} の辞書, {統計情報})
        統計情報: {'zip_total': int, 'excluded': int, 'images_used': int}
    """
    image_files = {}
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    zip_total = 0
    excluded = 0
    images_used = 0
    
    try:
        # Streamlit UploadedFileの場合はread()で取得
        if hasattr(zip_file, 'read'):
            zip_data = zip_file.read()
        else:
            # ファイルパスの場合
            with open(zip_file, 'rb') as f:
                zip_data = f.read()
        
        # ZIPを展開
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for file_info in zf.namelist():
                zip_total += 1
                
                # ディレクトリはスキップ
                if file_info.endswith('/'):
                    excluded += 1
                    continue
                
                # macOSメタファイルを除外
                file_path = Path(file_info)
                basename = file_path.name
                
                # __MACOSX/ を含むパスは除外
                if '__MACOSX/' in file_info or '__MACOSX\\' in file_info:
                    excluded += 1
                    continue
                
                # ._ で始まるbasenameは除外
                if basename.startswith('._'):
                    excluded += 1
                    continue
                
                # .DS_Store は除外
                if basename == '.DS_Store':
                    excluded += 1
                    continue
                
                # 拡張子チェック（小文字化して判定）
                suffix_lower = file_path.suffix.lower()
                if suffix_lower not in allowed_extensions:
                    excluded += 1
                    continue
                
                # 画像ファイルとして採用
                try:
                    file_data = zf.read(file_info)
                    
                    # ZIP内の日本語ファイル名を復元（CP437→UTF-8変換を試す）
                    file_name_raw = file_path.name
                    file_name_fixed = fix_zip_filename(file_name_raw)
                    
                    # ファイル名を正規化（NFKC、前後空白除去）
                    file_name_normalized = unicodedata.normalize('NFKC', file_name_fixed).strip()
                    
                    # 拡張子を除去してbasenameを取得（照合用キー）
                    basename_without_ext = Path(file_name_normalized).stem
                    extension = file_path.suffix.lower()
                    
                    # 正規化済みのbasename（拡張子除外）をキーとして使用
                    # 値は(完全なファイル名, ファイルデータ)のタプル
                    image_files[basename_without_ext] = (file_name_normalized, file_data)
                    images_used += 1
                except Exception as e:
                    logger.warning(f"Failed to extract {file_info}: {e}")
                    excluded += 1
                    continue
    
    except Exception as e:
        logger.error(f"Failed to extract ZIP file: {e}")
        raise
    
    stats = {
        'zip_total': zip_total,
        'excluded': excluded,
        'images_used': images_used
    }
    
    return image_files, stats


def _apply_not_null_defaults(material: Material) -> None:
    """
    NOT NULL列にデフォルト値を設定（値が無い場合のみ）
    
    Args:
        material: Materialオブジェクト
    """
    # NOT NULL列のデフォルト値マップ
    defaults = {
        'origin_type': '不明',
        'origin_detail': '不明',
        'transparency': '不明',
        'hardness_qualitative': '不明',
        'weight_qualitative': '不明',
        'water_resistance': '不明',
        'heat_resistance_range': '不明',
        'weather_resistance': '不明',
        'procurement_status': '不明',
        'cost_level': '不明',
        'visibility': '非公開（管理者のみ）',
        'is_deleted': 0,
    }
    
    # 各フィールドに対して、値が無い場合のみデフォルトを設定
    for field, default_value in defaults.items():
        if hasattr(material, field):
            current_value = getattr(material, field)
            # None、空文字列、または未設定の場合のみデフォルトを設定
            if current_value is None or (isinstance(current_value, str) and not current_value.strip()):
                setattr(material, field, default_value)
    
    # is_publishedはvisibilityから決定（既存ロジック）
    visibility = getattr(material, 'visibility', '')
    if visibility in ["公開", "公開（誰でも閲覧可）"]:
        material.is_published = 1
    elif visibility in ["非公開", "非公開（管理者のみ）"]:
        material.is_published = 0
    else:
        # デフォルトは非公開（安全側に倒す）
        material.is_published = 0


def validate_csv_row(row: Dict[str, str], row_num: int) -> Tuple[bool, List[str]]:
    """
    CSV行を検証
    
    Args:
        row: CSV行の辞書
        row_num: 行番号（1始まり）
    
    Returns:
        (検証OKか, エラーメッセージのリスト)
    """
    errors = []
    
    # 必須カラム
    required_fields = [
        'name_official', 'category_main', 'supplier_org', 'supplier_type',
        'origin_type', 'origin_detail', 'transparency', 'hardness_qualitative',
        'weight_qualitative', 'water_resistance', 'weather_resistance',
        'equipment_level', 'cost_level', 'use_categories'
    ]
    
    for field in required_fields:
        field_value = row.get(field)
        if not field_value or not str(field_value).strip():
            errors.append(f"必須フィールド '{field}' が空です")
    
    return len(errors) == 0, errors


def normalize_csv_value(value: str, field_name: str, options: Optional[List[str]] = None) -> str:
    """
    CSVの値を正規化（選択肢の正規化）
    
    Args:
        value: CSVの値
        field_name: フィールド名
        options: 有効な選択肢のリスト（Noneの場合は正規化しない）
    
    Returns:
        正規化された値（見つからない場合は元の値）
    """
    if not value:
        return value
    
    value = str(value).strip()
    
    # 選択肢が指定されていない場合はそのまま返す
    if not options:
        return value
    
    # 完全一致をチェック
    if value in options:
        return value
    
    # 大文字小文字を区別しない検索
    value_lower = value.lower()
    for opt in options:
        if opt.lower() == value_lower:
            return opt
    
    # 部分一致をチェック
    for opt in options:
        if value in opt or opt in value:
            return opt
    
    return value


def parse_csv(csv_file) -> List[Dict[str, str]]:
    """
    CSVファイルをパース
    
    Args:
        csv_file: CSVファイル（Streamlit UploadedFileまたはファイルパス）
    
    Returns:
        CSV行のリスト（辞書のリスト）
    """
    rows = []
    
    try:
        # Streamlit UploadedFileの場合はread()で取得
        if hasattr(csv_file, 'read'):
            csv_data = csv_file.read().decode('utf-8-sig')  # BOM対応
        else:
            # ファイルパスの場合
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                csv_data = f.read()
        
        # CSVをパース
        reader = csv.DictReader(io.StringIO(csv_data))
        for row_num, row in enumerate(reader, start=2):  # ヘッダー行を除くので2から
            rows.append(row)
    
    except Exception as e:
        logger.error(f"Failed to parse CSV: {e}")
        raise
    
    return rows


def create_or_update_material(
    db: Session,
    row: Dict[str, str],
    row_num: int
) -> Tuple[Material, str]:
    """
    材料を作成または更新
    
    Args:
        db: データベースセッション
        row: CSV行の辞書
        row_num: 行番号
    
    Returns:
        (Materialオブジェクト, 'created'または'updated')
    """
    # name_officialは必須フィールド（validate_csv_rowでチェック済み）
    name_official = str(row.get('name_official', '')).strip()
    if not name_official:
        raise ValueError(f"Row {row_num}: name_official is required")
    
    # 既存レコードを検索
    existing = db.query(Material).filter(
        Material.name_official == name_official
    ).first()
    
    if existing:
        # 更新
        material = existing
        action = 'updated'
    else:
        # 新規作成
        material_uuid = str(uuid.uuid4())
        material = Material(
            uuid=material_uuid,
            name_official=name_official
        )
        db.add(material)
        action = 'created'
    
    # フィールドを設定（JSON配列フィールドはJSON文字列に変換）
    json_fields = [
        'name_aliases', 'material_forms', 'color_tags', 'processing_methods',
        'use_environment', 'use_categories', 'safety_tags', 'question_templates', 'main_elements'
    ]
    
    # フィールドを設定（存在するキーのみ、値が空でない場合のみ）
    for key, value in row.items():
        # 値が存在しない、空、または空白のみの場合はスキップ
        if value is None or not str(value).strip():
            continue
        
        value_str = str(value).strip()
        
        # Materialモデルに存在しないキーはスキップ
        if not hasattr(material, key):
            continue
        
        # JSON配列フィールドの処理
        if key in json_fields:
            # カンマ区切りの場合は配列に変換
            if ',' in value_str:
                items = [item.strip() for item in value_str.split(',')]
                value_str = json.dumps(items, ensure_ascii=False)
            elif value_str.startswith('[') and value_str.endswith(']'):
                # 既にJSON配列形式の場合
                pass
            else:
                # 単一値の場合は配列に変換
                value_str = json.dumps([value_str], ensure_ascii=False)
        
        # 数値フィールドの処理
        numeric_fields = [
            'recycle_bio_rate', 'specific_gravity', 'heat_resistance_temp'
        ]
        if key in numeric_fields:
            try:
                setattr(material, key, float(value_str) if value_str else None)
            except (ValueError, TypeError):
                setattr(material, key, None)
            continue
        
        # 真偽値フィールドの処理
        boolean_fields = ['is_published', 'is_deleted']
        if key in boolean_fields:
            setattr(material, key, 1 if value_str.lower() in ['1', 'true', 'yes', '公開'] else 0)
            continue
        
        # 文字列フィールド
        setattr(material, key, value_str)
    
    # NOT NULL列のデフォルト値補完（値が無い場合のみ設定）
    _apply_not_null_defaults(material)
    
    # search_textを生成
    try:
        update_material_search_text(db, material)
    except Exception as e:
        logger.warning(f"Failed to update search_text for {name_official}: {e}")
    
    db.flush()
    
    return material, action


def upload_image_to_r2(
    material_id: int,
    image_data: bytes,
    kind: str,
    file_name: str
) -> Optional[Dict[str, str]]:
    """
    画像をR2にアップロード
    
    Args:
        material_id: 材料ID
        image_data: 画像データ（バイト）
        kind: 画像種別（primary/space/product）
        file_name: ファイル名
    
    Returns:
        {'r2_key': str, 'public_url': str} または None（失敗時）
    """
    try:
        import utils.r2_storage as r2_storage
        
        # R2設定の確認
        try:
            _ = r2_storage.get_r2_client()
        except RuntimeError as e:
            logger.warning(f"R2 configuration error: {e}")
            return None
        
        # SHA256ハッシュを計算
        sha256 = hashlib.sha256(image_data).hexdigest()
        
        # MIMEタイプを判定
        ext = Path(file_name).suffix.lower()
        mime_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }
        mime = mime_map.get(ext, 'image/jpeg')
        
        # R2キーを生成
        r2_key = f"materials/{material_id}/{kind}/{sha256[:16]}{ext}"
        
        # R2にアップロード
        r2_storage.upload_bytes_to_r2(r2_key, image_data, mime)
        
        # 公開URLを生成
        public_url = r2_storage.make_public_url(r2_key)
        
        return {
            'r2_key': r2_key,
            'public_url': public_url
        }
    
    except Exception as e:
        logger.error(f"Failed to upload image to R2: {e}")
        return None


def process_bulk_import(
    db: Session,
    csv_rows: List[Dict[str, str]],
    image_files_dict: Dict[str, Tuple[str, bytes]]
) -> List[Dict[str, Any]]:
    """
    一括登録を実行
    
    Args:
        db: データベースセッション
        csv_rows: CSV行のリスト
        image_files_dict: {ファイル名: ファイルデータ} の辞書
    
    Returns:
        結果レポートのリスト（各行の処理結果）
    """
    results = []
    
    for row_num, row in enumerate(csv_rows, start=2):  # ヘッダー行を除くので2から
        result = {
            'row_num': row_num,
            'name_official': row.get('name_official', ''),
            'status': 'pending',
            'action': None,
            'material_id': None,
            'error': None,
            'images': []
        }
        
        try:
            # CSV行を検証
            is_valid, errors = validate_csv_row(row, row_num)
            if not is_valid:
                result['status'] = 'error'
                result['error'] = '; '.join(errors)
                results.append(result)
                continue
            
            # 材料を作成または更新
            material, action = create_or_update_material(db, row, row_num)
            db.commit()
            
            result['action'] = action
            result['material_id'] = material.id
            
            # 画像を検索してアップロード
            material_name = material.name_official
            for kind in ['primary', 'space', 'product']:
                image_match = find_image_files(material_name, image_files_dict, kind)
                if image_match:
                    file_name, image_data = image_match
                    
                    # R2にアップロード
                    r2_result = upload_image_to_r2(material.id, image_data, kind, file_name)
                    
                    if r2_result:
                        # imagesテーブルにupsert
                        upsert_image(
                            db=db,
                            material_id=material.id,
                            kind=kind,
                            r2_key=r2_result['r2_key'],
                            public_url=r2_result['public_url'],
                            mime=r2_result.get('mime', 'image/jpeg'),
                            sha256=hashlib.sha256(image_data).hexdigest(),
                            bytes=len(image_data)
                        )
                        db.commit()
                        
                        result['images'].append({
                            'kind': kind,
                            'file_name': file_name,
                            'public_url': r2_result['public_url']
                        })
            
            result['status'] = 'success'
        
        except Exception as e:
            db.rollback()
            result['status'] = 'error'
            result['error'] = str(e)
            logger.exception(f"Error processing row {row_num}: {e}")
        
        results.append(result)
    
    return results


def create_bulk_submissions(
    db: Session,
    csv_rows: List[Dict[str, str]],
    image_files_dict: Dict[str, Tuple[str, bytes]],
    submitted_by: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    一括登録を承認待ちに送信（各行ごとにMaterialSubmissionを作成）
    
    Args:
        db: データベースセッション
        csv_rows: CSV行のリスト
        image_files_dict: {ファイル名: ファイルデータ} の辞書
        submitted_by: 投稿者情報（任意）
    
    Returns:
        結果レポートのリスト（各行の処理結果）
    """
    from database import MaterialSubmission
    
    results = []
    
    for row_num, row in enumerate(csv_rows, start=2):  # ヘッダー行を除くので2から
        result = {
            'row_num': row_num,
            'name_official': row.get('name_official', ''),
            'status': 'pending',
            'submission_id': None,
            'submission_uuid': None,
            'error': None,
            'images': []
        }
        
        try:
            # CSV行を検証
            is_valid, errors = validate_csv_row(row, row_num)
            if not is_valid:
                result['status'] = 'error'
                result['error'] = '; '.join(errors)
                results.append(result)
                continue
            
            # 画像情報を収集
            material_name = row.get('name_official', '').strip()
            images_info = []
            for kind in ['primary', 'space', 'product']:
                image_match = find_image_files(material_name, image_files_dict, kind)
                if image_match:
                    file_name, image_data = image_match
                    # 画像データをbase64エンコードして保存（承認時にデコードしてアップロード）
                    import base64
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                    images_info.append({
                        'kind': kind,
                        'file_name': file_name,
                        'data_base64': image_base64  # base64エンコードされた画像データ
                    })
            
            # MaterialSubmissionを作成
            submission_uuid = str(uuid.uuid4())
            
            # payload_jsonを作成（画像データを含める）
            payload = dict(row)
            payload['images_info'] = images_info
            
            submission = MaterialSubmission(
                uuid=submission_uuid,
                status='pending',
                name_official=material_name,
                payload_json=json.dumps(payload, ensure_ascii=False),
                submitted_by=submitted_by
            )
            
            db.add(submission)
            db.flush()
            
            # 画像情報を結果に追加（承認時にアップロードされる）
            for img_info in images_info:
                result['images'].append({
                    'kind': img_info['kind'],
                    'file_name': img_info['file_name'],
                    'public_url': None  # 承認時にアップロードされる
                })
            
            result['submission_id'] = submission.id
            result['submission_uuid'] = submission_uuid
            result['status'] = 'success'
        
        except Exception as e:
            db.rollback()
            result['status'] = 'error'
            result['error'] = str(e)
            logger.exception(f"Error creating submission for row {row_num}: {e}")
        
        results.append(result)
    
    db.commit()
    return results


def generate_report_csv(results: List[Dict[str, Any]]) -> str:
    """
    結果レポートCSVを生成
    
    Args:
        results: 処理結果のリスト
    
    Returns:
        CSV文字列
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # ヘッダー
    writer.writerow([
        '行番号', '材料名', 'ステータス', 'アクション', '材料ID',
        'エラー', '画像（primary）', '画像（space）', '画像（product）'
    ])
    
    # データ行
    for result in results:
        # 画像URLをkindごとに整理
        images_by_kind = {img['kind']: img['public_url'] for img in result.get('images', [])}
        
        writer.writerow([
            result['row_num'],
            result['name_official'],
            result['status'],
            result.get('action', ''),
            result.get('material_id', ''),
            result.get('error', ''),
            images_by_kind.get('primary', ''),
            images_by_kind.get('space', ''),
            images_by_kind.get('product', '')
        ])
    
    return output.getvalue()
