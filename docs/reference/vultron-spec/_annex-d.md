## Annex D — Possible Case Histories [I]

Case State has 32 compound states, but far fewer orderings among them are
reachable: a fix cannot be deployed before it is ready, and vendors learn of a
vulnerability no later than the public does. Applying those constraints to the six
case-state events reduces 720 naive orderings to 70 possible case histories.

This annex derives that result. It is informative: this specification does not yet
state the ordering constraints normatively
([§8.3 Case State as a Compound Tuple](tracking-models.md#83-case-state-as-a-compound-tuple)).

{% include-markdown "../../topics/measuring_cvd/possible_histories.md" start="<!-- possible-histories-start -->" end="<!-- possible-histories-end -->" heading-offset=1 %}

!!! info "See also"
    - [CS Transitions](../../topics/process_models/cs/transitions.md) — the
      complete transition grammar the derivation above rests on
