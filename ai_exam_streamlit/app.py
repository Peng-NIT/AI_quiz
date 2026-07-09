import json
import random
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import pyzipper
import streamlit as st

QUESTION_PATH = Path(__file__).with_name("questions.json")
TYPE_SCORE = {"单选题": 0.5, "判断题": 0.5, "多选题": 1.0}

# ====================== 管理员预设配置 ======================
# 说明：CSV 本身不支持原生密码保护，因此这里采用“加密 ZIP 包”的方式保存 CSV。
# 管理员提前设置该密码；考生成绩提交后，系统会生成一个需要该密码才能解压的成绩 CSV 文件。
ADMIN_EXPORT_PASSWORD = "Admin@123456"  # 请管理员在部署前修改为强密码

st.set_page_config(page_title="人工智能训练师交互答题系统", page_icon="🧠", layout="wide")


@st.cache_data
def load_questions(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for q in data:
        q["score"] = TYPE_SCORE.get(q["type"], 1.0)
    return data


def sample_questions(all_questions, selected_types, selected_sections, counts, shuffle=True, seed=None):
    pool = [q for q in all_questions if q["type"] in selected_types and q["section"] in selected_sections]
    rnd = random.Random(seed)
    selected = []
    for qtype, n in counts.items():
        type_pool = [q for q in pool if q["type"] == qtype]
        selected.extend(rnd.sample(type_pool, min(n, len(type_pool))))
    if shuffle:
        rnd.shuffle(selected)
    return selected


def grade(questions, answers):
    rows = []
    total_score, user_score = 0.0, 0.0
    for q in questions:
        correct = sorted(q["answer"])
        user_ans = answers.get(str(q["id"]), [])
        if isinstance(user_ans, str):
            user_ans = [user_ans] if user_ans else []
        user_ans = sorted(user_ans)
        is_right = user_ans == correct
        score = q["score"] if is_right else 0.0
        total_score += q["score"]
        user_score += score
        rows.append({
            "题号": q["id"],
            "题型": q["type"],
            "分类": q["section"],
            "题目": q["question"],
            "你的答案": " ".join(user_ans) if user_ans else "未作答",
            "正确答案": " ".join(correct),
            "得分": score,
            "满分": q["score"],
            "是否正确": "✅" if is_right else "❌",
        })
    return user_score, total_score, rows


def reset_exam():
    for key in [
        "exam_questions", "submitted", "result_rows", "user_score", "total_score",
        "start_time", "submit_time", "username", "answer_cache",
        "encrypted_result_bytes", "encrypted_result_filename"
    ]:
        st.session_state.pop(key, None)


def get_exam_statistics(rows):
    right_count = sum(r["是否正确"] == "✅" for r in rows)
    wrong_count = sum(r["是否正确"] == "❌" for r in rows)
    unanswered_count = sum(r["你的答案"] == "未作答" for r in rows)
    accuracy = right_count / len(rows) if rows else 0.0
    return right_count, wrong_count, unanswered_count, accuracy


def safe_filename(text: str) -> str:
    keep = []
    for ch in text.strip():
        if ch.isalnum() or ch in ("_", "-", "."):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "anonymous"


def build_result_dataframe(username, user_score, total_score, accuracy, right_count, wrong_count, unanswered_count, rows):
    summary_rows = [
        {"字段": "用户名", "值": username},
        {"字段": "开始时间", "值": st.session_state.get("start_time", "")},
        {"字段": "提交时间", "值": st.session_state.get("submit_time", "")},
        {"字段": "得分", "值": f"{user_score:.1f}"},
        {"字段": "满分", "值": f"{total_score:.1f}"},
        {"字段": "正确率", "值": f"{accuracy:.2%}"},
        {"字段": "答对题数", "值": right_count},
        {"字段": "答错题数", "值": wrong_count},
        {"字段": "未作答题数", "值": unanswered_count},
    ]
    summary_df = pd.DataFrame(summary_rows)
    detail_df = pd.DataFrame(rows)

    # 在同一个 CSV 中同时保存概要信息和答题明细，中间用空行分隔。
    csv_text = "【考试概要】\n"
    csv_text += summary_df.to_csv(index=False)
    csv_text += "\n【答题明细】\n"
    csv_text += detail_df.to_csv(index=False)
    return csv_text.encode("utf-8-sig")


def create_encrypted_csv_zip(csv_bytes: bytes, username: str, password: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_user = safe_filename(username)
    csv_name = f"exam_result_{safe_user}_{timestamp}.csv"
    zip_name = f"exam_result_{safe_user}_{timestamp}_encrypted.zip"

    buffer = BytesIO()
    with pyzipper.AESZipFile(
        buffer,
        mode="w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.writestr(csv_name, csv_bytes)

    encrypted_bytes = buffer.getvalue()
    # 不写入服务器磁盘，仅保存在内存中，供浏览器下载。
    return encrypted_bytes, zip_name


questions = load_questions(QUESTION_PATH)
sections = sorted({q["section"] for q in questions})
types = ["单选题", "判断题", "多选题"]

st.title("🧠 人工智能训练师选拔考试 · 交互答题系统")
st.caption("支持用户名输入、随机组卷、自动判分，并在提交后生成管理员密码保护的加密成绩 CSV 下载文件；考生端仅显示最终分数，不显示正确答案。")

with st.sidebar:
    st.header("考生信息")
    username_input = st.text_input(
        "用户名 / 姓名",
        value=st.session_state.get("username", ""),
        placeholder="请输入用户名或姓名",
    )

    st.header("组卷设置")
    selected_types = st.multiselect("题型", types, default=types)
    selected_sections = st.multiselect("知识模块", sections, default=sections)

    available = Counter(q["type"] for q in questions if q["section"] in selected_sections)
    counts = {}
    for t in types:
        if t in selected_types:
            default_n = min(10, available[t]) if t != "多选题" else min(5, available[t])
            counts[t] = st.number_input(f"{t}数量（最多 {available[t]}）", 0, int(available[t]), int(default_n), 1)

    shuffle = st.checkbox("随机打乱题目", value=True)
    seed_text = st.text_input("随机种子（可选，便于复现实验）", value="")
    seed = int(seed_text) if seed_text.strip().isdigit() else None

    col_a, col_b = st.columns(2)
    with col_a:
        start = st.button("开始答题", use_container_width=True)
    with col_b:
        clear = st.button("重置", use_container_width=True)

if clear:
    reset_exam()
    st.rerun()

if start:
    if not username_input.strip():
        st.warning("请先输入用户名 / 姓名，再开始答题。")
        st.stop()
    if not selected_types or not selected_sections or sum(counts.values()) == 0:
        st.warning("请至少选择一种题型、一个知识模块，并设置题目数量。")
        st.stop()
    reset_exam()
    st.session_state.username = username_input.strip()
    st.session_state.exam_questions = sample_questions(
        questions, selected_types, selected_sections, counts, shuffle=shuffle, seed=seed
    )
    st.session_state.submitted = False
    st.session_state.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.rerun()

if "exam_questions" not in st.session_state:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("题库总数", len(questions))
    c2.metric("单选题", Counter(q["type"] for q in questions).get("单选题", 0))
    c3.metric("判断题", Counter(q["type"] for q in questions).get("判断题", 0))
    c4.metric("多选题", Counter(q["type"] for q in questions).get("多选题", 0))
    st.info("请在左侧输入用户名，并设置题型、模块和题目数量，然后点击“开始答题”。")
    st.stop()

exam_questions = st.session_state.exam_questions
st.subheader(f"本次试卷：{len(exam_questions)} 题")
st.caption(f"考生：{st.session_state.get('username', '未填写')}")
if st.session_state.get("start_time"):
    st.caption(f"开始时间：{st.session_state.start_time}")

if st.session_state.get("submitted"):
    user_score = st.session_state.user_score
    total_score = st.session_state.total_score

    st.success(f"提交完成：{st.session_state.get('username', '未填写')}")

    # 考生端只展示最终分数，不展示正确答案、答题明细或错题回顾。
  #  score_col, total_col = st.columns(2)
  #  score_col.metric("得分", f"{user_score:.1f}")
  #  total_col.metric("满分", f"{total_score:.1f}")

    if st.session_state.get("encrypted_result_bytes"):
        st.download_button(
            "下载加密成绩 CSV（ZIP，需管理员密码解压）",
            data=st.session_state.encrypted_result_bytes,
            file_name=st.session_state.encrypted_result_filename,
            mime="application/zip",
            use_container_width=True,
        )

    if st.button("重新开始一次考试", use_container_width=True):
        reset_exam()
        st.rerun()
    st.stop()

answers = {}
with st.form("exam_form"):
    for idx, q in enumerate(exam_questions, start=1):
        st.markdown(f"### {idx}. [{q['type']}｜{q['score']}分] {q['question']}")
        options = q["options"]
        option_labels = [f"{k}. {v}" for k, v in options.items()]
        label_to_key = {f"{k}. {v}": k for k, v in options.items()}

        if q["type"] == "多选题":
            selected = st.multiselect("请选择一个或多个选项", option_labels, key=f"q_{q['id']}")
            answers[str(q["id"])] = [label_to_key[x] for x in selected]
        else:
            selected = st.radio("请选择一个选项", ["未作答"] + option_labels, key=f"q_{q['id']}")
            answers[str(q["id"])] = [] if selected == "未作答" else [label_to_key[selected]]
        st.divider()

    submitted = st.form_submit_button("提交试卷并生成加密成绩 CSV", use_container_width=True)

if submitted:
    if not st.session_state.get("username"):
        st.error("用户名缺失，请重置后重新输入用户名。")
        st.stop()

    st.session_state.submit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_score, total_score, rows = grade(exam_questions, answers)
    right_count, wrong_count, unanswered_count, accuracy = get_exam_statistics(rows)

    csv_bytes = build_result_dataframe(
        username=st.session_state.username,
        user_score=user_score,
        total_score=total_score,
        accuracy=accuracy,
        right_count=right_count,
        wrong_count=wrong_count,
        unanswered_count=unanswered_count,
        rows=rows,
    )
    encrypted_bytes, encrypted_filename = create_encrypted_csv_zip(
        csv_bytes=csv_bytes,
        username=st.session_state.username,
        password=ADMIN_EXPORT_PASSWORD,
    )

    st.session_state.submitted = True
    st.session_state.user_score = user_score
    st.session_state.total_score = total_score
    st.session_state.result_rows = rows
    st.session_state.encrypted_result_bytes = encrypted_bytes
    st.session_state.encrypted_result_filename = encrypted_filename
    st.rerun()
