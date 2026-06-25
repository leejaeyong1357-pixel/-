# -*- coding: utf-8 -*-
"""
LLM(AI) 연동 모듈 — 사내 H-chat API / OpenAI 호환 / Claude(Anthropic) 모두 지원.

환경변수로 설정 (없으면 AI 기능은 '미설정' 안내만 반환):
  LLM_PROVIDER   = custom | openai | anthropic   (기본 custom)
  LLM_API_URL    = 채팅 엔드포인트 URL
                   - custom/openai: .../v1/chat/completions
                   - anthropic    : https://api.anthropic.com/v1/messages
  LLM_API_KEY    = API 키
  LLM_MODEL      = 모델명 (예: 사내모델명 / gpt-4o / claude-sonnet-4-6)
  LLM_AUTH_HEADER= 인증 헤더 형식 (기본 'Bearer')  예) 'Bearer' 면 'Authorization: Bearer <KEY>'

➜ 사내 H-chat 연동 시: LLM_PROVIDER=custom 으로 두고 URL/KEY/MODEL 만 맞추면 됩니다.
  (대부분의 사내 게이트웨이가 OpenAI 호환 형식이라 그대로 동작)
"""
import os
import json
import urllib.request

SYS_PROMPT = (
    "당신은 자동차 부품 가공 라인의 품질·계측 전문가입니다. "
    "3차원 측정기(CMM) 데이터 분석 결과를 받아, 품질팀장과 경영진이 바로 쓸 수 있게 "
    "한국어로 간결하고 실행가능하게 설명합니다. "
    "불합격/위험 항목의 우선순위, 추정 원인(공구 마모·셋업 오프셋·고정 픽스처 등), "
    "권장 조치(보정/교체/추가점검), 추세상 주의점을 bullet로 제시하세요. "
    "데이터에 없는 수치는 지어내지 마세요."
)


def is_configured():
    return bool(os.environ.get("LLM_API_URL") and os.environ.get("LLM_API_KEY"))


def _post(url, headers, payload, timeout=60):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat(user_msg, context_text=""):
    """user_msg + 분석 컨텍스트 → AI 답변 텍스트."""
    if not is_configured():
        return ("⚠️ AI가 아직 연결되지 않았습니다. 서버 실행 전 환경변수를 설정하세요:\n"
                "  set LLM_API_URL=<사내 H-chat 엔드포인트>\n"
                "  set LLM_API_KEY=<발급키>\n"
                "  set LLM_MODEL=<모델명>\n"
                "그러면 이 패널에서 측정데이터에 대한 AI 분석/질의응답이 동작합니다.")

    provider = os.environ.get("LLM_PROVIDER", "custom").lower()
    url = os.environ["LLM_API_URL"]
    key = os.environ["LLM_API_KEY"]
    model = os.environ.get("LLM_MODEL", "gpt-4o")
    auth = os.environ.get("LLM_AUTH_HEADER", "Bearer")
    full_user = (f"[측정 분석 컨텍스트]\n{context_text}\n\n[질문/요청]\n{user_msg}"
                 if context_text else user_msg)

    try:
        if provider == "anthropic":
            data = _post(url, {"x-api-key": key, "anthropic-version": "2023-06-01"}, {
                "model": model, "max_tokens": 1200, "system": SYS_PROMPT,
                "messages": [{"role": "user", "content": full_user}],
            })
            return data["content"][0]["text"]
        else:  # custom / openai (OpenAI 호환)
            headers = {"Authorization": f"{auth} {key}"}
            data = _post(url, headers, {
                "model": model, "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": SYS_PROMPT},
                    {"role": "user", "content": full_user},
                ],
            })
            return data["choices"][0]["message"]["content"]
    except Exception as e:  # 네트워크/형식 오류 시 친절히 안내
        return f"⚠️ AI 호출 실패: {e}\n(엔드포인트/키/모델/헤더 형식을 확인하세요. LLM_PROVIDER={provider})"


def build_context(analytics_result):
    """분석 결과 dict → AI에게 줄 요약 컨텍스트 문자열."""
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
