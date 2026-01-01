"""
データベース設定とモデル定義
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# SQLiteデータベースの作成
SQLALCHEMY_DATABASE_URL = "sqlite:///./materials.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Material(Base):
    """材料テーブル"""
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    properties = relationship("Property", back_populates="material", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="material", cascade="all, delete-orphan")
    metadata = relationship("Metadata", back_populates="material", cascade="all, delete-orphan")


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


class Metadata(Base):
    """メタデータテーブル"""
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="metadata")


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

