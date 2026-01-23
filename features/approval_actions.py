"""
承認アクション関連の関数（UI非依存）
"""
APPROVAL_ACTIONS_VERSION = "v2026-01-23-01"


def approve_submission(submission_id: int, editor_note = None, update_existing: bool = True, db=None, **kwargs):
    """投稿を承認してmaterialsテーブルに反映"""
    pass


def reject_submission(submission_id: int, reject_reason = None, db=None, **kwargs):
    """投稿を却下"""
    if reject_reason is None and "reason" in kwargs:
        reject_reason = kwargs.get("reason")
    pass


def reopen_submission(submission_id: int, db=None, **kwargs):
    """却下済みsubmissionを再審査（pendingに戻す）"""
    pass


def calculate_submission_diff(existing_material, payload: dict, **kwargs) -> dict:
    """既存材料とsubmission payloadの差分を計算"""
    pass
