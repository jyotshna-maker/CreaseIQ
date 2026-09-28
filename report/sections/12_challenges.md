# 12. Challenges Faced

These challenges actually occurred and were logged during the build (`PROGRESS.md`, ADRs).

1. **A column whose meaning changes over time.** From 2018 `team1` always bats first; before that the order is effectively random. The column's name does not reveal this, and it is easy to feed into a model. We discovered it by profiling the share of `team1` batting first per season. The fix was to derive batting order from the toss and orient matches with a hash-seeded coin flip (ADR-005), and a test now documents the trap.
2. **Super-over contamination.** The anomaly "12 wickets lost" turned out to be systematic. All 16 tie rows add super-over runs and wickets, and one adds two super overs. It was found only by checking scorecards during research (R8). The fix was verified regulation scores, with two independent sources per tie.
3. **A voided match that looks like a washout.** PBKS v DC on 08-05-2025 was stopped by a security blackout and replayed elsewhere. Without the research, it would have counted as a genuine no-result with scores.
4. **Low recall of the D/L heuristic.** Margin logic caught only the D/L results that contradict batting order. D/L chases "won by N wickets" are invisible in match-level data, so a researched external list was combined with the heuristic.
5. **Subtle venue identity.** Three kinds of trap appeared:
   - A demolished and rebuilt stadium on the same site (Motera).
   - A new ground in the same district (Mullanpur vs Mohali).
   - Naming-rights renames (Sahara / MCA Pune).

   Some research tallies also disagreed. The subagent's count said 40 venues; the mapping itself yields 37, which we trust.
6. **A toolchain that was out of date.** The plan targeted Python 3.11, but the current numpy and scipy require 3.12, so the floor moved (ADR-002). The machine had no git or GitHub CLI, so both were installed before any version control could start.
7. **Secret hygiene.** A personal access token was pasted into the original build plan. It was removed before the first commit, authentication was delegated to `gh auth login`, and a secrets-scan test now guards the repository.
8. **Performance.** Under pandas 3, `itertuples` over about 950 small date groups made one feature build take 7 s, which made grid search and the leakage tests impractical. Profiling showed 117k indexer calls. Converting to plain records once cut the build to 0.33 s, a 21× speed-up.
9. **A negative holdout result.** On 2025–26 no model beat a coin flip. The temptation was to keep tuning until it did. Instead the selection was frozen and hashed before evaluation, and the result is reported as a finding about regime change. ADR-006 openly discloses one ledger reset after an exploratory run of the same selection.
10. **Plan errors found by review.** The plan's chase-rate baseline was computed over all seasons, which would have leaked the holdout base rate. Its toss test conditioned on a post-treatment choice. Both were corrected (`docs/plan_review.md`, 13 findings).
11. **Bugs caught by tests and types.**
    - A logging handler wrote to a stream that the test runner had closed.
    - An output writer assumed that `docs/` existed.
    - A loop variable was shadowed in the registry code, which mypy caught.
    - Franchise alias validity windows ended in 2026, which would have rejected any 2027 upload.
12. **Unreliable research tools.** ESPNcricinfo blocks automated fetches, and the page summariser misreported some facts. The research therefore relied on raw Wikipedia wikitext and cross-checked sources, and every finding records its confidence.
