# -*- coding: utf-8 -*-
"""
3차원 측정데이터 AI 대시보드 (웹)

실행:
  python app.py
  → 브라우저에서 http://127.0.0.1:5000 열기

기능:
  - PDF / 텍스트 측정 리포트 드래그&드롭 업로드
  - 가운데: 정제된 측정 데이터 표 + 엑셀 다운로드
  - 오른쪽: 추세선·불합격 Pareto·공차소진 분포·편향 분석 + AI 코멘트
  - AI: 사내 H-chat API(또는 OpenAI/Claude) 연동 (src/llm.py, 환경변수 설정)
"""
import os
import io
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from flask import Flask, request, jsonify, send_file, render_template

from parse_cmm import parse_text, parse_file, parse_title
from build_excel import build_excel
from web_analytics import analytics, table_records
import llm

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

# 마지막 분석 결과를 메모리에 보관(엑셀 다운로드/AI 컨텍스트용)
STATE = {"rows": [], "analytics": {}}


def _pdf_to_text(file_bytes):
    import pdfplumber
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(file_bytes); path = tf.name
    try:
        parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
    finally:
        os.unlink(path)


@app.route("/")
def index():
    return render_template("index.html", ai_ready=llm.is_configured())


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "파일이 없습니다."}), 400
    rows = []
    for f in files:
        raw = f.read()
        name = f.filename or "report"
        if name.lower().endswith(".pdf"):
            text = _pdf_to_text(raw)
        else:
            text = raw.decode("utf-8", errors="ignore")
        first = text.splitlines()[0] if text.splitlines() else name
        part, date = parse_title(first, os.path.splitext(name)[0])
        rows += parse_text(text, report_id=os.path.splitext(name)[0],
                           part_name=part, meas_date=date)
    if not rows:
        return jsonify({"error": "측정 항목을 인식하지 못했습니다. 양식을 확인하세요."}), 422

    a = analytics(rows)
    STATE["rows"] = rows
    STATE["analytics"] = a
    return jsonify({"table": table_records(rows), "analytics": a})


@app.route("/api/sample", methods=["POST"])
def api_sample():
    """레포의 기본 '3d' 파일로 데모."""
    path = os.path.join(os.path.dirname(__file__), "3d")
    if not os.path.exists(path):
        return jsonify({"error": "샘플 파일(3d)이 없습니다."}), 404
    rows = parse_file(path)
    a = analytics(rows)
    STATE["rows"] = rows; STATE["analytics"] = a
    return jsonify({"table": table_records(rows), "analytics": a})


@app.route("/api/excel")
def api_excel():
    if not STATE["rows"]:
        return jsonify({"error": "먼저 데이터를 분석하세요."}), 400
    tmp = os.path.join(tempfile.gettempdir(), "측정데이터_정리.xlsx")
    build_excel(STATE["rows"], tmp)
    return send_file(tmp, as_attachment=True, download_name="측정데이터_정리.xlsx")


@app.route("/api/ai", methods=["POST"])
def api_ai():
    msg = (request.json or {}).get("message", "").strip()
    if not msg:
        msg = "이 측정 결과를 종합 분석하고, 불합격/위험 항목의 우선순위와 추정 원인, 권장 조치를 알려줘."
    ctx = llm.build_context(STATE.get("analytics", {})) if STATE.get("analytics") else ""
    answer = llm.chat(msg, ctx)
    return jsonify({"answer": answer, "configured": llm.is_configured()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  대시보드 → http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
