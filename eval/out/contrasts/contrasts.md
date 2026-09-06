# Pre-registered pooled contrasts (GEE, cluster-robust; model as fixed effect)

Primary arm = reasoning OFF, six models, rep 0. Robustness arm = reasoning ON, four models. `pp` = model-pooled percentage-point difference (identity link); `OR` = odds ratio (logit link). Cluster = seed × level pair where cells share seeds (1/2/3/4/8; 5/6 by seed), else the image.

## Summary table

| contrast                                | arm                                        | outcome                                             | pp       | pp_ci          | p_pp    | OR        | OR_ci             | p_or    | d10      | d5       |
|:----------------------------------------|:-------------------------------------------|:----------------------------------------------------|:---------|:---------------|:--------|:----------|:------------------|:--------|:---------|:---------|
| gibberish - text                        | reasoning off (6 models)                   | accuracy, all levels                                | +3.0 pp  | [-0.9, +6.8]   | 0.132   | OR 1.24   | [0.93, 1.65]      | 0.138   | nan      | nan      |
| gibberish - text                        | reasoning off (6 models)                   | accuracy, all levels | ink covaried                 | +3.0 pp  | [-0.9, +6.8]   | 0.132   | OR 1.24   | [0.93, 1.65]      | 0.138   | nan      | nan      |
| c02_bar - text                          | reasoning off (6 models)                   | accuracy, all levels                                | +17.6 pp | [+13.4, +21.8] | < 0.001 | OR 8.73   | [5.45, 13.96]     | < 0.001 | nan      | nan      |
| c03_matched - text                      | reasoning off (6 models)                   | accuracy, all levels                                | +10.9 pp | [+7.0, +14.9]  | < 0.001 | OR 2.63   | [1.94, 3.56]      | < 0.001 | nan      | nan      |
| gibberish - text                        | reasoning off (6 models)                   | hit rate (positives)                                | +8.1 pp  | [+1.7, +14.6]  | 0.014   | OR 2.28   | [1.18, 4.43]      | 0.014   | nan      | nan      |
| gibberish - text                        | reasoning off (6 models)                   | hit rate (positives) | ink covaried                 | +8.1 pp  | [+1.7, +14.6]  | 0.014   | OR 2.28   | [1.18, 4.43]      | 0.015   | nan      | nan      |
| c02_bar - text                          | reasoning off (6 models)                   | hit rate (positives)                                | +26.7 pp | [+20.7, +32.6] | < 0.001 | OR 25.95  | [11.37, 59.26]    | < 0.001 | nan      | nan      |
| c03_matched - text                      | reasoning off (6 models)                   | hit rate (positives)                                | +14.1 pp | [+7.7, +20.5]  | < 0.001 | OR 4.33   | [2.17, 8.65]      | < 0.001 | nan      | nan      |
| gibberish - text                        | reasoning off (6 models)                   | false-alarm rate (negatives)                        | +2.2 pp  | [-1.5, +5.9]   | 0.239   | OR 1.29   | [0.86, 1.92]      | 0.218   | nan      | nan      |
| gibberish - text                        | reasoning off (6 models)                   | false-alarm rate (negatives) | ink covaried         | +2.2 pp  | [-1.5, +5.9]   | 0.239   | OR 1.29   | [0.86, 1.92]      | 0.217   | nan      | nan      |
| c02_bar - text                          | reasoning off (6 models)                   | false-alarm rate (negatives)                        | -8.5 pp  | [-13.3, -3.8]  | < 0.001 | OR 0.10   | [0.03, 0.30]      | < 0.001 | nan      | nan      |
| c03_matched - text                      | reasoning off (6 models)                   | false-alarm rate (negatives)                        | -7.8 pp  | [-12.3, -3.3]  | < 0.001 | OR 0.17   | [0.07, 0.37]      | < 0.001 | nan      | nan      |
| hit rate pill - rect (+4/+12 px)        | reasoning off (6 models)                   | matched positive levels                             | -19.4 pp | [-26.2, -12.7] | < 0.001 | OR 0.11   | [0.04, 0.28]      | < 0.001 | nan      | nan      |
| false-alarm rate pill - rect            | reasoning off (6 models)                   | negatives (anchor/−10/−3)                           | -0.7 pp  | [-5.1, +3.7]   | 0.742   | OR 0.86   | [0.34, 2.15]      | 0.741   | nan      | nan      |
| hit rate pill corner-cross - rect +4 px | reasoning off (6 models)                   | ink inside the bounding box but across the curve    | -32.2 pp | [-42.2, -22.3] | < 0.001 | OR 0.02   | [0.00, 0.12]      | < 0.001 | nan      | nan      |
| P(yes) decoy - word-gap negatives       | reasoning off (6 models)                   | false alarms on a separate control vs a fitting run | +13.0 pp | [+9.3, +16.6]  | < 0.001 | OR 3.38   | [2.21, 5.18]      | < 0.001 | nan      | nan      |
| P(yes) word-gap positives - decoy       | reasoning off (6 models)                   | discrimination: spilled word vs separate control    | +68.1 pp | [+63.4, +72.9] | < 0.001 | OR 103.80 | [64.37, 167.39]   | < 0.001 | nan      | nan      |
| decoy FA: incomplete - complete phrase  | reasoning off (6 models)                   | within decoys, gap covaried                         | +26.7 pp | [+22.6, +30.7] | < 0.001 | OR 12.74  | [8.22, 19.73]     | < 0.001 | nan      | nan      |
| decoy FA: gap g12 - g30                 | reasoning off (6 models)                   | within decoys, phrase covaried                      | +1.1 pp  | [-3.7, +5.9]   | 0.649   | OR 1.13   | [0.67, 1.89]      | 0.646   | nan      | nan      |
| decoy FA: gap gTwin - g30               | reasoning off (6 models)                   | within decoys, phrase covaried                      | +8.9 pp  | [+2.4, +15.4]  | 0.008   | OR 2.39   | [1.25, 4.56]      | 0.008   | nan      | nan      |
| script double difference (10−1) − (5−1) | reasoning off (6 models)                   | accuracy                                            | -5.9 pp  | [-10.2, -1.6]  | 0.007   | OR 0.57   | [0.37, 0.86]      | 0.008   | +5.7 pp  | +11.7 pp |
| script double difference (10−1) − (5−1) | reasoning off (6 models)                   | hit rate                                            | -12.6 pp | [-18.2, -7.0]  | < 0.001 | OR 0.30   | [0.17, 0.52]      | < 0.001 | +10.4 pp | +23.0 pp |
| script double difference (10−1) − (5−1) | reasoning off (6 models)                   | false-alarm rate                                    | -0.7 pp  | [-6.6, +5.1]   | 0.805   | OR 0.91   | [0.42, 1.98]      | 0.804   | -1.1 pp  | -0.4 pp  |
| script double difference (10−1) − (5−1) | reasoning off (6 models) | OCR-conditioned | accuracy                                            | -10.9 pp | [-19.8, -2.0]  | 0.016   | OR 0.39   | [0.18, 0.84]      | 0.017   | -1.5 pp  | +9.5 pp  |
| script double difference (10−1) − (5−1) | reasoning off (6 models) | OCR-conditioned | hit rate                                            | -13.8 pp | [-24.4, -3.2]  | 0.011   | OR 0.29   | [0.11, 0.73]      | 0.009   | +4.0 pp  | +17.8 pp |
| script double difference (10−1) − (5−1) | reasoning off (6 models) | OCR-conditioned | false-alarm rate                                    | -0.6 pp  | [-10.5, +9.3]  | 0.898   | OR 0.91   | [0.13, 6.28]      | 0.925   | +0.6 pp  | +1.3 pp  |
| gibberish - text                        | reasoning on (4 models)                    | accuracy, all levels                                | +0.6 pp  | [-3.1, +4.2]   | 0.765   | OR 1.05   | [0.75, 1.47]      | 0.764   | nan      | nan      |
| gibberish - text                        | reasoning on (4 models)                    | accuracy, all levels | ink covaried                 | +0.6 pp  | [-3.1, +4.2]   | 0.765   | OR 1.05   | [0.75, 1.47]      | 0.765   | nan      | nan      |
| c02_bar - text                          | reasoning on (4 models)                    | accuracy, all levels                                | +7.2 pp  | [+3.2, +11.3]  | < 0.001 | OR 2.36   | [1.47, 3.76]      | < 0.001 | nan      | nan      |
| c03_matched - text                      | reasoning on (4 models)                    | accuracy, all levels                                | +6.1 pp  | [+2.5, +9.7]   | < 0.001 | OR 1.99   | [1.38, 2.85]      | < 0.001 | nan      | nan      |
| gibberish - text                        | reasoning on (4 models)                    | hit rate (positives)                                | +0.6 pp  | [-5.2, +6.3]   | 0.850   | OR 1.08   | [0.50, 2.35]      | 0.849   | nan      | nan      |
| gibberish - text                        | reasoning on (4 models)                    | hit rate (positives) | ink covaried                 | +0.6 pp  | [-5.2, +6.3]   | 0.850   | OR 1.08   | [0.49, 2.35]      | 0.850   | nan      | nan      |
| c02_bar - text                          | reasoning on (4 models)                    | hit rate (positives)                                | +10.6 pp | [+4.8, +16.3]  | < 0.001 | OR 4.77   | [1.98, 11.51]     | < 0.001 | nan      | nan      |
| c03_matched - text                      | reasoning on (4 models)                    | hit rate (positives)                                | +5.6 pp  | [+0.4, +10.7]  | 0.035   | OR 2.15   | [1.07, 4.32]      | 0.032   | nan      | nan      |
| gibberish - text                        | reasoning on (4 models)                    | false-alarm rate (negatives)                        | -0.6 pp  | [-5.1, +4.0]   | 0.811   | OR 0.94   | [0.56, 1.58]      | 0.809   | nan      | nan      |
| gibberish - text                        | reasoning on (4 models)                    | false-alarm rate (negatives) | ink covaried         | -0.6 pp  | [-5.1, +4.0]   | 0.811   | OR 0.94   | [0.56, 1.58]      | 0.810   | nan      | nan      |
| c02_bar - text                          | reasoning on (4 models)                    | false-alarm rate (negatives)                        | -3.9 pp  | [-9.5, +1.7]   | 0.176   | OR 0.59   | [0.29, 1.18]      | 0.137   | nan      | nan      |
| c03_matched - text                      | reasoning on (4 models)                    | false-alarm rate (negatives)                        | -6.7 pp  | [-11.7, -1.6]  | 0.010   | OR 0.33   | [0.17, 0.63]      | < 0.001 | nan      | nan      |
| hit rate pill - rect (+4/+12 px)        | reasoning on (4 models)                    | matched positive levels                             | -11.7 pp | [-18.0, -5.3]  | < 0.001 | OR 0.14   | [0.04, 0.54]      | 0.004   | nan      | nan      |
| false-alarm rate pill - rect            | reasoning on (4 models)                    | negatives (anchor/−10/−3)                           | +2.8 pp  | [-2.4, +7.9]   | 0.292   | OR 1.63   | [0.66, 4.04]      | 0.294   | nan      | nan      |
| hit rate pill corner-cross - rect +4 px | reasoning on (4 models)                    | ink inside the bounding box but across the curve    | -21.7 pp | [-30.7, -12.7] | < 0.001 | OR 0.04   | [0.00, 0.28]      | 0.001   | nan      | nan      |
| P(yes) decoy - word-gap negatives       | reasoning on (4 models)                    | false alarms on a separate control vs a fitting run | +6.7 pp  | [+1.5, +11.8]  | 0.012   | OR 1.78   | [1.10, 2.89]      | 0.020   | nan      | nan      |
| P(yes) word-gap positives - decoy       | reasoning on (4 models)                    | discrimination: spilled word vs separate control    | +78.3 pp | [+73.4, +83.3] | < 0.001 | OR 362.87 | [119.30, 1103.71] | < 0.001 | nan      | nan      |
| decoy FA: incomplete - complete phrase  | reasoning on (4 models)                    | within decoys, gap covaried                         | +10.0 pp | [+1.8, +18.2]  | 0.017   | OR 2.17   | [1.12, 4.22]      | 0.021   | nan      | nan      |
| decoy FA: gap g12 - g30                 | reasoning on (4 models)                    | within decoys, phrase covaried                      | +5.0 pp  | [-2.5, +12.5]  | 0.194   | OR 1.60   | [0.76, 3.35]      | 0.216   | nan      | nan      |
| decoy FA: gap gTwin - g30               | reasoning on (4 models)                    | within decoys, phrase covaried                      | +15.8 pp | [+6.4, +25.3]  | 0.001   | OR 3.32   | [1.56, 7.06]      | 0.002   | nan      | nan      |
| script double difference (10−1) − (5−1) | reasoning on (4 models)                    | accuracy                                            | -4.7 pp  | [-9.3, -0.1]   | 0.045   | OR 0.57   | [0.31, 1.03]      | 0.062   | +1.9 pp  | +6.7 pp  |
| script double difference (10−1) − (5−1) | reasoning on (4 models)                    | hit rate                                            | -15.0 pp | [-19.9, -10.1] | < 0.001 | OR 0.10   | [0.04, 0.25]      | < 0.001 | -1.1 pp  | +13.9 pp |
| script double difference (10−1) − (5−1) | reasoning on (4 models)                    | false-alarm rate                                    | -5.6 pp  | [-12.7, +1.6]  | 0.130   | OR 0.46   | [0.16, 1.26]      | 0.130   | -5.0 pp  | +0.6 pp  |

