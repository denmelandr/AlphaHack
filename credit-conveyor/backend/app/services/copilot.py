"""Копилот андеррайтера.

Готовит саммари заявки, список аномалий и черновик обоснования решения для
аудита. Аномалии считаются детерминированно (правила) и потому надёжны. Текст
саммари и обоснования по умолчанию собирается из шаблонов; при включённом LLM
(модель с открытыми весами через Ollama) тексты генерирует модель, а при любой
ошибке копилот откатывается к шаблону. ИИ не принимает решение — он ускоряет
работу андеррайтера (кейс: «ИИ только там, где создаёт ценность»)."""

import httpx

from app.core.config import settings


def _fmt(n) -> str:
    try:
        return f"{float(n):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def build_anomalies(app, profile: dict, company_annual_revenue: float) -> list[str]:
    a: list[str] = []
    ofd_year = (profile.get("avg_monthly_revenue") or 0) * 12
    if company_annual_revenue and ofd_year:
        diff = abs(company_annual_revenue - ofd_year) / company_annual_revenue
        if diff > 0.3:
            a.append(
                f"Расхождение выручки: в профиле компании {_fmt(company_annual_revenue)} ₽/год, "
                f"по ОФД ~{_fmt(ofd_year)} ₽/год (разница {int(diff*100)}%)."
            )
    if (profile.get("overdue_count") or 0) > 0:
        a.append(
            f"Есть просрочки: {profile.get('overdue_count')} шт., "
            f"до {profile.get('max_overdue_days')} дней."
        )
    if (profile.get("debt_load_percent") or 0) >= 50:
        a.append(f"Высокая долговая нагрузка: {profile.get('debt_load_percent')}%.")
    if profile.get("account_blocked"):
        a.append("Расчётный счёт заблокирован по данным ФНС.")
    if (profile.get("tax_arrears") or 0) > 0:
        a.append(f"Налоговая задолженность: {_fmt(profile.get('tax_arrears'))} ₽.")
    if (profile.get("inquiries_last_90d") or 0) > 5:
        a.append(f"Много запросов в БКИ за 90 дней: {profile.get('inquiries_last_90d')}.")
    if not a:
        a.append("Явных аномалий не выявлено.")
    return a


def _facts(app, profile, score, decision, offer) -> dict:
    return {
        "amount": _fmt(app.amount),
        "term": app.term_months,
        "score": score.score if score else "—",
        "risk_band": score.risk_band if score else "—",
        "pd": score.pd_estimate if score else "—",
        "outcome": decision.outcome if decision else "—",
        "offer_amount": _fmt(offer.amount) if offer else None,
        "offer_rate": float(offer.rate) if offer else None,
        "revenue": _fmt(profile.get("avg_monthly_revenue")),
        "company_age": profile.get("registered_years_ago"),
        "credit_score": profile.get("credit_score"),
    }


OUTCOME_RU = {
    "approve": "одобрение", "counter": "контрпредложение",
    "need_info": "запрос данных", "decline": "отказ",
}


def template_summary(f: dict) -> str:
    base = (
        f"Заявка на {f['amount']} ₽ сроком {f['term']} мес. "
        f"Балл кредитоспособности {f['score']} ({f['risk_band']} риск, PD {f['pd']}). "
        f"Средняя выручка по ОФД {f['revenue']} ₽/мес, возраст бизнеса {f['company_age']} лет, "
        f"кредитный рейтинг БКИ {f['credit_score']}. "
        f"Решение движка: {OUTCOME_RU.get(f['outcome'], f['outcome'])}."
    )
    if f.get("offer_amount"):
        base += f" Предложено {f['offer_amount']} ₽ под {f['offer_rate']}% годовых."
    return base


def template_justification(f: dict, anomalies: list[str]) -> str:
    return (
        f"Обоснование решения ({OUTCOME_RU.get(f['outcome'], f['outcome'])}). "
        f"Балл {f['score']} при уровне риска {f['risk_band']} и PD {f['pd']}. "
        f"Ключевые наблюдения: {' '.join(anomalies)} "
        f"Решение соответствует действующей кредитной политике и сформировано на "
        f"основании скоринга и внешних проверок (БКИ, ЕГРЮЛ, ФНС, ОФД)."
    )


def _llm(prompt: str) -> str:
    resp = httpx.post(
        f"{settings.ollama_url}/api/generate",
        json={"model": settings.llm_model, "prompt": prompt, "stream": False},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def generate(db, app) -> dict:
    from app.models.company import Company

    snap = app.latest_enrichment
    profile = snap.profile if snap else {}
    score = app.latest_score
    decision = app.latest_decision
    offer = app.latest_offer
    company = db.get(Company, app.company_id)

    anomalies = build_anomalies(app, profile, float(company.annual_revenue) if company else 0)
    f = _facts(app, profile, score, decision, offer)

    source = "template"
    summary = template_summary(f)
    justification = template_justification(f, anomalies)

    if settings.llm_enabled:
        try:
            ctx = (
                f"Данные заявки: {f}. Аномалии: {anomalies}. "
                "Ты помощник андеррайтера в банке. Отвечай по-русски, кратко и по делу."
            )
            summary = _llm(ctx + " Дай саммари заявки в 2-3 предложениях.")
            justification = _llm(
                ctx + " Напиши черновик обоснования кредитного решения для аудита "
                "в 3-4 предложениях. Не принимай решение сам, опиши основания."
            )
            source = "llm"
        except Exception:
            source = "template"  # деградация: демо не падает без модели

    return {
        "summary": summary,
        "anomalies": anomalies,
        "justification": justification,
        "source": source,
    }
