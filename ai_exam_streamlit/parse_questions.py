"""Parse the Word question bank into questions.json.
Usage: python parse_questions.py --input 人工智能训练师选拔考试.docx --output questions.json
"""
import argparse, json, re
from pathlib import Path
from docx import Document

TYPE_PATTERNS = {
    "单选题": re.compile(r"^一、单选题"),
    "判断题": re.compile(r"^二、判断题"),
    "多选题": re.compile(r"^三、多选题"),
}
SECTION_RE = re.compile(r"^（[^）]+）(.+?)（\d+题）")
OPT_RE = re.compile(r"^([A-Z])\.\s*(.+)")
ANS_RE = re.compile(r"^答案[:：]\s*(.+)")


def read_lines(docx_path: str):
    doc = Document(docx_path)
    lines = []
    for p in doc.paragraphs:
        for line in p.text.splitlines():
            line = line.strip()
            if line:
                lines.append(line)
    return lines


def normalize_answer(answer_text: str, qtype: str):
    answer_text = answer_text.strip()
    if qtype == "判断题":
        return [answer_text]
    return answer_text.replace("，", " ").replace(",", " ").split()


def parse_docx(docx_path: str):
    lines = read_lines(docx_path)
    questions, qid = [], 0
    current_type, current_section = None, "未分类"
    cur = None

    for line in lines:
        for t, pat in TYPE_PATTERNS.items():
            if pat.match(line):
                current_type = t
                cur = None
                break
        else:
            sec = SECTION_RE.match(line)
            if sec:
                current_section = sec.group(1).strip()
                cur = None
                continue

            ans = ANS_RE.match(line)
            if ans and cur:
                cur["answer"] = normalize_answer(ans.group(1), cur["type"])
                questions.append(cur)
                cur = None
                continue

            opt = OPT_RE.match(line)
            if opt and cur:
                cur["options"][opt.group(1)] = opt.group(2).strip()
                continue

            if current_type and not line.startswith(("一、", "二、", "三、")):
                # A non-heading, non-option, non-answer line is a new question stem.
                qid += 1
                cur = {
                    "id": qid,
                    "type": current_type,
                    "section": current_section,
                    "question": line,
                    "options": {"对": "对", "错": "错"} if current_type == "判断题" else {},
                    "answer": [],
                }
    return questions


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="questions.json")
    args = parser.parse_args()
    qs = parse_docx(args.input)
    Path(args.output).write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed {len(qs)} questions -> {args.output}")
