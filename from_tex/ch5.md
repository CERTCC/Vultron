# Discriminating Skill and Luck in Observations {#sec:skill_luck}

This section defines a method for measuring skillful behavior in
CVD, which we will
need to answer **RQ3** about measuring and evaluating
CVD "in the wild."
The measurement method makes use of all the modeling tools and baselines
established thus far: a comprehensive set of possible histories
$\mathcal{H}$, a partial order over them in terms of the presence of
desired event precedence $(\mathcal{H},\leq_{\mathbb{D}})$, and the *a
priori* expected frequency of each desiderata $d \in \mathbb{D}$.

If we expected to be able to observe all events in all
CVD cases, we could
be assured of having complete histories and could be done here. But the
real world is messy. Not all events $\mathbf{e} \in \mathcal{E}$ are
always observable. We need to develop a way to make sense of what we
*can* observe, regardless of whether we are ever able to capture
complete histories. Continuing towards our goal of measuring efficacy,
we return to considering the balance between skill and luck in
determining our observed outcomes.

## A Measure of Skill in CVD {#sec:skillmodel}

There are many reasons why we might expect our observations to differ
from the expected frequencies we established in
§[4](#sec:reasoning){reference-type="ref" reference="sec:reasoning"}.
Adversaries might be rare, or conversely very well equipped. Vendors
might be very good at releasing fixes faster than adversaries can
discover vulnerabilities and develop exploits for them. System owners
might be diligent at applying patches. (We did say *might*, didn't we?)
Regardless, for now we will lump all of those possible explanations into
a single attribute called "skill."

In a world of pure skill, one would expect that a player could achieve
all 12 desiderata $d \in \mathbb{D}$ consistently. That is, a maximally
skillful player could consistently achieve the specific ordering
$h=(\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A})$
with probability $p_{skill} = 1$.

Thus, we construct the following model: for each of our preferred
orderings $d \in \mathbb{D}$, we model their occurrence due to luck
using the binomial distribution with parameter $p_{luck} = f_d$ taken
from Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}.

Recall that the mean of a binomial distribution is simply the
probability of success $p$, and that the mean of a weighted mixture of
two binomial distributions is simply the weighted mixture of the
individual means. Therefore our model adds a parameter $\alpha_d$ to
represent the weighting between our success rates arising from skill
$p_{skill}$ and luck $p_{luck}$. Because there are 12 desiderata
$d \in \mathbb{D}$, each $d$ will have its own observations and
corresponding value for $\alpha_d$ for each history $h_a$.

$$\label{eq:obs_skill_luck}
    f_d^{obs} = \alpha_d \cdot p_{skill} + (1 - \alpha_d) \cdot p_{luck}$$

Where $f_d^{obs}$ is the observed frequency of successes for desiderata
$d$. Because $p_{skill} = 1$, one of those binomial distributions is
degenerate. Substituting $p_{skill} = 1$, $p_{luck} = f_d$ and solving
Eq. [\[eq:obs_skill_luck\]](#eq:obs_skill_luck){reference-type="ref"
reference="eq:obs_skill_luck"} for $\alpha$, we get

$$\label{eq:alpha_freq}
    \alpha_d \stackrel{\mathsf{def}}{=}\frac{f_d^{obs} - f_d} {1 - f_d}$$

The value of $\alpha_d$ therefore gives us a measure of the observed
skill normalized against the background success rate provided by luck
$f_d$. We denote the set of $\alpha_d$ values for a given history as
$\alpha_\mathbb{D}$. When we refer to the $\alpha_d$ coefficient for a
specific $d$ we will use the specific ordering as the subscript, for
example: $\alpha_{\mathbf{F} \prec \mathbf{P}}$.

$$\alpha_\mathbb{D} \stackrel{\mathsf{def}}{=}\{ \alpha_d : d \in \mathbb{D} \}$$

