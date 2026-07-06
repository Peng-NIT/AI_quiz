# 人工智能训练师选拔考试 · Streamlit 交互答题系统

## 功能

- 从 `questions.json` 加载 Word 题库解析结果
- 支持单选题、多选题、判断题
- 支持按题型、知识模块、题目数量随机组卷
- 支持“用户名 / 姓名”输入
- 点击提交按钮后自动判分
- 考生端提交后只显示最终分数，不显示正确答案、答题明细或错题回顾
- 点击提交按钮后生成加密成绩文件
- 加密文件中包含 CSV 格式的考试概要和答题明细，供管理员使用密码解压后查看

## 重要说明

CSV 文件本身不支持原生密码保护。因此，本系统采用更通用的方式：

```text
提交试卷 → 生成 CSV 成绩内容 → 放入 AES 加密 ZIP 包 → 管理员用预设密码解压查看 CSV
```

生成的文件名类似：

```text
exam_result_张三_20260706_113000_encrypted.zip
```

解压后可以得到真正的 CSV 文件。

## 管理员密码配置

打开 `app.py`，修改顶部配置：

```python
ADMIN_EXPORT_PASSWORD = "Admin@123456"
```

部署前建议修改为强密码，例如包含大小写字母、数字和特殊符号。

## 运行方式

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 文件说明

```text
app.py              # Streamlit 主程序，包含页面、答题、判分和加密成绩文件生成逻辑
questions.json      # 从 Word 题库解析得到的结构化题库
parse_questions.py  # Word 题库解析脚本
requirements.txt    # Python 依赖
exam_results/       # 自动生成的加密成绩文件保存目录，运行后出现
```

## 重新解析 Word 题库

```bash
python parse_questions.py --input 人工智能训练师选拔考试.docx --output questions.json
```

如果 Word 文件不在当前目录，请把 `--input` 后面的路径改为实际路径。
