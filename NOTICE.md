# QuantItera notice

Copyright (c) 2026 wysking. Original public research-engine code and
documentation are provided under the MIT License in `LICENSE`.
Project: https://github.com/wysking/quantitera

The MIT grant does not grant rights in third-party source material, market
data, announcements, or externally supplied workspace content. In particular,
the finite calendars are source-derived factual schedules, not synthetic
fixtures. Their provenance and the limits of this review are recorded in
`licenses/README.md`. The bundled Apache licence is not a claim that all
generated output or HKEX modifications are licensed by the upstream project.

The 2026-10-29 public-boundary change moved the calendar implementation and
historical JSON into `quantitera_calendars`, retained the existing import API,
and corrected the upstream tag URL. No calendar values or research algorithms
were changed. The XERJ reference subset excludes that package; the complete
Python distribution still includes it and these notices.
