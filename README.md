# 3차원 측정데이터 AI 분석

CMM(3차원 측정기, pc-dmis) 측정 리포트(텍스트/PDF)를 자동으로 **엑셀 정리 + 추세/이상/공정능력 분석 + AI 코멘트**로 바꾸는 도구.

## 방법 1. 웹 대시보드 (권장) — PDF 드롭 → 표·추세·AI 한 화면

```bash
pip install -r requirements.txt
python app.py
# 브라우저에서 http://127.0.0.1:5000 접속
```
윈도우는 **`대시보드_실행.bat` 더블클릭**이면 끝.

- 가운데: 정제된 측정 데이터 표(검색/필터/공차소진율 색상) + **엑셀 다운로드**
- 오른쪽: 추세선(보어 직경)·불합격 Pareto·공차소진 분포·공정 편향 + **AI 분석 패널**
- 외부 라이브러리 0개(차트는 순수 SVG) → 공장 오프라인망에서도 동작
- `샘플(3d)로 보기` 버튼으로 바로 데모

### AI(H-chat) 연동
서버 실행 전 환경변수만 설정하면 AI 패널이 살아납니다(사내 H-chat / OpenAI호환 / Claude 지원):
```cmd
set LLM_PROVIDER=custom
set LLM_API_URL=https://사내-hchat-주소/v1/chat/completions
set LLM_API_KEY=발급키
set LLM_MODEL=모델명
python app.py
```
> 측정 요약만 API로 전송하며, 원본 파일은 로컬에만 있습니다. 자세한 형식은 `src/llm.py`.

## 방법 2. 명령줄 일괄 처리 (리포트/차트 파일 생성)

```bash
python run.py            # 기본 '3d' 파일 분석
python run.py data/*.pdf # PDF 여러 장 한꺼번에
```
결과: `out/측정데이터_정리.xlsx`, `out/charts/00_대시보드.png`(+개별 차트, SPC 관리도)

## 무엇을 해주나
- 줄글 측정 리포트 → 항목별 표(엑셀 6개 시트: 전체/요약/불합격/위험관리/추세)
- 공정별 불합격 Pareto, 공차 소진율 분포, 편향(공구/셋업 신호), 보어 직경 추세, SPC 관리도, AI 종합분석

## 폴더 구조
```
app.py                 웹 대시보드 서버(Flask)
run.py                 명령줄 일괄 처리
대시보드_실행.bat       윈도우 원클릭 실행
templates/index.html   대시보드 화면
static/                style.css, app.js (순수 SVG 차트)
src/
  parse_cmm.py         리포트(텍스트/PDF) → 표 파서
  build_excel.py       엑셀 생성
  analyze.py           차트(PNG) 생성
  web_analytics.py     대시보드용 분석 JSON
  llm.py               AI(H-chat/OpenAI/Claude) 연동
```

자세한 배경·데이터 해설·고도화 로드맵은 **`분석_솔루션_제안.md`** 참고.
