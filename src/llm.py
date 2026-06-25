# -*- coding: utf-8 -*-
"""
LLM(AI) 연동 — 사내 H-chat / OpenAI 호환 / Claude(Anthropic) 지원.
설정은 (1) 화면에서 입력(런타임) 또는 (2) 환경변수로 가능.

H-chat 예시:
  Base URL : https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/
  → 채팅 엔드포인트는 Base URL + 'chat/completions'
  인증 헤더 형식은 게이트웨이마다 다르므로(Authorization/x-api-key 등)
  연결 테스트 시 여러 후보를 자동으로 시도해 통하는 방식을 찾는다.
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

# 런타임 설정(화면 입력) — 비어있으면 환경변수 사용
CONFIG = {"provider": "", "base_url": "", "endpoint": "", "api_key": "", "model": "", "auth_header": ""}

# 인증 헤더 후보(게이트웨이마다 다름). 연결 테스트가 차례로 시도.
AUTH_SCHEMES = [
    ("Authorization", "Bearer {k}"),
    ("x-api-key", "{k}"),
    ("api-key", "{k}"),
    ("apikey", "{k}"),
    ("X-API-KEY", "{k}"),
    ("Authorization", "{k}"),
]
_WORKING = {"scheme": None}   # 성공한 인증 방식 기억


def _cfg(key, env, default=""):
    return CONFIG.get(key) or os.environ.get(env, default)


def set_config(d):
    for k in CONFIG:
        if k in d and d[k] is not None:
            CONFIG[k] = str(d[k]).strip()
    _WORKING["scheme"] = None   # 설정 바뀌면 인증 재탐지
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


def _is_anthropic():
    return _cfg("provider", "LLM_PROVIDER", "custom").lower() == "anthropic"


def _payload(messages):
    model = _cfg("model", "LLM_MODEL", "gpt-4o")
    if _is_anthropic():
        sysmsg = next((m["content"] for m in messages if m["role"] == "system"), "")
        usr = [m for m in messages if m["role"] != "system"]
        return {"model": model, "max_tokens": 1200, "system": sysmsg, "messages": usr}
    return {"model": model, "temperature": 0.3, "messages": messages}


def _extract(data):
    if _is_anthropic():
        return data["content"][0]["text"]
    return data["choices"][0]["message"]["content"]


def _schemes():
    """수동 지정(auth_header)>기억된 성공방식>후보 전체 순."""
    if _is_anthropic():
        return [("x-api-key", "{k}")]
    manual = _cfg("auth_header", "LLM_AUTH_HEADER")
    if manual:
        if ":" in manual:
            name, val = manual.split(":", 1)
            val = val.strip()
            return [(name.strip(), val if "{k}" in val else val + " {k}")]
        return [(manual.strip(), "{k}")]
    if _WORKING["scheme"]:
        return [_WORKING["scheme"]]
    return AUTH_SCHEMES


def _call(messages, timeout=60):
    """통하는 인증 방식을 찾아 호출 → (텍스트, scheme). 실패 시 RuntimeError."""
    key = _cfg("api_key", "LLM_API_KEY")
    url = _resolve_url()
    payload = _payload(messages)
    extra = {"anthropic-version": "2023-06-01"} if _is_anthropic() else {}
    last = None
    for sch in _schemes():
        name, tmpl = sch
        headers = {name: tmpl.format(k=key), **extra}
        try:
            _, data = _post(url, headers, payload, timeout=timeout)
            _WORKING["scheme"] = sch
            return _extract(data), sch
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            last = (e.code, body)
            if e.code not in (401, 403):   # 인증 외 오류면 헤더 더 바꿔도 무의미
                raise RuntimeError(f"HTTP {e.code} — {body}")
        except Exception as e:
            last = (None, f"{type(e).__name__}: {e}")
    code, body = last if last else (None, "원인 미상")
    raise RuntimeError(f"인증 실패(HTTP {code}). 시도한 인증헤더가 모두 거부됨. 마지막 응답: {body}")


def chat(user_msg, context_text=""):
    if not is_configured():
        return ("⚠️ AI가 아직 연결되지 않았습니다. 우측 'AI 설정'에 Base URL · API Key · 모델명을 입력하고 "
                "[연결 테스트]를 눌러 주세요.")
    full = (f"[측정 분석 컨텍스트]\n{context_text}\n\n[질문/요청]\n{user_msg}"
            if context_text else user_msg)
    messages = [{"role": "system", "content": SYS_PROMPT},
                {"role": "user", "content": full}]
    try:
        text, _ = _call(messages)
        return text
    except Exception as e:
        return f"⚠️ AI 호출 실패: {e}\n(URL: {_resolve_url()})"


def test():
    """여러 인증 방식을 자동 시도 → {ok, detail}."""
    if not is_configured():
        return {"ok": False, "detail": "Base URL 또는 API Key가 비어 있습니다."}
    messages = [{"role": "system", "content": "한국어로 한 단어만 답하세요."},
                {"role": "user", "content": "연결확인. '정상'이라고만 답해."}]
    try:
        ans, sch = _call(messages, timeout=30)
        return {"ok": True, "detail": f"연결 성공 (인증헤더: {sch[0]}) · 응답: {ans[:30]}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


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
