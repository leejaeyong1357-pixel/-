# -*- coding: utf-8 -*-
"""측정데이터 분석 + 시각화.
산출:
  out/charts/01_불합격_파레토.png   - 공정별 불합격 Pareto
  out/charts/02_공차소진_분포.png   - 공차 소진율 분포(위험 구간)
  out/charts/03_편향_섹션별.png     - 공정별 평균 편차(체계적 쏠림 = 공구/셋업 신호)
  out/charts/04_추세_실린더보어.png - 실린더 보어 직경 편차 회차별 추세
  out/charts/05_SPC관리도.png       - 반복 측정 항목 I-MR 관리도(예시)
  out/charts/00_대시보드.png        - 위 핵심을 한 장에 요약
콘솔: 핵심 인사이트 텍스트
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

NANUM = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"


def setup_font():
    if os.path.exists(NANUM):
        fm.fontManager.addfont(NANUM)
        name = fm.FontProperties(fname=NANUM).get_name()
    else:
        name = "WenQuanYi Zen Hei"
    plt.rcParams["font.family"] = name
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"


GREEN, AMBER, RED, BLUE = "#63BE7B", "#FFC000", "#E15759", "#1F4E78"


def pareto(ax, df):
    g = (df.assign(NG=(df.judge == "NG").astype(int)).groupby("section").NG.sum()
         .sort_values(ascending=False))
    g = g[g > 0]
    if g.empty:
        ax.text(0.5, 0.5, "불합격 없음", ha="center"); return
    cum = g.cumsum() / g.sum() * 100
    x = range(len(g))
    ax.bar(x, g.values, color=RED, alpha=0.85)
    ax.set_xticks(list(x)); ax.set_xticklabels(g.index, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("불합격 건수")
    ax.set_title("① 공정별 불합격 Pareto — 어디부터 잡아야 하는가", fontsize=12, fontweight="bold")
    ax2 = ax.twinx()
    ax2.plot(x, cum.values, color=BLUE, marker="o", lw=2)
    ax2.axhline(80, color="gray", ls="--", lw=1)
    ax2.set_ylim(0, 105); ax2.set_ylabel("누적 %")
    for i, v in enumerate(g.values):
        ax.text(i, v + 0.1, str(int(v)), ha="center", fontsize=8)


def dist(ax, df):
    ok = df[df.judge == "OK"].tol_used_pct.dropna()
    ng = df[df.judge == "NG"].tol_used_pct.dropna()
    bins = np.arange(0, 220, 10)
    ax.hist(ok, bins=bins, color=GREEN, alpha=0.8, label="합격")
    ax.hist(ng, bins=bins, color=RED, alpha=0.8, label="불합격")
    ax.axvspan(70, 100, color=AMBER, alpha=0.18)
    ax.axvline(100, color="black", ls="--", lw=1.2)
    ax.text(85, ax.get_ylim()[1]*0.9, "위험구간\n70~100%", ha="center", fontsize=8, color="#8a6d00")
    ax.set_xlabel("공차 소진율 (%)"); ax.set_ylabel("항목 수")
    ax.set_title("② 공차 소진율 분포 — 100% 넘으면 불합격", fontsize=12, fontweight="bold")
    ax.legend()


def bias(ax, df):
    # 섹션별 평균 편차(정규화: dev/tol) — 한 방향 쏠림은 공구/셋업 보정 신호
    d = df.dropna(subset=["dev", "tol_plus"]).copy()
    d["norm"] = d.apply(lambda r: r.dev / (r.tol_plus if r.dev >= 0 else abs(r.tol_minus) if r.tol_minus else r.tol_plus), axis=1)
    g = d.groupby("section").norm.mean().sort_values()
    g = pd.concat([g.head(6), g.tail(6)])
    colors = [RED if abs(v) > 0.5 else AMBER if abs(v) > 0.3 else GREEN for v in g.values]
    ax.barh(range(len(g)), g.values, color=colors)
    ax.set_yticks(range(len(g))); ax.set_yticklabels(g.index, fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("평균 정규화 편차 (─쪽으로 갈수록 작게 가공)")
    ax.set_title("③ 공정별 편향 — 한쪽 쏠림 = 공구/셋업 보정 대상", fontsize=12, fontweight="bold")


def trend_bore(ax, df):
    d = df[(df.feature.str.contains("CYL_BORE", na=False)) & (df.axis == "DF")].copy()
    if d.empty:
        ax.text(0.5, 0.5, "데이터 없음", ha="center"); return
    for blk, sub in d.groupby("block"):
        ax.scatter([blk]*len(sub), sub.dev, alpha=0.6, s=30, color=BLUE)
    m = d.groupby("block").dev.mean()
    ax.plot(m.index, m.values, color=RED, marker="s", lw=2, label="회차 평균")
    # 규격선(직경 +0.020 가정: 데이터의 tol_plus 사용)
    tol = d.tol_plus.dropna().median()
    if pd.notna(tol):
        ax.axhline(tol, color="black", ls="--", lw=1, label=f"상한 +{tol:.3f}")
    ax.set_xlabel("측정 회차(시간 →)"); ax.set_ylabel("직경 편차 (mm)")
    ax.set_title("④ 실린더 보어 직경 추세 — 초기 규격초과→보정", fontsize=12, fontweight="bold")
    ax.set_xticks(sorted(d.block.unique()))
    ax.legend(fontsize=8)


def make_dashboard(df, out_dir):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    pareto(axes[0, 0], df)
    dist(axes[0, 1], df)
    bias(axes[1, 0], df)
    trend_bore(axes[1, 1], df)
    fig.suptitle("3차원 측정데이터 AI 분석 대시보드", fontsize=16, fontweight="bold", color=BLUE)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    p = os.path.join(out_dir, "00_대시보드.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def make_individual(df, out_dir):
    for fn, name in [(pareto, "01_불합격_파레토"), (dist, "02_공차소진_분포"),
                     (bias, "03_편향_섹션별"), (trend_bore, "04_추세_실린더보어")]:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        fn(ax, df); fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"{name}.png"), dpi=120); plt.close(fig)


def spc_chart(df, out_dir):
    """반복 측정이 가장 많은 항목으로 I-MR 관리도 예시."""
    key = df.groupby(["feature", "axis"]).size().sort_values(ascending=False)
    key = key[key >= 3]
    if key.empty:
        return None
    feat, axis = key.index[0]
    d = df[(df.feature == feat) & (df.axis == axis)].sort_values("block")
    x = d.dev.values
    mr = np.abs(np.diff(x))
    cl = x.mean(); ucl = cl + 2.66 * mr.mean(); lcl = cl - 2.66 * mr.mean()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    a1.plot(range(len(x)), x, marker="o", color=BLUE)
    a1.axhline(cl, color="green"); a1.axhline(ucl, color="red", ls="--"); a1.axhline(lcl, color="red", ls="--")
    a1.set_ylabel("편차(개별값 I)")
    a1.set_title(f"⑤ SPC 관리도 예시 — {feat[:30]} ({axis})", fontsize=12, fontweight="bold")
    a2.plot(range(1, len(x)), mr, marker="o", color="#8a6d00")
    a2.axhline(mr.mean(), color="green"); a2.axhline(3.27*mr.mean(), color="red", ls="--")
    a2.set_ylabel("이동범위(MR)"); a2.set_xlabel("측정 순서")
    fig.tight_layout()
    p = os.path.join(out_dir, "05_SPC관리도.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def insights(df):
    out = []
    n = len(df); ng = int((df.judge == "NG").sum())
    out.append(f"총 {n}개 측정항목 중 불합격 {ng}개 (불합격률 {ng/n*100:.1f}%)")
    risk = df[(df.judge == "OK") & (df.tol_used_pct >= 70)]
    out.append(f"합격이지만 공차 70%+ 소진한 '예비 불량' {len(risk)}개 → 다음 차수 불량 위험")
    g = df.assign(NG=(df.judge == "NG").astype(int)).groupby("section").NG.sum().sort_values(ascending=False)
    top = g[g > 0].head(3)
    out.append("불합격 집중 공정 TOP3: " + ", ".join(f"{k}({int(v)})" for k, v in top.items()))
    # 체계적 편향
    d = df.dropna(subset=["dev", "tol_plus"]).copy()
    d["norm"] = d.apply(lambda r: r.dev/(r.tol_plus if r.dev >= 0 else abs(r.tol_minus) if r.tol_minus else r.tol_plus), axis=1)
    b = d.groupby("section").norm.mean().sort_values()
    out.append(f"가장 작게(-) 쏠린 공정: {b.index[0]} (평균 {b.iloc[0]*100:.0f}% 소진, 한 방향) → 공구/셋업 보정 후보")
    return out


def run(rows, out_dir="out/charts"):
    setup_font()
    os.makedirs(out_dir, exist_ok=True)
    df = pd.DataFrame(rows)
    dash = make_dashboard(df, out_dir)
    make_individual(df, out_dir)
    spc = spc_chart(df, out_dir)
    return dash, spc, insights(df)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from parse_cmm import parse_file
    rows = parse_file(sys.argv[1] if len(sys.argv) > 1 else "3d")
    dash, spc, ins = run(rows)
    print("대시보드:", dash); print("SPC:", spc)
    print("\n=== 핵심 인사이트 ===")
    for i in ins:
        print(" -", i)
