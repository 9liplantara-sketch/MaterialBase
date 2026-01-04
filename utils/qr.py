"""
QRコード生成ユーティリティ（Streamlit対応版）
"""
import qrcode
from io import BytesIO
from PIL import Image as PILImage
from typing import Optional


def generate_qr_png_bytes(data: str, box_size: int = 10, border: int = 5) -> Optional[bytes]:
    """
    QRコードをPNG形式のbytesとして生成（Streamlit対応）
    
    Args:
        data: QRコードにエンコードするデータ
        box_size: QRコードのボックスサイズ
        border: ボーダーサイズ
    
    Returns:
        PNG形式のbytes、生成失敗時はNone
    """
    try:
        qr = qrcode.QRCode(version=1, box_size=box_size, border=border)
        qr.add_data(data)
        qr.make(fit=True)
        
        # QRコード画像を生成
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # PIL Imageオブジェクトを取得（wrapperの場合は変換）
        if hasattr(qr_img, 'get_image'):
            # qrcodeのPIL wrapperの場合
            pil_img = qr_img.get_image()
        elif isinstance(qr_img, PILImage.Image):
            # 既にPIL Imageの場合
            pil_img = qr_img
        else:
            # その他の場合は変換を試みる
            pil_img = PILImage.fromarray(qr_img) if hasattr(qr_img, '__array__') else qr_img
        
        # RGBモードに変換（確実に表示できるように）
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        
        # PNG形式でBytesIOに保存
        buffer = BytesIO()
        pil_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
    except Exception as e:
        print(f"QRコード生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_qr_pil_image(data: str, box_size: int = 10, border: int = 5) -> Optional[PILImage.Image]:
    """
    QRコードをPIL Imageオブジェクトとして生成
    
    Args:
        data: QRコードにエンコードするデータ
        box_size: QRコードのボックスサイズ
        border: ボーダーサイズ
    
    Returns:
        PIL Imageオブジェクト（RGBモード）、生成失敗時はNone
    """
    try:
        qr = qrcode.QRCode(version=1, box_size=box_size, border=border)
        qr.add_data(data)
        qr.make(fit=True)
        
        # QRコード画像を生成
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # PIL Imageオブジェクトを取得
        if hasattr(qr_img, 'get_image'):
            pil_img = qr_img.get_image()
        elif isinstance(qr_img, PILImage.Image):
            pil_img = qr_img
        else:
            pil_img = PILImage.fromarray(qr_img) if hasattr(qr_img, '__array__') else qr_img
        
        # RGBモードに変換
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        
        return pil_img
    except Exception as e:
        print(f"QRコード生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return None

