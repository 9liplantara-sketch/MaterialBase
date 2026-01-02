"""
サンプルデータの初期化スクリプト
データベースにサンプル材料データを追加します
"""

from database import SessionLocal, Material, Property, Image, MaterialMetadata
from datetime import datetime


def init_sample_data():
    """サンプルデータをデータベースに追加"""
    db = SessionLocal()
    
    try:
        # サンプル材料1: ステンレス鋼
        material1 = Material(
            name="ステンレス鋼 SUS304",
            category="金属",
            description="オーステナイト系ステンレス鋼。優れた耐食性と加工性を持つ。"
        )
        db.add(material1)
        db.flush()
        
        db.add(Property(material_id=material1.id, property_name="密度", value=7.93, unit="g/cm³"))
        db.add(Property(material_id=material1.id, property_name="引張強度", value=520, unit="MPa"))
        db.add(Property(material_id=material1.id, property_name="降伏強度", value=205, unit="MPa"))
        db.add(Property(material_id=material1.id, property_name="融点", value=1400, unit="°C"))
        db.add(Property(material_id=material1.id, property_name="熱伝導率", value=16.3, unit="W/(m·K)"))
        
        db.add(MaterialMetadata(material_id=material1.id, key="JIS規格", value="JIS G 4305"))
        db.add(MaterialMetadata(material_id=material1.id, key="主成分", value="Fe, Cr 18%, Ni 8%"))
        
        # サンプル材料2: アルミニウム合金
        material2 = Material(
            name="アルミニウム合金 A5052",
            category="金属",
            description="マグネシウムを主合金元素とするアルミニウム合金。軽量で耐食性に優れる。"
        )
        db.add(material2)
        db.flush()
        
        db.add(Property(material_id=material2.id, property_name="密度", value=2.68, unit="g/cm³"))
        db.add(Property(material_id=material2.id, property_name="引張強度", value=230, unit="MPa"))
        db.add(Property(material_id=material2.id, property_name="降伏強度", value=195, unit="MPa"))
        db.add(Property(material_id=material2.id, property_name="融点", value=607, unit="°C"))
        db.add(Property(material_id=material2.id, property_name="熱伝導率", value=138, unit="W/(m·K)"))
        
        db.add(MaterialMetadata(material_id=material2.id, key="JIS規格", value="JIS H 4000"))
        db.add(MaterialMetadata(material_id=material2.id, key="主成分", value="Al, Mg 2.5%"))
        
        # サンプル材料3: ポリエチレン
        material3 = Material(
            name="ポリエチレン (PE)",
            category="プラスチック",
            description="最も一般的な熱可塑性樹脂。優れた化学的安定性と電気絶縁性を持つ。"
        )
        db.add(material3)
        db.flush()
        
        db.add(Property(material_id=material3.id, property_name="密度", value=0.92, unit="g/cm³"))
        db.add(Property(material_id=material3.id, property_name="引張強度", value=20, unit="MPa"))
        db.add(Property(material_id=material3.id, property_name="融点", value=130, unit="°C"))
        db.add(Property(material_id=material3.id, property_name="ガラス転移温度", value=-120, unit="°C"))
        
        db.add(MaterialMetadata(material_id=material3.id, key="化学式", value="(C2H4)n"))
        db.add(MaterialMetadata(material_id=material3.id, key="用途", value="包装材、パイプ、容器"))
        
        # サンプル材料4: セラミック
        material4 = Material(
            name="アルミナセラミック",
            category="セラミック",
            description="高純度アルミナを主成分とするセラミック。高い硬度と耐熱性を持つ。"
        )
        db.add(material4)
        db.flush()
        
        db.add(Property(material_id=material4.id, property_name="密度", value=3.9, unit="g/cm³"))
        db.add(Property(material_id=material4.id, property_name="引張強度", value=300, unit="MPa"))
        db.add(Property(material_id=material4.id, property_name="硬度", value=9, unit="モース硬度"))
        db.add(Property(material_id=material4.id, property_name="融点", value=2050, unit="°C"))
        db.add(Property(material_id=material4.id, property_name="熱伝導率", value=30, unit="W/(m·K)"))
        
        db.add(MaterialMetadata(material_id=material4.id, key="主成分", value="Al2O3 99%以上"))
        db.add(MaterialMetadata(material_id=material4.id, key="用途", value="絶縁材料、機械部品"))
        
        db.commit()
        print("サンプルデータの追加が完了しました！")
        print(f"- 材料1: {material1.name} (ID: {material1.id})")
        print(f"- 材料2: {material2.name} (ID: {material2.id})")
        print(f"- 材料3: {material3.name} (ID: {material3.id})")
        print(f"- 材料4: {material4.name} (ID: {material4.id})")
        
    except Exception as e:
        db.rollback()
        print(f"エラーが発生しました: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    init_sample_data()

