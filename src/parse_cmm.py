# -*- coding: utf-8 -*-
"""
CMM(3차원 측정기) 리포트 파서
- pc-dmis 등에서 출력된 측정 리포트(텍스트/PDF)를 깨끗한 테이블(행 단위)로 변환한다.
- 공백이 살아있는 형식과, 복사하며 공백이 사라진 형식(예: DIMLOC1=LOCATIONOFPLANE...) 둘 다 처리.

각 측정 항목(특성)을 1행으로 정리:
  report_id, part_name, meas_date, block, section, dim_id, char_type,
  feature, axis, nominal, tol_plus, tol_minus, meas, dev, outtol,
  judge(OK/NG), direction, tol_used_pct(공차 소진율)
"""
import re
import os

NUM = re.compile(r"-?\d+\.\d+")          # 부호 포함 소수 (예: -418.500)
PAGE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")   # 페이지 마커  N / M
CHAR_TYPES = [
    ("POSITION", "위치도"),
    ("LOCATION", "위치"),
    ("PERPENDICULARITY", "직각도"),
    ("FLATNESS", "평면도"),
    ("CIRCULARITY", "진원도"),
    ("CYLINDRICITY", "원통도"),
    ("PARALLELISM", "평행도"),
    ("CONCENTRICITY", "동심도"),
    ("ANGULARITY", "경사도"),
    ("PROFILE", "윤곽도"),
]
AXES = ("X", "Y", "Z", "M", "TP", "DF", "DA")


def _detect_char_type(line_nospace):
    for key, ko in CHAR_TYPES:
        if key in line_nospace:
            return key, ko
    return "OTHER", "기타"


def _clean_feature(text):
    # 특성명 추출: 키워드(OF) 뒤 ~ UNITS= 앞
    t = text
    for tok in ["UNITS=", "USEAXIS=", "REFLENGTH=", "EXTENDLENGTH=",
                "PerUnitLength=", "PerUnitWidth=", "PERUNITLENGTH="]:
        idx = t.upper().find(tok.upper())
        if idx != -1:
            t = t[:idx]
    m = re.search(r"\bOF\b", t)
    if m:
        t = t[m.end():]
    # 'OF' 가 공백없이 붙어있는 케이스(...PLANEPLN_...) 처리: 첫 OF 이후
    if "OF" in t and m is None:
        t = t.split("OF", 1)[-1]
    return t.strip(" _-=")


def _parse_dim_header(line):
    """DIM/FCF 정의 줄 → (dim_id, char_type_en, char_type_ko, feature)"""
    nospace = line.replace(" ", "")
    # dim_id: DIM 또는 FCF 뒤, '=' 앞
    m = re.search(r"(?:DIM|FCF)\s*([A-Z]+[0-9]+)\s*=", line)
    if not m:
        m = re.search(r"(?:DIM|FCF)([A-Z]+[0-9]+)=", nospace)
    dim_id = m.group(1) if m else ""
    ct_en, ct_ko = _detect_char_type(nospace)
    feat = _clean_feature(line)
    return dim_id, ct_en, ct_ko, feat


