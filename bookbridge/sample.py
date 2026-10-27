from __future__ import annotations

from uuid import UUID
from .qloo import Entity

ANCHORS = [
 Entity("11111111-1111-4111-8111-111111111111", "Lattice Lanterns", "movie"),
 Entity("22222222-2222-4222-8222-222222222222", "Harbor Signals", "artist"),
 Entity("33333333-3333-4333-8333-333333333333", "The Clockwork Garden", "book"),
]
BOOKS = [
 Entity("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", "Cartographers of Rain", "book", "Mira Vale"),
 Entity("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2", "The Archive at Low Tide", "book", "Jon Bell"),
 Entity("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3", "Orbits of Glass", "book", "N. Rowan"),
 Entity("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4", "A Choir of Small Machines", "book", "Sana Ives"),
 Entity("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5", "North of the Last Library", "book", "Em Cole"),
]

class SyntheticTransport:
    async def search(self, query: str, kind: str, take: int = 8):
        q = query.casefold()
        return [e for e in ANCHORS if e.kind == kind and q in e.name.casefold()][:take]
    async def books(self, seed_ids: list[str], take: int = 20, candidates: list[str] | None = None):
        order = BOOKS if seed_ids[0].startswith(("1", "3")) else [BOOKS[1], BOOKS[2], BOOKS[4], BOOKS[0]]
        if candidates is not None: order = [b for b in order if b.id in candidates]
        return order[:take]
