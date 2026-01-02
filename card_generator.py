"""
素材カード生成モジュール - リッチなデザイン版
"""
from models import MaterialCard
import qrcode
from io import BytesIO
import base64


def generate_material_card(card_data: MaterialCard) -> str:
    """素材カードのHTMLを生成（リッチなデザイン）"""
    material = card_data.material
    primary_image = card_data.primary_image
    
    # QRコード生成
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Material ID: {material.id}")
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
    main_properties = material.properties[:8] if material.properties else []
    
    # カテゴリに応じたカラー
    category_colors = {
        "金属": "#FF6B6B",
        "プラスチック": "#4ECDC4",
        "セラミック": "#95E1D3",
        "複合材料": "#F38181",
        "その他": "#667eea"
    }
    primary_color = category_colors.get(material.category, "#667eea")
    secondary_color = "#764ba2"
    
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
                    margin: 15mm;
                }}
                body {{
                    background: white;
                }}
            }}
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Yu Gothic', '游ゴシック', 'Hiragino Sans', 'Meiryo', 'Helvetica Neue', Arial, sans-serif;
                margin: 0;
                padding: 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
                min-height: 100vh;
            }}
            .card-container {{
                max-width: 900px;
                margin: 0 auto;
                background: white;
                border-radius: 25px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                padding: 0;
                overflow: hidden;
                position: relative;
            }}
            .card-header {{
                background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%);
                color: white;
                padding: 40px;
                position: relative;
                overflow: hidden;
            }}
            .card-header::before {{
                content: '';
                position: absolute;
                top: -50%;
                right: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                animation: pulse 3s ease-in-out infinite;
            }}
            @keyframes pulse {{
                0%, 100% {{ opacity: 0.3; }}
                50% {{ opacity: 0.6; }}
            }}
            .material-name {{
                font-size: 42px;
                font-weight: 900;
                margin: 0 0 15px 0;
                text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
                position: relative;
                z-index: 1;
            }}
            .category-badge {{
                display: inline-block;
                background: rgba(255, 255, 255, 0.25);
                backdrop-filter: blur(10px);
                color: white;
                padding: 10px 25px;
                border-radius: 30px;
                font-size: 14px;
                font-weight: 600;
                margin-top: 10px;
                border: 2px solid rgba(255, 255, 255, 0.3);
                position: relative;
                z-index: 1;
            }}
            .card-body {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 40px;
                padding: 40px;
                background: white;
            }}
            .image-section {{
                text-align: center;
                position: relative;
            }}
            .material-image {{
                max-width: 100%;
                max-height: 350px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
                object-fit: cover;
            }}
            .no-image {{
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                padding: 120px 20px;
                border-radius: 15px;
                color: #999;
                text-align: center;
                font-size: 16px;
                border: 2px dashed #ddd;
            }}
            .properties-section {{
                background: linear-gradient(135deg, #f8f9ff 0%, #ffffff 100%);
                padding: 30px;
                border-radius: 20px;
                border: 2px solid #f0f0f0;
            }}
            .properties-section h3 {{
                margin-top: 0;
                color: {primary_color};
                font-size: 24px;
                font-weight: 700;
                border-bottom: 3px solid {primary_color};
                padding-bottom: 15px;
                margin-bottom: 20px;
            }}
            .property-item {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px 0;
                border-bottom: 1px solid #e8e8e8;
                transition: all 0.3s ease;
            }}
            .property-item:last-child {{
                border-bottom: none;
            }}
            .property-item:hover {{
                background: rgba(102, 126, 234, 0.05);
                padding-left: 10px;
                border-radius: 8px;
            }}
            .property-name {{
                font-weight: 600;
                color: #333;
                font-size: 15px;
            }}
            .property-value {{
                color: {primary_color};
                font-weight: 700;
                font-size: 16px;
            }}
            .description-section {{
                margin: 0 40px 30px 40px;
                padding: 30px;
                background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);
                border-radius: 20px;
                border-left: 5px solid {primary_color};
            }}
            .description-section h3 {{
                margin-top: 0;
                color: {primary_color};
                font-size: 22px;
                font-weight: 700;
                margin-bottom: 15px;
            }}
            .description-section p {{
                color: #555;
                line-height: 1.8;
                font-size: 15px;
            }}
            .card-footer {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 30px 40px;
                background: #f8f9fa;
                border-top: 2px solid #e8e8e8;
            }}
            .qr-code {{
                text-align: center;
                background: white;
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            }}
            .qr-code img {{
                width: 120px;
                height: 120px;
            }}
            .qr-code p {{
                font-size: 11px;
                color: #999;
                margin-top: 8px;
            }}
            .metadata {{
                font-size: 13px;
                color: #666;
            }}
            .metadata p {{
                margin: 5px 0;
            }}
            .material-id {{
                display: inline-block;
                background: {primary_color};
                color: white;
                padding: 8px 15px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 14px;
            }}
            .date-info {{
                color: #999;
                font-size: 13px;
            }}
            .decorative-element {{
                position: absolute;
                width: 200px;
                height: 200px;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                border-radius: 50%;
                top: -100px;
                right: -100px;
            }}
            @media (max-width: 768px) {{
                .card-body {{
                    grid-template-columns: 1fr;
                    gap: 30px;
                }}
                .material-name {{
                    font-size: 32px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="card-container">
            <div class="card-header">
                <div class="decorative-element"></div>
                <h1 class="material-name">{material.name}</h1>
                {f'<span class="category-badge">{material.category}</span>' if material.category else ''}
            </div>
            
            <div class="card-body">
                <div class="image-section">
                    {f'<img src="{image_url}" alt="{material.name}" class="material-image" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';">' if primary_image else ''}
                    {f'<div class="no-image" style="display:none;">📷 画像なし</div>' if primary_image else '<div class="no-image">📷 画像なし</div>'}
                </div>
                
                <div class="properties-section">
                    <h3>📊 主要物性</h3>
                    {''.join([f'''
                    <div class="property-item">
                        <span class="property-name">{prop.property_name}</span>
                        <span class="property-value">{prop.value if prop.value is not None else 'N/A'} {prop.unit or ''}</span>
                    </div>
                    ''' for prop in main_properties]) if main_properties else '<p style="color: #999; text-align: center; padding: 20px;">物性データが登録されていません</p>'}
                </div>
            </div>
            
            {f'''
            <div class="description-section">
                <h3>📝 説明</h3>
                <p>{material.description or '説明が登録されていません'}</p>
            </div>
            ''' if material.description else ''}
            
            <div class="card-footer">
                <div class="metadata">
                    <p><span class="material-id">ID: {material.id}</span></p>
                    <p class="date-info">登録日: {material.created_at.strftime('%Y年%m月%d日') if material.created_at else 'N/A'}</p>
                    {f'<p class="date-info">更新日: {material.updated_at.strftime("%Y年%m月%d日") if material.updated_at else "N/A"}</p>' if material.updated_at else ''}
                </div>
                <div class="qr-code">
                    <img src="data:image/png;base64,{qr_base64}" alt="QR Code">
                    <p>詳細情報</p>
                </div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <button onclick="window.print()" style="
                padding: 15px 40px;
                font-size: 16px;
                font-weight: 600;
                background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%);
                color: white;
                border: none;
                border-radius: 30px;
                cursor: pointer;
                box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
                transition: all 0.3s ease;
            " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 15px 40px rgba(102, 126, 234, 0.4)';" 
               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 10px 30px rgba(102, 126, 234, 0.3)';">
                🖨️ 印刷
            </button>
        </div>
    </body>
    </html>
    """
    
    return html
