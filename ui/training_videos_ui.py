def run_ui():
    import streamlit as st
    from services.dropbox_client import download_file_from_dropbox
    from core.constants import DROPBOX_TRAINING_VIDEO_DIR
    from core.error_handling import handle_error

    st.title("🎥 Training Video Library")
    st.markdown(
        "Browse internal video tutorials for each tool. All videos are securely streamed from Dropbox."
    )

    TRAINING_VIDEOS = {
        "Litigation Dashboard": f"{DROPBOX_TRAINING_VIDEO_DIR}/Litigation_Dashboard_Tutorial.mp4",
        "Welcome Email Sender": f"{DROPBOX_TRAINING_VIDEO_DIR}/Welcome_Email_Sender_Tutorial.mp4",
        "Batch Doc Generator": f"{DROPBOX_TRAINING_VIDEO_DIR}/Batch_Doc_Generator_Tutorial.mp4",
        "Style Mimic Generator": f"{DROPBOX_TRAINING_VIDEO_DIR}/Style_Mimic_Tutorial.mp4",
        "FOIA Requests": f"{DROPBOX_TRAINING_VIDEO_DIR}/FOIA_Tutorial.mp4",
        "Demand Letters": f"{DROPBOX_TRAINING_VIDEO_DIR}/Demand_Tutorial.mp4",
        "Mediation Memos": f"{DROPBOX_TRAINING_VIDEO_DIR}/Memo_Tutorial.mp4",
    }

    selected = st.selectbox("Select a training module:", list(TRAINING_VIDEOS.keys()))
    video_path = TRAINING_VIDEOS[selected]

    try:
        video_bytes = download_file_from_dropbox(video_path)
        if video_bytes:
            st.video(video_bytes)
        else:
            st.warning("⚠️ Video not available. Please contact admin.")
    except Exception as e:
        handle_error(e, code="TRAINING_VIDEO_LOAD_ERROR", raise_it=False)
        st.error("❌ Failed to load video. Please contact your admin.")