## Detail

### 1. Gibberish vs text (cells 4 vs 1), with solid-bar and matched-bar controls — reasoning off (6 models)

Model-averaged accuracy: c01_base 0.789, c04_gibberish 0.819, c02_bar 0.965, c03_matched 0.898

Per model (accuracy text / gibberish / difference):

| slot       |   c01_base |   c04_gibberish |   diff_pp |
|:-----------|-----------:|----------------:|----------:|
| dsv4       |      0.633 |           0.667 |     3.333 |
| gemini38   |      0.933 |           0.956 |     2.222 |
| glm53flash |      0.878 |           0.867 |    -1.111 |
| gpt56luna  |      0.589 |           0.7   |    11.111 |
| gpt56sol   |      0.844 |           0.867 |     2.222 |
| qwen38     |      0.856 |           0.856 |     0     |

### 2. Rect vs pill (cells 1 vs 7; bounding-box shortcut) — reasoning off (6 models)

Model-averaged hit rate at +4/+12 px: rect 0.706, pill 0.511

Per model hit rate by level:

|                            |   corner |   p12 |    p30 |   p4 |
|:---------------------------|---------:|------:|-------:|-----:|
| ('dsv4', 'c01_base')       |   nan    |  0.2  |   0.27 | 0.33 |
| ('dsv4', 'c07_pill')       |     0    |  0    | nan    | 0    |
| ('gemini38', 'c01_base')   |   nan    |  1    |   1    | 1    |
| ('gemini38', 'c07_pill')   |     0.93 |  1    | nan    | 1    |
| ('glm53flash', 'c01_base') |   nan    |  1    |   1    | 1    |
| ('glm53flash', 'c07_pill') |     0.73 |  1    | nan    | 0.87 |
| ('gpt56luna', 'c01_base')  |   nan    |  0.13 |   0.2  | 0.2  |
| ('gpt56luna', 'c07_pill')  |     0    |  0.07 | nan    | 0.07 |
| ('gpt56sol', 'c01_base')   |   nan    |  0.73 |   0.53 | 0.93 |
| ('gpt56sol', 'c07_pill')   |     0.33 |  0.4  | nan    | 0.4  |
| ('qwen38', 'c01_base')     |   nan    |  0.93 |   0.67 | 1    |
| ('qwen38', 'c07_pill')     |     0.53 |  0.73 | nan    | 0.6  |

