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
        with session_scope() as s:
            from sqlalchemy import text

            try:
                # 1) DB接続先の雰囲気（database名とかは方言あるので最低限）
                s.execute(text("select 1")).all()

                # 2) submissions件数
                cnt = s.execute(text(f"select count(*) from material_submissions")).scalar()
                # 3) 直近のID確認
                rows = s.execute(text(f"select id, status from material_submissions order by id desc limit 5")).all()

                return {
                    "ok": False,
                    "error": f"DEBUG: submission_id={submission_id} submissions_count={cnt} recent={rows}",
                    "traceback": ""
                }
            except Exception as e:
                import traceback
                return {"ok": False, "error": f"DEBUG SQL failed: {e}", "traceback": traceback.format_exc()}
            sub = s.query(MaterialSubmission).filter(MaterialSubmission.id == submission_id).first()
            if not sub:
                return {"ok": False, "error": f"submission {submission_id} not found", "traceback": ""}

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
            _tx2_upsert_images(material_id, uploaded_images, payload, submission_id=submission_id)
            image_warning = None
        except Exception:
            image_warning = "images upsert failed (ignored)"

        # 4) TxSub: submissions を approved に（必須）
        _txsub_mark_submission_approved(submission_id, material_id, editor_note=editor_note_str)

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
