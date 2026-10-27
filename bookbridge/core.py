from __future__ import annotations

import asyncio
from dataclasses import asdict

from .models import Anchor, RecommendationRequest
from .qloo import Entity, QlooError, TasteTransport


async def find_shared(transport: TasteTransport, members: list[list[Anchor]], top_k: int = 3) -> dict:
    RecommendationRequest(members=members, top_k=top_k)
    seed_ids = [[str(a.id) for a in group] for group in members]
    generated = await asyncio.gather(*(transport.books(ids, 20) for ids in seed_ids))
    excluded = {str(a.id) for group in members for a in group if a.kind == "book"}
    pool: dict[str, Entity] = {}
    for group in generated:
        if len(group) > 20: raise QlooError("Qloo returned too many initial candidates.")
    for book in sorted((b for group in generated for b in group), key=lambda b: (b.id, b.name.casefold())):
        if book.id not in excluded: pool.setdefault(book.id, book)
    pool_ids = sorted(pool)
    rescored = await asyncio.gather(*(transport.books(ids, 40, pool_ids) for ids in seed_ids)) if pool_ids else [[], []]
    ranks = []
    for rows in rescored:
        if len(rows) > 40 or any(e.id not in pool for e in rows):
            raise QlooError("Qloo did not honor the candidate-pool filter.")
        rank = {}
        for entity in rows:
            if entity.id not in rank: rank[entity.id] = len(rank) + 1
        ranks.append(rank)
    covered = set(ranks[0]) & set(ranks[1])
    ordered = sorted(covered, key=lambda i: (max(ranks[0][i], ranks[1][i]), ranks[0][i] + ranks[1][i], pool[i].name.casefold(), i))
    title_seen = set()
    unique = []
    for eid in ordered:
        title = pool[eid].name.casefold().strip()
        if title not in title_seen:
            title_seen.add(title)
            unique.append(eid)
    ordered = unique
    shared_ids = ordered[:top_k]
    leftovers = [i for i in ordered if i not in shared_ids and ranks[0][i] != ranks[1][i]]
    # Stretch favors the strongest one-member rank while remaining evidenced for both.
    stretch_id = min(leftovers, key=lambda i: (min(ranks[0][i], ranks[1][i]), max(ranks[0][i], ranks[1][i]), pool[i].name.casefold(), i), default=None)
    def item(i: str) -> dict:
        return {**asdict(pool[i]), "member_ranks": [ranks[0][i], ranks[1][i]], "worst_rank": max(ranks[0][i], ranks[1][i]), "rank_gap": abs(ranks[0][i] - ranks[1][i])}
    return {
        "shared": [item(i) for i in shared_ids], "stretch": item(stretch_id) if stretch_id else None,
        "coverage": [{"returned": len(r), "pool": len(pool_ids), "missing": len(pool_ids) - len(r)} for r in ranks],
        "candidate_pool_size": len(pool_ids),
        "method": "Same-pool rank evidence; shared uses rank-based maximin, then rank sum and stable title/ID ties. Missing results are unknown, never zero affinity.",
        "trace": ["Requested up to 20 candidates per member", f"{len(pool_ids)} unique entity IDs pooled", "same pool rescored separately for each member"],
    }