The concept embodied by $f_d$ is founded on the idea that if attackers
and defenders are in a state of equilibrium, the frequency of observed
outcomes (i.e., how often each desiderata $d$ and history $h$ actually
occurs) will appear consistent with those predicted by chance. So
another way of interpreting $\alpha_d$ is as a measure of the degree to
which a set of observed histories is out of equilibrium.

The following are a few comments on how $\alpha_d$ behaves. Note that
$\alpha_d < 0$ when $0 \leq f_d^{obs} < f_d$ and
$0 \leq \alpha_d \leq 1$ when $f_d \leq f_d^{obs} \leq 1$. The
implication is that a negative value for $\alpha_d$ indicates that our
observed outcomes are actually *worse* than those predicted by pure
luck. In other words, we can only infer positive skill when the
observations are higher ($f_d^{obs} > f_d$). That makes intuitive sense:
if you are likely to win purely by chance, then you have to attribute
most of your wins to luck rather than skill. From Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"},
the largest value for any $d \in \mathbb{D}$ is
$f_{\mathbf{V} \prec \mathbf{A}}=0.75$, implying that even if a vendor
knows about 7 out of 10 vulnerabilities before attacks occur
($f_{\mathbf{V} \prec \mathbf{A}}^{obs} = 0.7$), they are still not
doing better than random.

On the other hand, when $f_d$ is small it is easier to infer skill
should we observe anything better than $f_d$. However, it takes larger
increments of observations $f_d^{obs}$ to infer growth in skill when
$f_d$ is small than when it is large. The smallest $f_d$ we see in Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"}
is $f_{\mathbf{D} \prec \mathbf{P}} = 0.037$.

Inherent to the binomial distribution is the expectation that the
variance of results is lower for both extremes (as $p$ approaches either
0 or 1) and highest at $p=0.5$. Therefore we should generally be less
certain of our observations when they fall in the middle of the
distribution. We address uncertainty further in
§[5.1.2](#sec:uncertainty){reference-type="ref"
reference="sec:uncertainty"}.

### Computing $\alpha_d$ from Observations {#sec:computing_observations}

Although Eq. [\[eq:alpha_freq\]](#eq:alpha_freq){reference-type="eqref"
reference="eq:alpha_freq"} develops a skill metric from observed
frequencies, our observations will in fact be based on counts.
Observations consist of some number of successes $S_d^{obs}$ out of some
number of trials $T$, i.e., $$\label{eq:observed_wins}
    f_d^{obs} = \frac{S_d^{obs}}{T}$$ We likewise revisit our
interpretation of $f_d$. $$\label{eq:lucky_wins}
    f_d = \frac{S_d^{luck}}{T}$$ where $S_d^{luck}$ is the number of
successes at $d$ we would expect due to luck in $T$ trials.

Substituting
[\[eq:observed_wins\]](#eq:observed_wins){reference-type="eqref"
reference="eq:observed_wins"} and
[\[eq:lucky_wins\]](#eq:lucky_wins){reference-type="eqref"
reference="eq:lucky_wins"} into
[\[eq:alpha_freq\]](#eq:alpha_freq){reference-type="eqref"
reference="eq:alpha_freq"}, and recalling that $p_{skill} = 1$ because a
maximally skillful player succeeds in $T$ out of $T$ trials, we get
$$\label{eq:alpha_obs1}
    \alpha_{d} = \frac{\cfrac{S_d^{obs}}{T}-\cfrac{S_d^{luck}}{T}}
    {\cfrac{T}{T}-\cfrac{S_d^l}{T}}$$

Rearranging [\[eq:lucky_wins\]](#eq:lucky_wins){reference-type="eqref"
reference="eq:lucky_wins"} to $S_d^{luck} = {f_d}T$, substituting into
[\[eq:alpha_obs1\]](#eq:alpha_obs1){reference-type="eqref"
reference="eq:alpha_obs1"}, and simplifying, we arrive at:
$$\alpha_{d} = \frac{{S_d^{obs}}-{f_d}T}{(1-{f_d})T}$$ Hence for any of
our desiderata $\mathbb{D}$ we can compute $\alpha_d$ given $S_d^{obs}$
observed successes out of $T$ trials in light of $f_d$ taken from Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"}.