### 3. Word-gap vs decoy (grouping; cells 5 vs 6, matched seeds) — reasoning off (6 models)

Model-averaged P(yes): wordgap_neg 0.093, decoy 0.222, wordgap_pos 0.904

Decoy false-alarm rate per model by in-box phrase:

| slot       |   complete |   incomplete |
|:-----------|-----------:|-------------:|
| dsv4       |      0     |        0.133 |
| gemini38   |      0     |        0.067 |
| glm53flash |      0.2   |        0.689 |
| gpt56luna  |      0.044 |        0.067 |
| gpt56sol   |      0.022 |        0.311 |
| qwen38     |      0.267 |        0.867 |

### 4. Script as a double difference: (cell 10 − cell 1) vs (cell 5 − cell 1) — reasoning off (6 models)

Model-averaged accuracy: c01_base 0.789, c05_wordgap 0.906, c10_thai 0.846 (n = 1620)

Per model (accuracy):

| slot       |   c01_base |   c05_wordgap |   c10_thai |   (10-1) |   (5-1) |   double |
|:-----------|-----------:|--------------:|-----------:|---------:|--------:|---------:|
| dsv4       |      0.633 |         0.822 |      0.911 |    0.278 |   0.189 |    0.089 |
| gemini38   |      0.933 |         0.922 |      0.956 |    0.022 |  -0.011 |    0.033 |
| glm53flash |      0.878 |         0.867 |      0.956 |    0.078 |  -0.011 |    0.089 |
| gpt56luna  |      0.589 |         0.933 |      0.711 |    0.122 |   0.344 |   -0.222 |
| gpt56sol   |      0.844 |         0.944 |      0.711 |   -0.133 |   0.1   |   -0.233 |
| qwen38     |      0.856 |         0.944 |      0.833 |   -0.022 |   0.089 |   -0.111 |

