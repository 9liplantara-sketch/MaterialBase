"""
FastAPIメインアプリケーション
"""
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from pathlib import Path

from database import get_db, init_db, Material, Property, Image, Metadata
from models import (
    MaterialCreate, MaterialUpdate, Material as MaterialModel,
    PropertyCreate, Property, Image as ImageModel, Metadata as MetadataModel,
    MaterialCard
)
from card_generator import generate_material_card

app = FastAPI(title="マテリアルデータベース", version="1.0.0")

# 静的ファイルとテンプレートの設定
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="templates")

# アップロードディレクトリの作成
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# データベース初期化
init_db()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """ホームページ"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>マテリアルデータベース</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #333; }
            .nav { margin: 20px 0; }
            .nav a { margin-right: 20px; text-decoration: none; color: #0066cc; }
            .nav a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>マテリアルデータベース</h1>
            <div class="nav">
                <a href="/materials">材料一覧</a>
                <a href="/materials/create">材料登録</a>
                <a href="/api/docs">API ドキュメント</a>
            </div>
            <p>素材カード形式でマテリアル情報を管理するシステムです。</p>
        </div>
    </body>
    </html>
    """


@app.get("/api/materials", response_model=List[MaterialModel])
async def get_materials(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """材料一覧取得"""
    query = db.query(Material)
    
    if category:
        query = query.filter(Material.category == category)
    
    if search:
        query = query.filter(Material.name.contains(search))
    
    materials = query.offset(skip).limit(limit).all()
    return materials


@app.get("/api/materials/{material_id}", response_model=MaterialModel)
async def get_material(material_id: int, db: Session = Depends(get_db)):
    """材料詳細取得"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@app.post("/api/materials", response_model=MaterialModel)
async def create_material(material: MaterialCreate, db: Session = Depends(get_db)):
    """材料作成"""
    db_material = Material(
        name=material.name,
        category=material.category,
        description=material.description
    )
    db.add(db_material)
    db.flush()
    
    # 物性データの追加
    for prop in material.properties:
        db_property = Property(
            material_id=db_material.id,
            property_name=prop.property_name,
            value=prop.value,
            unit=prop.unit,
            measurement_condition=prop.measurement_condition
        )
        db.add(db_property)
    
    # メタデータの追加
    for meta in material.metadata:
        db_metadata = Metadata(
            material_id=db_material.id,
            key=meta.key,
            value=meta.value
        )
        db.add(db_metadata)
    
    db.commit()
    db.refresh(db_material)
    return db_material


@app.put("/api/materials/{material_id}", response_model=MaterialModel)
async def update_material(
    material_id: int,
    material_update: MaterialUpdate,
    db: Session = Depends(get_db)
):
    """材料更新"""
    db_material = db.query(Material).filter(Material.id == material_id).first()
    if not db_material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    update_data = material_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_material, field, value)
    
    db.commit()
    db.refresh(db_material)
    return db_material


@app.delete("/api/materials/{material_id}")
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    """材料削除"""
    db_material = db.query(Material).filter(Material.id == material_id).first()
    if not db_material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    db.delete(db_material)
    db.commit()
    return {"message": "Material deleted successfully"}


@app.post("/api/materials/{material_id}/images", response_model=ImageModel)
async def upload_image(
    material_id: int,
    file: UploadFile = File(...),
    image_type: Optional[str] = None,
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """画像アップロード"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # ファイル保存
    file_extension = Path(file.filename).suffix
    file_name = f"{material_id}_{file.filename}"
    file_path = UPLOAD_DIR / file_name
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # データベースに記録（相対パスを保存）
    db_image = Image(
        material_id=material_id,
        file_path=file_name,  # 相対パスのみ保存
        image_type=image_type,
        description=description
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    return db_image


@app.get("/api/materials/{material_id}/card")
async def get_material_card(material_id: int, db: Session = Depends(get_db)):
    """素材カード生成（HTML形式）"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # 主要画像を取得
    primary_image = None
    if material.images:
        primary_image = material.images[0]
    
    card_data = MaterialCard(
        material=material,
        primary_image=primary_image
    )
    
    card_html = generate_material_card(card_data)
    return HTMLResponse(content=card_html)


@app.get("/api/materials/{material_id}/card/pdf")
async def get_material_card_pdf(material_id: int, db: Session = Depends(get_db)):
    """素材カード生成（PDF形式）"""
    # TODO: PDF生成機能の実装
    raise HTTPException(status_code=501, detail="PDF generation not implemented yet")


@app.get("/materials", response_class=HTMLResponse)
async def materials_list_page():
    """材料一覧ページ"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>材料一覧 - マテリアルデータベース</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .material-card { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            .material-card h3 { margin-top: 0; }
            .nav { margin: 20px 0; }
            .nav a { margin-right: 20px; text-decoration: none; color: #0066cc; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>材料一覧</h1>
            <div class="nav">
                <a href="/">ホーム</a>
                <a href="/materials/create">材料登録</a>
            </div>
            <div id="materials-list"></div>
        </div>
        <script>
            fetch('/api/materials')
                .then(response => response.json())
                .then(data => {
                    const list = document.getElementById('materials-list');
                    data.forEach(material => {
                        const card = document.createElement('div');
                        card.className = 'material-card';
                        card.innerHTML = `
                            <h3><a href="/materials/${material.id}">${material.name}</a></h3>
                            <p><strong>カテゴリ:</strong> ${material.category || '未設定'}</p>
                            <p>${material.description || ''}</p>
                            <a href="/materials/${material.id}/card">素材カードを見る</a>
                        `;
                        list.appendChild(card);
                    });
                });
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

