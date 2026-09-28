# Research notes (Phase 0)

All sources were accessed on **2026-09-28** and actually opened (page, PDF text, raw wikitext or PyPI JSON). Some pages could not be fetched: ESPNcricinfo (HTTP 403), vityarthi.com (403), and paywalled Springer/OUP pages. Findings from those pages are marked **M** (secondary or abstract-level) or **L**. All text is paraphrased.

Confidence: **H** = primary text read · **M** = abstract or secondary · **L** = partial or inferred.

---

## R1 — Course and syllabus

| Question | Answer | Source | Conf. | Decision it drives |
|---|---|---|---|---|
| Which course? | The student confirmed **Machine Learning**. Other VITyarthi "Build Your Own Project" submissions cite the flipped course *Fundamentals of AI & ML* (VIT Bhopal CSA2001). | Student's answer; https://github.com/tanushrihalmare01/student-performance-predictor | H (student) / M | ML is the core. AI concepts are mapped explicitly as a safety margin (ADR-001). |
| Syllabus units | CSA2001 modules, as found: (1) intro and intelligent agents; (2) production systems and state-space search; (3) problem-solving methods (uninformed and informed search, heuristics, local search and optimisation) and knowledge representation (predicate logic); (4) planning and learning. VITyarthi's course blurb lists supervised and unsupervised learning, data preprocessing, model evaluation and ethics. | vityarthi.com course page (403; search-result extract), Scribd/Studocu listings for CSA2001 | M | `docs/course_mapping.md` maps each unit to a module. We add one unsupervised component (venue clustering) and frame hyperparameter search as heuristic/local search. |
| Official syllabus text | Not publicly reachable. The portal requires a login. | — | — | If the student adds `docs/assignment/syllabus.txt`, the course mapping is revised. |

## R2 — IPL structural history (franchises, venues, home grounds)

**Franchise lineage.** 19 team strings map to **15 franchises**. Canonicalisation rules are in `configs/team_lineage.yaml`.
- These are **the same franchise, renamed**:
  - Delhi Daredevils → Delhi Capitals (renamed Dec 2018; first season as DC 2019).
  - Kings XI Punjab → Punjab Kings (renamed Feb 2021).
  - Royal Challengers Bangalore → Bengaluru (renamed 19 Mar 2024).
  - Rising Pune Supergiants → Supergiant (renamed 26 Mar 2017).
- These are **distinct franchises**:
  - Deccan Chargers (2008–12) vs Sunrisers Hyderabad (2013–): new owner and new contract.
  - Gujarat Lions (2016–17) vs Gujarat Titans (2022–).
  - Rising Pune Supergiant vs Lucknow Super Giants: same owner group, but a new franchise.
  - Pune Warriors (2011–13) and Kochi Tuskers Kerala (2011) are defunct.
- CSK and RR were suspended in 2016–17.
- Sources: https://en.wikipedia.org/wiki/Delhi_Capitals, https://en.wikipedia.org/wiki/Punjab_Kings, https://en.wikipedia.org/wiki/Royal_Challengers_Bengaluru, https://www.royalchallengers.com/rcb-cricket-news/news/rcb-renamed-as-royal-challengers-bengaluru-at-rcb-unbox-2024, https://en.wikipedia.org/wiki/Rising_Pune_Supergiant, https://en.wikipedia.org/wiki/Sunrisers_Hyderabad, https://en.wikipedia.org/wiki/Deccan_Chargers, https://en.wikipedia.org/wiki/Gujarat_Lions, https://en.wikipedia.org/wiki/Pune_Warriors_India, https://en.wikipedia.org/wiki/Kochi_Tuskers_Kerala.
- Confidence: **H**.
- Decision: ADR-003. Elo ratings carry across renames; distinct franchises start fresh at 1500.

**Venues.** The **60 raw strings map to 37 venue IDs**: 36 grounds plus old Motera, which is kept separate. The subagent's tally said "40 grounds", but counting the finished mapping gives 37. Full per-string mapping with city corrections is in `configs/venue_canonical.yaml`.

Traps:
- **Renamed grounds:**
  - Feroz Shah Kotla → Arun Jaitley Stadium (Sep 2019).
  - Subrata Roy Sahara Stadium = MCA Stadium Pune (naming rights lapsed).
  - Sheikh Zayed Stadium = Zayed Cricket Stadium (same ground).
  - PCA Stadium → I. S. Bindra PCA Stadium, Mohali (2015).
  - OUTsurance Oval = Mangaung Oval.
