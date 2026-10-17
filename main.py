
# -*- coding: utf-8 -*-
import random
import uuid

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

ROUND_NAMES = {
    8: "8강",
    4: "4강",
    2: "결승",
}


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
        options=ClientOptions(
            postgrest_client_timeout=10
        ),
    )


def start_game():
    """새 월드컵을 시작하고 대진 순서를 섞습니다."""
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

    # 현재 라운드의 대결이 남아 있다면 계속 진행합니다.
    if (
        st.session_state.pair_index
        < len(st.session_state.pairs)
    ):
        return

    # 결승까지 끝났다면 우승자를 결정합니다.
    if len(st.session_state.winners) == 1:
        st.session_state.champion = (
            st.session_state.winners[0]
        )
        return

    # 다음 라운드의 대진을 만듭니다.
    next_round_menus = st.session_state.winners[:]

    st.session_state.round_size = len(
        next_round_menus
    )

    st.session_state.pairs = [
        (
            next_round_menus[i],
            next_round_menus[i + 1],
        )
        for i in range(
            0,
            len(next_round_menus),
            2,
        )
    ]

    st.session_state.pair_index = 0
    st.session_state.winners = []


def save_duel_and_advance(winner):
    """대결 결과를 저장하고 저장 성공을 확인한 뒤 진행합니다."""
    left_menu, right_menu = (
        st.session_state.pairs[
            st.session_state.pair_index
        ]
    )

    # 서로 다른 두 후보 중 하나를 선택했는지 확인합니다.
    if (
        left_menu == right_menu
        or winner not in (left_menu, right_menu)
    ):
        st.session_state.locked = True
        st.session_state.save_error = (
            "대결 정보가 올바르지 않습니다. "
            "확인이 필요합니다."
        )
        return

    # 앱에서 기록할 열은 다섯 개입니다.
    # id와 created_at은 데이터베이스가 처리합니다.
    row = {
        "game_id": st.session_state.game_id,
        "round": ROUND_NAMES[
            st.session_state.round_size
        ],
        "left_menu": left_menu,
        "right_menu": right_menu,
        "winner": winner,
    }

    try:
        client = get_supabase()

        # 기존 menu_duels 테이블에 한 행을 저장합니다.
        response = (
            client.table("menu_duels")
            .insert(row)
            .execute()
        )

        # 실제 삽입 결과가 응답에 있는지 확인합니다.
        inserted = response.data

        if (
            not inserted
            or not isinstance(inserted, list)
        ):
            raise RuntimeError(
                "삽입된 행을 확인할 수 없습니다."
            )

        saved = inserted[0]

        # 저장된 값이 요청한 값과 일치하는지 확인합니다.
        for field, expected in row.items():
            if saved.get(field) != expected:
                raise RuntimeError(
                    "저장된 대결 정보가 일치하지 않습니다."
                )

    except Exception:
        # 저장 여부가 불확실하면 재선택을 막습니다.
        st.session_state.locked = True

        st.session_state.save_error = (
            "대결 저장 결과를 확인하지 못했습니다. "
            "재선택과 추가 진행을 잠갔습니다. "
            "교사가 Supabase의 menu_duels 표와 "
            "연결 설정을 확인해야 합니다."
        )
        return

    # 저장 성공을 확인한 경우에만 다음 대결로 이동합니다.
    advance_after_win(winner)


# ------------------------------
# 화면 구성
# ------------------------------

st.title("🍱 급식 반찬 월드컵")

st.write(
    "8개 반찬 중 가장 먹고 싶은 반찬을 골라 주세요. "
    "총 7번 선택하면 우승 반찬이 정해집니다."
)

with st.expander("후보 반찬 보기"):
    st.write(" · ".join(MENUS))

if "started" not in st.session_state:
    st.session_state.started = False


# 시작 화면
if not st.session_state.started:
    st.info(
        "시작 버튼을 누르면 후보 순서를 섞어 "
        "8강 대진을 만듭니다."
    )

    if st.button(
        "월드컵 시작하기",
        type="primary",
        use_container_width=True,
    ):
        start_game()
        st.rerun()

    st.stop()


# 저장 오류 화면
if st.session_state.locked:
    st.error(
        st.session_state.save_error
        or "저장 확인이 필요합니다."
    )

    st.warning(
        "중복 저장을 피하기 위해 현재 판에서는 "
        "더 이상 선택할 수 없습니다. "
        "교사에게 확인을 요청해 주세요."
    )

    if st.button(
        "새 판 시작하기",
        use_container_width=True,
    ):
        start_game()
        st.rerun()

    st.stop()


# 우승 결과 화면
if st.session_state.champion:
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

    st.stop()


# 현재 대결 정보
round_label = ROUND_NAMES[
    st.session_state.round_size
]

left_menu, right_menu = (
    st.session_state.pairs[
        st.session_state.pair_index
    ]
)

total_matches = {
    8: 4,
    4: 2,
    2: 1,
}[st.session_state.round_size]

match_number = (
    st.session_state.pair_index + 1
)

st.subheader(
    f"{round_label} · "
    f"{match_number}/{total_matches}번째 대결"
)

# 전체 7번 선택 중 현재까지의 진행 상황
if st.session_state.round_size == 8:
    completed = st.session_state.pair_index
elif st.session_state.round_size == 4:
    completed = 4 + st.session_state.pair_index
else:
    completed = 6 + st.session_state.pair_index

st.progress(completed / 7)

st.write(
    "두 반찬 중 더 먹고 싶은 반찬 하나를 선택하세요."
)

# 두 반찬을 나란히 표시합니다.
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

