"""
素材カード生成モジュール
"""
from models import MaterialCard
import qrcode
from io import BytesIO
import base64


def generate_material_card(card_data: MaterialCard) -> str:
    """素材カードのHTMLを生成"""
    material = card_data.material
    primary_image = card_data.primary_image
    
    # QRコード生成
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"/materials/{material.id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # QRコードをBase64エンコード
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
    
    # 画像パスの処理
    image_url = ""
    if primary_image:
        # ファイルパスから相対パスを生成
        file_name = primary_image.file_path.split('/')[-1] if '/' in primary_image.file_path else primary_image.file_path.split('\\')[-1]
        image_url = f"/uploads/{file_name}"
    
    # 主要物性データの取得
    main_properties = material.properties[:5] if material.properties else []
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>素材カード - {material.name}</title>
        <style>
            @media print {{
                @page {{
                    size: A4;
                    margin: 20mm;
                }}
            }}
            body {{
                font-family: 'Yu Gothic', '游ゴシック', 'Hiragino Sans', 'Meiryo', sans-serif;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }}
            .card-container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                padding: 30px;
            }}
            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 30px;
                border-bottom: 3px solid #0066cc;
                padding-bottom: 20px;
            }}
            .material-name {{
                font-size: 32px;
                font-weight: bold;
                color: #333;
                margin: 0;
            }}
            .category-badge {{
                display: inline-block;
                background: #0066cc;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                margin-top: 10px;
            }}
            .card-body {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin-bottom: 30px;
            }}
            .image-section {{
                text-align: center;
            }}
            .material-image {{
                max-width: 100%;
                max-height: 300px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .properties-section {{
                background: #f9f9f9;
                padding: 20px;
                border-radius: 8px;
            }}
            .properties-section h3 {{
                margin-top: 0;
                color: #0066cc;
                border-bottom: 2px solid #0066cc;
                padding-bottom: 10px;
            }}
            .property-item {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
            }}
            .property-item:last-child {{
                border-bottom: none;
            }}
            .property-name {{
                font-weight: bold;
                color: #555;
            }}
            .property-value {{
                color: #333;
            }}
            .description-section {{
                margin-bottom: 30px;
                padding: 20px;
                background: #f9f9f9;
                border-radius: 8px;
            }}
            .description-section h3 {{
                margin-top: 0;
                color: #0066cc;
            }}
            .card-footer {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-top: 20px;
                border-top: 2px solid #e0e0e0;
            }}
            .qr-code {{
                text-align: center;
            }}
            .qr-code img {{
                width: 100px;
                height: 100px;
            }}
            .metadata {{
                font-size: 12px;
                color: #666;
            }}
            .no-image {{
                background: #e0e0e0;
                padding: 100px 20px;
                border-radius: 8px;
                color: #999;
                text-align: center;
            }}
            @media print {{
                body {{
                    background: white;
                }}
                .card-container {{
                    box-shadow: none;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="card-container">
            <div class="card-header">
                <div>
                    <h1 class="material-name">{material.name}</h1>
                    {f'<span class="category-badge">{material.category}</span>' if material.category else ''}
                </div>
            </div>
            
            <div class="card-body">
                <div class="image-section">
                    {f'<img src="{image_url}" alt="{material.name}" class="material-image" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';">' if primary_image else ''}
                    {f'<div class="no-image" style="display:none;">画像なし</div>' if primary_image else '<div class="no-image">画像なし</div>'}
                </div>
                
                <div class="properties-section">
                    <h3>主要物性</h3>
                    {''.join([f'''
                    <div class="property-item">
                        <span class="property-name">{prop.property_name}</span>
                        <span class="property-value">{prop.value if prop.value is not None else 'N/A'} {prop.unit or ''}</span>
                    </div>
                    ''' for prop in main_properties]) if main_properties else '<p>物性データが登録されていません</p>'}
                </div>
            </div>
            
            {f'''
            <div class="description-section">
                <h3>説明</h3>
                <p>{material.description or '説明が登録されていません'}</p>
            </div>
            ''' if material.description else ''}
            
            <div class="card-footer">
                <div class="metadata">
                    <p>材料ID: {material.id}</p>
                    <p>登録日: {material.created_at.strftime('%Y年%m月%d日') if material.created_at else 'N/A'}</p>
                </div>
                <div class="qr-code">
                    <img src="data:image/png;base64,{qr_base64}" alt="QR Code">
                    <p style="font-size: 10px; margin-top: 5px;">詳細情報</p>
                </div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 20px;">
            <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; background: #0066cc; color: white; border: none; border-radius: 5px; cursor: pointer;">
                印刷
            </button>
            <a href="/materials/{material.id}" style="margin-left: 10px; padding: 10px 20px; font-size: 16px; background: #666; color: white; text-decoration: none; border-radius: 5px; display: inline-block;">
                詳細ページへ
            </a>
        </div>
    </body>
    </html>
    """
    
    return html

