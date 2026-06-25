# -*- coding: utf-8 -*-
"""
LLM(AI) 연동 — 사내 H-chat / OpenAI 호환 / Claude(Anthropic) 지원.
설정은 (1) 화면에서 입력(런타임) 또는 (2) 환경변수로 가능.

H-chat 예시 (사진의 값):
  Base URL : https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/
  → 채팅 엔드포인트는 보통 Base URL + 'chat/completions'
  API Key  : 발급받은 개인 키
  Model    : 사내 모델명
"""
import os
import json
import urllib.request
import urllib.error

SYS_PROMPT = (
    "당신은 자동차 부품 가공 라인의 품질·계측 전문가입니다. "
    "3차원 측정기(CMM) 데이터 분석 결과를 받아, 품질팀장과 경영진이 바로 쓸 수 있게 "
    "한국어로 간결하고 실행가능하게 설명합니다. "
    "불합격/위험 항목의 우선순위, 추정 원인(공구 마모·셋업 오프셋·고정 픽스처 등), "
    "권장 조치(보정/교체/추가점검), 추세상 주의점을 bullet로 제시하세요. "
    "데이터에 없는 수치는 지어내지 마세요."
)

# 런타임 설정(화면에서 입력) — 비어있으면 환경변수 사용
CONFIG = {"provider": "", "base_url": "", "endpoint": "", "api_key": "", "model": "", "auth_header": ""}


def _cfg(key, env, default=""):
    return CONFIG.get(key) or os.environ.get(env, default)


def set_config(d):
    for k in CONFIG:
        if k in d and d[k] is not None:
            CONFIG[k] = str(d[k]).strip()
    return status()


def is_configured():
    return bool(_resolve_url() and _cfg("api_key", "LLM_API_KEY"))


def status():
    key = _cfg("api_key", "LLM_API_KEY")
    return {
        "configured": is_configured(),
        "provider": _cfg("provider", "LLM_PROVIDER", "custom"),
        "url": _resolve_url(),
        "model": _cfg("model", "LLM_MODEL", "gpt-4o"),
        "key_masked": (key[:4] + "…" + key[-4:]) if len(key) > 8 else ("설정됨" if key else ""),
    }


def _resolve_url():
    """endpoint가 절대 URL이면 그대로, 아니면 base_url + 'chat/completions'."""
    ep = _cfg("endpoint", "LLM_API_URL")
    base = _cfg("base_url", "LLM_BASE_URL")
    if ep and ep.startswith("http"):
        return ep
    if base:
        b = base if base.endswith("/") else base + "/"
        return b + (ep or "chat/completions")
    return ""


def _post(url, headers, payload, timeout=60):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _payload_and_headers(messages):
    provider = _cfg("provider", "LLM_PROVIDER", "custom").lower()
    key = _cfg("api_key", "LLM_API_KEY")
    model = _cfg("model", "LLM_MODEL", "gpt-4o")
    if provider == "anthropic":
        sys = next((m["content"] for m in messages if m["role"] == "system"), "")
        usr = [m for m in messages if m["role"] != "system"]
        return ({"x-api-key": key, "anthropic-version": "2023-06-01"},
                {"model": model, "max_tokens": 1200, "system": sys, "messages": usr},
                "anthropic")
    auth = _cfg("auth_header", "LLM_AUTH_HEADER") or "Bearer"
    return ({"Authorization": f"{auth} {key}"},
            {"model": model, "temperature": 0.3, "messages": messages},
            "openai")


def _extract(kind, data):
    if kind == "anthropic":
        return data["content"][0]["text"]
    return data["choices"][0]["message"]["content"]


def chat(user_msg, context_text=""):
    if not is_configured():
        return ("⚠️ AI가 아직 연결되지 않았습니다. 우측 'AI 설정'에 Base URL · API Key · 모델명을 입력하고 "
                "[연결 테스트]를 눌러 주세요.")
    full = (f"[측정 분석 컨텍스트]\n{context_text}\n\n[질문/요청]\n{user_msg}"
            if context_text else user_msg)
    messages = [{"role": "system", "content": SYS_PROMPT},
                {"role": "user", "content": full}]
    headers, payload, kind = _payload_and_headers(messages)
    try:
        _, data = _post(_resolve_url(), headers, payload)
        return _extract(kind, data)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        return f"⚠️ AI 호출 실패 (HTTP {e.code}). 엔드포인트/키/모델을 확인하세요.\n응답: {body}"
    except Exception as e:
        return f"⚠️ AI 호출 실패: {e}\n(URL: {_resolve_url()})"


def test():
    """최소 요청으로 연결 확인 → {ok, detail}."""
    if not is_configured():
        return {"ok": False, "detail": "Base URL 또는 API Key가 비어 있습니다."}
    messages = [{"role": "system", "content": "한국어로 한 단어만 답하세요."},
                {"role": "user", "content": "연결확인. '정상'이라고만 답해."}]
    headers, payload, kind = _payload_and_headers(messages)
    payload = {**payload}
    try:
        st, data = _post(_resolve_url(), headers, payload, timeout=30)
        ans = _extract(kind, data)
        return {"ok": True, "detail": f"연결 성공 · 모델 응답: {ans[:40]}"}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:400]
        return {"ok": False, "detail": f"HTTP {e.code} — {body}"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}


def build_context(analytics_result):
    k = analytics_result.get("kpi", {})
    lines = [f"부품: {k.get('part','')} / 측정일: {k.get('date','')}",
             f"총 {k.get('total')}개 항목, 불합격 {k.get('ng')}개({k.get('ng_rate')}%), 위험(예비불량) {k.get('risk')}개"]
    p = analytics_result.get("pareto", {})
    if p.get("labels"):
        pairs = list(zip(p["labels"], p["counts"]))[:8]
        lines.append("불합격 집중 공정: " + ", ".join(f"{l}={c}건" for l, c in pairs))
    for r in analytics_result.get("ng_rows", [])[:15]:
        lines.append(f"- NG: {r.get('section')} {r.get('dim_id')} {r.get('feature')} "
                     f"축{r.get('axis')} 편차{r.get('dev')} 초과{r.get('outtol')} 방향{r.get('direction')}")
    return "\n".join(lines)
