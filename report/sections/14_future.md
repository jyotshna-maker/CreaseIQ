# 14. Future Enhancements

1. **Ball-by-ball data.** Ingest Cricsheet ball-by-ball JSON through the existing `MatchSource` interface. This would enable in-play win probability (given the score, wickets and balls left), player batting and bowling ratings, and phase-wise analytics (powerplay and death overs).
2. **Player-level team strength.** Build pre-match squad strength from player ratings and auction data. Squad turnover is the main reason history-only features fail after mega-auctions.
3. **Regime-aware models.** Down-weight older seasons (time-decayed training), add explicit era terms, or use Bayesian hierarchical models with team-by-season effects. All of these would be evaluated with the same walk-forward protocol.
4. **Conditions data.** Add weather and dew (evening humidity), pitch reports and venue-by-era effects, which are the known confounders of toss and chasing results.
5. **Automated drift response.** Trigger retraining when the PSI crosses its alert threshold, and use champion/challenger evaluation before promoting a model.
6. **A service interface.** Expose a REST API (e.g. FastAPI) over the existing services layer, with authentication and rate limiting for multi-user use.
7. **Deployment.** Package in a container and deploy the read-only dashboard to Streamlit Community Cloud with PostgreSQL. The database URL switch already exists.
8. **Data pipeline hardening.** Add a scheduled incremental ingest of new fixtures, with the same strict validation and dry-run canonicalisation used for uploads.
9. **Better player identity.** Adopt Cricsheet registry person ids instead of exact name strings, which would remove the known ambiguous name.
10. **Accessibility.** Add a full keyboard and screen-reader audit of the dashboard, a high-contrast theme and text alternatives for every chart.