Before we address the data analysis we take a moment to discuss
uncertainty.

### Calculating Measurement Error {#sec:uncertainty}

We have already described the basis of our $f_d^{obs}$ model in the
binomial distribution. While we could just estimate the error in our
observations using the binomial's variance $np(1-p)$, because of
boundary conditions at 0 and 1 we should not assume symmetric error. An
extensive discussion of uncertainty in the binomial distribution is
given in [@brown2001interval].

However, for our purpose the Beta distribution lends itself to this
problem nicely. The Beta distribution is specified by two parameters
$(a,b)$. It is common to interpret $a$ as the number of successes and
$b$ as the number of failures in a set of observations of Bernoulli
trials to estimate the mean of the binomial distribution from which the
observations are drawn. For any given mean, the width of the Beta
distribution narrows as the total number of trials increases.

We use this interpretation to estimate a 95% credible interval for
$f_d^{obs}$ using a Beta distribution with parameters $a = S_d^{obs}$ as
successes and $b = T - S_d^{obs}$ representing the number of failures
using the `scipy.stats.beta.interval` function in Python. This gives us
an upper and lower estimate for $f_d^{obs}$, which we multiply by $T$ to
get upper and lower estimates of $S_d^{obs}$ as in
[\[eq:observed_wins\]](#eq:observed_wins){reference-type="eqref"
reference="eq:observed_wins"}.

## Observing CVD in the Wild {#sec:observation}

As a proof of concept, we apply the model to two data sets: Microsoft's
security updates from 2017 through early 2020 in
§[5.2.1](#sec:ms2017-20){reference-type="ref"
reference="sec:ms2017-20"}, and commodity public exploits from 2015-2019
in §[5.2.2](#sec:commodity_15_19){reference-type="ref"
reference="sec:commodity_15_19"}.

### Microsoft 2017-2020 {#sec:ms2017-20}

We are now ready to proceed with our data analysis. First, we examine
Microsoft's monthly security updates for the period between March 2017
and May 2020, as curated by the Zero Day Initiative blog[^4]. Figure
[\[fig:ms_patched\]](#fig:ms_patched){reference-type="ref"
reference="fig:ms_patched"} shows monthly totals for all vulnerabilities
while
[\[fig:ms_observations\]](#fig:ms_observations){reference-type="ref"
reference="fig:ms_observations"} has monthly observations of
$\mathbf{P} \prec \mathbf{F}$ and $\mathbf{A} \prec \mathbf{F}$. This
data set allowed us to compute the monthly counts for two of our
desiderata, $\mathbf{F} \prec \mathbf{P}$ and
$\mathbf{F} \prec \mathbf{A}$.

<figure>

<figcaption>Publicly Disclosed Microsoft Vulnerabilities
2017-2020</figcaption>
</figure>

*Observations of $\mathbf{F} \prec \mathbf{P}$:* In total, Microsoft
issued patches for 2,694 vulnerabilities; 2,610 (0.97) of them met the
fix-ready-before-public-awareness ($\mathbf{F} \prec \mathbf{P}$)
objective. The mean monthly
$\alpha_{\mathbf{F} \prec \mathbf{P}} = 0.967$, with a range of \[0.878,
1.0\]. We can also use the cumulative data to estimate an overall skill
level for the observation period, which gives us a bit more precision on
$\alpha_{\mathbf{F} \prec \mathbf{P}} = 0.969$ with the 0.95 interval of
\[0.962, 0.975\]. Figure
[\[fig:ms_fapa\]](#fig:ms_fapa){reference-type="ref"
reference="fig:ms_fapa"} shows the trend for both the monthly
observations and the cumulative estimate of
$\alpha_{\mathbf{F} \prec \mathbf{P}}$.

