# 15. References

All sources were accessed on 28 September 2026 and actually opened during the research phase (`docs/research_notes.md`). The ESPNcricinfo and journal pages that blocked automated access are cited only where an accessible version was read. Link check performed at report build time: {{ refcheck.ok }} of {{ refcheck.total }} URLs resolved{% if refcheck.failed %}; not resolving to an automated client: {{ refcheck.failed | join(", ") }}{% endif %}.

[1] S. Rushe, "Cricsheet: IPL match data (JSON) and Register," cricsheet.org. Available: https://cricsheet.org/matches/ and https://cricsheet.org/register/ (Open Data Commons Attribution License v1.0).

[2] G. Sood and D. Willis, "Fairly random: The impact of winning the toss on the probability of winning," arXiv:1605.08753, 2016.

[3] S. Kampakis and W. Thomas, "Using machine learning to predict the outcome of English county twenty over cricket matches," arXiv:1511.05837, 2015.

[4] N. Lamsal and A. Choudhary, "Predicting outcome of Indian Premier League (IPL) matches using machine learning," arXiv:1809.09813, 2018.

[5] L. M. Hvattum and H. Arntzen, "Using ELO ratings for match result prediction in association football," *International Journal of Forecasting*, vol. 26, no. 3, pp. 460–470, 2010.

[6] FiveThirtyEight, "nfl-elo-game: forecast.py," GitHub repository. Available: https://github.com/fivethirtyeight/nfl-elo-game

[7] N. Johnsson, "A simple improvement to FiveThirtyEight's NBA Elo model," Harvard Sports Analysis Collective, 2019.

[8] P. Puram, S. Roy, D. Srivastav and S. Gurumurthy, "Contextual factors and decision making in T20 cricket: an interpretable machine learning approach," *Annals of Operations Research*, vol. 325, 2023.

[9] C. Walsh and A. Joshi, "Machine learning for sports betting: should model selection be based on accuracy or calibration?," *Machine Learning with Applications*, 2024 (arXiv:2303.06021).

[10] C. Bergmeir and J. M. Benítez, "On the use of cross-validation for time series predictor evaluation," *Information Sciences*, vol. 191, pp. 192–213, 2012.

[11] V. Cerqueira, L. Torgo and I. Mozetič, "Evaluating time series forecasting models: an empirical study on performance estimation methods," *Machine Learning*, vol. 109, pp. 1997–2028, 2020.

[12] A. Niculescu-Mizil and R. Caruana, "Predicting good probabilities with supervised learning," in *Proc. 22nd ICML*, 2005.

[13] scikit-learn developers, "Probability calibration," scikit-learn User Guide. Available: https://scikit-learn.org/stable/modules/calibration.html

[14] J. Nixon, M. Dusenberry, L. Zhang, G. Jerfel and D. Tran, "Measuring calibration in deep learning," in *CVPR Workshops*, 2019 (arXiv:1904.01685).

[15] A. Kumar, P. Liang and T. Ma, "Verified uncertainty calibration," in *NeurIPS*, 2019 (arXiv:1909.10155).

[16] R. Roelofs, N. Cain, J. Shlens and M. C. Mozer, "Mitigating bias in calibration error estimation," in *AISTATS*, 2022 (arXiv:2012.08668).

[17] "Brier score" (Murphy decomposition), Wikipedia. Available: https://en.wikipedia.org/wiki/Brier_score

[18] Real Statistics Using Excel, "Diebold-Mariano test." Available: https://real-statistics.com/time-series-analysis/forecasting-accuracy/diebold-mariano-test/

[19] S. Bhaskar, "Rational adversaries? Evidence from randomised trials in one day cricket," *The Economic Journal*, vol. 119, no. 534, pp. 1–23, 2009.

[20] "List of Indian Premier League seasons and results," "2025 Indian Premier League," "2026 Indian Premier League," Wikipedia. Available: https://en.wikipedia.org/wiki/List_of_Indian_Premier_League_seasons_and_results

[21] Open Data Commons, "Attribution License (ODC-By) v1.0 summary." Available: https://opendatacommons.org/licenses/by/summary/

[22] "Promotion and Regulation of Online Gaming Act, 2025," Wikipedia. Available: https://en.wikipedia.org/wiki/Promotion_and_Regulation_of_Online_Gaming_Act,_2025

[23] Python Software Foundation, "Status of Python versions," Python Developer's Guide. Available: https://devguide.python.org/versions/

[24] Streamlit, "st.testing.v1.AppTest," Streamlit documentation. Available: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest

[25] Microsoft, "Page.pdf," Playwright for Python documentation. Available: https://playwright.dev/python/docs/api/class-page#page-pdf

[26] Cricsheet, "JSON format specification." Available: https://cricsheet.org/format/json/

[27] Vellore Institute of Technology, "Research Integrity Policy." Available: https://vit.ac.in/files/ebooks/Research-Integrity-Policy/files/basic-html/page7.html

<h2>Appendix: AI assistance statement</h2>

This project was built with AI coding assistance (Claude Code), used for scaffolding, literature and fact research, and review. The author reviewed and approved the design decisions (ADR-001…006) and can explain every module; see `docs/viva_prep.md`. Each external fact carries its source and confidence in `docs/research_notes.md`. No code was copied from the IPL projects surveyed for differentiation.
