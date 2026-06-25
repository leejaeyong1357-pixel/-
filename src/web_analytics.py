# -*- coding: utf-8 -*-
"""웹 대시보드용 분석 데이터 생성 (Chart.js가 그릴 수 있는 JSON 구조로 반환)."""
import pandas as pd
import numpy as np


def _norm(r):
    if pd.isna(r["dev"]):
        return None
    if r["dev"] >= 0 and r["tol_plus"]:
        return r["dev"] / abs(r["tol_plus"])
    if r["dev"] < 0 and r["tol_minus"]:
        return r["dev"] / abs(r["tol_minus"])
    if r["tol_plus"]:
        return r["dev"] / abs(r["tol_plus"])
    return None


def analytics(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return {"kpi": {}, "pareto": {}, "dist": {}, "bias": {}, "trend": {}, "insights": []}

    n = len(df)
    ng = int((df["judge"] == "NG").sum())
    risk = int(((df["judge"] == "OK") & (df["tol_used_pct"] >= 70)).sum())

    kpi = {
        "total": n, "ng": ng, "ng_rate": round(ng / n * 100, 1),
        "risk": risk, "ok": n - ng,
        "sections": int(df["section"].nunique()),
        "part": df["part_name"].iloc[0] if "part_name" in df else "",
        "date": df["meas_date"].iloc[0] if "meas_date" in df else "",
    }

    # Pareto: 공정별 불합격
    g = (df.assign(NG=(df["judge"] == "NG").astype(int)).groupby("section")["NG"]
         .sum().sort_values(ascending=False))
    g = g[g > 0].head(12)
    cum = (g.cumsum() / g.sum() * 100).round(1) if g.sum() else g
    pareto = {"labels": list(g.index), "counts": [int(v) for v in g.values],
              "cum": [float(v) for v in cum.values]}

    # 분포: 공차 소진율 히스토그램(합격/불합격)
    bins = list(range(0, 210, 10))
    ok = df[df["judge"] == "OK"]["tol_used_pct"].dropna()
    ngv = df[df["judge"] == "NG"]["tol_used_pct"].dropna()
    ok_h = np.histogram(ok, bins=bins)[0].tolist()
    ng_h = np.histogram(ngv, bins=bins)[0].tolist()
    dist = {"labels": [f"{b}" for b in bins[:-1]], "ok": ok_h, "ng": ng_h}

    # 편향: 공정별 평균 정규화 편차(상·하위)
    d = df.dropna(subset=["dev", "tol_plus"]).copy()
    d["norm"] = d.apply(_norm, axis=1)
    b = d.groupby("section")["norm"].mean().dropna().sort_values()
    b = pd.concat([b.head(6), b.tail(6)])
    b = b[~b.index.duplicated()]
    bias = {"labels": list(b.index), "values": [round(float(v) * 100, 1) for v in b.values]}

    # 추세: 반복 측정이 가장 많은 항목 + 실린더 보어 직경
    trend = {}
    bore = df[(df["feature"].str.contains("CYL_BORE", na=False)) & (df["axis"] == "DF")]
    if not bore.empty:
        m = bore.groupby("block")["dev"].mean()
        pts = bore.groupby("block").apply(lambda s: list(zip(s["dev"], s["judge"])), include_groups=False)
        trend["bore"] = {
            "blocks": [int(x) for x in m.index],
            "mean": [round(float(v), 4) for v in m.values],
            "tol": float(bore["tol_plus"].dropna().median()) if bore["tol_plus"].notna().any() else None,
            "scatter": {int(k): [[round(float(dv), 4), j] for dv, j in v] for k, v in pts.items()},
        }
    # 가장 많이 반복된 일반 항목
    key = df.groupby(["feature", "axis"]).size().sort_values(ascending=False)
    key = key[key >= 3]
    if not key.empty:
        feat, axis = key.index[0]
        s = df[(df["feature"] == feat) & (df["axis"] == axis)].sort_values("block")
        trend["repeat"] = {"feature": feat, "axis": axis,
                           "dev": [round(float(v), 4) for v in s["dev"]],
                           "x": list(range(len(s)))}

    # 인사이트(문장)
    insights = []
    insights.append(f"총 {n}개 측정항목 중 불합격 {ng}개 (불합격률 {kpi['ng_rate']}%).")
    insights.append(f"합격이지만 공차 70% 이상 소진한 '예비 불량' {risk}개 → 다음 로트 불량 위험.")
    if len(pareto["labels"]):
        top = ", ".join(f"{l}({c})" for l, c in list(zip(pareto["labels"], pareto["counts"]))[:3])
        insights.append(f"불합격 집중 공정 TOP3: {top}.")
    if bias["labels"]:
        worst = bias["labels"][0]; wv = bias["values"][0]
        insights.append(f"가장 한쪽으로 쏠린 공정: {worst} (평균 {wv:.0f}%) → 공구/셋업 보정 후보.")

    # 불합격 상세 테이블(상위)
    ng_rows = (df[df["judge"] == "NG"]
               .sort_values("outtol", ascending=False)
               [["section", "dim_id", "char_type", "feature", "axis",
                 "nominal", "meas", "dev", "outtol", "tol_used_pct", "direction"]]
               .head(50).fillna("").to_dict("records"))

    return {"kpi": kpi, "pareto": pareto, "dist": dist, "bias": bias,
            "trend": trend, "insights": insights, "ng_rows": ng_rows}


def table_records(rows):
    """가운데 표에 뿌릴 전체 레코드(한글 헤더)."""
    df = pd.DataFrame(rows)
    cols = ["section", "dim_id", "char_type", "feature", "axis", "nominal",
            "tol_plus", "tol_minus", "meas", "dev", "outtol", "tol_used_pct", "judge", "direction"]
    df = df[[c for c in cols if c in df.columns]].fillna("")
    return df.to_dict("records")