### 4. Script as a double difference: (cell 10 − cell 1) vs (cell 5 − cell 1) — reasoning off (6 models) — restricted to items the model transcribed with CER < 0.3

Model-averaged accuracy: c01_base 0.811, c05_wordgap 0.905, c10_thai 0.822 (n = 507)

Per model (accuracy):

| slot       |   c01_base |   c05_wordgap |   c10_thai |   (10-1) |   (5-1) |   double |
|:-----------|-----------:|--------------:|-----------:|---------:|--------:|---------:|
| dsv4       |      0.633 |         0.833 |      0.867 |    0.233 |   0.2   |    0.033 |
| gemini38   |      0.933 |         0.931 |      1     |    0.067 |  -0.002 |    0.069 |
| glm53flash |      0.933 |         0.867 |      1     |    0.067 |  -0.067 |    0.133 |
| gpt56luna  |      0.6   |         0.867 |      0.567 |   -0.033 |   0.267 |   -0.3   |
| gpt56sol   |      0.867 |         0.967 |      0.6   |   -0.267 |   0.1   |   -0.367 |
| qwen38     |      0.9   |         0.967 |      0.897 |   -0.003 |   0.067 |   -0.07  |

### 1. Gibberish vs text (cells 4 vs 1), with solid-bar and matched-bar controls — reasoning on (4 models)

