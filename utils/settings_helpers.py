"""
utils.settings の安全な呼び出しヘルパー
get_flag が無い場合に備えた二重化（最後の保険）
"""
import os


def safe_get_flag(settings_module, key: str, default: bool = False) -> bool:
    """
    settings.get_flag を安全に呼び出す（get_flag が無い場合のフォールバック付き）
    
    Args:
        settings_module: utils.settings モジュール（または None）
        key: フラグキー
        default: デフォルト値
    
    Returns:
        フラグ値（bool）
    """
    # settings モジュールから get_flag を取得
    flag_fn = None
    if settings_module is not None:
        flag_fn = getattr(settings_module, "get_flag", None)
        if not callable(flag_fn):
            flag_fn = None
    
    # get_flag が使える場合はそれを使う
    if flag_fn is not None:
        try:
            return flag_fn(key, default)
        except Exception:
            pass  # 失敗した場合はフォールバックへ
    
    # フォールバック: os.getenv のみで判定
    value = os.getenv(key)
    if value is not None:
        value_str = str(value).lower().strip()
        if value_str in ("1", "true", "yes", "y", "on"):
            return True
        elif value_str in ("0", "false", "no", "n", "off", ""):
            return False
    
    return default
