# Sequences of Events and Possible Histories in CVD {#sec:poss_hist}

In §[2](#sec:model){== TODO fix ref to sec:model ==}, we
began by identifying a set of events of interest in
CVD cases. Then we
constructed a state model describing how the occurrence of these events
can interact with each other. In this section, we look at paths through
the resulting state model.

A sequence $s$ is an ordered set of some number of events
$\sigma_i \in \Sigma$ for $1 \leq i \leq n$ and the length of $s$ is
$|s| \stackrel{\mathsf{def}}{=}n$. In other words, a sequence $s$ is an
input string to the DFA defined in
§[2](#sec:model){== TODO fix ref to sec:model ==}.

$$\label{eq:sequence}
    s \stackrel{\mathsf{def}}{=}\left( \sigma_1, \sigma_2, \dots \sigma_n \right)$$

A vulnerability disclosure history $h$ is a sequence $s$ containing one
and only one of each of the symbols in $\Sigma$; by definition
$|h| = |\Sigma| = 6$. Note this is a slight abuse of notation;
$|\textrm{ }|$ represents both sequence length and the cardinality of a
set.

$$\label{eq:history_definition}
\begin{split}
    h \stackrel{\mathsf{def}}{=}s : & \forall \sigma_i, \sigma_j \in s \textrm{ it is the case that } \sigma_i \neq \sigma_j \textrm{ and } \\
    & \forall \sigma_k \in \Sigma \textrm{ it is the case that } \exists \sigma_i \in s \textrm{ such that } \sigma_k = \sigma_i 
\end{split}$$

where two members of the set $\Sigma$ are equal if they are represented
by the same symbol and not equal otherwise. The set of all potential
histories, $\mathcal{H}_p$, is a set of all the sequences $h$ that
satisfy this definition.

## The Possible Histories of CVD

Given that a history $h$ contains all six events $\Sigma$ in some order,
there could be at most 720 ($_{6} \mathrm{P}_{6} = 6! = 720$) potential
histories. However, because of the causal requirements outlined in
[2.4.2](#sec:transition_function){== TODO fix ref to sec:transition_function ==}, we know that Vendor Awareness
($\mathbf{V}$) must precede Fix Ready ($\mathbf{F}$) and that Fix Ready
must precede Fix Deployed ($\mathbf{D}$).

The DFA developed
in §[2](#sec:model){== TODO fix ref to sec:model ==} provides
the mechanism to validate histories: a history $h$ is valid if the
DFA accepts it as a
valid input string. Once this constraint is applied, only 70 possible
histories $h \in \mathcal{H}p$ remain viable. We denote the set of all
such valid histories as $\mathcal{H}$ and have $|\mathcal{H}| = 70$. The
set of possible histories $\mathcal{H}$ corresponds to the 70 allowable
paths through $\mathcal{Q}$ as can be derived from Table
[2.6](#tab:delta_vfdpxa){== TODO fix ref to tab:delta_vfdpxa ==} and Fig.
[2.4](#fig:vfdpxa_map){== TODO fix ref to fig:vfdpxa_map ==}.

The set of possible histories $\mathcal{H}$ is listed exhaustively in
Table [3.1](#tab:possible_histories){== TODO fix ref to tab:possible_histories ==}. Commas and parentheses indicating
ordered sets were omitted from column $h$ for readability. The skill
ranking function on the histories will be defined in
§[4.4](#sec:h_poset_skill){== TODO fix ref to sec:h_poset_skill ==}. The desirability of the history
($\mathbb{D}^h$) will be defined in
§[3.2](#sec:desirability){== TODO fix ref to sec:desirability ==}. The expected frequency of each history
$f_h$ is explained in
§[4.1](#sec:history_frequency_analysis){== TODO fix ref to sec:history_frequency_analysis ==}.

::: {#tab:possible_histories}
<table>
<caption>Possible Histories <span
class="math inline"><em>h</em> ∈ ℋ</span> of CVD</caption>
<thead>
<tr class="header">
<th style="text-align: center;">#</th>
<th style="text-align: center;"><span
class="math inline"><em>h</em></span></th>
<th style="text-align: center;">rank</th>
<th style="text-align: center;"><span
class="math inline">|𝔻<sup><em>h</em></sup>|</span></th>
<th style="text-align: center;"><span
class="math inline"><em>f</em><sub><em>h</em></sub></span></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>D</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>D</strong> ≺ <strong>P</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>D</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>F</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>F</strong> ≺ <strong>P</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>F</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>P</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>P</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>V</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>V</strong> ≺ <strong>P</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>V</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>X</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"></th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td colspan="15" style="text-align: right;"><span>Continued on next
page</span></td>
<td style="text-align: center;"></td>
<td style="text-align: center;"></td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;"></td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>X</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0.0833</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">1</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>P</strong><strong>V</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">0.0417</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">2</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">0.0278</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">3</td>
<td style="text-align: center;"><span
class="math inline"><strong>X</strong><strong>P</strong><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.1250</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">4</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">5</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>A</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0417</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">6</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">7</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">8</td>
<td style="text-align: center;"><span
class="math inline"><strong>X</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0625</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">9</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0104</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">10</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>X</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0417</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">11</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>A</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0104</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">12</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>A</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">13</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>X</strong><strong>P</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0312</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">14</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">12</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0069</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">15</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">13</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">16</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">14</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">17</td>
<td style="text-align: center;"><span
class="math inline"><strong>X</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">15</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0625</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">18</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>X</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">16</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">19</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>D</strong></span></td>
<td style="text-align: center;">17</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0093</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">20</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>X</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">18</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0104</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">21</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>A</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">19</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">22</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">19</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0156</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">23</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>A</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">20</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">24</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>D</strong></span></td>
<td style="text-align: center;">21</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0069</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">25</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">22</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">26</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">23</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0069</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">27</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">24</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">28</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">25</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">29</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">25</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">30</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">26</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">31</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">27</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">32</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>X</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">28</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">33</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>A</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">29</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">34</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>X</strong><strong>P</strong><strong>D</strong></span></td>
<td style="text-align: center;">30</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">35</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">31</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0156</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">36</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">32</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">37</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">33</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">38</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">34</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">39</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">35</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">40</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>P</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">36</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">41</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">37</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">42</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">37</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">43</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">38</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">44</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">39</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">45</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>A</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">40</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">46</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">41</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0078</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">47</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">42</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">48</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">43</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">49</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">44</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">50</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">45</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">51</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>P</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">46</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">52</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">46</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">53</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">47</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">54</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">48</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">55</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">49</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">56</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">50</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0078</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">57</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>A</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">51</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">58</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">52</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">59</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">53</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">60</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">54</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">61</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">55</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">62</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">56</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">63</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">57</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">64</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">58</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">65</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">59</td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">66</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">60</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">67</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>P</strong><strong>A</strong></span></td>
<td style="text-align: center;">61</td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">68</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">61</td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">69</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">62</td>
<td style="text-align: center;">12</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
</tbody>
</table>

: Possible Histories $h \in \mathcal{H}$ of CVD
:::

Now that we have defined the set of histories $\mathcal{H}$, we can
summarize the effects of the transition function $\delta$ developed in
§[2.4](#sec:transitions){== TODO fix ref to sec:transitions ==} (Table
[2.6](#tab:delta_vfdpxa){== TODO fix ref to tab:delta_vfdpxa ==}) as a set of patterns it imposes on all
histories $h \in \mathcal{H}$. First, the causality constraint of the
vendor fix path must hold. $$\label{eq:history_vfd_rule}
\mathbf{V} \prec \mathbf{F} \prec \mathbf{D}$$

Second, the model makes the simplifying assumption that vendors know at
least as much as the public does. In other words, all histories must
meet one of two criteria: either Vendor Awareness precedes Public
Awareness ($\mathbf{P}$) or Vendor Awareness must immediately follow it.

$$\label{eq:history_vp_rule}
    \mathbf{V} \prec \mathbf{P} \textrm{ or } \mathbf{P} \rightarrow \mathbf{V}$$

Third, the model assumes that the public can be informed about a
vulnerability by a public exploit. Therefore, either Public Awareness
precedes Exploit Public ($\mathbf{X}$) or must immediately follow it.

$$\label{eq:history_px_rule}
    \mathbf{P} \prec \mathbf{X} \textrm{ or } \mathbf{X} \rightarrow \mathbf{P}$$

This model is amenable for analysis of CVD, but we need to add a way to express
preferences before it is complete. Thus we are part way through **RQ1**.
§[6.2](#sec:mpcvd){== TODO fix ref to sec:mpcvd ==} will
address how this model can generalize from CVD to MPCVD.

## On the Desirability of Possible Histories {#sec:desirability}

All histories are not equally preferable. Some are quite badfor example,
those in which attacks precede vendor awareness
($\mathbf{A} \prec \mathbf{V}$). Others are very desirablefor example,
those in which fixes are deployed before either an exploit is made
public ($\mathbf{D} \prec \mathbf{X}$) or attacks occur
($\mathbf{D} \prec \mathbf{A}$).

In pursuit of a way to reason about our preferences for some histories
over others, we define the following preference criteria: history $h_a$
is preferred over history $h_b$ if, all else being equal, a more
desirable event $\sigma_1$ precedes a less desirable event $\sigma_2$.
This preference is denoted as $\sigma_1 \prec \sigma_2$. We define the
following ordering preferences:

-   $\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$, or
    $\mathbf{V} \prec \mathbf{A}$---Vendors can take no action to
    produce a fix if they are unaware of the vulnerability. Public
    awareness prior to vendor awareness can cause increased support
    costs for vendors at the same time they are experiencing increased
    pressure to prepare a fix. If public awareness of the vulnerability
    prior to vendor awareness is bad, then a public exploit is at least
    as bad because it encompasses the former and makes it readily
    evident that adversaries have exploit code available for use.
    Attacks prior to vendor awareness represent a complete failure of
    the vulnerability remediation process because they indicate that
    adversaries are far ahead of defenders.

-   $\mathbf{F} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{X}$, or
    $\mathbf{F} \prec \mathbf{A}$---As noted above, the public can take
    no action until a fix is ready. Because public awareness also
    implies adversary awareness, the vendor/adversary race becomes even
    more critical if this condition is not met. When fixes exist before
    exploits or attacks, defenders are better able to protect their
    users.

-   $\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$, or
    $\mathbf{D} \prec \mathbf{A}$---Even better than vendor awareness
    and fix availability prior to public awareness, exploit publication
    or attacks are scenarios in which fixes are deployed prior to one or
    more of those transitions.

-   $\mathbf{P} \prec \mathbf{X}$ or $\mathbf{P} \prec \mathbf{A}$---In
    many cases, fix deployment ($\mathbf{D}$) requires system owners to
    take action, which implies a need for public awareness of the
    vulnerability. We therefore prefer histories in which public
    awareness happens prior to either exploit publication or attacks.

-   $\mathbf{X} \prec \mathbf{A}$---This criteria is not about whether
    exploits should be published or not.[^3] It is about whether we
    should prefer histories in which exploits are published *before*
    attacks happen over histories in which exploits are published
    *after* attacks happen. Our position is that attackers have more
    advantages in the latter case than the former, and therefore we
    should prefer histories in which $\mathbf{X} \prec \mathbf{A}$.

Equation [\[eq:desiderata\]](#eq:desiderata){== TODO fix ref to eq:desiderata ==} formalizes our definition of desired
orderings $\mathbb{D}$. Table
[3.3](#tab:ordered_pairs){== TODO fix ref to tab:ordered_pairs ==} displays all 36 possible orderings of
paired transitions and whether they are considered impossible, required
(as defined by
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"},
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"}, and
[\[eq:history_px_rule\]](#eq:history_px_rule){reference-type="eqref"
reference="eq:history_px_rule"}), desirable (as defined by
[\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"}), or undesirable (the complement of the set
defined in [\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"}).

Before proceeding, we note that our model focuses on the ordering of
transitions, not their timing. We acknowledge that in some situations,
the interval between transitions may be of more interest than merely the
order of those transitions, as a rapid tempo of transitions can alter
the options available to stakeholders in their response. We discuss this
limitation further in §[8](#sec:limitationsAnd){== TODO fix ref to sec:limitationsAnd ==}; however, the following model posits
event sequence timing on a human-oriented timescale measured in minutes
to weeks.

$$\label{eq:desiderata}
\begin{split}
 \mathbb{D} \stackrel{\mathsf{def}}{=}\{
\mathbf{V} \prec \mathbf{P}, \mathbf{V} \prec \mathbf{X}, \mathbf{V} \prec \mathbf{A},\\
\mathbf{F} \prec \mathbf{P}, \mathbf{F} \prec \mathbf{X}, \mathbf{F} \prec \mathbf{A},\\
\mathbf{D} \prec \mathbf{P}, \mathbf{D} \prec \mathbf{X}, \mathbf{D} \prec \mathbf{A},\\
\mathbf{P} \prec \mathbf{X}, \mathbf{P} \prec \mathbf{A}, \mathbf{X} \prec \mathbf{A} \}
\end{split}$$ An element $d \in \mathbb{D}$ is of the form
$\sigma_i \prec \sigma_j$. More formally, $d$ is a relation of the form
$d\left(\sigma_1, \sigma_2, \prec \right)$. $\mathbb{D}$ is a set of
such relations.

##### Some states are preferable to others {#sec:state_preference}

The desiderata in
[\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"} address the preferred ordering of transitions
in CVD histories,
which imply that one should prefer to pass through some states and avoid
others. For example, $\mathbf{V} \prec \mathbf{P}$ implies that we
prefer the paths
${vp} \xrightarrow{\mathbf{V}} {Vp} \xrightarrow{\mathbf{P}} {VP}$ over
the paths
${vp} \xrightarrow{\mathbf{P}} {vP} \xrightarrow{\mathbf{V}} {VP}$. In
Table [3.2](#tab:desired_states){== TODO fix ref to tab:desired_states ==} we adapt those desiderata into specific
subsets of states that should be preferred or avoided if the criteria is
to be met.

::: {#tab:desired_states}
      Event Precedence ($d$)       State Subsets to Prefer   State Subsets to Avoid
  ------------------------------- ------------------------- ------------------------
   $\mathbf{V} \prec \mathbf{X}$           ${Vx}$                    ${vX}$
   $\mathbf{V} \prec \mathbf{A}$           ${Va}$                    ${vA}$
   $\mathbf{V} \prec \mathbf{P}$           ${Vp}$                    ${vP}$
   $\mathbf{P} \prec \mathbf{X}$           ${Px}$                    ${pX}$
   $\mathbf{F} \prec \mathbf{X}$           ${VFx}$                  ${fdX}$
   $\mathbf{P} \prec \mathbf{A}$           ${Pa}$                    ${pA}$
   $\mathbf{F} \prec \mathbf{A}$           ${VFa}$                  ${fdA}$
   $\mathbf{F} \prec \mathbf{P}$           ${VFp}$                  ${fdP}$
   $\mathbf{D} \prec \mathbf{X}$          ${VFDx}$                   ${dX}$
   $\mathbf{X} \prec \mathbf{A}$           ${Xa}$                    ${xA}$
   $\mathbf{D} \prec \mathbf{A}$          ${VFDa}$                   ${dA}$
   $\mathbf{D} \prec \mathbf{P}$          ${VFDp}$                   ${dP}$

  : Desired event precedence mapped to subsets of states
:::

##### A partial order over possible histories

Given the desired preferences over orderings of transitions
($\mathbb{D}$ in
[\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"}), we can construct a partial ordering over
all possible histories $\mathcal{H}$, as defined in
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}. This partial order requires a formal
definition of which desiderata are met by a given history, provided by
[\[eq:desiderata_h\]](#eq:desiderata_h){reference-type="eqref"
reference="eq:desiderata_h"}. $$\label{eq:desiderata_h}
\setlength{\jot}{-1pt} % decrease vertical line spacing inside the following split.
\begin{split}
    \mathbb{D}^{h} \stackrel{\mathsf{def}}{=}\{ d \in \mathbb{D} \textrm{ such that } d \textrm{ is true for } h \} \textrm{, for } h \in \mathcal{H} \\
    \textrm{where } d\left(\sigma_1,\sigma_2,\prec\right) \textrm{ is true for } h \textrm{ if and only if: } \\
    \exists \sigma_i, \sigma_j \in h \textrm{ such that } \sigma_i = \sigma_1 \textrm{ and } \sigma_j = \sigma_2 \textrm{ and } h \textrm{ satisfies the relation } d\left(\sigma_i,\sigma_j,\prec\right)
\end{split}$$

$$\label{eq:ordering}
%    \textrm{The pre-order relation } > \textrm{ is defined over } H \textrm{ as:} \\
   (\mathcal{H},\leq_{H}) \stackrel{\mathsf{def}}{=}\forall h_a, h_b \in \mathcal{H} \textrm{ it is the case that } h_b \leq_{H} h_a \textrm{ if and only if } \mathbb{D}^{h_b} \subseteq \mathbb{D}^{h_a}$$

A visualization of the resulting partially ordered set, or poset,
$(\mathcal{H},\leq_{H})$ is shown as a Hasse Diagram in Figure
[3.1](#fig:poset){== TODO fix ref to fig:poset ==}. Hasse
Diagrams represent the transitive reduction of a poset. Each node in the
diagram represents an individual history $h_a$ from
Table [3.1](#tab:possible_histories){== TODO fix ref to tab:possible_histories ==}; labels correspond to the index of
the table. Figure [3.1](#fig:poset){== TODO fix ref to fig:poset ==} follows
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}, in that $h_a$ is higher in the order than
$h_b$ when $h_a$ contains all the desiderata from $h_b$ and at least one
more. Histories that do not share a path are incomparable (formally, two
histories incomparable if both
$\mathbb{D}^{h_a} \not\supset \mathbb{D}^{h_b}$ and
$\mathbb{D}^{h_a} \not\subset \mathbb{D}^{h_b}$). The diagram flows from
least desirable histories at the bottom to most desirable at the top.
This model satisfies **RQ1**; §[4](#sec:reasoning){== TODO fix ref to sec:reasoning ==} and
§[5](#sec:skill_luck){== TODO fix ref to sec:skill_luck ==}
will demonstrate that the model is amenable to analysis and
§[6.2.2](#sec:mpcvd criteria){== TODO fix ref to sec:mpcvd criteria ==} will lay out the criteria for extending
it to cover MPCVD.

The poset $(\mathcal{H},\leq_{H})$, has as its upper bound
$$h_{69} = (\mathbf{V}, \mathbf{F}, \mathbf{D}, \mathbf{P}, \mathbf{X}, \mathbf{A})$$
while its lower bound is
$$h_{0} = (\mathbf{A}, \mathbf{X}, \mathbf{P}, \mathbf{V}, \mathbf{F}, \mathbf{D}).$$

::: {#tab:ordered_pairs}
                  $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  -------------- -------------- -------------- -------------- -------------- -------------- --------------
   $\mathbf{V}$        \-             r              r              d              d              d
   $\mathbf{F}$        \-             \-             r              d              d              d
   $\mathbf{D}$        \-             \-             \-             d              d              d
   $\mathbf{P}$        u              u              u              \-             d              d
   $\mathbf{X}$        u              u              u              u              \-             d
   $\mathbf{A}$        u              u              u              u              u              \-

  : Ordered pairs of events where ${row} \prec {col}$ (Key: - =
  impossible, r = required, d = desired, u = undesired)
:::

Thus far, we have made no assertions about the relative desirability of
any two desiderata (that is, $d_i,d_j \in \mathbb{D}$ where $i \neq j$).
In the next section we will expand the model to include a partial order
over our desiderata, but for now it is sufficient to note that any
simple ordering over $\mathbb{D}$ would remain compatible with the
partial order given in
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}. In fact, a total order on $\mathbb{D}$ would
create a linear extension of the poset defined here, whereas a partial
order on $\mathbb{D}$ would result in a more constrained poset of which
this poset would be a subset.

![The Lattice of Possible CVD Histories: A Hasse Diagram of the partial
ordering $(\mathcal{H}, \leq_{H})$ of $h_a \in \mathcal{H}$ given
$\mathbb{D}$ as defined in
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}. The diagram flows from least desirable
histories at the bottom to most desirable at the top. Histories that do
not share a path are incomparable. Labels indicate the index (row
number) $a$ of $h_a$ in Table
[3.1](#tab:possible_histories){== TODO fix ref to tab:possible_histories ==}.](figures/h_poset.png){#fig:poset
width="140mm"}

## A Random Walk through CVD States {#sec:random_walk}

To begin to differentiate skill from chance in the next few sections, we
need a model of what the CVD world would look like without any skill. We
cannot derive this model by observation. Even when CVD was first
practiced in the 1980s, some people may have had social, technical, or
organizational skills that transferred to better CVD. We follow the
principle of indifference, as stated in [@pittphilsci16041]:

> **Principle of Indifference:** Let $X = \{x_1,x_2,...,x_n\}$ be a
> partition of the set $W$ of possible worlds into $n$ mutually
> exclusive and jointly exhaustive possibilities. In the absence of any
> relevant evidence pertaining to which cell of the partition is the
> true one, a rational agent should assign an equal initial credence of
> $n$ to each cell.

While the principle of indifference is rather strong, it is inherently
difficult to reason about absolutely skill-less
CVD when the work
of CVD is, by its
nature, a skilled job. Given the set of states and allowable transitions
between them, we can apply the principle of indifference to define a
baseline against which measurement can be meaningful.

##### Estimating State Transition Probabilities

Our assumption is that *transitions* are equally probable, not that
*states* or *histories* are. The events $\sigma \in \Sigma$ trigger
state transitions according to $\delta$ and the histories
$h \in \mathcal{H}$ are paths (traces) through the states. This meets
the definition above because each $\sigma \in \Sigma$ is unique
(mutually exclusive) and $\delta$ defines an exhaustive set of valid
$\sigma$ at each state $q \in \mathcal{Q}$. For example, because
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"} requires $\mathbf{V} \prec \mathbf{F}$
and $\mathbf{F} \prec \mathbf{D}$, only four of the six events in
$\Sigma$ are possible at the beginning of each history at $q_0=vfdpxa$:
$\{\mathbf{V},\mathbf{P},\mathbf{X},\mathbf{A}\}$. Since the principle
of indifference assigns each possible transition event as equally
probable in this model of unskilled CVD, we assign an initial
probability of 0.25 to each possible event. $$\begin{aligned}
    p(\mathbf{V}|q_0) = p(\mathbf{P}|q_0) = p(\mathbf{X}|q_0) = p(\mathbf{A}|q_0) &= 0.25\\
    p(\mathbf{F}|q_0) = p(\mathbf{D}|q_0) &= 0
\end{aligned}$$

From there, we see that the other rules dictate possible transitions
from each subsequent state. For example,
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"} says that any $h$ starting with
$(\mathbf{P})$ must start with $(\mathbf{P},\mathbf{V})$. And
[\[eq:history_px_rule\]](#eq:history_px_rule){reference-type="eqref"
reference="eq:history_px_rule"} requires any $h$ starting with
$(\mathbf{X})$ must proceed through $(\mathbf{X},\mathbf{P})$ and again
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"} gets us to
$(\mathbf{X},\mathbf{P},\mathbf{V})$. Therefore, we expect histories
starting with $(\mathbf{P},\mathbf{V})$ or
$(\mathbf{X},\mathbf{P},\mathbf{V})$ to occur with frequency 0.25 as
well. We can use these transition probabilities to estimate a neutral
baseline expectation of which states would be common if we weren't doing
anything special to coordinate vulnerability disclosures. Specifically,
for each state we set the transition probability to any other state
proportional to the inverse of the outdegree of the state, as shown in
the $p(transition)$ column of Table
[3.4](#tab:allowed_state_transitions){== TODO fix ref to tab:allowed_state_transitions ==}. Real world data is unlikely
to ever reflect such a sad state of affairs (because
CVD *is* happening
after all).

::: {#tab:allowed_state_transitions}
   Start State  Next State(s)                             $p({transition})$   PageRank
  ------------- ---------------------------------------- ------------------- ----------
    $vfdpxa$    $vfdpxA$, $vfdpXa$, $vfdPxa$, $Vfdpxa$          0.250          0.123
    $vfdpxA$    $vfdpXA$, $vfdPxA$, $VfdpxA$                    0.333          0.031
    $vfdpXa$    $vfdPXa$                                        1.000          0.031
    $vfdpXA$    $vfdPXA$                                        1.000          0.013
    $vfdPxa$    $VfdPxa$                                        1.000          0.031
    $vfdPxA$    $VfdPxA$                                        1.000          0.013
    $vfdPXa$    $VfdPXa$                                        1.000          0.031
    $vfdPXA$    $VfdPXA$                                        1.000          0.016
    $Vfdpxa$    $VfdpxA$, $VfdpXa$, $VfdPxa$, $VFdpxa$          0.250          0.031
    $VfdpxA$    $VfdpXA$, $VfdPxA$, $VFdpxA$                    0.333          0.020
    $VfdpXa$    $VfdPXa$                                        1.000          0.011
    $VfdpXA$    $VfdPXA$                                        1.000          0.010
    $VfdPxa$    $VfdPxA$, $VfdPXa$, $VFdPxa$                    0.333          0.037
    $VfdPxA$    $VfdPXA$, $VFdPxA$                              0.500          0.032
    $VfdPXa$    $VfdPXA$, $VFdPXa$                              0.500          0.051
    $VfdPXA$    $VFdPXA$                                        1.000          0.063
    $VFdpxa$    $VFdpxA$, $VFdpXa$, $VFdPxa$, $VFDpxa$          0.250          0.011
    $VFdpxA$    $VFdpXA$, $VFdPxA$, $VFDpxA$                    0.333          0.013
    $VFdpXa$    $VFdPXa$                                        1.000          0.007
    $VFdpXA$    $VFdPXA$                                        1.000          0.008
    $VFdPxa$    $VFdPxA$, $VFdPXa$, $VFDPxa$                    0.333          0.018
    $VFdPxA$    $VFdPXA$, $VFDPxA$                              0.500          0.027
    $VFdPXa$    $VFdPXA$, $VFDPXa$                              0.500          0.037
    $VFdPXA$    $VFDPXA$                                        1.000          0.092
    $VFDpxa$    $VFDpxA$, $VFDpXa$, $VFDPxa$                    0.333          0.007
    $VFDpxA$    $VFDpXA$, $VFDPxA$                              0.500          0.010
    $VFDpXa$    $VFDPXa$                                        1.000          0.007
    $VFDpXA$    $VFDPXA$                                        1.000          0.009
    $VFDPxa$    $VFDPxA$, $VFDPXa$                              0.500          0.012
    $VFDPxA$    $VFDPXA$                                        1.000          0.026
    $VFDPXa$    $VFDPXA$                                        1.000          0.031
    $VFDPXA$    $\emptyset$                                     0.000          0.139

  : Sparse state transition matrix and state PageRank assuming
  equiprobable transitions in a random walk over $\mathcal{S}$ as shown
  Figure [2.4](#fig:vfdpxa_map){== TODO fix ref to fig:vfdpxa_map ==}.)
:::

##### Using PageRank to Estimate Baseline State Probabilities

We use the PageRank algorithm to provide state probability estimates.
The PageRank algorithm provides a probability estimate for each state
based on a Markov random walk of the directed graph of states
[@page1999pagerank]. PageRank assumes each available transition is
equally probable, consistent with our model. To avoid becoming stuck in
dead ends, PageRank adds a *teleport* feature by which walks can, with a
small probability, randomly jump to another node in the graph.

Before proceeding, we need to make a small modification of our state
digraph. Without modification, the PageRank algorithm will tend to be
biased toward later states because the only way to reach the earlier
states is for the algorithm to teleport there. Teleportation chooses
states uniformly, so for example there is only a $1/32$ chance of our
actual start state ($q_0={vfdpxa}$) ever being chosen. Therefore, to
ensure that the early states in our process are fairly represented we
add a single link from ${VFDPXA}$ to ${vfdpxa}$, representing a model
reset whenever the end state is reached. This modification allows
PageRank traversals to wrap around naturally and reach the early states
in the random walk process without needing to rely on teleportation.
With our modification in place, we are ready to compute the PageRank of
each node in the graph. Results are shown in Table
[3.4](#tab:allowed_state_transitions){== TODO fix ref to tab:allowed_state_transitions ==}