- **Sardar Patel Stadium, Motera** was demolished and rebuilt as the Narendra Modi Stadium (opened 2020). It is the same site but a new stadium, so it gets its own `venue_id` (`motera_old`).
- **Maharaja Yadavindra Singh Stadium (Mullanpur / New Chandigarh)** is a new ground (first used 2024), *not* PCA Mohali.
- **Wrong or missing city values:**
  - DY Patil is in Navi Mumbai, not Mumbai.
  - PCA shows "Chandigarh" but the ground is in Mohali.
  - Dubai and Sharjah show "Unknown" 51 times.
- Sources: Wikipedia pages for each stadium (Arun Jaitley, Narendra Modi, Sardar Patel Stadium, MCA Stadium, Sheikh Zayed Cricket Stadium, I. S. Bindra Stadium, Maharaja Yadavindra Singh Stadium, DY Patil Stadium, ACA–VDCA, Niranjan Shah Stadium, Assam Cricket Association Stadium, Ekana, Mangaung Oval, St George's Park, Buffalo Park, De Beers Diamond Oval, Wanderers, VCA, Holkar, JSCA, Rajiv Gandhi, HPCA, Raipur, JN Stadium Kochi).
- Confidence: **H**. The Zayed rename date is M.

**Home grounds and neutral seasons.** Primary homes are recorded in `configs/home_grounds.yaml`. Secondary homes (Raipur, Dharamsala, Guwahati, Visakhapatnam, Indore, etc.) are listed there too.
- **Neutral or abroad:** 2009 (South Africa); 2014 first leg (UAE); 2020 (UAE); 2021 (India hubs with no home games, then UAE); 2022 league stage (Maharashtra hub).
- Sources: season pages https://en.wikipedia.org/wiki/2009_Indian_Premier_League … https://en.wikipedia.org/wiki/2026_Indian_Premier_League.
- Confidence: **H** for primary homes, **M** for secondary-venue years.
- Decision: `is_home` is 0 for both teams in neutral seasons, and home advantage is estimated rather than assumed.

**Player-name aliases.** There are 811 exact name strings. Every `player_of_match` value appears in a squad list.
- Known risks:
  - "Harmeet Singh" is probably two different people (KXIP and RR, 2013).
  - Many distinct players share an initial and surname (RG Sharma / R Sharma, DJ Bravo / DM Bravo, …).
- Confidence: **M**.
- Decision: key players on the **exact string** and never collapse names. The Harmeet Singh ambiguity is documented as a known limitation.

## R3 — Pre-match outcome prediction: realistic ceilings and Elo design

| # | Source | Finding (paraphrased) | Conf. |
|---|---|---|---|
| 1 | Kampakis & Thomas (2015), arXiv:1511.05837 — https://arxiv.org/abs/1511.05837 | English county T20, season-ahead temporal evaluation. Random forest reached about 56%, rising to about 58% with player features. T20 is described as less predictable than many sports, and home advantage drifts over time. | H |
| 2 | Lamsal & Choudhary (2018), arXiv:1809.09813 — https://arxiv.org/abs/1809.09813 | About 72% on a single 60-match IPL season using post-toss inputs. The 95% CI is roughly ±11 pp, so it is anecdotal. | M |
| 3 | Bandyopadhyay & Mukherjee (2026), arXiv:2603.02574 — https://arxiv.org/html/2603.02574 | Temporal Test-cricket evaluation. Plain Elo scored Brier 0.190 and log-loss 0.657. Test cricket is more predictable than T20. | H |
| 4 | Puram et al. (2023), *Annals of OR* 325 — https://ideas.repec.org/a/spr/annopr/v325y2023i1d10.1007_s10479-022-05027-1.html | Interpretable ML (tree ensembles, BART, PDP/ALE) on 563 IPL matches to rank contextual factors such as home, toss and decision. | M |
| 5 | Hvattum & Arntzen (2010), *Int. J. Forecasting* 26:460–470 — https://ideas.repec.org/a/eee/intfor/v26yi3p460-470.html | The Elo difference used as a covariate in an ordered logit is among the strongest single predictors of football results. | M |
| 6 | FiveThirtyEight `nfl-elo-game/forecast.py` — https://github.com/fivethirtyeight/nfl-elo-game/blob/master/forecast.py | K=20; home advantage 65; 1/3 reversion between seasons. The margin-of-victory multiplier ln(margin+1)·2.2/(0.001·Δelo_winner+2.2) includes an autocorrelation correction. | H |
| 7 | Johnsson (2019), Harvard Sports Analysis — https://harvardsportsanalysis.org/2019/01/a-simple-improvement-to-fivethirtyeights-nba-elo-model/ | A higher K early in the season that decays over the season improved NBA Elo log-loss. | H |
| 8 | Walsh & Joshi (2024), *ML with Applications*, arXiv:2303.06021 — https://arxiv.org/abs/2303.06021 | Selecting models on calibration rather than accuracy led to much better downstream decisions. | H |

**Synthesis.** We found no peer-reviewed IPL pre-match study with a strict temporal holdout that reports log-loss or AUC. Adjacent evidence suggests a realistic range:
- Accuracy 53–60%.
- Log-loss 0.675–0.695 (a coin flip scores ln 2 = 0.693).
- Brier 0.240–0.250.
- AUC 0.55–0.63.

Decisions driven:
- The "too good" guard fires at **AUC > 0.72** (kept) and **accuracy > 68%** (kept).
- Model selection uses **log-loss** (source 8).
- Elo search grid: K ∈ {10, 15, 20, 25, 32, 40}; home bonus ∈ {0, 15, 30, 50, 75}; season reversion ∈ {0, 0.1, 0.2, 0.33, 0.5}; margin-of-victory multiplier on or off (538 form); an optional early-season K boost.

## R4 — Toss effect

| # | Source | Finding | Conf. |
|---|---|---|---|
| 1 | Sood & Willis (2016), arXiv:1605.08753 — https://arxiv.org/abs/1605.08753 | Across about 5.4k T20 matches, the toss advantage is about 1.3 pp and not statistically significant. The toss is random, so a simple comparison of toss winner vs loser is causal. Conditioning on the bat/field decision is **post-treatment** and biases the estimate. | H |
| 2 | Dawson, Morley, Paton & Thomas (2009), *JORS* 60(12) | Winning the toss in day/night ODIs was associated with higher win rates. Critiqued in #1 for conditioning on the decision. | M (via #1) |
| 3 | Bhaskar (2009), *Economic Journal* 119(534) — https://academic.oup.com/ej/article-abstract/119/534/1/5089654 | Uses the toss as a natural experiment. Captains' toss decisions are often suboptimal. | M |
| 4 | "Determinants of success in Twenty20 cricket" (Univ. of Chichester) — https://eprints.chi.ac.uk/3871/1/Determinants%20of%20Success%20in%20Twenty20%20Cricket.pdf | Reviews earlier work: De Silva & Swartz (1997) found home advantage but no toss advantage; Morley & Thomas (2005) found a toss × home interaction. | M |
| 5 | The Federal (2026) — https://thefederal.com/sports/cricket/ipl-2026-early-trends-how-chasing-teams-dominating-toss-crucial-238128 | Early-2026 media claims that chasing teams dominate. Small-n anecdote. | L |

Test design adopted (`analytics/toss_analysis.py`):
1. Exact binomial test of P(toss winner wins) = 0.5 with a Wilson CI. We report the **minimum detectable effect** (about ±2.8 pp at n ≈ 1,218) so a null result is not overstated.
2. Chasing advantage is tested separately, with a binomial test and an era comparison (two-proportion z-test before vs after the Impact Player rule).
3. Chi-square of decision × outcome, labelled *associational*.
4. Venue-level heterogeneity is controlled for multiple comparisons with Holm correction.

## R5 — Data provenance and license

- The column set maps one-to-one onto the **Cricsheet JSON `info` section** (`event.name`, `event.match_number`, `officials.*`, `season` "such as 2018, or 2011/12"). Source: https://cricsheet.org/format/json/ (H).
- Cricsheet lists **1,243 IPL matches**, exactly our row count. Source: https://cricsheet.org/matches/ (H).
- Cricsheet is maintained by Stephen Rushe (https://cricsheet.org/about/).
- **License:** the Open Data Commons Attribution License v1.0 is stated on https://cricsheet.org/register/.
  - It requires attribution of any public use and keeping notices intact. Source: https://opendatacommons.org/licenses/by/summary/ (H).
  - The statement appears only on the Register page, so we conservatively treat all Cricsheet data as ODC-BY.
- **Probable intermediary:** the Kaggle dataset "IPL Complete Cricket Dataset (2008–2026)" by `tankharsh07`, CC BY 4.0, "sourced from CricSheet". Source: https://www.kaggle.com/api/v1/datasets/view/tankharsh07/ipl-complete-match-dataset-20082026. The exact 31-column origin is **unconfirmed** (M).
- Decision: README "Data attribution" credits Cricsheet (ODC-BY 1.0) and notes the probable Kaggle intermediary. `LICENSE` excludes `data/raw/`. The SHA-256 is recorded.

## R6 — Tooling currency

Checked on PyPI's versioned JSON endpoints on 2026-09-28:

| Package | Version |
|---|---|
| pandas | 3.0.6 |
| numpy | 2.5.3 (**requires Python ≥ 3.12**) |
| scipy | 1.18.1 (**requires Python ≥ 3.12**) |
| statsmodels | 0.15.0 |
| scikit-learn | 1.9.1 |
| xgboost | 3.4.1 |
| lightgbm | 4.7.0 |
| streamlit | 1.64.0 |
| plotly | 7.1.0 |
| SQLAlchemy | 2.1.1 |
| pandera | 0.33.1 |
| typer | 0.27.2 |
| rich | 15.0.0 |
| PyYAML | 6.0.3 |
| Jinja2 | 3.1.6 |
| joblib | 1.6.0 |
| pyarrow | 25.0.1 |
| pytest | 9.1.1 |
| hypothesis | 6.168.3 |
| ruff | 0.16.9 |
| mypy | 2.3.1 |
| bandit | 1.9.4 |
| pip-audit | 2.10.1 |
| import-linter | 2.15 |
| playwright | 1.63.0 |
| @mermaid-js/mermaid-cli | 12.0.0 (Node ≥ 22.13) |

Further findings:
- **pandera:** `import pandera.pandas as pa` is now the recommended import; the top-level import is being deprecated.
- **Streamlit:** the `pages/` directory is still supported (https://docs.streamlit.io/develop/concepts/multipage-apps/pages-directory), and `streamlit.testing.v1.AppTest` exists (https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
- **PDF rendering:** WeasyPrint on Windows needs MSYS2/Pango (https://doc.courtbouillon.org/weasyprint/stable/first_steps.html). Playwright's `page.pdf()` (Chromium only) is pip-installable (https://playwright.dev/python/docs/api/class-page#page-pdf).
- **GitHub Actions:** `actions/checkout@v7` and `actions/setup-python@v7`.
- **Python lifecycle** (https://devguide.python.org/versions/): 3.12 is security-only; 3.13 is in bugfix.

Decisions (ADR-002):
- `requires-python >= 3.12`; CI runs 3.12 and 3.13; local development on 3.12.10.
- Use scikit-learn only for models. xgboost and lightgbm are skipped to avoid the macOS `libomp` native dependency; HistGradientBoosting covers gradient boosting.
- Use Playwright for the PDF and screenshots.

## R7 — Evaluation methodology for small, time-ordered data

| # | Source | Finding | Conf. |
|---|---|---|---|
| 1 | Bergmeir & Benítez (2012), *Information Sciences* 191 — https://research.monash.edu/en/publications/on-the-use-of-cross-validation-for-time-series-predictor-evaluati/ | Blocked CV gives robust model selection for stationary series. | M |
| 2 | Cerqueira, Torgo & Mozetič (2020), *Machine Learning* 109 — https://arxiv.org/abs/1905.11744 | For non-stationary real series, out-of-sample time-ordered estimation is preferable to CV. | H |
| 3 | Niculescu-Mizil & Caruana (2005), ICML — https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf | Logistic regression and bagged trees are already fairly well calibrated. With a small calibration set (below about 1,000), Platt scaling beats isotonic, which overfits. | H |
| 4 | scikit-learn user guide, *Probability calibration* — https://scikit-learn.org/stable/modules/calibration.html | Prefer sigmoid for small n. The default CV in `CalibratedClassifierCV` is not time-aware. A lower Brier score does not by itself mean better calibration. | H |
| 5 | Brier score and the Murphy decomposition — https://en.wikipedia.org/wiki/Brier_score | BS = REL − RES + UNC. Brier skill score is measured against a reference forecast. | H |
| 6 | Nixon et al. (2019), arXiv:1904.01685 — https://arxiv.org/abs/1904.01685 | ECE is sensitive to the binning scheme; adaptive bins are recommended. | H |
| 7 | Kumar, Liang & Ma (2019), NeurIPS, arXiv:1909.10155 — https://arxiv.org/abs/1909.10155 | Binned ECE underestimates the calibration error of scaling methods. | H |
| 8 | Roelofs et al. (2022), AISTATS, arXiv:2012.08668 — https://arxiv.org/abs/2012.08668 | Equal-mass bins have lower bias than equal-width bins. | H |
| 9 | Diebold–Mariano test with HLN correction — https://real-statistics.com/time-series-analysis/forecasting-accuracy/diebold-mariano-test/ | Tests for equal predictive accuracy; the HLN correction is needed in small samples. | M |

Decisions:
- **Expanding-window walk-forward** by season for model selection.
- **Platt (sigmoid)** calibration fitted on time-ordered out-of-fold predictions; isotonic is reported only as a comparison.
- ECE uses **equal-mass bins** and is labelled descriptive.
- Brier score is reported with its decomposition and as a skill score against the base-rate and Elo-only forecasts.
- Model comparisons use a **paired bootstrap** (10,000 resamples) on per-match log-loss differences plus a Diebold–Mariano/HLN test.

## R8 — Ties, super overs and anomalies

- **The raw CSV adds super-over runs and wickets to the innings totals of tied matches.** For example:
  - 2017-04-29: MI 164/12 = 153 all out (10 wickets) + 11/2 in the super over.
  - 2015-04-21: RR 197/8 = 191/6 + 6/2.
  - 2026-04-26: LSG 156/10 = 155/8 + 1/2.
  - 2020-10-18: MI v KXIP includes **two** super overs.
- Consequence: scoring statistics must use the **regulation** score for ties.
- All 16 super-over winners, with regulation tied scores and two sources each, are in `data/external/super_over_winners.csv`.
- The 2009 KKR v RR tie was a super over, not a bowl-out (the IPL has never had a bowl-out).
- All 9 no-result rows are real. **08-05-2025 PBKS v DC (Dharamsala)** was voided because of a security blackout during the India–Pakistan hostilities and replayed in full at Jaipur on 24-05-2025; that replay is **not** in the CSV.
  - Source: https://www.outlookindia.com/sports/cricket/pbks-vs-dc-indian-premier-league-2025-why-and-when-is-punjab-kings-vs-delhi-capitals-match-being-replayed-at-jaipur
- **D/L results 2008–2017** are listed in `data/external/dls_matches.csv` (16 matches, from Wikipedia season pages; M).
  - Our "winner inconsistent with batting order" heuristic flags exactly **6** matches, all of which appear in that list.
  - The other D/L matches (e.g. "won by 10 wickets" chases) are undetectable from the CSV, so the external list is the source of truth.
  - Pre-match shortened games (e.g. 2015-05-02) are *not* D/L.
- Sources: ESPNcricinfo match reports (URLs in the CSV), Wikipedia season pages, https://www.mykhel.com/cricket/ipl-super-over-list-all-16-ties-from-2009-to-2026-records-winners-narine-rewrites-history-428527.html.
- Confidence: **H** for winners, **M** for the D/L list.

## R9 — Existing IPL prediction projects (for differentiation, no code reused)

| Project | Pattern observed | Conf. |
|---|---|---|
| dilipkumar104/IPL-Match-Predictor — https://github.com/dilipkumar104/IPL-Match-Predictor | Team and head-to-head win rates aggregated over the **whole dataset**, including future matches. This is target leakage, and it reports about 0.97 AUC. | H |
| sanidhyajadaun/IPL-Match-Winner-Prediction — https://github.com/sanidhyajadaun/IPL-Match-Winner-Prediction | Uses **`player_of_match` as a feature**, a random `train_test_split` and accuracy only. | H |
| Rajdeepjena05/Ipl-match-winner-prediction- — https://github.com/Rajdeepjena05/Ipl-match-winner-prediction- | In-play model with a row-level random split, so the same match appears in both train and test. | M–H |
| manpatell/IPL-Winner-Prediction-2026 — https://github.com/manpatell/IPL-Winner-Prediction-2026 | Reports about 65–67% accuracy and AUC around 0.70; leakage controls are not documented. | M |
| samarth1809/ipl-win-predictor — https://github.com/samarth1809/ipl-win-predictor | Synthetic data; accuracy-only reporting. | M |

**CreaseIQ's differentiators:**
- Every feature is computed as of the day before the match, and five automated leakage tests check this.
- Probabilities are symmetric under swapping the two teams.
- Validation is walk-forward, with a single-shot holdout.
- The primary metric is log-loss, with calibration and bootstrap CIs.
- Models are compared against baselines.
- The pipeline discovers the `team1` semantic drift and the super-over contamination in the data.

## R10 — Ground truth: finals and champions

| Year | Final | Champion | Runner-up |
|---|---|---|---|
| 2008 | 1 Jun | RR | CSK |
| 2009 | 24 May | Deccan Chargers | RCB |
| 2010 | 25 Apr | CSK | MI |
| 2011 | 28 May | CSK | RCB |
| 2012 | 27 May | KKR | CSK |
| 2013 | 26 May | MI | CSK |
| 2014 | 1 Jun | KKR | KXIP |
| 2015 | 24 May | MI | CSK |
| 2016 | 29 May | SRH | RCB |
| 2017 | 21 May | MI | RPS |
| 2018 | 27 May | CSK | SRH |
| 2019 | 12 May | MI | CSK |
| 2020 | 10 Nov | MI | DC |
| 2021 | 15 Oct | CSK | KKR |
| 2022 | 29 May | GT | RR |
| 2023 | 29 May (reserve day) | CSK (DLS) | GT |
| 2024 | 26 May | KKR | SRH |
| 2025 | 3 Jun | **RCB** | PBKS |
| 2026 | 31 May | **RCB** | GT |

- Sources: https://en.wikipedia.org/wiki/List_of_Indian_Premier_League_seasons_and_results, https://en.wikipedia.org/wiki/2025_Indian_Premier_League, https://en.wikipedia.org/wiki/2026_Indian_Premier_League (H).
- **Playoff format:**
  - 2008–2010: semi-finals and a final.
  - 2010: also a third-place play-off.
  - 2011 onward: Qualifier 1, Eliminator, Qualifier 2, Final.
- **Teams per season:** 8 (2008–10), 10 (2011), 9 (2012–13), 8 (2014–21), 10 (2022–26).
- **Impact Player rule:** introduced in 2023 and still in force in 2025 and 2026, extended to at least 2027.
  - Sources: https://en.wikipedia.org/wiki/2023_Indian_Premier_League, https://www.tribuneindia.com/news/sports/the-shining-bcci-lifts-saliva-ban-in-ipl-after-majority-of-captains-agree-to-proposal/, https://www.pratidintime.com/sports/ipl-2026/ipl-2026-captains-meeting-explained-impact-player-rule-ball-change-policy-and-new-playing-conditions-11364369
- **Rows per season are below the official counts** in 2008, 2009, 2011, 2012, 2015, 2017 and 2024, because matches abandoned without a ball being bowled are absent.
- Decisions:
  - `champion` (the winner of each season's last match) is tested against this table.
  - `stage` labels follow the era-specific format.
  - `impact_era = season_year ≥ 2023`.

## R11 — Responsible use and academic integrity

- **Promotion and Regulation of Online Gaming Act, 2025** (Act 32 of 2025; assent 22 Aug 2025) prohibits online money games and their promotion.
  - Source: https://en.wikipedia.org/wiki/Promotion_and_Regulation_of_Online_Gaming_Act,_2025 (M–H). PIB pages returned 403.
- **VIT Research Integrity Policy** defines plagiarism to include unacknowledged use of code and data.
  - Source: https://vit.ac.in/files/ebooks/Research-Integrity-Policy/files/basic-html/page7.html (M).
- No public VIT or VITyarthi policy on AI-assisted work was found.
- Decisions:
  - A disclaimer (educational use; not betting, fantasy or financial advice; not affiliated with BCCI, IPL or Cricsheet) appears in the README, the app footer and the report.
  - An **"AI assistance & sources"** statement appears in the README and report.
  - `docs/viva_prep.md` is written so the student can explain and defend every module.