<figure>

<figcaption>Selected Skill Measurement for Publicly Disclosed Microsoft
Vulnerabilities 2017-2020</figcaption>
</figure>

*Observations of $\mathbf{F} \prec \mathbf{A}$:* Meanwhile, 2,655 (0.99)
vulnerabilities met the fix-ready-before-attacks-observed
($\mathbf{F} \prec \mathbf{A}$) criteria. Thus we compute a mean monthly
$\alpha_{\mathbf{F} \prec \mathbf{A}} = 0.976$ with range \[0.893,
1.0\]. The cumulative estimate yields
$\alpha_{\mathbf{F} \prec \mathbf{A}} = 0.986$ with an interval of
\[0.980, 0.989\]. The trend for both is shown in Figure
[\[fig:ms_faat\]](#fig:ms_faat){reference-type="ref"
reference="fig:ms_faat"}.

*Inferring Histories from Observations:* []{#sec:inferring_history
label="sec:inferring_history"} Another possible application of our model
is to estimate unobserved $\alpha_d$ based on the cumulative
observations of both $f_{\mathbf{F} \prec \mathbf{P}}^{obs}$ and
$f_{\mathbf{F} \prec \mathbf{A}}^{obs}$ above. Here we estimate the
frequency $f_d$ of the other $d \in \mathbb{D}$ for this period. Our
procedure is as follows:

1.  For 10000 rounds, draw an $f_d^{est}$ for both
    $\mathbf{F} \prec \mathbf{P}$ and $\mathbf{F} \prec \mathbf{A}$ from
    the Beta distribution with parameters $a=S_d^{obs}$ and
    $b=T-S_d^{obs}$ where $S_d^{obs}$ is 2,610 or 2,655, respectively,
    and $T$ is 2,694.

2.  Assign each $h \in \mathcal{H}$ a weight according to standard joint
    probability based whether it meets both, either, or neither
    $A = \mathbf{F} \prec \mathbf{P}$ and
    $B = \mathbf{F} \prec \mathbf{A}$, respectively.

    $$w_h = 
    \begin{cases}
    p_{AB} = f_A * f_B \textrm{ if } A \textrm{ and } B\\
    p_{Ab} = f_A * f_b \textrm{ if } A \textrm{ and } \lnot B\\
    p_{aB} = f_a * f_B \textrm{ if } \lnot A \textrm{ and } B\\
    p_{ab} = f_a * f_b \textrm{ if } \lnot A \textrm{ and } \lnot B
    \end{cases}$$ where $f_a = 1 - f_A$ and $f_b = 1-f_B$

3.  Draw a weighted sample (with replacement) of size $N = 2,694$ from
    $\mathcal{H}$ according to these weights.

4.  Compute the sample frequency $f_{d}^{sample} = S_d^{sample} / N$ for
    each $d \in \mathbb{D}$, and record the median rank of all histories
    $h$ in the sample.

5.  Compute the estimated frequency as the mean of the sample
    frequencies, namely $f_{d}^{est} = \langle f_{d}^{sample} \rangle$,
    for each $d \in \mathbb{D}$.

6.  Compute $\alpha_d$ from $f_{d}^{est}$ for each $d \in \mathbb{D}$ .

As one might expect given the causal requirement that vendor awareness
precedes fix availability, the estimated values of $\alpha_d$ are quite
high ($0.96-0.99$) for our desiderata involving either $\mathbf{V}$ or
$\mathbf{F}$. We also estimate that $\alpha_d$ is positive---indicating
that we are observing skill over and above mere luck---for all $d$
except $\mathbf{P} \prec \mathbf{A}$ and $\mathbf{X} \prec \mathbf{A}$
which are slightly negative. The results are shown in Figure
[5.1](#fig:ms_estimates){reference-type="ref"
reference="fig:ms_estimates"}. The most common sample median history
rank across all runs is 53, with all sample median history ranks falling
between 51-55. The median rank of possible histories weighted according
to the assumption of equiprobable transitions is 11. We take this as
evidence that the observations are indicative of skill.

