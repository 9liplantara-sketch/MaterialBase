"""
データベース設定とモデル定義（詳細仕様対応版）
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

# SQLiteデータベースの作成
SQLALCHEMY_DATABASE_URL = "sqlite:///./materials.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Material(Base):
    """材料テーブル（詳細仕様対応）"""
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True)  # UUID
    
    # 1. 基本識別情報
    name_official = Column(String(255), nullable=False, index=True)  # 材料名（正式）
    name_aliases = Column(Text)  # 材料名（通称・略称）複数（JSON文字列）
    supplier_org = Column(String(255))  # 供給元・開発主体（組織名）
    supplier_type = Column(String(50))  # 供給元種別
    supplier_other = Column(String(255))  # その他（自由記述）
    
    # 2. 分類
    category_main = Column(String(100), nullable=False, index=True)  # 材料カテゴリ（大分類）
    category_other = Column(String(255))  # その他（自由記述）
    material_forms = Column(Text)  # 材料形態（複数選択）（JSON文字列）
    material_forms_other = Column(String(255))  # その他（自由記述）
    
    # 3. 由来・原料
    origin_type = Column(String(50), nullable=False)  # 原料由来（一次分類）
    origin_detail = Column(String(255), nullable=False)  # 原料詳細（具体名）
    origin_other = Column(String(255))  # その他（自由記述）
    recycle_bio_rate = Column(Float)  # リサイクル/バイオ含有率（%）
    recycle_bio_basis = Column(String(50))  # 根拠
    
    # 4. 基本特性
    color_tags = Column(Text)  # 色（複数選択）（JSON文字列）
    transparency = Column(String(50), nullable=False)  # 透明性
    hardness_qualitative = Column(String(50), nullable=False)  # 硬さ（定性）
    hardness_value = Column(String(100))  # 硬さ（数値）
    weight_qualitative = Column(String(50), nullable=False)  # 重さ感（定性）
    specific_gravity = Column(Float)  # 比重
    water_resistance = Column(String(50), nullable=False)  # 耐水性・耐湿性
    heat_resistance_temp = Column(Float)  # 耐熱性（温度℃）
    heat_resistance_range = Column(String(50), nullable=False)  # 耐熱性（範囲）
    weather_resistance = Column(String(50), nullable=False)  # 耐候性
    
    # 5. 加工・実装条件
    processing_methods = Column(Text)  # 加工方法（複数選択）（JSON文字列）
    processing_other = Column(String(255))  # その他（自由記述）
    equipment_level = Column(String(50), nullable=False)  # 必要設備レベル
    prototyping_difficulty = Column(String(50), nullable=False)  # 試作難易度
    
    # 6. 用途・市場状態
    use_categories = Column(Text)  # 主用途カテゴリ（複数選択）（JSON文字列）
    use_other = Column(String(255))  # その他（自由記述）
    procurement_status = Column(String(50), nullable=False)  # 調達性
    cost_level = Column(String(50), nullable=False)  # コスト帯
    cost_value = Column(Float)  # 価格情報（数値）
    cost_unit = Column(String(50))  # 価格単位
    
    # 7. 制約・安全・法規
    safety_tags = Column(Text)  # 安全区分（複数選択）（JSON文字列）
    safety_other = Column(String(255))  # その他（自由記述）
    restrictions = Column(Text)  # 禁止・注意事項
    
    # 8. 公開範囲
    visibility = Column(String(50), nullable=False, default="公開")  # 公開設定
    
    # レイヤー②：あったら良い情報
    # A. ストーリー・背景
    development_motives = Column(Text)  # 開発動機タイプ（複数選択）（JSON文字列）
    development_motive_other = Column(String(255))  # その他（自由記述）
    development_background_short = Column(String(500))  # 開発背景（短文）
    development_story = Column(Text)  # 開発ストーリー（長文）
    
    # B. 歴史・系譜
    related_materials = Column(Text)  # 関連材料（複数選択＋自由記述）（JSON文字列）
    
    # C. 感覚的特性
    tactile_tags = Column(Text)  # 触感タグ（複数選択）（JSON文字列）
    tactile_other = Column(String(255))  # その他（自由記述）
    visual_tags = Column(Text)  # 視覚タグ（複数選択）（JSON文字列）
    visual_other = Column(String(255))  # その他（自由記述）
    sound_smell = Column(String(500))  # 音・匂い
    
    # D. 使われなかった可能性
    ng_uses = Column(Text)  # NG用途（複数選択）（JSON文字列）
    ng_uses_detail = Column(Text)  # NG用途詳細
    rejected_uses = Column(Text)  # 実験したが採用されなかった用途
    
    # E. デザイナー向け実装知
    suitable_shapes = Column(Text)  # 向いている形状/スケール（複数選択）（JSON文字列）
    suitable_shapes_other = Column(String(255))  # その他（自由記述）
    compatible_materials = Column(Text)  # 相性の良い組み合わせ
    processing_knowhow = Column(Text)  # 加工ノウハウ
    
    # F. 環境・倫理・未来
    circularity = Column(String(50))  # 循環性
    certifications = Column(Text)  # 認証・規格（複数選択）（JSON文字列）
    certifications_other = Column(String(255))  # その他（自由記述）
    
    # G. 想像を促す問い
    question_templates = Column(Text)  # "問い"テンプレ（複数選択）（JSON文字列）
    question_answers = Column(Text)  # その問いへの回答
    
    # 旧フィールド（後方互換性のため保持）
    name = Column(String(255))  # 旧name（後方互換）
    category = Column(String(100), index=True)  # 旧category（後方互換）
    description = Column(Text)  # 旧description（後方互換）
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    properties = relationship("Property", back_populates="material", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="material", cascade="all, delete-orphan")
    metadata_items = relationship("MaterialMetadata", back_populates="material", cascade="all, delete-orphan")
    reference_urls = relationship("ReferenceURL", back_populates="material", cascade="all, delete-orphan")
    use_examples = relationship("UseExample", back_populates="material", cascade="all, delete-orphan")


class Property(Base):
    """物性テーブル"""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    property_name = Column(String(100), nullable=False)
    value = Column(Float)
    unit = Column(String(50))
    measurement_condition = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="properties")


class Image(Base):
    """画像テーブル"""
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    image_type = Column(String(50))  # sample, microscope, etc.
    description = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="images")


class MaterialMetadata(Base):
    """メタデータテーブル"""
    __tablename__ = "material_metadata"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="metadata_items")


class ReferenceURL(Base):
    """参照URLテーブル"""
    __tablename__ = "reference_urls"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    url = Column(String(500), nullable=False)
    url_type = Column(String(50))  # 公式/製品/論文/プレス等
    description = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="reference_urls")


class UseExample(Base):
    """代表的使用例テーブル"""
    __tablename__ = "use_examples"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    example_name = Column(String(255), nullable=False)  # 製品名/事例名
    example_url = Column(String(500))  # リンク
    description = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="use_examples")


# データベーステーブルの作成
def init_db():
    Base.metadata.create_all(bind=engine)


# データベースセッションの依存性注入用
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

