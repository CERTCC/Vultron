# Discriminating Skill and Luck in Observations

{% include-markdown "../../includes/not_normative.md" %}

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

## A Measure of Skill in CVD

There are many reasons why we might expect our observations to differ
from the expected frequencies we established in
§[4](#sec:reasoning){== TODO fix ref to sec:reasoning ==}.
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
from Table [4.1](#tab:event_freq){== TODO fix ref to tab:event_freq ==}.

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
Eq. [\[eq:obs_skill_luck\]](#eq:obs_skill_luck){== TODO fix ref to eq:obs_skill_luck ==} for $\alpha$, we get

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
[4.1](#tab:event_freq){== TODO fix ref to tab:event_freq ==},
the largest value for any $d \in \mathbb{D}$ is
$f_{\mathbf{V} \prec \mathbf{A}}=0.75$, implying that even if a vendor
knows about 7 out of 10 vulnerabilities before attacks occur
($f_{\mathbf{V} \prec \mathbf{A}}^{obs} = 0.7$), they are still not
doing better than random.

On the other hand, when $f_d$ is small it is easier to infer skill
should we observe anything better than $f_d$. However, it takes larger
increments of observations $f_d^{obs}$ to infer growth in skill when
$f_d$ is small than when it is large. The smallest $f_d$ we see in Table
[4.1](#tab:event_freq){== TODO fix ref to tab:event_freq ==}
is $f_{\mathbf{D} \prec \mathbf{P}} = 0.037$.

Inherent to the binomial distribution is the expectation that the
variance of results is lower for both extremes (as $p$ approaches either
0 or 1) and highest at $p=0.5$. Therefore we should generally be less
certain of our observations when they fall in the middle of the
distribution. We address uncertainty further in
§[5.1.2](#sec:uncertainty){== TODO fix ref to sec:uncertainty ==}.

### Computing $\alpha_d$ from Observations

Although Eq. [\[eq:alpha_freq\]](#eq:alpha_freq){== TODO fix ref to eq:alpha_freq ==} develops a skill metric from observed
frequencies, our observations will in fact be based on counts.
Observations consist of some number of successes $S_d^{obs}$ out of some
number of trials $T$, i.e., $$\label{eq:observed_wins}
    f_d^{obs} = \frac{S_d^{obs}}{T}$$ We likewise revisit our
interpretation of $f_d$. $$\label{eq:lucky_wins}
    f_d = \frac{S_d^{luck}}{T}$$ where $S_d^{luck}$ is the number of
successes at $d$ we would expect due to luck in $T$ trials.

Substituting
[\[eq:observed_wins\]](#eq:observed_wins){== TODO fix ref to eq:observed_wins ==} and
[\[eq:lucky_wins\]](#eq:lucky_wins){== TODO fix ref to eq:lucky_wins ==} into
[\[eq:alpha_freq\]](#eq:alpha_freq){== TODO fix ref to eq:alpha_freq ==}, and recalling that $p_{skill} = 1$ because a
maximally skillful player succeeds in $T$ out of $T$ trials, we get
$$\label{eq:alpha_obs1}
    \alpha_{d} = \frac{\cfrac{S_d^{obs}}{T}-\cfrac{S_d^{luck}}{T}}
    {\cfrac{T}{T}-\cfrac{S_d^l}{T}}$$

Rearranging [\[eq:lucky_wins\]](#eq:lucky_wins){== TODO fix ref to eq:lucky_wins ==} to $S_d^{luck} = {f_d}T$, substituting into
[\[eq:alpha_obs1\]](#eq:alpha_obs1){== TODO fix ref to eq:alpha_obs1 ==}, and simplifying, we arrive at:
$$\alpha_{d} = \frac{{S_d^{obs}}-{f_d}T}{(1-{f_d})T}$$ Hence for any of
our desiderata $\mathbb{D}$ we can compute $\alpha_d$ given $S_d^{obs}$
observed successes out of $T$ trials in light of $f_d$ taken from Table
[4.1](#tab:event_freq){== TODO fix ref to tab:event_freq ==}.

Before we address the data analysis we take a moment to discuss
uncertainty.

### Calculating Measurement Error

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
[\[eq:observed_wins\]](#eq:observed_wins){== TODO fix ref to eq:observed_wins ==}.

period.](figures/nvd_estimates.png)
