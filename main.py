# main.py — 급식 월드컵 8강. 대결 한 번이 표의 한 행이 된다.
import random
import uuid

import streamlit as st
from supabase import create_client

MENUS = ["제육볶음", "간장찜닭", "가자미순살튀김", "돈육불백",
         "미트볼데리야끼볶음", "수육", "진미채고추장볶음", "치즈떡닭갈비"]
ROUND = {8: "8강", 4: "4강", 2: "결승"}

st.header("🏆 급식 월드컵")
st.caption("이름 없이 참여하는 연습 게임입니다. 대결 기록 수는 참여 인원과 다릅니다.")


@st.cache_resource
def connect():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


try:
    db = connect()
except Exception:
    st.error("연결 정보를 확인하세요. 선생님이 표와 권한을 준비한 뒤 연결합니다.")
    st.stop()


def new_game():
    order = MENUS[:]
    random.shuffle(order)                      # 대진표를 판마다 섞는다
    st.session_state.game_id = uuid.uuid4().hex
    st.session_state.queue = order             # 이번 라운드에서 겨룰 차례
    st.session_state.winners = []              # 이번 라운드에서 이긴 반찬
    st.session_state.size = len(order)         # 이번 라운드의 크기 (8·4·2)
    st.session_state.save_pending = False


if "queue" not in st.session_state:
    new_game()

# 이번 라운드가 끝났으면 다음 라운드를 준비한다
if not st.session_state.queue and len(st.session_state.winners) > 1:
    st.session_state.queue = st.session_state.winners
    st.session_state.winners = []
    st.session_state.size = len(st.session_state.queue)

def choose(winner, left, right, round_name):
    st.session_state.save_pending = True
    try:
        db.table("menu_duels").insert({
            "game_id": st.session_state.game_id,
            "round": round_name,
            "left_menu": left,
            "right_menu": right,
            "winner": winner,
        }).execute()
    except Exception:
        # 통신 오류여도 DB에는 저장되었을 수 있어 재제출을 잠근다
        st.rerun()
    st.session_state.save_pending = False
    st.session_state.winners.append(winner)
    st.session_state.queue = st.session_state.queue[2:]
    st.rerun()


if not st.session_state.queue:                 # 결승까지 끝났다
    st.success("우승: " + st.session_state.winners[0])
    if st.button("다시 하기"):
        new_game()
        st.rerun()
else:
    left, right = st.session_state.queue[0], st.session_state.queue[1]
    round_name = ROUND[st.session_state.size]
    st.subheader(round_name)
    if st.session_state.save_pending:
        st.warning("저장 결과를 확인하지 못했습니다. 재선택을 잠갔습니다. 선생님에게 확인하세요.")
    col_l, col_r = st.columns(2)
    if col_l.button(left, use_container_width=True, disabled=st.session_state.save_pending):
        choose(left, left, right, round_name)
    if col_r.button(right, use_container_width=True, disabled=st.session_state.save_pending):
        choose(right, left, right, round_name)

st.caption("판 번호: " + st.session_state.game_id)
st.caption("반복 참여를 막지는 않습니다. 저장 결과 확인이 필요하면 이 판 번호를 준비 담당자에게 알려 주세요.")
