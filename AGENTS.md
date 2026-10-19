# QuantItera development contract

This is the public research engine. Mutable research data belongs to a separate private workspace.
Reuse the V6/P1 functions listed in provenance.json; do not replace tested algorithms with parallel implementations.
Do not commit personal assets, models, strategy parameters, portfolios, trades, inbox/outbox receipts, real research records or private Git history.
Use synthetic tests. Keep evidence, expectations, economic mechanisms, objective outcomes and personal execution separate.
Missing evidence stays missing. Preserve source, unit, horizon and availability boundaries; no source-count voting or automatic causal claims.
Events are append-only and writes are serialized. No brokerage execution or paid APIs.
Run python -m pytest -q before publishing changes. Public CI only tests; private workspace schedules are templates.
