import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

# 한국 시간대 사용
KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------
# 어제 날짜 계산
# ---------------------------------------------------------

def get_yesterday():
    """한국 시간 기준으로 어제 날짜를 yyyymmdd 형태로 반환합니다."""
    now_kst = datetime.now(KST)
    yesterday = now_kst - timedelta(days=1)

    return yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# KOBIS API 호출
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_date):
    """
    KOBIS 일일 박스오피스 API를 호출합니다.

    같은 날짜의 결과는 약 1시간 동안 캐시해서
    API를 불필요하게 반복 호출하지 않습니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 읽습니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as error:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"네트워크 또는 API 주소를 확인해 주세요.\n"
                f"상세 내용: {error}"
            ),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다.\n\n"
                "API 주소나 응답 상태를 확인해 주세요."
            ),
        }

    # 인증키가 잘못된 경우 HTTP 200이어도
    # faultInfo가 들어올 수 있으므로 반드시 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {fault_info}"
            ),
        }

    # 정상 응답인지 확인합니다.
    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과가 없습니다.\n\n"
                "KOBIS API 응답 구조 또는 인증키를 확인해 주세요."
            ),
        }

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 사용자에게 확인할 내용을 안내합니다.
    if not movie_list:
        return {
            "success": False,
            "message": (
                "해당 날짜의 영화 목록이 비어 있습니다.\n\n"
                "다음 사항을 확인해 주세요.\n"
                "- 조회 날짜가 올바른지 확인하세요.\n"
                "- KOBIS에서 해당 날짜의 일일 박스오피스가 집계되었는지 확인하세요.\n"
                "- KOBIS API 인증키가 정상인지 확인하세요.\n"
            ),
        }

    # API에서 숫자가 문자열로 오므로 숫자로 변환합니다.
    movies = []

    for movie in movie_list:
        movies.append(
            {
                "순위": int(movie.get("rank", 0)),
                "영화명": movie.get("movieNm", ""),
                "개봉일": movie.get("openDt", ""),
                "관객수": int(movie.get("audiCnt", 0)),
                "누적관객": int(movie.get("audiAcc", 0)),
                "스크린수": int(movie.get("scrnCnt", 0)),
            }
        )

    return {
        "success": True,
        "movies": movies,
    }


# ---------------------------------------------------------
# 숫자를 보기 좋게 표시하는 함수
# ---------------------------------------------------------

def format_number(number):
    """숫자에 천 단위 쉼표를 넣습니다."""
    return f"{number:,}"


# ---------------------------------------------------------
# 화면
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")

target_date = get_yesterday()

# 날짜를 사람이 읽기 쉬운 형태로 표시합니다.
display_date = datetime.strptime(target_date, "%Y%m%d").strftime("%Y년 %m월 %d일")

st.caption(f"KOBIS 일일 박스오피스 · {display_date} 기준")


# ---------------------------------------------------------
# 데이터 가져오기
# ---------------------------------------------------------

result = get_box_office(target_date)

if not result["success"]:
    # API 오류 등이 발생하면 빈 화면 대신 안내합니다.
    st.error("박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(result["message"])

    st.info(
        "Streamlit Cloud를 사용한다면 "
        "앱의 Settings → Secrets에서 "
        "`KOBIS_KEY`가 설정되어 있는지도 확인해 주세요."
    )

    st.stop()


movies = result["movies"]

# 혹시라도 목록이 비어 있는 경우를 한 번 더 방어합니다.
if not movies:
    st.warning(
        "표시할 영화가 없습니다. "
        "KOBIS의 해당 날짜 박스오피스 집계 여부와 인증키를 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader(f"🥇 1위 · {first_movie['영화명']}")

# 지표 카드 세 개
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "당일 관객수",
        f"{format_number(first_movie['관객수'])}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{format_number(first_movie['누적관객'])}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{format_number(first_movie['스크린수'])}개",
    )


# ---------------------------------------------------------
# 관객수 상위 5편 그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# API 결과 자체가 순위순으로 오지만,
# 관객수를 기준으로 다시 정렬해서 그래프에 사용합니다.
top_5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart에 넣기 좋은 형태로 만듭니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top_5
}

st.bar_chart(
    chart_data,
    horizontal=True,
    x_label="관객수",
    y_label="영화명",
)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["순위"],
            "영화명": movie["영화명"],
            "개봉일": movie["개봉일"],
            "관객수": format_number(movie["관객수"]),
            "누적관객": format_number(movie["누적관객"]),
            "스크린수": format_number(movie["스크린수"]),
        }
    )

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d위",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.TextColumn(
            "관객수",
        ),
        "누적관객": st.column_config.TextColumn(
            "누적관객",
        ),
        "스크린수": st.column_config.TextColumn(
            "스크린수",
        ),
    },
)
