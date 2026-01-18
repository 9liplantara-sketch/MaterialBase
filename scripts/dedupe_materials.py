"""
同名重複 Materials の棚卸し・統合スクリプト（dry-run デフォルト）

方針:
- is_deleted=0 を対象に、正規化キーで同名重複を検出
- dry-run で CSV レポートを出力
- --apply で関連テーブルを canonical に付け替え、dup は is_deleted=1
"""
import sys
import argparse
import csv
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import (
    SessionLocal,
    Material,
    Property,
    Image,
    ReferenceURL,
    UseExample,
    MaterialSubmission,
    init_db,
)
from sqlalchemy import func
from sqlalchemy.orm import Session


def normalize_name(name: str) -> str:
    if name is None:
        return ""
    s = name.strip()
    s = s.replace("\u3000", " ")  # 全角スペース → 半角
    s = re.sub(r"\s+", " ", s)
    if re.search(r"[A-Za-z]", s):
        s = s.lower()
    return s


def ensure_reports_dir() -> Path:
    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def collect_materials(db: Session) -> List[Material]:
    return (
        db.query(Material)
        .filter(Material.is_deleted == 0)
        .filter(Material.name_official.isnot(None))
        .all()
    )


def get_counts(db: Session) -> Dict[str, Dict[int, int]]:
    def _count(model, col_name: str) -> Dict[int, int]:
        rows = (
            db.query(model.material_id, func.count(model.id))
            .group_by(model.material_id)
            .all()
        )
        return {mid: cnt for mid, cnt in rows}

    return {
        "images": _count(Image, "images"),
        "properties": _count(Property, "properties"),
        "reference_urls": _count(ReferenceURL, "reference_urls"),
        "use_examples": _count(UseExample, "use_examples"),
        "approved_submissions": {
            mid: cnt
            for mid, cnt in db.query(MaterialSubmission.approved_material_id, func.count(MaterialSubmission.id))
            .filter(MaterialSubmission.approved_material_id.isnot(None))
            .group_by(MaterialSubmission.approved_material_id)
            .all()
        },
    }


def choose_canonical(materials: List[Material], counts: Dict[str, Dict[int, int]]) -> Material:
    def score(m: Material) -> Tuple:
        has_desc = 1 if (m.description and str(m.description).strip()) else 0
        img_count = counts["images"].get(m.id, 0)
        prop_count = counts["properties"].get(m.id, 0)
        is_published = 1 if getattr(m, "is_published", 0) == 1 else 0
        return (
            is_published,
            has_desc,
            img_count,
            prop_count,
            -m.id,  # tie-breaker: smaller id wins (reverse for max)
        )

    return sorted(materials, key=score, reverse=True)[0]


def build_duplicate_groups(materials: List[Material]) -> Dict[str, List[Material]]:
    groups: Dict[str, List[Material]] = defaultdict(list)
    for m in materials:
        key = normalize_name(m.name_official or "")
        if key:
            groups[key].append(m)
    return {k: v for k, v in groups.items() if len(v) > 1}


def report_duplicates(duplicates: Dict[str, List[Material]], counts: Dict[str, Dict[int, int]]) -> Path:
    reports_dir = ensure_reports_dir()
    filename = f"duplicates_report_{datetime.now().strftime('%Y%m%d')}.csv"
    report_path = reports_dir / filename

    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "group_key",
            "material_id",
            "name_official",
            "created_at",
            "updated_at",
            "is_published",
            "is_deleted",
            "has_description",
            "images_count",
            "properties_count",
            "reference_urls_count",
            "use_examples_count",
            "approved_submissions_count",
        ])
        for key, mats in duplicates.items():
            for m in mats:
                writer.writerow([
                    key,
                    m.id,
                    m.name_official,
                    m.created_at.isoformat() if m.created_at else "",
                    m.updated_at.isoformat() if m.updated_at else "",
                    getattr(m, "is_published", 0),
                    getattr(m, "is_deleted", 0),
                    1 if (m.description and str(m.description).strip()) else 0,
                    counts["images"].get(m.id, 0),
                    counts["properties"].get(m.id, 0),
                    counts["reference_urls"].get(m.id, 0),
                    counts["use_examples"].get(m.id, 0),
                    counts["approved_submissions"].get(m.id, 0),
                ])

    return report_path


def merge_fill_canonical(canonical: Material, dup: Material) -> None:
    fill_fields = [
        "description",
        "category_main",
        "category_other",
        "origin_type",
        "origin_detail",
        "supplier_org",
        "supplier_type",
        "supplier_other",
        "procurement_status",
        "cost_level",
        "cost_value",
        "cost_unit",
    ]
    for field in fill_fields:
        c_val = getattr(canonical, field, None)
        d_val = getattr(dup, field, None)
        if (c_val is None or str(c_val).strip() == "") and d_val not in (None, ""):
            setattr(canonical, field, d_val)

    # 統合先IDを description に追記
    note = f"\n[Merged into ID: {canonical.id} at {datetime.utcnow().isoformat()}]"
    if dup.description:
        if "Merged into ID:" not in dup.description:
            dup.description = f"{dup.description}{note}"
    else:
        dup.description = note.strip()


