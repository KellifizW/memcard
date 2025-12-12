import streamlit as st
import random
import time

st.title("🧠 翻牌記憶小遊戲")
st.markdown("點擊卡片翻牌，配對相同圖案！")

# 初始化遊戲狀態
if 'board' not in st.session_state:
    images = ['🍎', '🍌', '🍇', '🍉', '🍓', '🥝', '🍒', '🫐'] * 2
    random.shuffle(images)
    st.session_state.board = images
    st.session_state.matched = set()
    st.session_state.flipped_this_turn = []
    st.session_state.moves = 0
    st.session_state.start_time = time.time()
    st.session_state.game_won = False

# 重新開始按鈕
if st.button("🔄 重新開始"):
    images = ['🍎', '🍌', '🍇', '🍉', '🍓', '🥝', '🍒', '🫐'] * 2
    random.shuffle(images)
    st.session_state.board = images
    st.session_state.matched = set()
    st.session_state.flipped_this_turn = []
    st.session_state.moves = 0
    st.session_state.start_time = time.time()
    st.session_state.game_won = False
    st.rerun()

# 建立4x4網格
cols = st.columns(4)
for i in range(16):
    col_idx = i % 4
    with cols[col_idx]:
        is_matched = i in st.session_state.matched
        is_flipped = i in st.session_state.flipped_this_turn or is_matched
        
        if is_flipped:
            st.markdown(f"### {st.session_state.board[i]}")
        else:
            if st.button("❓", key=f"flip_{i}"):
                if len(st.session_state.flipped_this_turn) < 2:
                    st.session_state.flipped_this_turn.append(i)
                    st.session_state.moves += 1
                    st.rerun()

# 檢查配對邏輯（在網格渲染後執行）
if len(st.session_state.flipped_this_turn) == 2:
    i1, i2 = st.session_state.flipped_this_turn
    if st.session_state.board[i1] == st.session_state.board[i2]:
        st.session_state.matched.update([i1, i2])
        st.session_state.flipped_this_turn = []
        st.rerun()
    else:
        # 短暫顯示後翻回（使用時間戳模擬延遲）
        if 'mismatch_time' not in st.session_state:
            st.session_state.mismatch_time = time.time()
        if time.time() - st.session_state.mismatch_time > 1.0:
            st.session_state.flipped_this_turn = []
            del st.session_state.mismatch_time
            st.rerun()

# 遊戲資訊
elapsed = time.time() - st.session_state.start_time
st.metric("步數", st.session_state.moves)
st.metric("時間", f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}")

# 勝利判定
if len(st.session_state.matched) == 16 and not st.session_state.game_won:
    st.session_state.game_won = True
    st.balloons()
    st.success("🎉 恭喜通關！")

# 勝利後顯示最終成績
if st.session_state.game_won:
    st.info(f"最終成績：{st.session_state.moves} 步，{int(elapsed // 60):02d}:{int(elapsed % 60):02d}")
