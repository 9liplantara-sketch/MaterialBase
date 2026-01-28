"""
createモードのtouched gate検証スクリプト（SQLite前提）

目的:
createモードで主要6項目（CORE_FIELDS）が正しくtouched gateで制御されているかを
1コマンドで確認する。

使用方法:
    # デフォルト（最新5件を表示）
    python scripts/debug_submission_payload.py
    
    # 最新10件を表示
    python scripts/debug_submission_payload.py --limit 10
    
    # データベースファイルを指定
    python scripts/debug_submission_payload.py --db custom.db

出力例:
    ================================================================================
    material_submissions 検証結果（最新5件）
    ================================================================================
    
    [1] ID: 123, Status: pending, Name: テスト材料
        CORE_FIELDS:
          name_official: 'テスト材料' ✓
          category_main: None ✗ (touched gateで除外)
          origin_type: None ✗ (touched gateで除外)
          transparency: None ✗ (touched gateで除外)
          visibility: None ✗ (touched gateで除外)
          is_published: None ✗ (touched gateで除外)
        payload_json keys: ['name_official', 'supplier_org', ...] (15 keys)

注意:
- SQLiteのmaterials.dbを直接読み込みます（ORM不使用）
- 標準ライブラリのみ使用（sqlite3, json, argparse）
- payload_jsonがJSON文字列として保存されていることを前提とします
"""
import sqlite3
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

# CORE_FIELDSの定義（material_form_detailed.pyと一致）
CORE_FIELDS = [
    'name_official',
    'category_main',
    'origin_type',
    'transparency',
    'visibility',
    'is_published',
]


def format_value(value, max_length=60):
    """
    値を表示用にフォーマット（長すぎる場合は切る）
    
    Args:
        value: 表示する値
        max_length: 最大表示長
    
    Returns:
        str: フォーマット済み文字列
    """
    if value is None:
        return "None"
    
    value_str = repr(value)
    if len(value_str) > max_length:
        return value_str[:max_length-3] + "..."
    return value_str


def extract_core_fields(payload_dict):
    """
    payload_dictからCORE_FIELDSを抽出
    
    Args:
        payload_dict: payload_jsonをパースしたdict
    
    Returns:
        dict: CORE_FIELDSの値のみを含む辞書
    """
    return {field: payload_dict.get(field) for field in CORE_FIELDS}


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="createモードのtouched gate検証スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='表示する最新件数（デフォルト: 5）'
    )
    parser.add_argument(
        '--db',
        type=str,
        default='materials.db',
        help='SQLiteデータベースファイルのパス（デフォルト: materials.db）'
    )
    
    args = parser.parse_args()
    
    # データベースファイルのパスを解決
    db_path = Path(args.db)
    if not db_path.is_absolute():
        # 相対パスの場合、プロジェクトルートからの相対パスとして扱う
        project_root = Path(__file__).parent.parent
        db_path = project_root / args.db
    
    # データベースファイルの存在確認
    if not db_path.exists():
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        print(f"   （絶対パス: {db_path.absolute()})")
        return 1
    
    print("=" * 80)
    print(f"material_submissions 検証結果（最新{args.limit}件）")
    print("=" * 80)
    print(f"Database: {db_path}")
    print()
    
    try:
        # SQLite接続
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row  # 辞書形式で取得できるようにする
        cursor = conn.cursor()
        
        # material_submissionsテーブルの存在確認
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='material_submissions'
        """)
        if not cursor.fetchone():
            print("❌ material_submissions テーブルが存在しません。")
            print("   （マイグレーションが実行されていない可能性があります）")
            conn.close()
            return 1
        
        # 最新N件を取得
        cursor.execute("""
            SELECT 
                id,
                uuid,
                status,
                name_official,
                payload_json,
                created_at,
                submitted_by
            FROM material_submissions
            ORDER BY id DESC
            LIMIT ?
        """, (args.limit,))
        
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ material_submissions が見つかりませんでした。")
            print("   （データがありません）")
            conn.close()
            return 0
        
        # 各submissionを表示
        for idx, row in enumerate(rows, 1):
            submission_id = row['id']
            uuid = row['uuid']
            status = row['status']
            name_official = row['name_official']
            payload_json_raw = row['payload_json']
            created_at = row['created_at']
            submitted_by = row['submitted_by']
            
            print(f"[{idx}] ID: {submission_id}, Status: {status}, Name: {name_official or '(空)'}")
            if uuid:
                print(f"    UUID: {uuid}")
            if created_at:
                print(f"    Created: {created_at}")
            if submitted_by:
                print(f"    Submitted by: {submitted_by}")
            print()
            
            # payload_jsonをパース
            try:
                if isinstance(payload_json_raw, str):
                    payload_dict = json.loads(payload_json_raw)
                elif isinstance(payload_json_raw, dict):
                    payload_dict = payload_json_raw
                else:
                    print(f"    ⚠️  payload_json の型が不正です: {type(payload_json_raw)}")
                    print()
                    continue
            except json.JSONDecodeError as e:
                print(f"    ❌ payload_json のパースに失敗しました: {e}")
                print()
                continue
            
            # CORE_FIELDSを抽出して表示
            print("    CORE_FIELDS:")
            core_fields = extract_core_fields(payload_dict)
            for field, value in core_fields.items():
                # 含まれているかどうかでマークを付ける
                is_included = value is not None
                mark = "✓" if is_included else "✗"
                value_str = format_value(value)
                
                # touched gateで除外された場合の説明を追加
                if not is_included and field != 'name_official':
                    note = " (touched gateで除外)"
                elif not is_included and field == 'name_official':
                    note = " (空またはtouched gateで除外)"
                else:
                    note = ""
                
                print(f"      {field:20s}: {value_str:60s} {mark}{note}")
            
            # payload_jsonのkeysを表示
            payload_keys = list(payload_dict.keys())
            print(f"    payload_json keys: {payload_keys} ({len(payload_keys)} keys)")
            
            # CORE_FIELDSが含まれているかどうかのサマリー
            included_count = sum(1 for v in core_fields.values() if v is not None)
            excluded_count = len(CORE_FIELDS) - included_count
            if excluded_count > 0:
                excluded_fields = [f for f, v in core_fields.items() if v is None]
                print(f"    ⚠️  {excluded_count}個のCORE_FIELDSが除外されています: {excluded_fields}")
            else:
                print(f"    ✅ すべてのCORE_FIELDSが含まれています")
            
            print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ SQLiteエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("=" * 80)
    print("検証完了")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
