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
