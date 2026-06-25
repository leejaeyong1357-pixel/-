# 3차원 측정데이터 AI 분석

CMM(3차원 측정기, pc-dmis) 측정 리포트(텍스트/PDF)를 자동으로 **엑셀 정리 + 추세/이상/공정능력 분석**으로 바꾸는 도구.

## 빠른 시작
```bash
pip install -r requirements.txt
python3 run.py            # 기본 '3d' 파일 분석
python3 run.py data/*.pdf # PDF 여러 장 한꺼번에
```
결과: `out/측정데이터_정리.xlsx`, `out/charts/00_대시보드.png`

## 무엇을 해주나
- 줄글 측정 리포트 → 항목별 표(엑셀 6개 시트: 전체/요약/불합격/위험관리/추세)
- 공정별 불합격 Pareto, 공차 소진율 분포, 편향(공구/셋업 신호), 보어 직경 추세, SPC 관리도

자세한 배경·로드맵은 **`분석_솔루션_제안.md`** 참고.
