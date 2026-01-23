"""
承認待ち一覧ページの表示ロジック
"""
import streamlit as st
import os
from datetime import datetime
from features.approval_actions import approve_submission, reject_submission, reopen_submission, calculate_submission_diff


def show_approval_queue():
    """承認待ち一覧ページ（管理者のみ）"""
    # パフォーマンス計測（DEBUG=1のみ）
    import time
    
    # is_debug_flag関数を取得
    try:
        from utils.settings import is_debug as is_debug_flag
    except Exception:
        # fallback: os.getenvを使用
        def is_debug_flag():
            return os.getenv("DEBUG", "0") == "1"
    
    debug_enabled = is_debug_flag()
    t0 = time.perf_counter() if debug_enabled else None
    
    # ヘッダー表示
    try:
        from utils.logo import render_site_header
        st.markdown(render_site_header(debug=debug_enabled), unsafe_allow_html=True)
    except Exception:
        st.markdown('<h1>承認待ち一覧</h1>', unsafe_allow_html=True)
    
    st.markdown('<h2 class="section-title">📋 承認待ち一覧</h2>', unsafe_allow_html=True)
    
    # フィルタ：rejectedも表示するか
    # 初期化はwidget作成前にのみ行う
    if "approval_show_rejected" not in st.session_state:
        st.session_state["approval_show_rejected"] = False
    
    show_rejected = st.checkbox(
        "却下済みも表示",
        key="approval_show_rejected"
    )
    
    # 検索：name_official部分一致
    # 初期化はwidget作成前にのみ行う
    if "approval_search" not in st.session_state:
        st.session_state["approval_search"] = ""
    
    search_query = st.text_input(
        "材料名で検索（部分一致）",
        key="approval_search"
    )
    
    # TODO: DBアクセスは後で実装
    # 現時点ではモックデータでUI骨格を確認
    # モックSubmissionオブジェクト（UI骨格確認用）
    class MockSubmission:
        def __init__(self, id, status="pending", submitted_by="テストユーザー", created_at=None, editor_note=None, reject_reason=None, approved_material_id=None):
            self.id = id
            self.status = status
            self.submitted_by = submitted_by
            self.created_at = created_at or time.time()
            self.editor_note = editor_note
            self.reject_reason = reject_reason
            self.approved_material_id = approved_material_id
    
    # モックデータ（UI骨格確認用）
    mock_submissions = [
        MockSubmission(
            id=1,
            status="pending",
            submitted_by="テストユーザー",
            created_at=datetime.now()
        )
    ]
    
    # ステータス別の件数表示（モック）
    pending_count = len([s for s in mock_submissions if s.status == "pending"])
    rejected_count = len([s for s in mock_submissions if s.status == "rejected"])
    approved_count = len([s for s in mock_submissions if s.status == "approved"])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("承認待ち", pending_count)
    with col2:
        st.metric("却下済み", rejected_count)
    with col3:
        st.metric("承認済み", approved_count)
    
    # TODO: DBからsubmissionsを取得する処理は後で実装
    # 現時点ではモックデータでUI骨格を確認
    submissions = mock_submissions
    
    if not submissions:
        st.info("✅ 該当する投稿はありません。")
        return
    
    # 各submissionの表示
    for submission in submissions:
        # ステータスに応じたアイコンと色
        status_icon = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌"
        }.get(getattr(submission, "status", "pending"), "📄")
        
        status_color = {
            "pending": "#FFA500",
            "approved": "#28A745",
            "rejected": "#DC3545"
        }.get(getattr(submission, "status", "pending"), "#666")
        
        # モックデータ用の表示
        submission_id = getattr(submission, "id", 0)
        created_at_obj = getattr(submission, "created_at", None)
        if created_at_obj:
            if hasattr(created_at_obj, "strftime"):
                # datetimeオブジェクトの場合
                created_at_display = created_at_obj.strftime('%Y-%m-%d %H:%M')
            elif isinstance(created_at_obj, (int, float)):
                # タイムスタンプの場合
                created_at_display = datetime.fromtimestamp(created_at_obj).strftime('%Y-%m-%d %H:%M')
            else:
                created_at_display = str(created_at_obj)
        else:
            created_at_display = "N/A"
        
        submitted_by = getattr(submission, "submitted_by", None) or "匿名"
        submission_status = getattr(submission, "status", "pending")
        
        with st.expander(
            f"{status_icon} {created_at_display} - {submitted_by} - {submission_status}",
            expanded=False
        ):
            # payload_jsonをパースして表示（TODO: 実装）
            st.markdown("### 投稿内容")
            
            # 主要フィールドを表示（モック）
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**材料名（正式）**: N/A")
                st.write(f"**カテゴリ**: N/A")
                st.write(f"**供給元**: N/A")
            with col2:
                st.write(f"**投稿者**: {submitted_by}")
                st.write(f"**投稿日時**: {created_at_display}")
                st.markdown(f"**ステータス**: <span style='color: {status_color}'>{submission_status}</span>", unsafe_allow_html=True)
                if hasattr(submission, "approved_material_id") and submission.approved_material_id:
                    st.write(f"**承認済み材料ID**: {submission.approved_material_id}")
            
            # editor_noteを表示・編集
            st.markdown("---")
            st.markdown("### 編集者メモ")
            editor_note_key = f"editor_note_edit_{submission_id}"
            editor_note_value = st.text_area(
                "編集者メモ（いつでも編集可能）",
                value=getattr(submission, "editor_note", "") or "",
                key=editor_note_key,
                placeholder="編集者メモを入力・編集できます"
            )
            if st.button("💾 メモを保存", key=f"save_note_{submission_id}"):
                st.info("TODO: メモ保存機能を実装")
                # TODO: DB保存処理を実装
                # st.success("✅ メモを保存しました")
                # st.rerun()
            
            # 却下理由を表示（rejectedの場合）
            if submission_status == "rejected" and hasattr(submission, "reject_reason") and submission.reject_reason:
                st.markdown("---")
                st.markdown("### 却下理由")
                st.warning(submission.reject_reason)
            
            # 差分表示（既存materialsとの比較）
            st.markdown("---")
            st.markdown("### 差分表示（既存材料との比較）")
            st.info("TODO: 差分表示機能を実装")
            
            # アップロードされた画像のプレビュー
            st.markdown("---")
            st.markdown("### 📷 アップロードされた画像")
            st.info("TODO: 画像プレビュー機能を実装")
            
            # プレビュー（簡易表示）
            st.markdown("---")
            st.markdown("### プレビュー（全データ）")
            with st.expander("JSONデータ", expanded=False):
                st.info("TODO: JSONデータ表示を実装")
            
            # アクション（ステータスに応じて表示）
            st.markdown("---")
            st.markdown("### アクション")
            
            if submission_status == "pending":
                # 承認モード選択（新規作成 or 既存更新）
                approval_mode_key = f"approval_mode_{submission_id}"
                approval_mode = st.radio(
                    "承認モード",
                    ["既存へ反映（同名素材がある場合）", "新規作成"],
                    index=0,  # デフォルトは「既存へ反映」
                    key=approval_mode_key,
                    help="同名の材料が既に存在する場合の動作を選択します"
                )
                update_existing = (approval_mode == "既存へ反映（同名素材がある場合）")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ 承認", key=f"approve_{submission_id}", type="primary"):
                        result = approve_submission(submission_id, editor_note=editor_note_value, update_existing=update_existing, db=None)
                        if result.get("ok"):
                            st.success("✅ 承認しました！（非公開状態で保存されました）")
                            st.info("💡 承認後、材料一覧で公開トグルをONにしてください。")
                            if result.get("image_warning"):
                                st.warning(f"⚠️ {result['image_warning']}")
                            st.cache_data.clear()  # キャッシュをクリア
                            st.rerun()
                        else:
                            error_msg = result.get('error', '不明なエラー')
                            st.error(f"❌ エラー: {error_msg}")
                            # name_official が空の場合は特別なメッセージを表示
                            if result.get("error_code") == "name_official_empty":
                                st.info("💡 投稿内容を編集して材料名（正式）を埋めてから再度承認してください。")
                            # DEBUG時は traceback を表示
                            if result.get("traceback"):
                                with st.expander("🔍 エラー詳細", expanded=False):
                                    st.code(result["traceback"], language="python")
                
                with col2:
                    reject_reason_key = f"reject_reason_{submission_id}"
                    reject_reason = st.text_input(
                        "却下理由（任意）",
                        key=reject_reason_key,
                        placeholder="却下理由を入力してください"
                    )
                    if st.button("❌ 却下", key=f"reject_{submission_id}"):
                        result = reject_submission(submission_id, reject_reason=reject_reason, db=None)
                        if result.get("ok"):
                            st.success("❌ 却下しました。")
                            st.cache_data.clear()  # キャッシュをクリア
                            st.rerun()
                        else:
                            error_msg = result.get('error', '不明なエラー')
                            st.error(f"❌ エラー: {error_msg}")
                            # DEBUG時は traceback を表示
                            if result.get("traceback"):
                                with st.expander("🔍 エラー詳細", expanded=False):
                                    st.code(result["traceback"], language="python")
            
            elif submission_status == "rejected":
                if st.button("🔄 再審査（pendingに戻す）", key=f"reopen_{submission_id}", type="primary"):
                    result = reopen_submission(submission_id, db=None)
                    if result.get("ok"):
                        st.success("🔄 再審査に戻しました。")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        error_msg = result.get('error', '不明なエラー')
                        st.error(f"❌ エラー: {error_msg}")
                        # DEBUG時は traceback を表示
                        if result.get("traceback"):
                            with st.expander("🔍 エラー詳細", expanded=False):
                                st.code(result["traceback"], language="python")
            
            elif submission_status == "approved":
                if hasattr(submission, "approved_material_id") and submission.approved_material_id:
                    st.info(f"✅ 承認済み材料ID: {submission.approved_material_id}")
                    if st.button("📝 材料詳細を見る", key=f"view_material_{submission_id}"):
                        st.info("TODO: 材料詳細ページへの遷移を実装")
                        # TODO: 材料詳細ページへの遷移
                        # st.session_state.selected_material_id = submission.approved_material_id
                        # st.session_state.page = "材料一覧"
                        # st.rerun()
