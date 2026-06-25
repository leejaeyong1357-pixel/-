# -*- coding: utf-8 -*-
"""
3차원 측정데이터 분석 파이프라인 (원클릭 실행)

사용법:
  python3 run.py                 # 기본 '3d' 파일 분석
  python3 run.py data/*.pdf 3d   # 여러 리포트(텍스트/PDF) 한꺼번에 분석

동작:
  1) 입력(텍스트 또는 PDF) → 측정항목 테이블로 파싱
  2) out/측정데이터_정리.xlsx 생성 (안내/전체/요약/불합격/위험관리/추세)
  3) out/charts/*.png 분석 차트 생성
  4) 콘솔에 핵심 인사이트 출력
"""
import os
import sys
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from parse_cmm import parse_text, parse_title, parse_file  # noqa: E402
from build_excel import build_excel  # noqa: E402
import analyze  # noqa: E402


def pdf_to_text(path):
    """PDF 측정 리포트 → 텍스트. pdfplumber 사용."""
    import pdfplumber
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    return "\n".join(parts)


def load_rows(paths):
    rows = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        rid = os.path.splitext(os.path.basename(p))[0]
        if ext == ".pdf":
            text = pdf_to_text(p)
            part, date = parse_title(text.splitlines()[0] if text.splitlines() else rid, rid)
            rows += parse_text(text, report_id=rid, part_name=part, meas_date=date)
        else:
            rows += parse_file(p)
    return rows


def main():
    args = sys.argv[1:] or ["3d"]
    paths = []
    for a in args:
        paths += sorted(glob.glob(a)) or [a]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        print("입력 파일을 찾을 수 없습니다:", args); sys.exit(1)

    print("입력:", ", ".join(paths))
    rows = load_rows(paths)
    print(f"파싱 완료: {len(rows)}개 측정항목\n")

    os.makedirs("out", exist_ok=True)
    xlsx = build_excel(rows, "out/측정데이터_정리.xlsx")
    print("엑셀 저장:", xlsx)

    dash, spc, ins = analyze.run(rows)
    print("대시보드:", dash)
    if spc:
        print("SPC 관리도:", spc)
    print("\n=== 핵심 인사이트 ===")
    for i in ins:
        print(" -", i)


if __name__ == "__main__":
    main()
