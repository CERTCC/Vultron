# Benchmarking CVD

{% include-markdown "../../includes/not_normative.md" %}

Our [Observational analysis](./observing_skill.md) supports the conclusion that
vulnerability disclosure as currently practiced demonstrates
skill. In both data sets examined, our estimated $\alpha_d$ is positive
for most $d \in \mathbb{D}$. However, there is uncertainty in our
estimates due to the application of the principle of indifference to
unobserved data. This principle assumes a uniform distribution across
event transitions in the absence of CVD, which is an assumption we cannot readily
test. The spread of the estimates in [Observing Skill](./observing_skill.md)
represents the variance in our samples,
not this assumption-based uncertainty. Our interpretation of $\alpha_d$
values near zero is therefore that they reflect an absence of evidence
rather than evidence that skill is absent. While we cannot rule
definitively on luck or low skill, values of $\alpha_d > 0.9$ should
reliably indicate skillful defenders.

If, as seems plausible from the evidence, it turns out that further
observations of $h$ are significantly skewed toward the higher end of
the poset $(\mathcal{H},\leq_{\mathbb{D}})$, then it may be useful to
empirically calibrate our metrics rather than using the *a priori*
frequencies in [Reasoning over Histories](./reasoning_over_histories.md#event-order-frequency-analysis) as our baseline.
This analysis baseline
would provide context on "more skillful than the average for some set of
teams" rather than more skillful than blind luck.

- [CVD Benchmarks](#cvd-benchmarks) discusses this topic, which should be viewed as an examination of what
"reasonable" should mean in the context of a "reasonable baseline expectation."
- [MPCVD](#mpcvd) suggests how the model might be applied to establish benchmarks for
CVD processes involving any number of participants.

## CVD Benchmarks

As described above, in an ideal CVD situation, each observed history would
achieve all 12 desiderata $\mathbb{D}$. Realistically, this is unlikely
to happen. We can at least state that we would prefer that most cases
reach fix ready before attacks ($\mathbf{F} \prec \mathbf{A}$).

Per the Event Frequency table in [Reasoning Over Possible Histories](./reasoning_over_histories.md),
(reproduced below for convenience), even in a world without skill we would
expect $\mathbf{F} \prec \mathbf{A}$ to hold in 37.5% of cases.

{% include-markdown "../../includes/tab_exp_freq.md" %}

This means that $\alpha_{\mathbf{F} \prec \mathbf{A}} < 0$ for anything less than a
0.375 success rate.

!!! tip "Benchmarking CVD"

    In fact, we propose to generalize this for any
    $d \in \mathbb{D}$, such that $\alpha_d$ should be greater than some
    benchmark constant $c_d$:

    $$\alpha_d \geq c_d \geq 0$$

    where $c_d$ is a based on observations of $\alpha_d$ collected across
    some collection of CVD cases.

We propose as a starting point a naïve benchmark of $c_d = 0$. This is a
low bar, as it only requires that CVD actually do better than possible events
which are independent and identically distributed (i.i.d.) within each
case. For example, given a history in which
$(\mathbf{V}, \mathbf{F}, \mathbf{P})$ have already happened (i.e.,
state $q \in VFdPxa$), $\mathbf{D}$, $\mathbf{X}$, or $\mathbf{A}$ are
equally likely to occur next.

!!! note "The i.i.d. assumption may not be warranted."

    We anticipate that event
    ordering probabilities might be conditional on history: for example,
    exploit publication may be more likely when the vulnerability is public
    ($p(\mathbf{X}|q \in \mathcal{Q}_P) > p(\mathbf{X}|q \in \mathcal{Q}_p)$)
    or attacks may be more likely when an exploit is public
    ($p(\mathbf{A}|q \in \mathcal{Q}_{X}) > p(\mathbf{A}|q \in \mathcal{Q}_{x})$).
    If the i.i.d. assumption fails to hold for transition events
    $\sigma \in \Sigma$, observed frequencies of $h \in \mathcal{H}$ could
    differ significantly from the rates predicted by the uniform probability
    assumption behind the Event Frequency table above.

!!! example "Supporting Observations"

    Some example suggestive observations are:

    - There is reason to suspect that only a fraction of vulnerabilities
    ever reach the *exploit public* event $\mathbf{X}$, and fewer still
    reach the *attack* event $\mathbf{A}$. Recent work by the [Cyentia
    Institute](https://library.cyentia.com/report/report_002992.html) found that "5% of all CVEs are both observed within
    organizations AND known to be exploited",
    which suggests that $f_{\mathbf{D} \prec \mathbf{A}} \approx 0.95$.

    - Likewise, $\mathbf{D} \prec \mathbf{X}$ holds in 28 of 70 (0.4) $h$.
    However [Cyentia](https://library.cyentia.com/report/report_002992.html) found that "15.6% of all open vulnerabilities
    observed across organizational assets in our sample have known
    exploits", which suggests that
    $f_{\mathbf{D} \prec \mathbf{X}} \approx 0.844$.

    We might therefore expect to find many vulnerabilities remaining
    indefinitely in $VFDPxa$.

On their own these observations can equally well support the idea that
we are broadly observing skill in vulnerability response, rather than
that the world is biased from some other cause. However, we could choose
a slightly different goal than differentiating skill and "blind luck" as
represented by the i.i.d. assumption. One could aim to measure "more
skillful than the average for some set of teams" rather than more
skillful than blind luck.

If this were the "reasonable" baseline expectation, the
primary limitation is available observations. This model helps overcome
this limitation because it provides a clear path toward collecting
relevant observations. For example, by collecting dates for the six
$\sigma \in \Sigma$ for a large sample of vulnerabilities, we can get
better estimates of the relative frequency of each history $h$ in the
real world. It seems as though better data would serve more to improve
benchmarks rather than change expectations of the role of chance.

!!! example "Interpreting Frequency Observations as Skill Benchmarks"

    As an applied example, if we take the first item in the above list as a
    broad observation of $f_{\mathbf{D} \prec \mathbf{A}} = 0.95$, we can
    plug into

    $$
    \alpha_d \stackrel{\mathsf{def}}{=}\frac{f_d^{obs} - f_d} {1 - f_d}
    $$

    from [Discriminating Skill and Luck](./discriminating_skill_and_luck.md) 
    to get a potential benchmark of
    $\alpha_{\mathbf{D} \prec \mathbf{A}} = 0.94$, which is considerably
    higher than the naïve generic benchmark $\alpha_d = 0$. It also implies
    that we should expect actual observations of histories
    $h \in \mathcal{H}$ to skew toward the 19 $h$ in which
    $\mathbf{D} \prec \mathbf{A}$ nearly 20x as often as the 51 $h$ in which
    $\mathbf{A} \prec \mathbf{D}$. Similarly, if we interpret the second
    item as a broad observation of
    $f_{\mathbf{D} \prec \mathbf{X}} = 0.844$, we can then compute a
    benchmark $\alpha_{\mathbf{D} \prec \mathbf{X}} = 0.81$, which is again
    a significant improvement over the naïve $\alpha_d = 0$ benchmark.
