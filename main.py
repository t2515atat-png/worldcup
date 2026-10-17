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
# main.py에 이어 붙일 부분 — 학급의 대결 기록을 분석한다
import pandas as pd
import plotly.express as px

st.divider()
st.subheader("학급 대결 기록")

st.button("결과 새로 불러오기")
try:
    # 조회 시작 때의 마지막 id까지만, 빠짐없이 나누어 읽는다
    latest = db.table("menu_duels").select("id").order("id", desc=True).limit(1).execute().data
    upper = latest[0]["id"] if latest else 0
    records = []
    after = 0
    while after < upper:
        page = (db.table("menu_duels")
                .select("id,game_id,round,left_menu,right_menu,winner")
                .gt("id", after).lte("id", upper).order("id").limit(500).execute().data)
        if not page:
            raise RuntimeError("마지막 기록까지 조회하지 못했습니다.")
        records.extend(page)
        after = page[-1]["id"]
except Exception:
    st.error("기록을 불러오지 못했습니다.")
    st.stop()

if not records:
    st.info("아직 대결 기록이 없습니다.")
    st.stop()

duels = pd.DataFrame(records)
# 겨룬 횟수는 왼쪽과 오른쪽을 모두 센다
fought = pd.concat([duels["left_menu"], duels["right_menu"]]).value_counts()
won = duels["winner"].value_counts()
champion = duels[duels["round"] == "결승"]["winner"].value_counts()

board = pd.DataFrame({"겨룬 횟수": fought, "이긴 횟수": won, "우승": champion}).reindex(MENUS).fillna(0).astype(int)
board["승률(%)"] = (board["이긴 횟수"] / board["겨룬 횟수"].where(board["겨룬 횟수"] > 0) * 100).round(1)
board = board.sort_values("승률(%)", ascending=False).reset_index(names="반찬")

st.caption("대결 " + str(len(duels)) + "번 · 기록이 있는 판 " + str(duels["game_id"].nunique()) + "개")
st.caption("결승 기록이 있는 판 " + str(duels.loc[duels["round"] == "결승", "game_id"].nunique()) + "개 · 진행 중 기록도 포함합니다.")
st.caption("대결이 없는 후보의 승률은 비어 있습니다. 대결 수와 판 수는 참여 인원이 아닙니다.")
st.dataframe(board, hide_index=True, width="stretch")

fig = px.bar(board.dropna(subset=["승률(%)"]).sort_values("승률(%)"), x="승률(%)", y="반찬", orientation="h",
             text="승률(%)", color="승률(%)", color_continuous_scale="Oranges",
             title="반찬별 승률")
fig.update_layout(coloraxis_showscale=False, yaxis_title="")
st.plotly_chart(fig, width="stretch")
st.caption("조회 도중 들어온 새 기록은 다시 불러오면 반영됩니다. 승률은 대진표와 반복 참여의 영향을 받습니다.")
