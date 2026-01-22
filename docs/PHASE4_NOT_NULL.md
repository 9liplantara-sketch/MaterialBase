# Phase 4: materials の NOT NULL 列一覧

## 抽出元
- `database.py` の `Material` モデル定義から抽出（2026-01-15時点）

## NOT NULL 列一覧

| 列名 | 型 | デフォルト値（DB側） | 補完デフォルト値 | 備考 |
|------|-----|---------------------|-----------------|------|
| `name_official` | String(255) | - | - | 必須（空は許さない） |
| `category_main` | String(100) | - | - | 必須（空は許さない） |
| `origin_type` | String(50) | - | `'不明'` | 補完対象 |
| `origin_detail` | String(255) | - | `'不明'` | 補完対象 |
| `transparency` | String(50) | - | `'不明'` | 補完対象 |
| `hardness_qualitative` | String(50) | - | `'不明'` | 補完対象 |
| `weight_qualitative` | String(50) | - | `'不明'` | 補完対象 |
| `water_resistance` | String(50) | - | `'不明'` | 補完対象 |
| `weather_resistance` | String(50) | - | `'不明'` | 補完対象 |
| `equipment_level` | String(50) | `'家庭/工房レベル'` | `'家庭/工房レベル'` | DB側デフォルトあり |
| `prototyping_difficulty` | String(50) | `'中'` | `'中'` | DB側デフォルトあり |
| `procurement_status` | String(50) | - | `'不明'` | 補完対象 |
| `cost_level` | String(50) | - | `'不明'` | 補完対象 |
| `visibility` | String(50) | `'公開'` | `'非公開（管理者のみ）'` | DB側デフォルトあり、ただし安全側に倒す |
| `is_published` | Integer | `1` | `0` | DB側デフォルトあり、ただし安全側に倒す |
| `is_deleted` | Integer | `0` | `0` | DB側デフォルトあり |

## 補完方針

### 必須項目（補完しない）
- `name_official`: 空の場合はエラー（バリデーションで弾く）
- `category_main`: 空の場合はエラー（バリデーションで弾く）

### 補完対象（デフォルト値で埋める）
- `origin_type`, `origin_detail`, `transparency`, `hardness_qualitative`, `weight_qualitative`, `water_resistance`, `weather_resistance`, `procurement_status`, `cost_level`: `'不明'` で補完

### DB側デフォルトあり（ただし安全側に倒す）
- `equipment_level`: DB側デフォルト `'家庭/工房レベル'` を使用
- `prototyping_difficulty`: DB側デフォルト `'中'` を使用
- `visibility`: DB側デフォルト `'公開'` があるが、安全側に倒して `'非公開（管理者のみ）'` をデフォルトとする
- `is_published`: DB側デフォルト `1` があるが、安全側に倒して `0` をデフォルトとする（`visibility` から決定）
- `is_deleted`: DB側デフォルト `0` を使用

## 更新手順

新しい NOT NULL 列が追加された場合：
1. `database.py` の `Material` モデルに `nullable=False` の列を追加
2. `utils/material_defaults.py` の `REQUIRED_FIELDS` に列名を追加
3. `utils/material_defaults.py` の `DEFAULT_VALUES` にデフォルト値を追加（必要に応じて）
4. このドキュメントを更新
