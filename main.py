import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="일별 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 일별 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 공식 API 기준")


# --------------------------------------------------
# 2. 한국 시간 기준 날짜 계산
# --------------------------------------------------
# Streamlit Cloud 서버의 시간은 한국 시간이 아닐 수 있습니다.
# 따라서 반드시 Asia/Seoul 기준으로 오늘 날짜를 계산합니다.

KST = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(KST).date()
yesterday = today_kst - timedelta(days=1)


# --------------------------------------------------
# 3. 조회할 날짜 선택
# --------------------------------------------------
# 가장 최근에 선택할 수 있는 날짜는 '어제'입니다.
# 오늘 날짜는 아직 집계가 끝나지 않았으므로 선택할 수 없습니다.

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환합니다.
target_date = selected_date.strftime("%Y%m%d")


# --------------------------------------------------
# 4. KOBIS API 호출 함수
# --------------------------------------------------
# 같은 날짜를 다시 조회하면 1시간 동안 캐시된 결과를 사용합니다.
#
# 예:
# 9월 22일 조회 → API 호출
# 다시 9월 22일 조회 → 캐시 사용
# 9월 21일 조회 → 새로운 API 호출


@st.cache_data(ttl=3600, show_spinner=False)
def get_boxoffice(target_dt):
    # Streamlit Secrets에서 KOBIS 인증키를 가져옵니다.
    # 인증키를 코드에 직접 적지 않습니다.

    try:
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud에서 다음을 확인하세요.\n"
                "1. 앱의 Settings → Secrets로 이동하세요.\n"
                "2. KOBIS_KEY라는 이름으로 인증키를 등록하세요.\n"
                "3. 인증키 앞뒤에 불필요한 공백이나 따옴표가 없는지 확인하세요."
            ),
        }

    # KOBIS 일별 박스오피스 API 주소입니다.
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        # KOBIS API에 요청합니다.
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 실행해 보세요. "
                "계속 문제가 발생하면 KOBIS API 서버 상태와 "
                "네트워크 연결을 확인하세요."
            ),
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "인터넷 연결과 KOBIS API 주소를 확인하세요.\n"
                f"오류 내용: {e}"
            ),
        }

    except ValueError:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API가 정상적인 JSON 응답을 보내지 않았습니다.\n\n"
                "KOBIS API 서버 상태를 확인한 뒤 다시 실행해 보세요."
            ),
        }

    # --------------------------------------------------
    # 5. faultInfo 확인
    # --------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 응답 안에 faultInfo가 있는지 반드시 확인합니다.

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        error_message = fault_info.get(
            "message",
            "KOBIS API에서 오류를 반환했습니다.",
        )

        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {error_message}\n\n"
                "다음을 확인하세요.\n"
                "• Streamlit Secrets의 KOBIS_KEY가 정확한지\n"
                "• 인증키가 활성화되어 있는지\n"
                "• KOBIS API 이용이 정상적으로 가능한지"
            ),
        }

    # --------------------------------------------------
    # 6. boxOfficeResult 확인
    # --------------------------------------------------

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API의 응답 형식과 서버 상태를 확인해 주세요."
            ),
        }

    # 영화 목록을 가져옵니다.
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        [],
    )

    # 영화 목록이 비어 있으면 별도로 처리합니다.
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "그날은 아직 집계 전입니다.",
        }

    return {
        "success": True,
        "empty": False,
        "data": movie_list,
    }


# --------------------------------------------------
# 7. 선택한 날짜의 박스오피스 조회
# --------------------------------------------------

with st.spinner("박스오피스를 불러오는 중입니다..."):
    result = get_boxoffice(target_date)


# --------------------------------------------------
# 8. 오류 처리
# --------------------------------------------------

if not result["success"]:

    if result["empty"]:
        # 영화 목록이 비어 있는 경우에는
        # 사용자가 요청한 문구를 정확하게 보여 줍니다.
        st.warning("📊 그날은 아직 집계 전입니다.")

    else:
        # API 오류나 인증키 오류 등을 안내합니다.
        st.error(result["message"])

    st.stop()


# --------------------------------------------------
# 9. API 결과를 DataFrame으로 변환
# --------------------------------------------------

df = pd.DataFrame(result["data"])


# --------------------------------------------------
# 10. 숫자 데이터를 실제 숫자로 변환
# --------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 옵니다.
# 그래프, 정렬, 비교 등에 사용할 수 있도록 숫자로 변환합니다.

numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0).astype(int)


# --------------------------------------------------
# 11. 순위순으로 정렬
# --------------------------------------------------

df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 12. 영화명 꾸미기
# --------------------------------------------------
# 누적관객이 100만 명을 넘은 영화는
# 영화명 뒤에 트로피 이모지를 붙입니다.

df["movieNmDisplay"] = df.apply(
    lambda row: (
        f"{row['movieNm']} 🏆"
        if row["audiAcc"] >= 1_000_000
        else row["movieNm"]
    ),
    axis=1,
)


# --------------------------------------------------
# 13. 순위 증감 표시
# --------------------------------------------------
# rankInten의 의미:
# 양수 → 전날보다 순위가 올라감 → 빨간 위 화살표
# 음수 → 전날보다 순위가 내려감 → 파란 아래 화살표
# 0    → 변동 없음
#
# 예:
# +2 → 🔺 +2
# -1 → 🔽 -1


def format_rank_change(value):
    if value > 0:
        return f":red[⬆️ +{value}]"

    if value < 0:
        return f":blue[⬇️ {value}]"

    return "-"


df["rankChange"] = df["rankInten"].apply(
    format_rank_change
)


# --------------------------------------------------
# 14. 선택 날짜 표시
# --------------------------------------------------

st.subheader(
    f"📅 {selected_date.strftime('%Y년 %m월 %d일')} 박스오피스"
)


# --------------------------------------------------
# 15. 1위 영화 확인
# --------------------------------------------------

first_movie = df.iloc[0]

movie_name = first_movie["movieNmDisplay"]

first_audience = int(
    first_movie["audiCnt"]
)

first_acc = int(
    first_movie["audiAcc"]
)

first_screens = int(
    first_movie["scrnCnt"]
)


# --------------------------------------------------
# 16. 1위 영화 표시
# --------------------------------------------------

st.markdown(f"### 🏆 1위: {movie_name}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "당일 관객수",
        f"{first_audience:,}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_acc:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_screens:,}개",
    )


# --------------------------------------------------
# 17. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False,
    )
    .head(5)
    .copy()
)

# 영화명을 그래프의 항목으로 사용합니다.
chart_data = top5.set_index(
    "movieNmDisplay"
)[["audiCnt"]]

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수",
)


# --------------------------------------------------
# 18. 전체 영화 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

display_df = df[
    [
        "rank",
        "rankChange",
        "movieNmDisplay",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()


# 화면에 표시할 열 이름을 한국어로 변경합니다.

display_df.columns = [
    "순위",
    "전일 대비",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]


# 숫자에 천 단위 쉼표를 표시합니다.

display_df["관객수"] = display_df[
    "관객수"
].map(
    lambda x: f"{x:,}"
)

display_df["누적관객"] = display_df[
    "누적관객"
].map(
    lambda x: f"{x:,}"
)

display_df["스크린수"] = display_df[
    "스크린수"
].map(
    lambda x: f"{x:,}"
)


# --------------------------------------------------
# 19. 표 출력
# --------------------------------------------------

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# --------------------------------------------------
# 20. 데이터 출처
# --------------------------------------------------

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) "
    "일별 박스오피스 API"
)