Model-averaged accuracy: c01_base 0.858, c04_gibberish 0.864, c02_bar 0.931, c03_matched 0.919

Per model (accuracy text / gibberish / difference):

| slot       |   c01_base |   c04_gibberish |   diff_pp |
|:-----------|-----------:|----------------:|----------:|
| dsv4       |      0.689 |           0.689 |     0     |
| gemini38   |      0.967 |           0.989 |     2.222 |
| glm53flash |      0.9   |           0.9   |     0     |
| qwen38     |      0.878 |           0.878 |     0     |

### 2. Rect vs pill (cells 1 vs 7; bounding-box shortcut) — reasoning on (4 models)

Model-averaged hit rate at +4/+12 px: rect 0.808, pill 0.692

Per model hit rate by level:

|                            |   corner |   p12 |    p30 |   p4 |
|:---------------------------|---------:|------:|-------:|-----:|
| ('dsv4', 'c01_base')       |   nan    |  0.27 |   0.47 | 0.4  |
| ('dsv4', 'c07_pill')       |     0    |  0    | nan    | 0    |
| ('gemini38', 'c01_base')   |   nan    |  1    |   1    | 1    |
| ('gemini38', 'c07_pill')   |     1    |  1    | nan    | 0.93 |
| ('glm53flash', 'c01_base') |   nan    |  0.93 |   1    | 0.93 |
| ('glm53flash', 'c07_pill') |     0.47 |  1    | nan    | 0.73 |
| ('qwen38', 'c01_base')     |   nan    |  0.93 |   0.93 | 1    |
| ('qwen38', 'c07_pill')     |     1    |  0.93 | nan    | 0.93 |

