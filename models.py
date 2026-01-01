"""
Pydanticモデル（APIリクエスト/レスポンス用）
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PropertyBase(BaseModel):
    property_name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    measurement_condition: Optional[str] = None


class PropertyCreate(PropertyBase):
    pass


class Property(PropertyBase):
    id: int
    material_id: int

    class Config:
        from_attributes = True


class ImageBase(BaseModel):
    file_path: str
    image_type: Optional[str] = None
    description: Optional[str] = None


class ImageCreate(ImageBase):
    pass


class Image(ImageBase):
    id: int
    material_id: int

    class Config:
        from_attributes = True


class MetadataBase(BaseModel):
    key: str
    value: str


class MetadataCreate(MetadataBase):
    pass


class Metadata(MetadataBase):
    id: int
    material_id: int

    class Config:
        from_attributes = True


class MaterialBase(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None


class MaterialCreate(MaterialBase):
    properties: Optional[List[PropertyCreate]] = []
    metadata: Optional[List[MetadataCreate]] = []


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class Material(MaterialBase):
    id: int
    created_at: datetime
    updated_at: datetime
    properties: List[Property] = []
    images: List[Image] = []
    metadata: List[Metadata] = []

    class Config:
        from_attributes = True


class MaterialCard(BaseModel):
    """素材カード用のデータモデル"""
    material: Material
    primary_image: Optional[Image] = None

