"""
素材カード生成モジュール - マテリアル感のあるリッチなデザイン版
"""
from schemas import MaterialCard
import qrcode
from io import BytesIO
import base64
import os
from pathlib import Path
from typing import Optional

try:
    from utils.image_display import get_material_image_src
except ImportError:
    # フォールバック: 関数が存在しない場合
    def get_material_image_src(material, kind, project_root=None):
        return None, {}


def get_image_path(filename):
    """画像パスを取得"""
    possible_paths = [
        Path("static/images") / filename,
        Path("写真") / filename,
        Path(filename)
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path)
    return None


def get_base64_image(image_path):
    """画像をBase64エンコード"""
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        except Exception:
            return None
    return None


def generate_material_card(card_data: MaterialCard) -> str:
    """素材カードのHTMLを生成（マテリアル感のあるリッチなデザイン）"""
    payload = card_data.payload
    material_id = payload.id
    material_name = payload.name_official or payload.name
    material_category = payload.category_main or payload.category
    material_description = payload.description
    properties = payload.properties
    primary_image_path = payload.primary_image_path
    primary_image_type = payload.primary_image_type
    primary_image_description = payload.primary_image_description
    
    # QRコード生成
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Material ID: {material_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # QRコードをBase64エンコード
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
    
    # 背景画像の読み込み（サブ.webpをテクスチャとして使用）
    sub_bg_path = get_image_path("サブ.webp")
    sub_bg_base64 = get_base64_image(sub_bg_path) if sub_bg_path else None
    texture_bg = f'url("data:image/webp;base64,{sub_bg_base64}")' if sub_bg_base64 else 'none'
    
    # 画像パスの処理（参照URL方式に統一）
    # Materialオブジェクトを取得（payloadから構築、または直接受け取る）
    # 注意: payloadはPydanticモデルなので、Materialオブジェクトに変換する必要がある
    # ここでは、payloadの情報からMaterialオブジェクトを模擬的に作成
    class MaterialProxy:
        """Materialオブジェクトのプロキシ（payloadから情報を取得）"""
        def __init__(self, payload):
            self.id = payload.id
            self.name_official = getattr(payload, 'name_official', None) or getattr(payload, 'name', None)
            self.name = getattr(payload, 'name', None)
            self.texture_image_url = getattr(payload, 'texture_image_url', None)
            self.texture_image_path = getattr(payload, 'texture_image_path', None) or primary_image_path
            # use_examplesはpayloadに含まれていない可能性があるので、空リストを返す
            self.use_examples = []
    
    # Materialオブジェクトを取得（実際のMaterialオブジェクトが渡されている場合はそれを使用）
    material_obj = getattr(card_data, 'material_obj', None)
    if material_obj is None:
        # payloadからMaterialProxyを作成（フォールバック）
        # 注意: material_objがNoneの場合は、DBから引き直すか例外をdebugに出す
        import warnings
        warnings.warn(f"card_generator: material_obj is None for material_id={payload.id}, using MaterialProxy")
        material_obj = MaterialProxy(payload)
    
    # get_material_image_ref()を使用して画像srcを取得（primary/space/product）
    from utils.image_display import get_material_image_ref, to_data_url
    
    # primary画像
    primary_src, primary_debug = get_material_image_ref(material_obj, "primary", project_root=Path.cwd())
    primary_url = ""
    if primary_src is None:
        primary_url = ""
    elif isinstance(primary_src, str):
        primary_url = primary_src
    elif isinstance(primary_src, Path):
        data_url = to_data_url(primary_src)
        primary_url = data_url or ""
    
    # space画像
    space_src, space_debug = get_material_image_ref(material_obj, "space", project_root=Path.cwd())
    space_url = ""
    if space_src is None:
        space_url = ""
    elif isinstance(space_src, str):
        space_url = space_src
    elif isinstance(space_src, Path):
        data_url = to_data_url(space_src)
        space_url = data_url or ""
    
    # product画像
    product_src, product_debug = get_material_image_ref(material_obj, "product", project_root=Path.cwd())
    product_url = ""
    if product_src is None:
        product_url = ""
    elif isinstance(product_src, str):
        product_url = product_src
    elif isinstance(product_src, Path):
        data_url = to_data_url(product_src)
        product_url = data_url or ""
    
    # 後方互換性のため、primary_urlをimage_urlとしても使用
    image_url = primary_url
    
    # 主要物性データの取得
    main_properties = properties[:8] if properties else []
    
    # カテゴリに応じたカラー
    category_colors = {
        "金属": "#FF6B6B",
        "プラスチック": "#4ECDC4",
        "セラミック": "#95E1D3",
        "複合材料": "#F38181",
        "その他": "#667eea"
    }
    primary_color = category_colors.get(material_category, "#667eea")
    secondary_color = "#764ba2"
    
    # f-string内でバックスラッシュを使うための変数
    translate_y_up = "translateY(-2px)"
    translate_y_zero = "translateY(0)"
    box_shadow_hover = "0 15px 40px rgba(102, 126, 234, 0.4)"
    box_shadow_normal = "0 10px 30px rgba(102, 126, 234, 0.3)"
    display_none = "none"
    display_block = "block"
    
    # 画像のonerror属性用のJavaScriptコード
    if image_url:
        img_onerror = f'this.style.display="{display_none}"; this.nextElementSibling.style.display="{display_block}";'
    else:
        img_onerror = ""
    
    # space/product画像用のonerror属性（f-string内でバックスラッシュを使わないように変数に格納）
    img_onerror_hide = "this.style.display='none';"
    img_onerror_show = "this.nextElementSibling.style.display='block';"
    img_onerror_combined = img_onerror_hide + " " + img_onerror_show
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>素材カード - {material_name}</title>
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
                background: {texture_bg};
                background-size: 300%;
                background-position: center;
                background-attachment: fixed;
                min-height: 100vh;
                position: relative;
            }}
            body::before {{
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 50%, rgba(240, 147, 251, 0.1) 100%);
                z-index: 0;
                pointer-events: none;
            }}
            .card-container {{
                max-width: 900px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.98);
                backdrop-filter: blur(20px);
                border-radius: 25px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3),
                            inset 0 1px 0 rgba(255, 255, 255, 0.9);
                padding: 0;
                overflow: hidden;
                position: relative;
                z-index: 1;
                border: 1px solid rgba(255, 255, 255, 0.8);
            }}
            .card-container::after {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: {texture_bg};
                background-size: 200%;
                opacity: 0.03;
                pointer-events: none;
                mix-blend-mode: multiply;
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
            .use-examples-section {{
                grid-column: 1 / -1;
                margin-top: 20px;
                padding-top: 30px;
                border-top: 2px solid #e8e8e8;
            }}
            .use-examples-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin-top: 20px;
            }}
            .use-example-item {{
                text-align: center;
            }}
            .use-example-item h4 {{
                color: {primary_color};
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 15px;
            }}
            .use-example-image {{
                max-width: 100%;
                max-height: 250px;
                border-radius: 12px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
                object-fit: cover;
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
                <h1 class="material-name">{material_name}</h1>
                {f'<span class="category-badge">{material_category}</span>' if material_category else ''}
            </div>
            
            <div class="card-body">
                <div class="image-section">
                    {f'<img src="{image_url}" alt="{material_name}" class="material-image" onerror="{img_onerror}">' if image_url else ''}
                    {'<div class="no-image" style="display:none;">📷 画像なし</div>' if image_url else '<div class="no-image">📷 画像なし</div>'}
                </div>
                
                <div class="properties-section">
                    <h3>📊 主要物性</h3>
                    {''.join([f'''
                    <div class="property-item">
                        <span class="property-name">{prop.property_name if hasattr(prop, 'property_name') else '不明'}</span>
                        <span class="property-value">{prop.value if hasattr(prop, 'value') and prop.value is not None else 'N/A'} {prop.unit if hasattr(prop, 'unit') and prop.unit else ''}</span>
                    </div>
                    ''' for prop in main_properties]) if main_properties else '<p style="color: #999; text-align: center; padding: 20px;">物性データが登録されていません</p>'}
                </div>
            </div>
            
            {(f'''
            <div class="use-examples-section">
                <h3 style="color: {primary_color}; font-size: 24px; font-weight: 700; margin-bottom: 20px; border-bottom: 3px solid {primary_color}; padding-bottom: 15px;">📸 使用例</h3>
                <div class="use-examples-grid">
                    <div class="use-example-item">
                        <h4>空間用途</h4>
                        {f'<img src="{space_url}" alt="空間用途" class="use-example-image" onerror="{img_onerror_combined}">' if space_url else ''}
                        {'<div class="no-image" style="display:none; padding: 80px 20px; border-radius: 12px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #999; text-align: center; font-size: 14px; border: 2px dashed #ddd;">📷 画像なし</div>' if space_url else '<div class="no-image" style="display:block; padding: 80px 20px; border-radius: 12px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #999; text-align: center; font-size: 14px; border: 2px dashed #ddd;">📷 画像なし</div>'}
                    </div>
                    <div class="use-example-item">
                        <h4>製品用途</h4>
                        {f'<img src="{product_url}" alt="製品用途" class="use-example-image" onerror="{img_onerror_combined}">' if product_url else ''}
                        {'<div class="no-image" style="display:none; padding: 80px 20px; border-radius: 12px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #999; text-align: center; font-size: 14px; border: 2px dashed #ddd;">📷 画像なし</div>' if product_url else '<div class="no-image" style="display:block; padding: 80px 20px; border-radius: 12px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #999; text-align: center; font-size: 14px; border: 2px dashed #ddd;">📷 画像なし</div>'}
                    </div>
                </div>
            </div>
            ''' if (space_url or product_url) else '')}
            
            {f'''
            <div class="description-section">
                <h3>📝 説明</h3>
                <p>{material_description or '説明が登録されていません'}</p>
            </div>
            ''' if material_description else ''}
            
            <div class="card-footer">
                <div class="metadata">
                    <p><span class="material-id">ID: {material_id}</span></p>
                    <p class="date-info">登録日: N/A</p>
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
                box-shadow: {box_shadow_normal};
                transition: all 0.3s ease;
            " onmouseover="this.style.transform='{translate_y_up}'; this.style.boxShadow='{box_shadow_hover}';" 
               onmouseout="this.style.transform='{translate_y_zero}'; this.style.boxShadow='{box_shadow_normal}';">
                🖨️ 印刷
            </button>
        </div>
    </body>
    </html>
    """
    
    return html
