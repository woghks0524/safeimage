import streamlit as st
import gspread
import json
import time
import openai
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_autorefresh import st_autorefresh

# 페이지 구성
st.set_page_config(page_title="교사용 그림 승인", layout="wide")

st.caption("웹 어플리케이션 문의사항은 정재환(서울창일초), woghks0524jjh@gmail.com, 010-3393-0283으로 연락주세요.")

st_autorefresh(interval=10000, key="refresh_teacher")

# OpenAI 클라이언트 설정
api_keys = st.secrets["api"]["keys"]
openai.api_key = api_keys[0]
client = openai.OpenAI(api_key=openai.api_key)
assistant_id = 'asst_prIG3LL7UZnZ1qJ8ChTr5cye'

# 구글 시트 연결
@st.cache_resource
def get_sheet():
    credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    gc = gspread.authorize(credentials)
    return gc.open(st.secrets["google"]["safe_image"]).sheet1

sheet = get_sheet()
data = sheet.get_all_records()

# 사이드바 코드 입력
with st.sidebar:
    st.title("🧑‍🏫 교사용 승인 도구")
    code_input = st.text_input("🔐 코드 입력", placeholder="예: 바나나")

# 승인 UI
st.title("🎨 AI 그림 응답 승인 페이지")

if code_input:
    pending_data = [row for row in data if row["코드"] == code_input and row["승인여부"].upper() != "TRUE"]

    if not pending_data:
        st.warning("아직 승인되지 않은 그림 요청이 없습니다.")
    else:
        st.markdown(f"### 📝 '{code_input}' 코드에 대한 미승인 그림 요청 ({len(pending_data)}개)")

        rows = (len(pending_data) + 3) // 4
        for i in range(rows):
            cols = st.columns(4)
            for j, row in enumerate(pending_data[i * 4 : (i + 1) * 4]):
                with cols[j]:
                    with st.container(border=True):
                        st.markdown(f"#### 🙋 {row['이름']}")
                        st.markdown(f"**🎨 요청 설명:** {row['그림 설명']}")
                        st.image(row["이미지 링크"], use_column_width=True)

                        row_index = data.index(row) + 2
                        col_그림 = 5
                        col_승인 = 6

                        if st.button("✅ 승인", key=f"approve_{row_index}"):
                            sheet.update_cell(row_index, col_승인, "TRUE")
                            st.success("✅ 승인 완료")
                            st.rerun()

                        if st.button("🔁 재생성", key=f"regen_{row_index}"):
                            try:
                                # 재생성용 프롬프트 구성
                                base_prompt = (
                                    "A flat 2D illustration of the following scene, suitable for elementary school students. "
                                    "Avoid any surreal or scary imagery. Use a soft, friendly, and simple style with pastel colors.\n\n"
                                    f"{row['그림 설명']}"
                                )

                                # DALL·E 3 호출
                                dalle_response = client.images.generate(
                                    model="dall-e-3",
                                    prompt=base_prompt,
                                    size="1024x1024",
                                    quality="hd",
                                    n=1
                                )

                                new_image_url = dalle_response.data[0].url

                                # 시트 업데이트
                                sheet.update_cell(row_index, col_그림, new_image_url)
                                sheet.update_cell(row_index, col_승인, "FALSE")
                                st.success("✅ 새 그림으로 업데이트 완료")
                                st.rerun()

                            except Exception as e:
                                st.warning(f"❌ 이미지 생성 중 오류 발생: {e}")
else:
    st.info("왼쪽 사이드바에서 코드를 입력하세요.")
