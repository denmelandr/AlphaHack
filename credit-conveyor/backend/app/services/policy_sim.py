"""Прогон кредитной политики на исторических заявках (shadow-режим).

Берёт последние заявки, у которых есть скоринг и обогащение, и прогоняет через
заданную политику, не меняя сами заявки. Позволяет сравнить, сколько бы одобрила
кандидатная политика против активной, до включения (champion/challenger)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.product import Product
from app.services import policy as policy_engine


def _outcome(body: dict, app: Application, product: Product) -> str:
    score = app.latest_score
    snap = app.latest_enrichment
    result = policy_engine.decide(
        body,
        {"score": score.score, "risk_band": score.risk_band,
         "pd_estimate": score.pd_estimate},
        snap.profile,
        product,
        float(app.amount),
        int(app.term_months),
    )
    return result["outcome"]


def evaluate(db: Session, active_body: dict, candidate_body: dict, limit: int) -> dict:
    apps = list(db.scalars(select(Application).order_by(Application.id.desc())))
    sample = [a for a in apps if a.latest_score and a.latest_enrichment][:limit]

    diffs = []
    active_counts = {"approve": 0, "counter": 0, "need_info": 0, "decline": 0}
    cand_counts = {"approve": 0, "counter": 0, "need_info": 0, "decline": 0}

    for a in sample:
        product = db.get(Product, a.product_id)
        ao = _outcome(active_body, a, product)
        co = _outcome(candidate_body, a, product)
        active_counts[ao] = active_counts.get(ao, 0) + 1
        cand_counts[co] = cand_counts.get(co, 0) + 1
        if ao != co:
            diffs.append({"application_id": a.id, "active": ao, "candidate": co})

    n = len(sample)

    def rate(counts: dict, keys: tuple) -> float:
        if n == 0:
            return 0.0
        return round(sum(counts.get(k, 0) for k in keys) / n * 100, 1)

    return {
        "n": n,
        "active": {
            "counts": active_counts,
            "approve_rate": rate(active_counts, ("approve",)),
            "approve_or_counter_rate": rate(active_counts, ("approve", "counter")),
        },
        "candidate": {
            "counts": cand_counts,
            "approve_rate": rate(cand_counts, ("approve",)),
            "approve_or_counter_rate": rate(cand_counts, ("approve", "counter")),
        },
        "diffs": diffs,
    }
