
# -*- coding: utf-8 -*-
import random
import uuid

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client
from supabase.lib.client_options import ClientOptions

st.set_page_config(
    page_title="급식 반찬 월드컵",
    page_icon="🍱",
    layout="centered",
)

MENUS = [
    "제육볶음",
    "간장찜닭",
    "가자미순살튀김",
    "돈육불백",
    "미트볼데리야끼볶음",
    "수육",
    "진미채고추장볶음",
    "치즈떡닭갈비",
]

ROUND_NAMES = {8: "8강", 4: "4강", 2: "결승"}
DUEL_COLUMNS = "id, game_id, round, left_menu, right_menu, winner"


def get_supabase():
    """Secrets에서 Supabase 접속 정보를 가져옵니다."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Secrets에 SUPABASE_URL과 SUPABASE_KEY를 설정해 주세요."
        )

    return create_client(
        url,
        key,
        options=ClientOptions(postgrest_client_timeout=15),
    )


def fetch_all_duels():
    """페이지 단위로 menu_duels의 전체 기록을 조회합니다."""
    client = get_supabase()
    all_rows = []
    page_size = 1000
    start = 0

    while True:
        response = (
            client.table("menu_duels")
            .select(DUEL_COLUMNS)
            .order("id")
            .range(start, start + page_size - 1)
            .execute()
        )

        page = response.data
        if page is None:
            raise RuntimeError("대결 기록 조회 결과를 확인할 수 없습니다.")

        all_rows.extend(page)

        if len(page) < page_size:
            break

        start += page_size

    return all_rows


def build_menu_stats(rows):
    """반찬별 대결 수, 승리 수, 승률, 우승 횟수를 계산합니다."""
    stats = {
        menu: {
            "반찬": menu,
            "대결 수": 0,
            "승리 수": 0,
            "승률(%)": None,
            "우승 횟수": 0,
        }
        for menu in MENUS
    }

    for row in rows:
        left_menu = row.get("left_menu")
        right_menu = row.get("right_menu")
        winner = row.get("winner")

        # 대결 수는 왼쪽 후보와 오른쪽 후보를 각각 셉니다.
        if left_menu in stats:
            stats[left_menu]["대결 수"] += 1

        if right_menu in stats:
            stats[right_menu]["대결 수"] += 1

        # winner에 저장된 후보의 승리 수를 셉니다.
        if winner in stats:
            stats[winner]["승리 수"] += 1

        # 우승 횟수는 결승 기록의 winner만 셉니다.
        if row.get("round") == "결승" and winner in stats:
            stats[winner]["우승 횟수"] += 1

    for item in stats.values():
        games = item["대결 수"]

        if games > 0:
            item["승률(%)"] = round(
                item["승리 수"] / games * 100, 1
            )

    # 승률이 있는 후보는 높은 순서로, 기록이 없는 후보는 아래에 표시합니다.
    return sorted(
        stats.values(),
        key=lambda item: (
            item["승률(%)"] is None,
            -(item["승률(%)"] or 0),
            -item["우승 횟수"],
            item["반찬"],
        ),
    )


def start_game():
    """새 월드컵을 시작합니다."""
    menus = MENUS.copy()
    random.shuffle(menus)

    st.session_state.game_id = str(uuid.uuid4())
    st.session_state.round_size = 8
    st.session_state.pairs = [
        (menus[i], menus[i + 1])
        for i in range(0, len(menus), 2)
    ]
    st.session_state.pair_index = 0
    st.session_state.winners = []
    st.session_state.champion = None
    st.session_state.locked = False
    st.session_state.save_error = None
    st.session_state.started = True


def advance_after_win(winner):
    """저장 성공 후 승자를 다음 라운드로 올립니다."""
    st.session_state.winners.append(winner)
    st.session_state.pair_index += 1

    if st.session_state.pair_index < len(st.session_state.pairs):
        return

    if len(st.session_state.winners) == 1:
        st.session_state.champion = st.session_state.winners[0]
        return

    next_menus = st.session_state.winners[:]
    st.session_state.round_size = len(next_menus)
    st.session_state.pairs = [
        (next_menus[i], next_menus[i + 1])
        for i in range(0, len(next_menus), 2)
    ]
    st.session_state.pair_index = 0
    st.session_state.winners = []


def save_duel_and_advance(winner):
    """대결 결과를 저장하고 확인된 경우에만 진행합니다."""
    left_menu, right_menu = st.session_state.pairs[
        st.session_state.pair_index
    ]

    if left_menu == right_menu or winner not in (left_menu, right_menu):
        st.session_state.locked = True
        st.session_state.save_error = (
            "대결 정보가 올바르지 않습니다. 확인이 필요합니다."
        )
        return

    row = {
        "game_id": st.session_state.game_id,
        "round": ROUND_NAMES[st.session_state.round_size],
        "left_menu": left_menu,
        "right_menu": right_menu,
        "winner": winner,
    }

    try:
        response = (
            get_supabase()
            .table("menu_duels")
            .insert(row)
            .execute()
        )

        inserted = response.data
        if not inserted or not isinstance(inserted, list):
            raise RuntimeError("삽입된 행을 확인할 수 없습니다.")

        saved = inserted[0]

        for field, expected in row.items():
            if saved.get(field) != expected:
                raise RuntimeError(
                    "저장된 대결 정보가 요청한 값과 다릅니다."
                )

    except Exception:
        st.session_state.locked = True
        st.session_state.save_error = (
            "대결 저장 결과를 확인하지 못했습니다. "
            "재선택과 추가 진행을 잠갔습니다. "
            "교사가 Supabase의 menu_duels 표와 연결 설정을 "
            "확인해야 합니다."
        )
        return

    advance_after_win(winner)


def show_analytics():
    """학급 전체의 대결 기록을 분석합니다."""
    st.header("📊 학급 전체 대결 기록 분석")
    st.write(
        "menu_duels에 저장된 전체 대결 기록을 반찬별로 집계합니다. "
        "진행 중인 판의 대결도 저장되어 있다면 집계에 포함됩니다."
    )

    if st.button(
        "분석 결과 다시 불러오기",
        key="refresh_analytics",
    ):
        st.rerun()

    try:
        rows = fetch_all_duels()
    except Exception:
        st.error(
            "대결 기록을 조회하지 못했습니다. Supabase 접속 정보, "
            "테이블 권한 및 조회 정책을 확인한 뒤 다시 불러와 주세요."
        )
        return

    # 조회는 성공했지만 기록이 없는 경우
    if not rows:
        st.info(
            "아직 저장된 대결 기록이 없습니다. 월드컵에서 대결을 진행하면 "
            "저장된 기록을 이 화면에서 분석할 수 있습니다."
        )
        st.metric("대결 기록 수", "0개")
        st.metric("판 수", "0판")
        st.caption(
            "기록 수와 참여 인원은 다릅니다. "
            "진행 중에 남긴 대결도 집계에 들어갑니다."
        )
        return

    stats = build_menu_stats(rows)

    # 서로 다른 game_id의 수를 판 수로 계산합니다.
    game_ids = {
        row.get("game_id")
        for row in rows
        if row.get("game_id") is not None
    }

    col1, col2 = st.columns(2)
    col1.metric("대결 기록 수", f"{len(rows):,}개")
    col2.metric("판 수", f"{len(game_ids):,}판")

    st.caption(
        "기록 수와 참여 인원은 다릅니다. "
        "진행 중에 남긴 대결도 집계에 들어갑니다."
    )
    st.caption(
        "대결 수는 left_menu와 right_menu를 각각 셉니다. "
        "승률은 승리 수 ÷ 대결 수이며, 우승 횟수는 round가 "
        "'결승'인 기록의 winner만 셉니다."
    )

    st.subheader("반찬별 순위표")

    display_rows = []
    for item in stats:
        rate = item["승률(%)"]

        display_rows.append({
            "반찬": item["반찬"],
            "대결 수": item["대결 수"],
            "승리 수": item["승리 수"],
            "승률": (
                f"{rate:.1f}%"
                if rate is not None
                else "아직 알 수 없음"
            ),
            "우승 횟수": item["우승 횟수"],
        })

    st.dataframe(
        pd.DataFrame(display_rows),
        hide_index=True,
        use_container_width=True,
    )

    unknown = [
        item["반찬"]
        for item in stats
        if item["승률(%)"] is None
    ]

    if unknown:
        st.info(
            "대결 기록이 없는 후보의 승률은 아직 알 수 없습니다: "
            + ", ".join(unknown)
        )

    st.subheader("반찬별 승률 가로 막대그래프")

    chart_data = pd.DataFrame([
        {
            "반찬": item["반찬"],
            "승률(%)": item["승률(%)"],
            "승률 표시": (
                f'{item["승률(%)"]:.1f}%'
                if item["승률(%)"] is not None
                else "기록 없음"
            ),
        }
        for item in stats
    ])

    # 기록이 없는 후보를 0%로 오해하지 않도록 그래프에서 제외합니다.
    chart_data = chart_data.dropna(subset=["승률(%)"])

    if chart_data.empty:
        st.info(
            "아직 승률 그래프로 비교할 수 있는 대결 기록이 없습니다."
        )
    else:
        chart_data = chart_data.sort_values(
            "승률(%)",
            ascending=True,
        )

        fig = px.bar(
            chart_data,
            x="승률(%)",
            y="반찬",
            orientation="h",
            text="승률 표시",
            labels={
                "승률(%)": "승률 (%)",
                "반찬": "반찬",
            },
            title="반찬별 승률 비교",
        )

        fig.update_traces(
            textposition="outside",
            cliponaxis=False,
        )
        fig.update_layout(
            xaxis=dict(
                range=[
                    0,
                    max(
                        100,
                        float(chart_data["승률(%)"].max()) + 10,
                    ),
                ]
            ),
            yaxis_title="",
            margin=dict(l=10, r=30, t=60, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ------------------------------
# 앱 화면
# ------------------------------

st.title("🍱 급식 반찬 월드컵")

worldcup_tab, analytics_tab = st.tabs(
    ["🏆 반찬 월드컵", "📊 학급 기록 분석"]
)

with worldcup_tab:
    st.write(
        "8개 반찬 중 가장 먹고 싶은 반찬을 골라 주세요. "
        "총 7번 선택하면 우승 반찬이 정해집니다."
    )

    with st.expander("후보 반찬 보기"):
        st.write(" · ".join(MENUS))

    if "started" not in st.session_state:
        st.session_state.started = False

    # 월드컵 시작 화면
    if not st.session_state.started:
        st.info(
            "시작 버튼을 누르면 후보 순서를 섞어 8강 대진을 만듭니다."
        )

        if st.button(
            "월드컵 시작하기",
            type="primary",
            use_container_width=True,
        ):
            start_game()
            st.rerun()

    # 저장 오류 화면
    elif st.session_state.locked:
        st.error(
            st.session_state.save_error or "저장 확인이 필요합니다."
        )
        st.warning(
            "중복 저장을 피하기 위해 현재 판에서는 더 이상 선택할 수 없습니다. "
            "교사에게 확인을 요청해 주세요."
        )

        if st.button(
            "새 판 시작하기",
            use_container_width=True,
        ):
            start_game()
            st.rerun()

    # 우승 결과 화면
    elif st.session_state.champion:
        st.success("🏆 우승 반찬")
        st.header(st.session_state.champion)
        st.balloons()

        if st.button(
            "다시 시작하기",
            type="primary",
            use_container_width=True,
        ):
            start_game()
            st.rerun()

    # 대결 화면
    else:
        round_label = ROUND_NAMES[
            st.session_state.round_size
        ]

        left_menu, right_menu = st.session_state.pairs[
            st.session_state.pair_index
        ]

        total_matches = {
            8: 4,
            4: 2,
            2: 1,
        }[st.session_state.round_size]

        match_number = st.session_state.pair_index + 1

        st.subheader(
            f"{round_label} · "
            f"{match_number}/{total_matches}번째 대결"
        )

        if st.session_state.round_size == 8:
            completed = st.session_state.pair_index
        elif st.session_state.round_size == 4:
            completed = 4 + st.session_state.pair_index
        else:
            completed = 6 + st.session_state.pair_index

        st.progress(completed / 7)
        st.write("두 반찬 중 더 먹고 싶은 반찬 하나를 선택하세요.")

        col1, col2 = st.columns(2, gap="medium")

        with col1:
            st.markdown(f"### 🍚 {left_menu}")

            if st.button(
                f"{left_menu} 선택",
                key=(
                    f"left_{st.session_state.game_id}_"
                    f"{round_label}_{match_number}"
                ),
                type="primary",
                use_container_width=True,
            ):
                save_duel_and_advance(left_menu)
                st.rerun()

        with col2:
            st.markdown(f"### 🍚 {right_menu}")

            if st.button(
                f"{right_menu} 선택",
                key=(
                    f"right_{st.session_state.game_id}_"
                    f"{round_label}_{match_number}"
                ),
                type="primary",
                use_container_width=True,
            ):
                save_duel_and_advance(right_menu)
                st.rerun()

    st.caption(
        "선택한 대결만 저장됩니다. "
        "이름·학번·비밀번호는 수집하지 않습니다."
    )

# 우승 결과 화면에서도 이 탭을 열어 학급 분석을 볼 수 있습니다.
with analytics_tab:
    show_analytics()
