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
from utils.normalize import (
    normalize_text,
    normalize_filename,
    generate_image_basename_candidates,
    should_exclude_zip_entry,
    is_image_extension,
)

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
    
    Note:
        Phase 7: utils.normalize.normalize_text() を使用
    """
    return normalize_text(name)


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
) -> Tuple[Optional[Tuple[str, bytes]], Dict[str, Any]]:
    """
    材料名から画像ファイルを検索（Phase 7強化版：照合レポート付き）
    
    Args:
        material_name: 材料名（CSV側）
        image_files_dict: {正規化済みbasename（拡張子除外）: (完全なファイル名, ファイルデータ)} の辞書
        kind: 画像種別（primary/space/product）
    
    Returns:
        ((完全なファイル名, ファイルデータ) のタプル or None, 照合レポート辞書)
        照合レポート: {
            'material_name': str,  # 元の材料名
            'material_name_normalized': str,  # 正規化後の材料名
            'kind': str,  # primary/space/product
            'candidates': List[str],  # 照合候補リスト（正規化済み）
            'matched_candidate': Optional[str],  # 一致した候補
            'matched_filename': Optional[str],  # 一致したファイル名
            'available_files': List[str],  # ZIP内の利用可能なファイル名（正規化済みbasename）
        }
    """
    # Phase 7: utils.normalize.normalize_text() を使用
    material_name_normalized = normalize_text(material_name)
    
    # Phase 7: utils.normalize.generate_image_basename_candidates() を使用
    candidates = generate_image_basename_candidates(material_name)
    
    # kindに応じたbasenameパターンを生成（拡張子なし）
    if kind == 'primary':
        # primary: 材料名.jpg
        patterns = [candidates[0]] if len(candidates) > 0 else []
    elif kind == 'space':
        # space: 材料名1.jpg
        patterns = [candidates[1]] if len(candidates) > 1 else []
    elif kind == 'product':
        # product: 材料名2.jpg
        patterns = [candidates[2]] if len(candidates) > 2 else []
    else:
        patterns = []
    
    # 照合レポート用の情報を収集
    report = {
        'material_name': material_name,
        'material_name_normalized': material_name_normalized,
        'kind': kind,
        'candidates': patterns,
        'matched_candidate': None,
        'matched_filename': None,
        'available_files': list(image_files_dict.keys()),  # ZIP内の利用可能なファイル名
    }
    
    if not patterns:
        return None, report
    
    # ZIP側のキーも正規化済みなので、そのまま比較
    # 大文字小文字を区別しない検索
    # image_files_dictの値は (full_filename, file_data) のタプル
    image_files_lower = {k.lower(): v for k, v in image_files_dict.items()}
    
    for pattern in patterns:
        pattern_normalized = normalize_text(pattern)
        pattern_lower = pattern_normalized.lower()
        if pattern_lower in image_files_lower:
            # 見つかった場合は、値のタプル(完全なファイル名, ファイルデータ)を返す
            full_filename, file_data = image_files_lower[pattern_lower]
            report['matched_candidate'] = pattern_normalized
            report['matched_filename'] = full_filename
            return (full_filename, file_data), report
    
    return None, report


def extract_zip_images(zip_file) -> Tuple[Dict[str, Tuple[str, bytes]], Dict[str, int]]:
    """
    ZIPファイルから画像ファイルを展開（macOSメタファイルを除外、Phase 7強化版）
    
    Args:
        zip_file: ZIPファイル（Streamlit UploadedFileまたはファイルパス）
    
    Returns:
        ({正規化basename（拡張子除外）: (完全なファイル名, ファイルデータ)} の辞書, {統計情報})
        統計情報: {'zip_total': int, 'excluded': int, 'images_used': int}
    
    Phase 7 改善点:
        - utils.normalize.should_exclude_zip_entry() を使用して除外判定
        - utils.normalize.normalize_filename() を使用して正規化
        - 0バイトファイルも除外
    """
    image_files = {}
    
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
                
                # ZIPエントリ情報を取得
                try:
                    zip_entry_info = zf.getinfo(file_info)
                    file_size = zip_entry_info.file_size
                except KeyError:
                    file_size = 0
                
                # Phase 7: utils.normalize.should_exclude_zip_entry() で除外判定
                # 0バイトファイルも除外（should_exclude_zip_entry内で処理）
                if should_exclude_zip_entry(file_info, file_size):
                    excluded += 1
                    continue
                
                # Phase 7: utils.normalize.is_image_extension() で画像拡張子チェック
                if not is_image_extension(file_info):
                    excluded += 1
                    continue
                
                # 画像ファイルとして採用
                try:
                    file_data = zf.read(file_info)
                    
                    # ZIP内の日本語ファイル名を復元（CP437→UTF-8変換を試す）
                    file_path = Path(file_info)
                    file_name_raw = file_path.name
                    file_name_fixed = fix_zip_filename(file_name_raw)
                    
                    # Phase 7: utils.normalize.normalize_filename() を使用して正規化
                    basename_without_ext = normalize_filename(file_name_fixed)
                    
                    # 正規化済みのbasename（拡張子除外）をキーとして使用
                    # 値は(完全なファイル名, ファイルデータ)のタプル
                    # 完全なファイル名は正規化済みのbasename + 拡張子
                    extension = file_path.suffix.lower()
                    file_name_normalized = f"{basename_without_ext}{extension}"
                    
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


# Phase 4: 旧関数は削除済み（utils/material_defaults.py に集約）
# 補完ロジックは utils.material_defaults.apply_material_defaults() のみを使用


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
        # 'use_environment',  # 一時的にコメントアウト（DBにカラムが存在しない）
        'use_categories', 'safety_tags', 'question_templates', 'main_elements'
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
    
    # Phase 4: NOT NULL列のデフォルト値補完（flush前）
    # rowを補完してからMaterialオブジェクトに設定
    from utils.material_defaults import apply_material_defaults
    row = apply_material_defaults(row)
    
    # 補完済みのrowをMaterialオブジェクトに設定（まだ設定されていないフィールドのみ）
    for field, value in row.items():
        if hasattr(material, field):
            current_value = getattr(material, field)
            # 値が無い場合のみ補完済みの値を設定
            if current_value is None or (isinstance(current_value, str) and not current_value.strip()):
                if value is not None:
                    setattr(material, field, value)
    
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
            match_reports = []  # Phase 7: 照合レポートを収集
            for kind in ['primary', 'space', 'product']:
                image_match, match_report = find_image_files(material_name, image_files_dict, kind)
                match_reports.append(match_report)  # Phase 7: 照合レポートを保存
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
                            'public_url': r2_result['public_url'],
                            'match_report': match_report  # Phase 7: 照合レポートを含める
                        })
            
            # Phase 7: 照合レポートを結果に含める
            result['match_reports'] = match_reports
            
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
                image_match, match_report = find_image_files(material_name, image_files_dict, kind)
                if image_match:
                    file_name, image_data = image_match
                    # 画像データをbase64エンコードして保存（承認時にデコードしてアップロード）
                    import base64
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                    images_info.append({
                        'kind': kind,
                        'file_name': file_name,
                        'data_base64': image_base64,  # base64エンコードされた画像データ
                        'match_report': match_report  # Phase 7: 照合レポートを保存
                    })
            
            # MaterialSubmissionを作成
            submission_uuid = str(uuid.uuid4())
            
            # payload_jsonを作成（画像データを含める）
            payload = dict(row)
            payload['images_info'] = images_info
            
            # session 内で必要な値を取得し、session 外では submission を参照しない
            submission_id = None
            
            submission = MaterialSubmission(
                uuid=submission_uuid,
                status='pending',
                name_official=material_name,
                payload_json=json.dumps(payload, ensure_ascii=False),
                submitted_by=submitted_by
            )
            
            db.add(submission)
            db.flush()  # ← id を確実に取るため
            # session 内で必要な値を取得（session 外では submission を参照しない）
            submission_id = submission.id
            # session 内でのみ submission を使用（ここで終了）
            
            # 画像情報を結果に追加（承認時にアップロードされる）
            for img_info in images_info:
                result['images'].append({
                    'kind': img_info['kind'],
                    'file_name': img_info['file_name'],
                    'public_url': None  # 承認時にアップロードされる
                })
            
            # session 外で使う値は session 内で取得した primitive のみ
            result['submission_id'] = submission_id
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
