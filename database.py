"""
データベース設定とモデル定義（詳細仕様対応版）
Postgres対応: URL駆動でSQLite/Postgres両対応
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, Index, BigInteger
from sqlalchemy import text as sa_text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json
import os

# 設定からデータベースURLを取得（優先順位: st.secrets > os.environ > フォールバック）
try:
    from utils.settings import get_database_url, is_cloud, get_db_dialect
    SQLALCHEMY_DATABASE_URL = get_database_url()
    DB_DIALECT = get_db_dialect(SQLALCHEMY_DATABASE_URL)
    IS_CLOUD = is_cloud()
    
    # Cloud環境でSQLiteを使用しようとした場合は例外
    if IS_CLOUD and DB_DIALECT == "sqlite":
        raise RuntimeError(
            "SQLite is not allowed on Streamlit Cloud. "
            "Please set DATABASE_URL to PostgreSQL in Streamlit Secrets."
        )
except Exception as e:
    # エラーを再発生（Cloudでの設定ミスを明確にする）
    if "DATABASE_URL" in str(e) or "SQLite is not allowed" in str(e):
        raise
    
    # ローカル環境のみ: フォールバック（SQLite）
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./materials.db")
    DB_DIALECT = "postgresql" if SQLALCHEMY_DATABASE_URL.startswith(("postgresql://", "postgres://")) else "sqlite"
    IS_CLOUD = False

# DEBUGモード判定
DEBUG_MODE = os.getenv("DEBUG", "0") == "1"

# エンジンとSessionLocalをキャッシュ経由で取得（utils/db.py を使用）
try:
    from utils.db import get_engine, get_sessionmaker
    # キャッシュされた engine と sessionmaker を取得
    engine = get_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = get_sessionmaker(SQLALCHEMY_DATABASE_URL)
except Exception as e:
    # フォールバック: 従来の方法（後方互換性）
    if DB_DIALECT == "postgresql":
        # Postgres設定
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_pre_ping=True,  # 接続の死活監視
            future=True,  # SQLAlchemy 2.0互換
            echo=DEBUG_MODE,  # DEBUG時のみSQLログ
        )
    elif DB_DIALECT == "sqlite":
        # SQLite設定（ローカル開発用）
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=DEBUG_MODE,  # DEBUG時のみSQLログ
        )
    else:
        raise ValueError(f"Unsupported database dialect: {DB_DIALECT}")
    
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False
    )

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
    equipment_level = Column(String(50), nullable=False, default="家庭/工房レベル", server_default="家庭/工房レベル")  # 必要設備レベル
    prototyping_difficulty = Column(String(50), nullable=False, default="中", server_default="中")  # 試作難易度
    
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
    is_published = Column(Integer, nullable=False, default=1)  # 掲載可否（0: 非公開, 1: 公開）
    
    # 論理削除フラグ
    is_deleted = Column(Integer, nullable=False, default=0)  # 論理削除（0: 有効, 1: 削除済み）
    deleted_at = Column(DateTime, nullable=True)  # 削除日時
    
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
    
    # STEP 6: 材料×元素のマッピング
    main_elements = Column(Text)  # 主要元素リスト（原子番号のJSON配列、例: [1, 6, 8]）
    
    # 旧フィールド（後方互換性のため保持）
    name = Column(String(255))  # 旧name（後方互換）
    category = Column(String(100), index=True)  # 旧category（後方互換）
    description = Column(Text)  # 旧description（後方互換）
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 画像パス（生成物）
    texture_image_path = Column(String(500))  # テクスチャ画像パス（相対パス、後方互換）
    texture_image_url = Column(String(1000))  # テクスチャ画像URL（S3 URL、新規追加）
    
    # リレーション
    properties = relationship("Property", back_populates="material", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="material", cascade="all, delete-orphan")
    metadata_items = relationship("MaterialMetadata", back_populates="material", cascade="all, delete-orphan")
    reference_urls = relationship("ReferenceURL", back_populates="material", cascade="all, delete-orphan")
    use_examples = relationship("UseExample", back_populates="material", cascade="all, delete-orphan")
    process_example_images = relationship("ProcessExampleImage", back_populates="material", cascade="all, delete-orphan")


class MaterialSubmission(Base):
    """材料投稿テーブル（承認フロー用）"""
    __tablename__ = "material_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ステータス: pending/approved/rejected
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    
    # 材料名（正式）- 重複チェック用（DBには既に追加済み想定）
    name_official = Column(String(255), nullable=True, index=True)  # 材料名（正式）
    
    # 投稿内容（JSON形式でmaterial入力内容を丸ごと保存）
    payload_json = Column(Text, nullable=False)  # JSON文字列
    
    # 編集者メモ・却下理由
    editor_note = Column(Text)  # 編集者メモ
    reject_reason = Column(Text)  # 却下理由
    
    # 投稿者情報（任意）
    submitted_by = Column(String(255))  # 投稿者名/ID
    
    # 承認時に作成された材料ID（承認後の参照用）
    approved_material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)


class Property(Base):
    """物性テーブル"""
    __tablename__ = "properties"
    __table_args__ = (
        # material_id + property_nameを一意制約に（同じ材料に同じ物性を重複登録しない）
        UniqueConstraint('material_id', 'property_name', name='uq_property_material_name'),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    property_name = Column(String(100), nullable=False)
    value = Column(Float)
    unit = Column(String(50))
    measurement_condition = Column(Text)

    # リレーション
    material = relationship("Material", back_populates="properties")


class MaterialEmbedding(Base):
    """材料埋め込みテーブル（pgvector対応）"""
    __tablename__ = "material_embeddings"
    
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True)
    content_hash = Column(String(64), nullable=False)  # 内容のハッシュ（差分更新用）
    
    # pgvector.sqlalchemy.Vectorを使用（Postgresの場合のみ）
    try:
        from pgvector.sqlalchemy import Vector
        embedding = Column(Vector(1536), nullable=True)  # vector(1536)型
    except ImportError:
        # pgvectorがインストールされていない場合はText型でフォールバック
        embedding = Column(Text, nullable=True)
    
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    material = relationship("Material", backref="embedding")


class Image(Base):
    """画像テーブル"""
    __tablename__ = "images"
    __table_args__ = (
        # material_id + kind を一意制約に（同じ材料に同じkindの画像を重複登録しない）
        UniqueConstraint('material_id', 'kind', name='uq_image_material_kind'),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    kind = Column(String(50), nullable=False, default="primary")  # primary/space/product
    file_path = Column(String(500))  # ローカルパス（後方互換、nullableに変更）
    url = Column(String(1000))  # S3 URL（後方互換、nullable）
    r2_key = Column(String(500))  # R2内のキー（パス）
    public_url = Column(String(1000))  # R2公開URL（優先）
    bytes = Column(BigInteger, nullable=True)  # ファイルサイズ（バイト）。bigint型（Postgres）/ integer型（SQLite）
    mime = Column(String(100))  # MIMEタイプ（例: "image/jpeg"）
    sha256 = Column(String(64))  # SHA256ハッシュ
    image_type = Column(String(50))  # sample, microscope, etc.（後方互換）
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    material = relationship("Material", back_populates="images")


class MaterialMetadata(Base):
    """メタデータテーブル"""
    __tablename__ = "material_metadata"
    __table_args__ = (
        # material_id + keyを一意制約に（同じ材料に同じキーのメタデータを重複登録しない）
        UniqueConstraint('material_id', 'key', name='uq_metadata_material_key'),
    )

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
    """代表的使用例テーブル（用途写真対応）"""
    __tablename__ = "use_examples"
    __table_args__ = (
        # material_id + example_nameを一意制約に（同じ材料に同じ用途例を重複登録しない）
        UniqueConstraint('material_id', 'example_name', name='uq_use_example_material_name'),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    example_name = Column(String(255), nullable=False)  # 製品名/事例名（タイトル）
    domain = Column(String(100))  # 領域（内装/プロダクト/建築/キッチン等）
    description = Column(Text)  # 短い説明
    image_path = Column(String(500))  # 画像パス（相対パス、後方互換）
    image_url = Column(String(1000))  # 画像URL（S3 URL、新規追加）
    source_name = Column(String(255))  # 出典名（例: "Generated", "PhotoAC"）
    source_url = Column(String(500))  # 出典URL
    license_note = Column(Text)  # ライセンス表記
    example_url = Column(String(500))  # リンク（後方互換のため残す）

    # リレーション
    material = relationship("Material", back_populates="use_examples")


class ProcessExampleImage(Base):
    """加工例画像テーブル"""
    __tablename__ = "process_example_images"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    process_method = Column(String(100), nullable=False)  # 加工方法名（例: "射出成形"）
    image_path = Column(String(500))  # 画像パス（相対パス、後方互換、nullableに変更）
    image_url = Column(String(1000))  # 画像URL（S3 URL、新規追加）
    description = Column(Text)  # 説明
    source_name = Column(String(255), default="Generated")  # 出典名
    source_url = Column(String(500))  # 出典URL
    license_note = Column(Text)  # ライセンス表記

    # リレーション
    material = relationship("Material", back_populates="process_example_images")


# データベーステーブルの作成
def _sqlite_ensure_columns(db_path: str, table: str, required: dict[str, str]) -> list[str]:
    """
    SQLiteテーブルに不足カラムを自動追加
    
    Args:
        db_path: データベースファイルのパス
        table: テーブル名
        required: {column_name: sqlite_type_sql} の辞書
                 例: {"main_elements": "TEXT"}
    
    Returns:
        追加されたカラム名のリスト
    """
    import sqlite3
    
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}  # row[1] = column name
    
    added = []
    for col, coltype in required.items():
        if col not in existing:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                added.append(col)
            except Exception as e:
                print(f"Warning: Failed to add column {col} to {table}: {e}")
    
    con.commit()
    con.close()
    return added


def _sqlite_type_from_sqlalchemy_type(col_type) -> str:
    """
    SQLAlchemyの型をSQLite型に変換
    
    Args:
        col_type: SQLAlchemyのColumn型
    
    Returns:
        SQLite型文字列（INTEGER, REAL, TEXT）
    """
    type_name = str(col_type)
    
    if "Integer" in type_name or "Boolean" in type_name:
        return "INTEGER"
    elif "Float" in type_name or "Numeric" in type_name:
        return "REAL"
    else:
        # String, Text, DateTime, JSON等は全てTEXT
        return "TEXT"


def migrate_sqlite_schema_if_needed(engine) -> None:
    """
    SQLite DBのスキーマをSQLAlchemyモデルに合わせて自動補完（全テーブルの不足カラムを全部追加）
    
    Args:
        engine: SQLAlchemyエンジン
    """
    from pathlib import Path
    import sqlite3
    
    # engine.url.database が "./materials.db" みたいな形でも動くように正規化
    db_path = getattr(engine.url, "database", None) or "materials.db"
    db_path = db_path.lstrip("/")  # 念のため
    p = Path(db_path)
    
    # DBが無ければ create_all が作るのでここでは何もしない
    if not p.exists():
        return
    
    # SQLiteでない場合はスキップ
    if engine.url.get_backend_name() != "sqlite":
        return
    
    try:
        conn = sqlite3.connect(str(p))
        cursor = conn.cursor()
        
        # Base.metadata.tables に含まれる全テーブルを走査
        for table_name, table in Base.metadata.tables.items():
            try:
                # PRAGMA table_info(<table>) で既存列名を取得
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = {row[1] for row in cursor.fetchall()}  # row[1] = column name
                
                # SQLAlchemy側に存在する列で、SQLite側に無いものを列挙
                missing_columns = {}
                for col in table.columns:
                    col_name = col.name
                    if col_name not in existing_columns:
                        sqlite_type = _sqlite_type_from_sqlalchemy_type(col.type)
                        missing_columns[col_name] = sqlite_type
                
                # 不足カラムを追加
                if missing_columns:
                    added = _sqlite_ensure_columns(str(p), table_name, missing_columns)
                    if added:
                        for col_name in added:
                            col_type = missing_columns[col_name]
                            print(f"[DB MIGRATE] {table_name}: add column {col_name} {col_type}")
                else:
                    print(f"[DB MIGRATE] {table_name}: No missing columns found")
                    
            except Exception as e:
                # テーブル単位のエラーはログして継続（他のテーブルは処理を続ける）
                print(f"[DB MIGRATE] {table_name}: Failed to migrate: {e}")
                import traceback
                traceback.print_exc()
        
        conn.close()
            
    except Exception as e:
        # 起動を止めない（Cloudでログ確認できるようにする）
        print(f"[DB MIGRATION] Failed: {e}")
        import traceback
        traceback.print_exc()


def init_db():
    """
    データベースを初期化
    
    方針:
    - Postgres: Alembicによるマイグレーションを推奨（MIGRATE_ON_START=1で自動実行可）
    - SQLite（ローカルのみ）: create_all + スキーマ補完（後方互換）
    
    注意: Cloud環境ではSQLiteは使用不可（必ずPostgresを指定）
    """
    # Postgres + Cloud + 通常運用時はスキーマ検査をスキップ（パフォーマンス向上）
    if DB_DIALECT == "postgresql" and IS_CLOUD:
        try:
            import utils.settings as settings
            # get_flag が無い場合に備えた二重化
            flag_fn = getattr(settings, "get_flag", None)
            if callable(flag_fn):
                verify = flag_fn("VERIFY_SCHEMA_ON_START", False)
                migrate = flag_fn("MIGRATE_ON_START", False)
            else:
                # フォールバック: os.getenv のみで判定
                verify = os.getenv("VERIFY_SCHEMA_ON_START", "0") == "1"
                migrate = os.getenv("MIGRATE_ON_START", "0") == "1"
        except Exception:
            # utils.settings が利用できない場合はフォールバック
            verify = os.getenv("VERIFY_SCHEMA_ON_START", "0") == "1"
            migrate = os.getenv("MIGRATE_ON_START", "0") == "1"
        
        # スキーマ検査を走らせるのは VERIFY_SCHEMA_ON_START=1 の時だけ
        # MIGRATE_ON_START=1 の時は alembic upgrade head を実行
        # それ以外（通常運用、DEBUG=1含む）は pg_catalog を叩く検査を完全にスキップ
        if not migrate and not verify:
            print("[DB INIT] skip schema verification (postgres cloud, normal operation)")
            # 軽い接続確認だけ行う（SELECT 1）
            # text衝突を避けるため、トップレベルで import 済みの sa_text を使用
            try:
                with engine.connect() as conn:
                    conn.execute(sa_text("SELECT 1"))
                print("[DB INIT] connection check: OK")
            except Exception as e:
                print(f"[DB INIT] connection check failed: {e}")
                import traceback
                traceback.print_exc()
            return
    
    # Alembicマイグレーション（MIGRATE_ON_START=1の時のみ自動実行）
    migrate_on_start = os.getenv("MIGRATE_ON_START", "0") == "1"
    
    if migrate_on_start and DB_DIALECT == "postgresql":
        try:
            from alembic.config import Config
            from alembic import command
            import utils.settings as settings
            
            print("[DB INIT] Alembic migration start (MIGRATE_ON_START=1)")
            
            # データベースURLを取得（utils.settings を使用）
            db_url = settings.get_database_url()
            masked_url = settings.mask_db_url(db_url)
            print(f"[DB INIT] Database URL: {masked_url}")
            
            # Alembic Config を作成
            alembic_cfg = Config("alembic.ini")
            
            # sqlalchemy.url を必ず設定（Streamlit Secrets から取得した URL を使用）
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
            print("[DB INIT] sqlalchemy.url set in alembic config")
            
            # 環境変数にも設定（alembic/env.py のフォールバック用、setdefaultではなく代入で確実に）
            os.environ["DATABASE_URL"] = db_url
            print("[DB INIT] DATABASE_URL set in environment")
            
            # マイグレーション実行
            command.upgrade(alembic_cfg, "head")
            print("[DB INIT] Alembic migration end: SUCCESS")
            
            # migration後の"実確認": images.kind が本当に存在するかDBへ直接問い合わせ
            print("[DB INIT] Verifying images.kind column exists...")
            try:
                from sqlalchemy import create_engine
                verify_engine = create_engine(db_url, pool_pre_ping=True)
                with verify_engine.connect() as conn:
                    # Postgres の場合
                    if DB_DIALECT == "postgresql":
                        query = sa_text("""
                            SELECT COUNT(*) FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'images'
                              AND column_name = 'kind'
                        """)
                        row = conn.execute(query).fetchone()
                        kind_exists = (row[0] > 0) if row else False
                    # SQLite の場合
                    else:
                        query = sa_text("PRAGMA table_info(images)")
                        rows = conn.execute(query).fetchall()
                        column_names = [row[1] for row in rows]  # row[1] が column name
                        kind_exists = "kind" in column_names
                    
                    if not kind_exists:
                        print("[DB INIT] WARNING: images.kind column still missing after migration")
                        print("[DB INIT] Attempting direct ALTER TABLE as fallback...")
                        # 最終手段として明示的に1回だけ ALTER TABLE を実行
                        try:
                            if DB_DIALECT == "postgresql":
                                alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS kind VARCHAR(50)")
                            else:
                                alter_query = sa_text("ALTER TABLE images ADD COLUMN kind VARCHAR(50)")
                            conn.execute(alter_query)
                            conn.commit()
                            print("[DB INIT] ALTER TABLE executed successfully")
                            
                            # 再度存在確認
                            if DB_DIALECT == "postgresql":
                                verify_query = sa_text("""
                                    SELECT COUNT(*) FROM information_schema.columns
                                    WHERE table_schema = 'public'
                                      AND table_name = 'images'
                                      AND column_name = 'kind'
                                """)
                                verify_row = conn.execute(verify_query).fetchone()
                                kind_exists_after = (verify_row[0] > 0) if verify_row else False
                            else:
                                verify_query = sa_text("PRAGMA table_info(images)")
                                verify_rows = conn.execute(verify_query).fetchall()
                                verify_column_names = [row[1] for row in verify_rows]
                                kind_exists_after = "kind" in verify_column_names
                            
                            if kind_exists_after:
                                print("[DB INIT] images.kind column verified: EXISTS")
                            else:
                                print("[DB INIT] ERROR: images.kind column still missing after ALTER TABLE")
                        except Exception as alter_error:
                            print(f"[DB INIT] ERROR: ALTER TABLE failed: {alter_error}")
                    else:
                        print("[DB INIT] images.kind column verified: EXISTS")
                
                verify_engine.dispose()
            except Exception as verify_error:
                print(f"[DB INIT] WARNING: Column verification failed: {verify_error}")
            
            # migration成功後に schema drift 判定のキャッシュを必ず無効化
            try:
                # Streamlit が利用可能な場合はキャッシュをクリア
                if st is not None:
                    # get_schema_drift_status は @st.cache_data(ttl=60) でデコレートされている
                    # 循環インポートを避けるため、直接 st.cache_data.clear() を使用
                    st.cache_data.clear()
                    print("[DB INIT] Schema drift cache cleared (st.cache_data.clear())")
            except Exception as cache_error:
                print(f"[DB INIT] WARNING: Cache clear failed (non-critical): {cache_error}")
                import traceback
                traceback.print_exc()
            
            # (任意) MIGRATE_ON_START=1 のときに、足りない列を自動追加
            try:
                print("[DB INIT] Checking for missing images columns and auto-adding if needed...")
                from sqlalchemy import create_engine
                verify_engine = create_engine(db_url, pool_pre_ping=True)
                with verify_engine.connect() as conn:
                    # スキーマチェックを実行して欠けている列を確認
                    schema_result = check_schema_drift(verify_engine)
                    missing_columns = schema_result.get("images_missing_columns", [])
                    
                    if missing_columns:
                        print(f"[DB INIT] Auto-adding missing columns: {', '.join(missing_columns)}")
                        # 各欠けている列を追加
                        for col in missing_columns:
                            try:
                                if DB_DIALECT == "postgresql":
                                    # Postgres の場合は IF NOT EXISTS を使用
                                    if col == "kind":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS kind VARCHAR(50)")
                                    elif col == "r2_key":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS r2_key VARCHAR(500)")
                                    elif col == "public_url":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS public_url VARCHAR(1000)")
                                    elif col == "mime":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS mime VARCHAR(100)")
                                    elif col == "sha256":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS sha256 VARCHAR(64)")
                                    elif col == "bytes":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN IF NOT EXISTS bytes INTEGER")
                                    else:
                                        print(f"[DB INIT] WARNING: Unknown column name: {col}")
                                        continue
                                else:
                                    # SQLite の場合は IF NOT EXISTS が使えないので、存在確認してから追加
                                    query = sa_text("PRAGMA table_info(images)")
                                    rows = conn.execute(query).fetchall()
                                    existing_columns = {row[1] for row in rows}
                                    if col in existing_columns:
                                        print(f"[DB INIT] Column {col} already exists, skipping")
                                        continue
                                    
                                    if col == "kind":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN kind VARCHAR(50)")
                                    elif col == "r2_key":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN r2_key VARCHAR(500)")
                                    elif col == "public_url":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN public_url VARCHAR(1000)")
                                    elif col == "mime":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN mime VARCHAR(100)")
                                    elif col == "sha256":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN sha256 VARCHAR(64)")
                                    elif col == "bytes":
                                        alter_query = sa_text("ALTER TABLE images ADD COLUMN bytes INTEGER")
                                    else:
                                        print(f"[DB INIT] WARNING: Unknown column name: {col}")
                                        continue
                                
                                conn.execute(alter_query)
                                conn.commit()
                                print(f"[DB INIT] Column {col} added successfully")
                            except Exception as col_error:
                                print(f"[DB INIT] ERROR: Failed to add column {col}: {col_error}")
                        
                        # 再度スキーマチェックを実行して確認
                        schema_result_after = check_schema_drift(verify_engine)
                        missing_after = schema_result_after.get("images_missing_columns", [])
                        if len(missing_after) == 0:
                            print("[DB INIT] All required images columns verified: EXISTS")
                        else:
                            print(f"[DB INIT] WARNING: Some columns still missing after auto-add: {', '.join(missing_after)}")
                    else:
                        print("[DB INIT] All required images columns already exist, no auto-add needed")
                
                verify_engine.dispose()
            except Exception as auto_add_error:
                print(f"[DB INIT] WARNING: Auto-add columns failed (non-critical): {auto_add_error}")
                import traceback
                traceback.print_exc()
            
            # Alembicで処理した場合は後続のcreate_allはスキップ（ただし念のため継続）
            # 通常はAlembicが全てのスキーマ変更を管理するため、create_allは不要
            # ただし、既存のSQLite固有のマイグレーションロジックとの互換性のため、Postgresでも一部実行
        except FileNotFoundError:
            print("[DB INIT] Alembic migration failed: alembic.ini not found, skipping")
        except Exception as e:
            print(f"[DB INIT] Alembic migration end: FAILED - {e}")
            import traceback
            traceback.print_exc()
            # エラー時はcreate_allにフォールバック（開発環境のみ）
            if not IS_CLOUD:
                print("[DB INIT] Falling back to create_all (local dev only)")
    
    # 既存のDBがあっても create_all は無害（足りないテーブルだけ作る）
    # 注意: Postgresでは通常Alembicを使用するため、create_allは開発時のみ
    if DB_DIALECT == "sqlite":
        # SQLite（ローカル開発）: create_all + スキーマ補完
        Base.metadata.create_all(bind=engine)
    elif DB_DIALECT == "postgresql" and not migrate_on_start and not IS_CLOUD:
        # Postgres（ローカル開発、Alembic未使用時のみ）: create_all
        Base.metadata.create_all(bind=engine)
    elif DB_DIALECT == "postgresql" and IS_CLOUD and not migrate_on_start:
        # Cloud環境でPostgres + Alembic未使用の場合は警告（ただし動作は継続）
        print("[DB INIT] WARNING: Cloud環境でAlembic未使用。MIGRATE_ON_START=1を推奨します。")
        # 念のためcreate_allを実行（ただし通常はAlembicを使用）
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            print(f"[DB INIT] create_all failed (Alembic推奨): {e}")
    
    # SQLiteの不足カラム補完（今回のコア修正）
    if engine.url.get_backend_name() == "sqlite":
        try:
            migrate_sqlite_schema_if_needed(engine)
            
            # 既存データにis_published=1を設定（後方互換）
            try:
                with engine.begin() as conn:
                    # is_publishedカラムが存在する場合、NULLのレコードに1を設定
                    conn.execute(sa_text("UPDATE materials SET is_published = 1 WHERE is_published IS NULL"))
            except Exception as e:
                print(f"[DB MIGRATION] Failed to set default is_published: {e}")
            
            # 必須フィールドの空文字修正（既存DBの空文字をデフォルト値で埋める）
            try:
                with engine.begin() as conn:
                    # prototyping_difficulty が NULL または空文字列の場合、"中" に補完
                    result1 = conn.execute(sa_text("""
                        UPDATE materials
                        SET prototyping_difficulty = '中'
                        WHERE prototyping_difficulty IS NULL OR TRIM(prototyping_difficulty) = ''
                    """))
                    # equipment_level が NULL または空文字列の場合、"家庭/工房レベル" に補完
                    result2 = conn.execute(sa_text("""
                        UPDATE materials
                        SET equipment_level = '家庭/工房レベル'
                        WHERE equipment_level IS NULL OR TRIM(equipment_level) = ''
                    """))
                    # visibility が NULL または空文字列の場合、"公開（誰でも閲覧可）" に補完
                    result3 = conn.execute(sa_text("""
                        UPDATE materials
                        SET visibility = '公開（誰でも閲覧可）'
                        WHERE visibility IS NULL OR TRIM(visibility) = ''
                    """))
                    print(f"[DB MIGRATION] Fixed empty required fields: prototyping_difficulty={result1.rowcount}, equipment_level={result2.rowcount}, visibility={result3.rowcount}")
                    
                    # is_deleted/deleted_atカラムの追加と既存行の初期化
                    try:
                        from sqlalchemy import inspect
                        inspector = inspect(engine)
                        columns = [col['name'] for col in inspector.get_columns('materials')]
                        if 'is_deleted' not in columns:
                            conn.execute(sa_text("ALTER TABLE materials ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"))
                            print("[DB MIGRATION] Added is_deleted column to materials")
                        if 'deleted_at' not in columns:
                            conn.execute(sa_text("ALTER TABLE materials ADD COLUMN deleted_at DATETIME"))
                            print("[DB MIGRATION] Added deleted_at column to materials")
                        # 既存行をis_deleted=0で埋める
                        result4 = conn.execute(sa_text("UPDATE materials SET is_deleted = 0 WHERE is_deleted IS NULL"))
                        print(f"[DB MIGRATION] Initialized is_deleted: {result4.rowcount} rows")
                    except Exception as e:
                        print(f"[DB MIGRATION] Failed to add is_deleted/deleted_at: {e}")
            except Exception as e:
                print(f"[DB MIGRATION] Failed to fix empty required fields: {e}")
        except Exception as e:
            # 例外は握りつぶさずログ出して継続
            print(f"[DB MIGRATION] Error in migrate_sqlite_schema_if_needed: {e}")
            import traceback
            traceback.print_exc()
    
    # 既存データベースへのカラム追加（安全にALTER）
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        # 一意制約の追加（既存テーブルに追加を試みる、失敗しても続行）
        # SQLiteでは既存テーブルへの一意制約追加が難しいため、エラーは無視
        try:
            if 'materials' in inspector.get_table_names():
                existing_indexes = [idx['name'] for idx in inspector.get_indexes('materials')]
                if 'uq_material_name_official' not in existing_indexes:
                    # 一意インデックスを作成（SQLiteでは制約として機能）
                    with engine.connect() as conn:
                        try:
                            conn.execute(sa_text("CREATE UNIQUE INDEX IF NOT EXISTS uq_material_name_official ON materials(name_official)"))
                            conn.commit()
                        except Exception:
                            pass  # 既に存在するか、制約追加が失敗した場合は無視
            
            if 'properties' in inspector.get_table_names():
                existing_indexes = [idx['name'] for idx in inspector.get_indexes('properties')]
                if 'uq_property_material_name' not in existing_indexes:
                    with engine.connect() as conn:
                        try:
                            conn.execute(sa_text("CREATE UNIQUE INDEX IF NOT EXISTS uq_property_material_name ON properties(material_id, property_name)"))
                            conn.commit()
                        except Exception:
                            pass
            
            if 'use_examples' in inspector.get_table_names():
                existing_indexes = [idx['name'] for idx in inspector.get_indexes('use_examples')]
                if 'uq_use_example_material_name' not in existing_indexes:
                    with engine.connect() as conn:
                        try:
                            conn.execute(sa_text("CREATE UNIQUE INDEX IF NOT EXISTS uq_use_example_material_name ON use_examples(material_id, example_name)"))
                            conn.commit()
                        except Exception:
                            pass
            
            if 'material_metadata' in inspector.get_table_names():
                existing_indexes = [idx['name'] for idx in inspector.get_indexes('material_metadata')]
                if 'uq_metadata_material_key' not in existing_indexes:
                    with engine.connect() as conn:
                        try:
                            conn.execute(sa_text("CREATE UNIQUE INDEX IF NOT EXISTS uq_metadata_material_key ON material_metadata(material_id, key)"))
                            conn.commit()
                        except Exception:
                            pass
        except Exception as e:
            # 一意制約の追加に失敗しても続行（アプリ側のロジックで二重ガード）
            print(f"一意制約の追加をスキップしました（既存テーブルの場合、SQLite制限により追加できない場合があります）: {e}")
        
        # materials テーブルのカラム確認
        if 'materials' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('materials')]
            
            # texture_image_pathカラムが存在しない場合は追加
            if 'texture_image_path' not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE materials ADD COLUMN texture_image_path VARCHAR(500)"))
                    conn.commit()
                print("✓ texture_image_pathカラムを追加しました")
            
            # texture_image_urlカラムが存在しない場合は追加
            if 'texture_image_url' not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE materials ADD COLUMN texture_image_url VARCHAR(1000)"))
                    conn.commit()
                print("✓ texture_image_urlカラムを追加しました")
        
        # images テーブルのカラム確認
        if 'images' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('images')]
            
            # urlカラムが存在しない場合は追加
            if 'url' not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE images ADD COLUMN url VARCHAR(1000)"))
                    conn.commit()
                print("✓ images.urlカラムを追加しました")
            
            # file_pathをnullableに変更（既存データは保持）
            # SQLiteではALTER COLUMNが直接できないため、新しいテーブルを作成して移行する必要がある
            # ただし、既存データに影響を与えないため、ここではカラム追加のみ行う
            # file_pathのnullable変更は、既存データが存在する場合は手動で行うか、移行スクリプトで対応
        
        # use_examples テーブルのカラム確認
        if 'use_examples' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('use_examples')]
            
            # image_urlカラムが存在しない場合は追加
            if 'image_url' not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE use_examples ADD COLUMN image_url VARCHAR(1000)"))
                    conn.commit()
                print("✓ use_examples.image_urlカラムを追加しました")
        
        # process_example_images テーブルのカラム確認
        if 'process_example_images' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('process_example_images')]
            
            # image_urlカラムが存在しない場合は追加
            if 'image_url' not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE process_example_images ADD COLUMN image_url VARCHAR(1000)"))
                    conn.commit()
                print("✓ process_example_images.image_urlカラムを追加しました")
            
            # image_pathをnullableに変更（既存データは保持）
            # SQLiteではALTER COLUMNが直接できないため、新しいテーブルを作成して移行する必要がある
            # ただし、既存データに影響を与えないため、ここではカラム追加のみ行う
        
        # material_submissions テーブルのカラム確認
        if 'material_submissions' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('material_submissions')]
            
            # approved_material_idカラムが存在しない場合は追加
            if 'approved_material_id' not in existing_columns:
                with engine.begin() as conn:
                    conn.execute(sa_text("ALTER TABLE material_submissions ADD COLUMN approved_material_id INTEGER"))
                    print("[DB MIGRATION] Added approved_material_id column to material_submissions")
        
    except Exception as e:
        # 既に存在するか、その他のエラー（無視して続行）
        print(f"スキーマ拡張チェック: {e}")


# Streamlit のインポートを安全に行う（スキーマドリフト検知のキャッシュ用）
try:
    import streamlit as st
except Exception:
    st = None


# スキーマドリフト検知（軽量、pg_catalog大量アクセスを避ける）
def check_schema_drift(engine) -> dict:
    """
    スキーマドリフトを軽量に検知（information_schema.columns を使用、pg_catalog大量アクセスを避ける）
    
    Args:
        engine: SQLAlchemy Engine
    
    Returns:
        dict: {
            "images_kind_exists": bool,
            "errors": list[str],
            "warnings": list[str]
        }
    """
    result = {
        "images_kind_exists": False,
        "errors": [],
        "warnings": []
    }
    
    try:
        # information_schema.columns を使用（pg_catalog より軽量）
        if DB_DIALECT == "postgresql":
            with engine.connect() as conn:
                # images.kind 列の存在確認（軽量クエリ）
                query = sa_text("""
                    SELECT COUNT(*) as count
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'images'
                      AND column_name = 'kind'
                """)
                row = conn.execute(query).fetchone()
                result["images_kind_exists"] = (row[0] > 0) if row else False
                
                if not result["images_kind_exists"]:
                    result["warnings"].append("images.kind column does not exist (migration required)")
                    print("[SCHEMA] missing column images.kind - run migration with MIGRATE_ON_START=1")
        elif DB_DIALECT == "sqlite":
            # SQLite の場合は PRAGMA table_info を使用
            with engine.connect() as conn:
                query = sa_text("PRAGMA table_info(images)")
                rows = conn.execute(query).fetchall()
                column_names = [row[1] for row in rows]  # row[1] が column name
                result["images_kind_exists"] = "kind" in column_names
                
                if not result["images_kind_exists"]:
                    result["warnings"].append("images.kind column does not exist (migration required)")
                    print("[SCHEMA] missing column images.kind - run migration with MIGRATE_ON_START=1")
    except Exception as e:
        result["errors"].append(f"Schema check failed: {e}")
        print(f"[SCHEMA] schema check error: {e}")
    
    return result


# スキーマドリフト検知結果をキャッシュ（Streamlit再実行時の重複チェックを避ける）
def _get_schema_drift_status_impl(_db_url: str) -> dict:
    """
    スキーマドリフト検知結果を取得（内部実装、utils.db に依存しない）
    
    Args:
        _db_url: データベースURL（キャッシュキー用、実際に使用する）
    
    Returns:
        dict: {
            "ok": bool,
            "images_kind_exists": bool,  # 後方互換のため残す
            "images_ok": bool,  # 必須列が全て存在するか
            "images_missing_columns": list[str],  # 欠けている列のリスト
            "errors": list[str],
            "warnings": list[str]
        }
    """
    try:
        # utils.db に依存せず、直接 create_engine を使用
        from sqlalchemy import create_engine
        import utils.settings as settings
        db_dialect = settings.get_db_dialect(_db_url)
        
        # db_url が空の場合はエラー
        if not _db_url or not _db_url.strip():
            return {
                "ok": False,
                "images_kind_exists": False,
                "images_ok": False,
                "images_missing_columns": [],
                "errors": ["Database URL is empty"],
                "warnings": []
            }
        
        # データベースダイアレクトを取得（settings を使用）
        db_dialect = settings.get_db_dialect(_db_url)
        
        # エンジンを作成（軽量、接続プールは最小限）
        if db_dialect == "postgresql":
            engine = create_engine(
                _db_url,
                pool_pre_ping=True,
                future=True,
                echo=False,  # スキーマチェック時はログを出さない
                pool_size=1,  # 最小限のプールサイズ
                max_overflow=0
            )
        elif db_dialect == "sqlite":
            engine = create_engine(
                _db_url,
                connect_args={"check_same_thread": False},
                echo=False
            )
        else:
            return {
                "ok": False,
                "images_kind_exists": False,
                "images_ok": False,
                "images_missing_columns": [],
                "errors": [f"Unsupported database dialect: {db_dialect}"],
                "warnings": []
            }
        
        # スキーマドリフト検知を実行
        result = check_schema_drift(engine)
        
        # エンジンを閉じる
        engine.dispose()
        
        # 成功時は ok=True を追加
        result["ok"] = True
        # images_ok と images_missing_columns が設定されていない場合は安全側に倒す
        if "images_ok" not in result:
            result["images_ok"] = False
        if "images_missing_columns" not in result:
            result["images_missing_columns"] = []
        return result
        
    except Exception as e:
        # 失敗時は安全側に倒す（images_kind_exists=False, images_ok=False）
        return {
            "ok": False,
            "images_kind_exists": False,
            "images_ok": False,
            "images_missing_columns": [],
            "errors": [f"Failed to check schema: {e}"],
            "warnings": []
        }


# Streamlit が利用可能な場合は cache_data(ttl=60) でキャッシュ
if st is not None:
    @st.cache_data(ttl=60)
    def get_schema_drift_status(_db_url: str) -> dict:
        """
        スキーマドリフト検知結果を取得（キャッシュ付き、60秒TTL）
        
        Args:
            _db_url: データベースURL（キャッシュキー用）
        
        Returns:
            dict: check_schema_drift() の結果
        """
        return _get_schema_drift_status_impl(_db_url)
else:
    # Streamlit が利用できない場合は通常の関数として動作
    _schema_drift_cache = None
    
    def get_schema_drift_status(_db_url: str = None) -> dict:
        global _schema_drift_cache
        if _schema_drift_cache is None:
            _schema_drift_cache = _get_schema_drift_status_impl(_db_url or "")
        return _schema_drift_cache


# データベースセッションの依存性注入用
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