def parse_text(text, report_id="report", part_name="", meas_date=""):
    rows = []
    block = 1
    section = ""
    cur = None            # 현재 DIM 정의
    has_bonus = False     # 현재 헤더에 BONUS 컬럼 존재 여부(위치도)
    prev_was_sep = False  # 직전 줄이 ==== 구분선인지 → 다음 줄은 섹션명

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        s = line.strip()
        if not s:
            continue

        # 페이지 마커: 1/N 으로 리셋되면 새 측정블록으로 간주
        pm = PAGE.match(s)
        if pm:
            if pm.group(1) == "1":
                block += 1
            continue

        # 구분선
        if set(s) <= set("=-") and len(s) >= 10:
            prev_was_sep = True
            continue

        # 구분선 바로 다음 줄 = 섹션 제목 (단, DIM/FCF/AX/데이터 줄이면 닫는 구분선이므로 제외)
        if prev_was_sep:
            prev_was_sep = False
            looks_like_item = (s.startswith("DIM") or s.startswith("FCF")
                               or s.startswith("AX") or "=" in s)
            if not looks_like_item:
                section = s.strip("=- ")
                continue
            # else: 닫는 구분선 뒤의 항목 줄 → 아래 정상 로직으로 진행

        # 섹션 보조 헤더 (밀링 영역명에 ---- 가 붙은 경우)
        if ("MILL'G" in s or "GALLARY" in s or "GALLERY" in s) and "DIM" not in s and "=" not in s:
            section = s.strip("=- ")
            continue

        # DIM / FCF 정의 줄
        if (s.startswith("DIM") or s.startswith("FCF")) and "=" in s:
            dim_id, ct_en, ct_ko, feat = _parse_dim_header(s)
            cur = dict(dim_id=dim_id, char_type_en=ct_en, char_type_ko=ct_ko,
                       feature=feat)
            continue

        # 컬럼 헤더 줄
        if s.startswith("AX") and "NOMINAL" in s.replace(" ", "").upper():
            has_bonus = "BONUS" in s.upper()
            continue

        # 데이터 줄: 축 라벨로 시작
        tok = s.split()[0] if s.split() else ""
        axis = None
        for a in AXES:
            if tok == a or (len(tok) > len(a) and tok[:len(a)] == a and (tok[len(a)] in "-0123456789.")):
                axis = a
                break
        if axis is None:
            continue
        if cur is None:
            continue

        nums = [float(x) for x in NUM.findall(s)]
        judged = any(c in s for c in "#<>")

        if not judged:
            # 위치도 성분행(X/Y/Z: NOMINAL MEAS DEV) → 참고용, 판정 제외
            continue
        if len(nums) < 3:
            continue

        outtol = nums[-1]
        dev = nums[-2]
        meas = nums[-3]

        if axis == "TP":
            # 위치도 판정행: NOMINAL=RFS, nums[0]=공차존(지름), 한쪽공차
            tol_plus = nums[0] if len(nums) >= 4 else None
            tol_minus = 0.0
            nominal = None
        elif axis == "DF":
            nominal = nums[0]
            tol_plus = nums[1] if len(nums) >= 6 else None
            tol_minus = nums[2] if len(nums) >= 6 else None
        else:
            # 전형적 6값 행: NOMINAL +TOL -TOL MEAS DEV OUTTOL
            nominal = nums[0]
            tol_plus = nums[1] if len(nums) >= 6 else None
            tol_minus = nums[2] if len(nums) >= 6 else None

        # 판정 / 방향
        judge = "NG" if (outtol and abs(outtol) > 1e-9) else "OK"
        if "<" in s:
            direction = "LOW"      # 하한 초과(작게 가공)
        elif ">" in s:
            direction = "HIGH"     # 상한 초과(크게 가공)
        else:
            direction = "IN"

        # 공차 소진율(%): dev가 가까운 쪽 공차 대비 얼마나 찼는가
        tol_used = None
        if dev is not None:
            if dev >= 0 and tol_plus:
                tol_used = abs(dev) / abs(tol_plus)
            elif dev < 0 and tol_minus:
                tol_used = abs(dev) / abs(tol_minus)
            elif tol_plus:
                tol_used = abs(dev) / abs(tol_plus)

        rows.append(dict(
            report_id=report_id, part_name=part_name, meas_date=meas_date,
            block=block, section=section,
            dim_id=cur["dim_id"], char_type=cur["char_type_ko"],
            char_type_en=cur["char_type_en"], feature=cur["feature"],
            axis=axis, nominal=nominal, tol_plus=tol_plus, tol_minus=tol_minus,
            meas=meas, dev=dev, outtol=outtol, judge=judge, direction=direction,
            tol_used_pct=round(tol_used * 100, 1) if tol_used is not None else None,
        ))
    return rows


def parse_title(first_line, fallback_id="report"):
    """제목 줄에서 부품명/측정일 추출. 예: 'THETA_2.5_TLPDI_블록 3차원 측정데이터_260616'"""
    part = first_line.strip()
    date = ""
    m = re.search(r"_(\d{6})\b", first_line)
    if m:
        ymd = m.group(1)
        date = f"20{ymd[0:2]}-{ymd[2:4]}-{ymd[4:6]}"
        part = first_line[:m.start()].strip(" _")
    return part or fallback_id, date


def parse_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    first = text.splitlines()[0] if text.splitlines() else ""
    part, date = parse_title(first, os.path.basename(path))
    rid = os.path.splitext(os.path.basename(path))[0]
    return parse_text(text, report_id=rid, part_name=part, meas_date=date)


if __name__ == "__main__":
    import sys, json
    rows = parse_file(sys.argv[1] if len(sys.argv) > 1 else "3d")
    print(f"총 {len(rows)}개 측정항목 파싱")
    ng = [r for r in rows if r["judge"] == "NG"]
    print(f"불합격(NG): {len(ng)}개")
    for r in rows[:5]:
        print(json.dumps(r, ensure_ascii=False))
