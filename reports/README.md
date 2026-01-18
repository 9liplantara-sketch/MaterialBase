# 重複整理レポート

このフォルダには `scripts/dedupe_materials.py` の dry-run 出力CSVが保存されます。

## 出力ファイル例
`duplicates_report_YYYYMMDD.csv`

## CSVヘッダー
```
group_key,material_id,name_official,created_at,updated_at,is_published,is_deleted,has_description,images_count,properties_count,reference_urls_count,use_examples_count,approved_submissions_count
```

## 1行サンプル
```
コンクリート,12,コンクリート,2026-01-05T10:00:00,2026-01-10T08:30:00,1,0,1,2,3,1,0,0
```