![Simulated skill $\alpha_d$ for Microsoft 2017-2020 based on
observations of $\mathbf{F} \prec \mathbf{P}$ and
$\mathbf{F} \prec \mathbf{A}$ over the
period.](figures/ms_estimates.png){#fig:ms_estimates width="100mm"}

### Commodity Exploits 2015-2019 {#sec:commodity_15_19}

Next, we examine the overall trend in $\mathbf{P} \prec \mathbf{X}$ for
commodity exploits between 2015 and 2019. The data set is based on the
National Vulnerability Database [@NVD], in conjunction with the CERT
Vulnerability Data Archive [@certvda]. Between these two databases, a
number of candidate dates are available to represent the date a
vulnerability was made public. We use the minimum of these as the date
for $P$.

To estimate the exploit availability ($\mathbf{X}$) date, we extracted
the date a CVE ID appeared in the git logs for Metasploit [@metasploit]
or Exploitdb [@exploitdb]. When multiple dates were available for a CVE
ID, we kept the earliest. Note that commodity exploit tools such as
Metasploit and Exploitdb represent a non-random sample of the exploits
available to adversaries. These observations should be taken as a lower
bounds estimate of exploit availability, and therefore an upper bounds
estimate of observed desiderata $d$ and skill $\alpha_d$.

During the time period from 2013-2019, the data set contains $N=73,474$
vulnerabilities. Of these, 1,186 were observed to have public exploits
($\mathbf{X}$) prior to the earliest observed vulnerability disclosure
date ($\mathbf{P}$), giving an overall success rate for
$\mathbf{P} \prec \mathbf{X}$ of 0.984. The mean monthly
$\alpha_{\mathbf{P} \prec \mathbf{X}}$ is 0.966 with a range of \[0.873,
1.0\]. The volatility of this measurement appears to be higher than that
of the Microsoft data. The cumulative
$\alpha_{\mathbf{P} \prec \mathbf{X}}$ comes in at 0.968 with an
interval spanning \[0.966, 0.970\]. A chart of the trend is shown in
Fig. [5.2](#fig:ov_paea_2013_2019){reference-type="ref"
reference="fig:ov_paea_2013_2019"}.

![$\alpha_{\mathbf{P} \prec \mathbf{X}}$ for all NVD vulnerabilities
2013-2019 ($\mathbf{X}$ observations based on Metasploit and
ExploitDb)](figures/overall_skill_obs_paea.png){#fig:ov_paea_2013_2019
width="100mm"}

To estimate unobserved $\alpha_d$ from the commodity exploit
observations, we repeat the procedure outlined in
§[\[sec:inferring_history\]](#sec:inferring_history){reference-type="ref"
reference="sec:inferring_history"}. This time, we use $N=73,474$ and
estimate $f^{est}_{d}$ for $\mathbf{P} \prec \mathbf{X}$ with Beta
parameters $a=72,288$ and $b=1186$. As above, we find evidence of skill
in positive estimates of $\alpha_d$ for all desiderata except
$\mathbf{P} \prec \mathbf{A}$ and $\mathbf{X} \prec \mathbf{A}$, which
are negative. The most common sample median history rank in this
estimate is 33 with a range of \[32,33\], which while lower than the
median rank of 53 in the Microsoft estimate from
§[5.2.1](#sec:ms2017-20){reference-type="ref"
reference="sec:ms2017-20"}, still beats the median rank of 11 assuming
uniform event probabilities. The results are shown in Figure
[5.3](#fig:nvd_estimates){reference-type="ref"
reference="fig:nvd_estimates"}.

![Simulated skill $\alpha_d$ for all NVD vulnerabilities 2013-2019 based
on observations of $\mathbf{P} \prec \mathbf{X}$ over the
period.](figures/nvd_estimates.png){#fig:nvd_estimates width="100mm"}