### 3. Word-gap vs decoy (grouping; cells 5 vs 6, matched seeds) — reasoning on (4 models)

Model-averaged P(yes): wordgap_neg 0.111, decoy 0.178, wordgap_pos 0.961

Decoy false-alarm rate per model by in-box phrase:

| slot       |   complete |   incomplete |
|:-----------|-----------:|-------------:|
| dsv4       |      0.044 |        0.022 |
| gemini38   |      0.111 |        0.2   |
| glm53flash |      0.089 |        0.4   |
| qwen38     |      0.267 |        0.289 |

### 4. Script as a double difference: (cell 10 − cell 1) vs (cell 5 − cell 1) — reasoning on (4 models)

Model-averaged accuracy: c01_base 0.858, c05_wordgap 0.925, c10_thai 0.878 (n = 1080)

Per model (accuracy):

| slot       |   c01_base |   c05_wordgap |   c10_thai |   (10-1) |   (5-1) |   double |
|:-----------|-----------:|--------------:|-----------:|---------:|--------:|---------:|
| dsv4       |      0.689 |         0.922 |      0.722 |    0.033 |   0.233 |   -0.2   |
| gemini38   |      0.967 |         0.944 |      0.989 |    0.022 |  -0.022 |    0.044 |
| glm53flash |      0.9   |         0.911 |      0.856 |   -0.044 |   0.011 |   -0.056 |
| qwen38     |      0.878 |         0.922 |      0.944 |    0.067 |   0.044 |    0.022 |

### 5. Cell 11 (protruding Thai marks) × Thai transcription success — reasoning off

Cell 11 was not in the transcription probe; Thai readability is the model's median CER on cells 10 and 12 (30 items each). Reported per model, never pooled.

| slot       |   acc |   hit |    fa |   thai_median_cer |
|:-----------|------:|------:|------:|------------------:|
| dsv4       | 0.533 | 0.067 | 0     |             0.016 |
| gemini38   | 0.744 | 1     | 0.511 |             0.016 |
| glm53flash | 0.867 | 0.778 | 0.044 |             0.867 |
| gpt56luna  | 0.744 | 0.556 | 0.067 |             0     |
| gpt56sol   | 0.889 | 0.822 | 0.044 |             0     |
| qwen38     | 0.833 | 0.822 | 0.156 |             0.016 |

P(yes) by level:

| slot       |   anchor |   m1 |   m3 |   p3 |   p6 |   p9 |
|:-----------|---------:|-----:|-----:|-----:|-----:|-----:|
| dsv4       |        0 | 0    | 0    | 0.07 | 0.07 | 0.07 |
| gemini38   |        0 | 0.87 | 0.67 | 1    | 1    | 1    |
| glm53flash |        0 | 0.13 | 0    | 0.47 | 0.87 | 1    |
| gpt56luna  |        0 | 0.2  | 0    | 0.4  | 0.53 | 0.73 |
| gpt56sol   |        0 | 0.13 | 0    | 0.47 | 1    | 1    |
| qwen38     |        0 | 0.33 | 0.13 | 0.53 | 0.93 | 1    |
