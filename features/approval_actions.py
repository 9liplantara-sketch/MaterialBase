"""
承認アクション関連の関数（UI非依存）
"""
APPROVAL_ACTIONS_VERSION = "v2026-01-23-01"


def approve_submission(submission_id: int, editor_note=None, update_existing: bool = True, db=None, **kwargs):
    """投稿を承認してmaterialsテーブルに反映（Tx分離版）"""
    import traceback
    try:
        from utils.db import session_scope
        from database import MaterialSubmission
        from core.approval_impl import (
            _tx1_upsert_material_core,
            _tx2_upsert_images,
            _txsub_mark_submission_approved,
        )

        editor_note_str = editor_note if (editor_note is not None) else ""

        # 1) submission を読む
        from utils.db import normalize_submission_key
        
        with session_scope() as s:
            kind, normalized_key = normalize_submission_key(submission_id)
            if kind is None or normalized_key is None:
                return {"ok": False, "error": f"submission {submission_id} not found", "traceback": ""}
            
            if kind == "id":
                sub = s.query(MaterialSubmission).filter(MaterialSubmission.id == normalized_key).first()
            elif kind == "uuid":
                sub = s.query(MaterialSubmission).filter(MaterialSubmission.uuid == normalized_key).first()
            else:
                sub = None
            
            if not sub:
                return {"ok": False, "error": f"submission {submission_id} not found", "traceback": ""}
            
            # 後続処理で id が必要な場合に備えて、sub.id を取得
            submission_id_for_tx = sub.id

            # payload_json は既に dict の想定。str の場合だけフォールバックで json.loads
            payload = sub.payload_json
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)

        # 2) Tx1: materials upsert（必須）
        material_id, action = _tx1_upsert_material_core(sub, payload, update_existing=update_existing)

        # 3) Tx2: images upsert（失敗しても続行）
        try:
            uploaded_images = []
            _tx2_upsert_images(material_id, uploaded_images, payload, submission_id=submission_id_for_tx)
            image_warning = None
        except Exception:
            image_warning = "images upsert failed (ignored)"

        # 4) TxSub: submissions を approved に（必須）
        _txsub_mark_submission_approved(submission_id_for_tx, material_id, editor_note=editor_note_str)

        out = {"ok": True, "material_id": material_id, "action": action}
        if image_warning:
            out["image_warning"] = image_warning
        return out

    except Exception as e:
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}


def reject_submission(submission_id: int, reject_reason = None, db=None, **kwargs):
    """投稿を却下"""
    if reject_reason is None and "reason" in kwargs:
        reject_reason = kwargs.get("reason")
    pass
    return {"ok": False, "error": "unhandled path", "traceback": ""}


def reopen_submission(submission_id: int, db=None, **kwargs):
    """却下済みsubmissionを再審査（pendingに戻す）"""
    pass
    return {"ok": False, "error": "unhandled path", "traceback": ""}


def calculate_submission_diff(existing_material, payload: dict, **kwargs) -> dict:
    """既存材料とsubmission payloadの差分を計算（暫定）"""
    return {}