def migrate_relations(db: Session, canonical: Material, dup: Material) -> Dict[str, int]:
    moved = {"images": 0, "properties": 0, "reference_urls": 0, "use_examples": 0, "submissions": 0}

    # images: r2_key / kind 重複はスキップ
    existing_r2 = {
        img.r2_key for img in db.query(Image).filter(Image.material_id == canonical.id).all() if img.r2_key
    }
    existing_kind = {
        img.kind for img in db.query(Image).filter(Image.material_id == canonical.id).all() if img.kind
    }
    for img in db.query(Image).filter(Image.material_id == dup.id).all():
        if img.r2_key and img.r2_key in existing_r2:
            continue
        if img.kind and img.kind in existing_kind:
            continue
        img.material_id = canonical.id
        moved["images"] += 1

    # properties: canonical に値がある場合はスキップ、無ければ補完
    for prop in db.query(Property).filter(Property.material_id == dup.id).all():
        existing = (
            db.query(Property)
            .filter(Property.material_id == canonical.id, Property.property_name == prop.property_name)
            .first()
        )
        if existing:
            if (existing.value is None) and (prop.value is not None):
                existing.value = prop.value
                existing.unit = existing.unit or prop.unit
                existing.measurement_condition = existing.measurement_condition or prop.measurement_condition
            continue
        # そのまま移動
        prop.material_id = canonical.id
        moved["properties"] += 1

    # reference_urls: url 重複はスキップ
    existing_urls = {
        r.url for r in db.query(ReferenceURL).filter(ReferenceURL.material_id == canonical.id).all()
    }
    for ref in db.query(ReferenceURL).filter(ReferenceURL.material_id == dup.id).all():
        if ref.url in existing_urls:
            continue
        ref.material_id = canonical.id
        moved["reference_urls"] += 1

    # use_examples: (example_name, example_url) 重複はスキップ
    existing_ue = {
        (u.example_name, u.example_url)
        for u in db.query(UseExample).filter(UseExample.material_id == canonical.id).all()
    }
    for ue in db.query(UseExample).filter(UseExample.material_id == dup.id).all():
        key = (ue.example_name, ue.example_url)
        if key in existing_ue:
            continue
        ue.material_id = canonical.id
        moved["use_examples"] += 1

    # submissions approved_material_id
    for sub in (
        db.query(MaterialSubmission)
        .filter(MaterialSubmission.approved_material_id == dup.id)
        .all()
    ):
        sub.approved_material_id = canonical.id
        moved["submissions"] += 1

    return moved


def dedupe(dry_run: bool, only_name: Optional[str], limit: Optional[int]) -> None:
    init_db()
    db = SessionLocal()
    try:
        materials = collect_materials(db)
        counts = get_counts(db)
        duplicates = build_duplicate_groups(materials)

        if only_name:
            key = normalize_name(only_name)
            duplicates = {key: duplicates.get(key, [])} if duplicates.get(key) else {}

        if not duplicates:
            print("✅ 重複している材料はありません。")
            return

        report_path = report_duplicates(duplicates, counts)
        print(f"✅ レポート出力: {report_path}")

        if dry_run:
            print("🔍 dry-run 完了（apply していません）")
            return

        # apply モード
        group_items = list(duplicates.items())
        if limit:
            group_items = group_items[:limit]

        for key, mats in group_items:
            canonical = choose_canonical(mats, counts)
            dups = [m for m in mats if m.id != canonical.id]
            print(f"\n[MERGE] {key} -> canonical ID {canonical.id} ({len(dups)} dup)")
            try:
                for dup in dups:
                    moved = migrate_relations(db, canonical, dup)
                    merge_fill_canonical(canonical, dup)
                    dup.is_deleted = 1
                    dup.deleted_at = datetime.utcnow()
                    print(f"  - dup {dup.id} merged, moved: {moved}")
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"❌ group merge failed: {key} error={e}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="同名重複 Materials の整理（dry-run デフォルト）")
    parser.add_argument("--dry-run", action="store_true", help="dry-run（デフォルト）")
    parser.add_argument("--apply", action="store_true", help="実際に適用する")
    parser.add_argument("--only-name", type=str, help="指定名のみ適用")
    parser.add_argument("--limit", type=int, help="処理する重複グループ数の上限")
    args = parser.parse_args()

    dry_run = not args.apply
    if dry_run:
        print("🔍 dry-run モード（apply しません）")
    else:
        print("⚠️  apply モード（実際に更新します）")

    dedupe(dry_run=dry_run, only_name=args.only_name, limit=args.limit)


if __name__ == "__main__":
    main()

