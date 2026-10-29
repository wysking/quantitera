# Licence, provenance, and reference scope

QuantItera's original public code and documentation are copyright (c) 2026
wysking, under [MIT](MIT.txt). Preserve the copyright and permission notice
when redistributing substantial portions. Source and author:
https://github.com/wysking/quantitera and https://github.com/wysking.

## Calendar provenance

`quantitera_calendars/cash_history_2021_2024.json` declares schedules generated
with `exchange_calendars==4.11.3` and HKEX announcement overrides. The correct
upstream tag is [`4.11.3`](https://github.com/gerrymanoim/exchange_calendars/tree/4.11.3),
commit `79a4c2cbeed5a16adee5d013edd76f5c8c82d656`.
Its [actual licence](https://github.com/gerrymanoim/exchange_calendars/blob/79a4c2cbeed5a16adee5d013edd76f5c8c82d656/LICENSE)
is copied verbatim in `exchange_calendars-Apache-2.0.txt`, including the
copyright notice "Copyright 2018 Quantopian, Inc.". The upstream tree at this
pin contains no separate NOTICE file; none is invented here.

The JSON is generated output with subsequent factual corrections; it is not
third-party Python source. A generator's software licence alone does not
establish the rights in all output or in later modifications. The provenance
fields and existing source URLs are retained. The 2026-10-29 change relocates
the file and fixes `/tree/v4.11.3` to `/tree/4.11.3`; it changes no date values.

The finite calendar implementation also contains 2025/2026 schedules and
official-source links. Public announcements, objective trading-date facts,
and a potentially protected selection or arrangement are distinct things.
We have not established that the repository contains copied announcement prose,
nor do we assert that every individual date is protected. However, the public
history does not establish an independent redistribution permission for every
source-derived table. The original extraction hashes in `provenance.json`
are provenance records, not third-party permission.

[HKEX's published terms, section 5](https://www.hkex.com.hk/Global/Exchange/Terms-of-Use?sc_lang=en)
restrict redistribution and derivative compilations without express written
permission. The [Hong Kong Copyright Ordinance, section 4](https://www.elegislation.gov.hk/hk/cap528)
separately addresses original selection or arrangement of compilations. This
agent review records the evidence gap; it does not adjudicate infringement,
infer permission from visibility, or extend MIT/Apache to third-party material.
Source announcements remain linked in the calendar files for provenance.

## XERJ reference subset

The application selects only `research_engine`, `docs`, `examples`, `tests`,
and `licenses`. It excludes the entire `quantitera_calendars` package,
including both the implementation and all finite schedule tables. This is
an evidence/research/review-engine corpus, not a full QuantItera installation
or a calendar-data corpus. The compatibility module `research_engine/calendar.py`
contains only an import and boundary documentation.

The retained implementation covers append-only observations, source and
availability boundaries, expectations, competing explanations, knowledge
supersession, due-review feedback, and research/portfolio-performance methods.
It includes fictional demos and synthetic regression tests. Consumers needing
the calendar implementation must assess it separately in the full source repo.
The complete Python package remains compatible and still installs that package;
this reference boundary does not silently change runtime market behaviour.

No private repository, workspace, holding, trade, account, strategy configuration,
or credential was used in preparing this boundary. The public examples and test
fixtures remain labelled as synthetic; real source-derived calendars do not.
