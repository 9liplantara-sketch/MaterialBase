"""
材料（Material）のNOT NULL列に対するデフォルト値補完仕様

Phase 4: NOT NULL補完を単一の仕様に集約
- approve_submission の Tx1 と bulk_import の双方が "同じ補完関数" を必ず通る
- CSV必須項目チェックも同じ定義から生成できる
- NotNullViolation を運用上ゼロに近づける
"""
from typing import Dict, Any, Set


# NOT NULL列の一覧（database.py の Material モデルから抽出）
REQUIRED_FIELDS: Set[str] = {
    'name_official',  # 必須（補完しない、バリデーションで弾く）
    'category_main',  # 必須（補完しない、バリデーションで弾く）
    'origin_type',
    'origin_detail',
    'transparency',
    'hardness_qualitative',
    'weight_qualitative',
    'water_resistance',
    'weather_resistance',
    'equipment_level',
    'prototyping_difficulty',
    'procurement_status',
    'cost_level',
    'visibility',
    'is_published',
    'is_deleted',
}


# デフォルト値マップ（未入力時に補完する値）
DEFAULT_VALUES: Dict[str, Any] = {
    'origin_type': '不明',
    'origin_detail': '不明',
    'transparency': '不明',
    'hardness_qualitative': '不明',
    'weight_qualitative': '不明',
    'water_resistance': '不明',
    'weather_resistance': '不明',
    'equipment_level': '家庭/工房レベル',  # DB側デフォルトと同じ
    'prototyping_difficulty': '中',  # DB側デフォルトと同じ
    'procurement_status': '不明',
    'cost_level': '不明',
    'visibility': '非公開（管理者のみ）',  # 安全側に倒す（DB側デフォルトは'公開'だが）
    'is_published': 0,  # 安全側に倒す（DB側デフォルトは1だが、visibilityから決定）
    'is_deleted': 0,  # DB側デフォルトと同じ
}


def apply_material_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    材料データのNOT NULL列に対してデフォルト値を補完する
    
    Args:
        data: 材料データの辞書（Materialカラム名をキーとする）
    
    Returns:
        補完済みの材料データの辞書（新しい辞書を返す、元のdataは変更しない）
    
    Note:
        - 文字列の正規化（strip）もここで行う
        - None/空文字列/空白のみの文字列は「値が無い」とみなす
        - REQUIRED_FIELDS に対して値が欠けていれば DEFAULT_VALUES で埋める
        - DEFAULT_VALUESに無い必須列があれば警告を出す（開発時に気づけるように）
        - name_official と category_main は補完しない（バリデーションで弾く前提）
    """
    # 新しい辞書を作成（元のdataを変更しない）
    result = dict(data)
    
    # 文字列フィールドの正規化（strip）
    for key, value in result.items():
        if isinstance(value, str):
            result[key] = value.strip()
    
    # REQUIRED_FIELDS に対して値が欠けていれば DEFAULT_VALUES で埋める
    # name_official と category_main は補完しない（バリデーションで弾く前提）
    skip_fields = {'name_official', 'category_main'}
    
    for field in REQUIRED_FIELDS:
        if field in skip_fields:
            continue  # バリデーションで弾く前提なので補完しない
        
        # 値が無いかチェック
        current_value = result.get(field)
        is_empty = (
            current_value is None
            or (isinstance(current_value, str) and not current_value.strip())
            or (isinstance(current_value, (list, dict)) and len(current_value) == 0)
        )
        
        if is_empty:
            # DEFAULT_VALUES から取得
            if field in DEFAULT_VALUES:
                result[field] = DEFAULT_VALUES[field]
            else:
                # DEFAULT_VALUESに無い必須列があれば警告（開発時に気づけるように）
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"[material_defaults] REQUIRED_FIELDSに '{field}' があるが、"
                    f"DEFAULT_VALUESにデフォルト値が定義されていません。"
                    f"NotNullViolationが発生する可能性があります。"
                )
                # 運用で落ちると困る場合は、暫定値を必ず用意する方針で行く
                # ここでは警告のみ（必要に応じて例外を投げることも可）
    
    # visibility に基づいて is_published を設定（既存ロジックと整合）
    visibility = result.get('visibility', '')
    if visibility in ["公開", "公開（誰でも閲覧可）"]:
        result['is_published'] = 1
    elif visibility in ["非公開", "非公開（管理者のみ）"]:
        result['is_published'] = 0
    else:
        # デフォルトは非公開（安全側に倒す）
        result['is_published'] = 0
    
    return result


def get_csv_required_fields() -> Set[str]:
    """
    CSV必須項目の一覧を返す（REQUIRED_FIELDSから生成）
    
    Returns:
        CSVで必須とすべき項目のセット（name_official, category_main など）
    
    Note:
        - CSV必須とDB必須は異なる概念
        - CSV必須: 運用上必須（ユーザーが入力すべき）
        - DB必須: 制約上必須（NOT NULL制約）
        - CSV必須はDB必須のサブセット（一部はデフォルト補完でOK）
    """
    # CSVで必須とすべき項目（補完しない項目）
    csv_required = {'name_official', 'category_main'}
    
    # 将来的に他の項目もCSV必須にしたい場合はここに追加
    # 例: csv_required.add('supplier_org')
    
    return csv_required
