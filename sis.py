import streamlit as st
import openai
import random
import json
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_autorefresh import st_autorefresh

# ────────────────
# 기본 설정
# ────────────────
st.set_page_config(page_title="학생용 그림 생성", layout="wide")

st.caption("웹 어플리케이션 문의사항은 정재환(서울창일초), woghks0524jjh@gmail.com, 010-3393-0283으로 연락주세요.")
st.title("🎨 생성형AI 그림 그리기")

api_keys = st.secrets["api"]["keys"]
api_key = random.choice(api_keys)
client = openai.OpenAI(api_key=api_key)

# ────────────────
# 세션 초기화
# ────────────────
if "conversation" not in st.session_state:
    st.session_state["conversation"] = []
if "status" not in st.session_state:
    st.session_state["status"] = "idle"
if "latest_info" not in st.session_state:
    st.session_state["latest_info"] = {}
if "prompt_history" not in st.session_state:
    st.session_state["prompt_history"] = []
if "starter_message_shown" not in st.session_state:
    st.session_state["starter_message_shown"] = False

# ────────────────
# 구글 시트 연결
# ────────────────
def get_sheet():
    credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    gc = gspread.authorize(credentials)
    return gc.open(st.secrets["google"]["safe_image"]).sheet1

sheet = get_sheet()

# ────────────────
# 사이드바 사용자 정보
# ────────────────
with st.sidebar:
    st.header("👤 사용자 정보")
    code = st.text_input("🔑 코드 입력")
    student_name = st.text_input("🧒 이름 입력")

# ────────────────
# 대화 UI 출력
# ────────────────
with st.container(height=500, border=True):
    if not st.session_state["starter_message_shown"]:
        st.session_state["conversation"].append(("assistant", "안녕하세요! 그리고 싶은 그림에 대해 자세히 설명해주세요. 설명을 수정하면서 그림을 바꿔 나갈 수 있어요."))
        st.session_state["starter_message_shown"] = True

    for role, msg in st.session_state["conversation"]:
        if role == "user":
            st.chat_message("user").write(msg)
        elif role == "assistant":
            if isinstance(msg, str) and msg.startswith("http"):
                st.chat_message("assistant").image(msg)
            else:
                st.chat_message("assistant").write(msg)

# ────────────────
# 사용자 입력 처리
# ────────────────
user_input = st.chat_input("✍️ 그리고 싶은 내용을 자세히 설명해보세요. 그림체, 분위기, 인물, 색감, 동작 등")

if user_input and code and student_name:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 사용자 입력 누적
    st.session_state["prompt_history"].append(user_input)
    st.session_state["conversation"].append(("user", user_input))
    st.session_state["status"] = "waiting"
    st.session_state["latest_info"] = {
        "code": code,
        "student_name": student_name,
        "prompt": user_input
    }

    # GPT 프롬프트 생성
    full_context = "\n".join([f"- {p}" for p in st.session_state["prompt_history"]])
    gpt_prompt = f"""
너는 세계 최고 수준의 이미지 생성 프롬프트 전문가야.
사용자의 설명을 바탕으로, DALL·E 3 모델이 이해할 수 있도록
감성적이고 시각적으로 풍부한 영어 프롬프트를 만들어줘.

설명은 누적된 대화 흐름이야:
{full_context}

다만 아래 조건을 꼭 반영해줘:

- 절대로 하이퍼리얼리즘(hyperrealism), photorealism, 3D rendering 스타일은 사용하지 마
- **'flat 2D cartoon style', 'minimal shading', 'no lighting effects'** 이런 표현을 꼭 포함시켜줘
- 배경은 단순하고 그림자는 거의 없는 평면 스타일을 유지해
- 어린이 그림책이나 애니메이션처럼 부드럽고 명확한 라인, 따뜻한 색감, 단순한 구성이어야 해
- 무섭거나 해괴한 조합은 금지야. 아이들이 편안하게 볼 수 있어야 해

결과는 영어로, 아래처럼 시작해줘:
"A flat 2D illustration of..."
"""

    try:
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "너는 이미지 생성 전문 프롬프트 엔지니어야."},
                {"role": "user", "content": gpt_prompt}
            ]
        )
        dalle_prompt = gpt_response.choices[0].message.content.strip()

        response = client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size="1024x1024",
            quality="hd",
            n=1
        )
        image_url = response.data[0].url

        # 시트에 저장
        sheet.append_row([code, student_name, user_input, dalle_prompt, image_url, "FALSE", now])
        st.info("⏳ 선생님이 그림을 확인 중이에요.")
    except Exception as e:
        st.session_state["status"] = "idle"
        st.error(f"❌ 오류 발생: {e}")

# ────────────────
# 승인 여부 확인 (🔁 매번 최신 시트로 다시 조회)
# ────────────────
if st.session_state["status"] == "waiting":
    data = sheet.get_all_records()  # ✅ 최신 시트 내용 불러오기
    latest = st.session_state["latest_info"]
    
    for row in reversed(data):
        if (
            row["코드"] == latest.get("code") and
            row["이름"] == latest.get("student_name") and
            row["그림 설명"] == latest.get("prompt")
        ):
            if row["승인여부"].upper() == "TRUE":
                st.session_state["conversation"].append(("assistant", row["이미지 링크"]))
                st.session_state["status"] = "idle"
                st.success("✅ 선생님이 그림을 승인했어요!")
                st.rerun()
            else:
                st.info("⏳ 선생님이 그림을 확인 중이에요.")
            break

# ────────────────
# 자동 새로고침
# ────────────────
if st.session_state["status"] == "waiting":
    st_autorefresh(interval=10000, key="refresh")
