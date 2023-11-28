# Per-State Details {#appendix:actions}

This appendix gives a brief description of each state
$q \in \mathcal{Q}$ as developed in
§[2](#sec:model){== TODO fix ref to sec:model ==}. See
§[2.3](#sec:states){== TODO fix ref to sec:states ==} for an
explanation of the states in the model. States are presented in the
order given in
[\[eq:all_states\]](#eq:all_states){reference-type="eqref"
reference="eq:all_states"}, which follows a hierarchy implied by
traversal of the $PXA$ submodel found in
[\[eq:pxa_dfa\]](#eq:pxa_dfa){reference-type="eqref"
reference="eq:pxa_dfa"} for each step of the $VFD$ submodel given in
[\[eq:vfd_dfa\]](#eq:vfd_dfa){reference-type="eqref"
reference="eq:vfd_dfa"}. See
§[2.4](#sec:transitions){== TODO fix ref to sec:transitions ==} for an explanation of the state transitions
permitted by the model.

In this appendix, state transitions are cross-referenced by page number
to enable easier navigation through the state descriptions. See
§[3.2](#sec:desirability){== TODO fix ref to sec:desirability ==} for more on transition ordering
desiderata. Where applicable, the specific definitions of *zero day*
matched by a given state are shown based on
§[6.5.1](#sec:zerodays){== TODO fix ref to sec:zerodays ==}.
Additional notes on each state are consistent with
§[6.6](#sec:situation_awareness){== TODO fix ref to sec:situation_awareness ==}. Also included for each state is a
table containing suggested actions as derived from
§[6.8](#sec:cvd_action_rules){== TODO fix ref to sec:cvd_action_rules ==}. The embargo initiation, continuation,
and exit advice in those rules are consistent with the discussion found
in §[6.4](#sec:policy_formalism){== TODO fix ref to sec:policy_formalism ==}. Each state is given its own page to
allow for consistent formatting.

## vfdpxa {#sec:vfdpxa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* N/A

*Next State(s):* $vfdpxA$ (p.), $vfdpXa$ (p.), $vfdPxa$ (p.), $Vfdpxa$
(p.)

*Desiderata met:* N/A

*Desiderata blocked:* N/A

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). Embargo continuation is viable. Embargo
initiation may be appropriate. SSVC v2 Exploitation: None. SSVC v2
Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC v2
Supplier Contacted: No. VEP remains tenable. See Table
[10.1](#tab:vfdpxa_actions){== TODO fix ref to tab:vfdpxa_actions ==} for actions.

::: {#tab:vfdpxa_actions}
  Role         Action                                                  Reason                       Transition
  ------------ ------------------------------------------------------- -------------------------- --------------
  any          Publish vul and any mitigations (if no vendor exists)   Defense                     $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination                $\mathbf{V}$
  any          Monitor for exploit publication                         SA                               \-
  any          Monitor for attacks                                     SA                               \-
  any          Maintain vigilance for embargo exit criteria            SA                               \-
  any          Maintain any existing disclosure embargo                Coordination                     \-
  any          Negotiate or establish disclosure embargo               Coordination                     \-
  any          Discourage exploit publication until at least F         Limit attacker advantage         \-
  US Gov't     Initiate VEP (if applicable)                            Policy                           \-

  : CVD Action Options for State $vfdpxa$
:::

## vfdpxA {#sec:vfdpxA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $vfdpXA$ (p.), $vfdPxA$ (p.), $VfdpxA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1, Zero Day
Attack Type 1, Zero Day Attack Type 2, Zero Day Attack Type 3

*Other notes:* Attack success likely. Embargo is at risk. SSVC v2
Exploitation: Active. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: No. VEP remains tenable.
See Table [10.2](#tab:vfdpxA_actions){== TODO fix ref to tab:vfdpxA_actions ==} for actions.

::: {#tab:vfdpxA_actions}
  Role         Action                                                  Reason               Transition
  ------------ ------------------------------------------------------- ------------------ --------------
  any          Publish detection(s) for attacks                        Detection           $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense             $\mathbf{P}$
  any          Publish vul and any mitigations (if no vendor exists)   Defense             $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination        $\mathbf{V}$
  any          Terminate any existing embargo                          Attacks observed         \-
  any          Monitor for exploit publication                         SA                       \-
  any          Monitor for additional attacks                          SA                       \-
  any          Escalate response priority among responding parties     Coordination             \-
  US Gov't     Initiate VEP (if applicable)                            Policy                   \-

  : CVD Action Options for State $vfdpxA$
:::

## vfdpXa {#sec:vfdpXa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $vfdPXa$ (p.)

*Desiderata met:* $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1, Zero Day
Exploit Type 1, Zero Day Exploit Type 2, Zero Day Exploit Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). Embargo is at risk. Expect
both Vendor and Public awareness imminently. SSVC v2 Exploitation: PoC.
SSVC v2 Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC
v2 Supplier Contacted: No. VEP does not apply. See Table
[10.3](#tab:vfdpXa_actions){== TODO fix ref to tab:vfdpXa_actions ==} for actions.

::: {#tab:vfdpXa_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Publish vul and any mitigations (if no vendor exists)   Defense              $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for attacks                                     SA                        \-
  any          Escalate response priority among responding parties     Coordination              \-

  : CVD Action Options for State $vfdpXa$
:::

## vfdpXA {#sec:vfdpXA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxA$ (p.)

*Next State(s):* $vfdPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1, Zero Day
Exploit Type 1, Zero Day Exploit Type 2, Zero Day Exploit Type 3, Zero
Day Attack Type 1, Zero Day Attack Type 2, Zero Day Attack Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). Embargo is at risk. Expect both Vendor and Public
awareness imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value
Added: Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier
Contacted: No. VEP does not apply. See Table
[10.4](#tab:vfdpXA_actions){== TODO fix ref to tab:vfdpXA_actions ==} for actions.

::: {#tab:vfdpXA_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish detection(s) for attacks                        Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Publish vul and any mitigations (if no vendor exists)   Defense              $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Terminate any existing embargo                          Attacks observed          \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for additional attacks                          SA                        \-
  any          Escalate response priority among responding parties     Coordination              \-

  : CVD Action Options for State $vfdpXA$
:::

## vfdPxa {#sec:vfdPxa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $VfdPxa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{P}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). Embargo is no longer viable. Expect
Vendor awareness imminently. SSVC v2 Exploitation: None. SSVC v2 Public
Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier
Contacted: No. VEP does not apply. See Table
[10.5](#tab:vfdPxa_actions){== TODO fix ref to tab:vfdPxa_actions ==} for actions.

::: {#tab:vfdPxa_actions}
  Role         Action                                                Reason                       Transition
  ------------ ----------------------------------------------------- -------------------------- --------------
  vendor       Pay attention to public reports                       SA                          $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination                $\mathbf{V}$
  any          Terminate any existing embargo                        Vul is public                    \-
  any          Monitor for exploit publication                       SA                               \-
  any          Monitor for attacks                                   SA                               \-
  any          Publish mitigations                                   Defense                          \-
  any          Escalate response priority among responding parties   Coordination                     \-
  any          Discourage exploit publication until at least F       Limit attacker advantage         \-

  : CVD Action Options for State $vfdPxa$
:::

## vfdPxA {#sec:vfdPxA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxA$ (p.)

*Next State(s):* $VfdPxA$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3, Zero Day Attack Type 1, Zero Day Attack Type 2

*Other notes:* Attack success likely. Embargo is no longer viable.
Expect Vendor awareness imminently. SSVC v2 Exploitation: Active. SSVC
v2 Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: No. VEP does not apply. See Table
[10.6](#tab:vfdPxA_actions){== TODO fix ref to tab:vfdPxA_actions ==} for actions.

::: {#tab:vfdPxA_actions}
  Role         Action                                                Reason                 Transition
  ------------ ----------------------------------------------------- -------------------- --------------
  any          Publish detection(s) for attacks                      Detection             $\mathbf{P}$
  vendor       Pay attention to public reports                       SA                    $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination          $\mathbf{V}$
  any          Publish exploit code                                  Defense, Detection    $\mathbf{X}$
  any          Terminate any existing embargo                        Vul is public              \-
  any          Terminate any existing embargo                        Attacks observed           \-
  any          Monitor for exploit publication                       SA                         \-
  any          Monitor for additional attacks                        SA                         \-
  any          Publish mitigations                                   Defense                    \-
  any          Escalate response priority among responding parties   Coordination               \-

  : CVD Action Options for State $vfdPxA$
:::

## vfdPXa {#sec:vfdPXa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpXa$ (p.)

*Next State(s):* $VfdPXa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3, Zero Day Exploit Type 1, Zero Day Exploit Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). Embargo is no longer
viable. Expect Vendor awareness imminently. SSVC v2 Exploitation: PoC.
SSVC v2 Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC
v2 Supplier Contacted: No. VEP does not apply. See Table
[10.7](#tab:vfdPXa_actions){== TODO fix ref to tab:vfdPXa_actions ==} for actions.

::: {#tab:vfdPXa_actions}
  Role         Action                                                Reason                Transition
  ------------ ----------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                     Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                       Defense              $\mathbf{P}$
  vendor       Pay attention to public reports                       SA                   $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                        Vul is public             \-
  any          Terminate any existing embargo                        Exploit is public         \-
  any          Monitor for exploit refinement                        SA                        \-
  any          Monitor for attacks                                   SA                        \-
  any          Publish mitigations                                   Defense                   \-
  any          Escalate response priority among responding parties   Coordination              \-

  : CVD Action Options for State $vfdPXa$
:::

## vfdPXA {#sec:vfdPXA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpXA$ (p.)

*Next State(s):* $VfdPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3, Zero Day Exploit Type 1, Zero Day Exploit Type 2,
Zero Day Attack Type 1, Zero Day Attack Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). Embargo is no longer viable. Expect Vendor
awareness imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value
Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier
Contacted: No. VEP does not apply. See Table
[10.8](#tab:vfdPXA_actions){== TODO fix ref to tab:vfdPXA_actions ==} for actions.

::: {#tab:vfdPXA_actions}
  Role         Action                                                Reason                Transition
  ------------ ----------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                     Detection            $\mathbf{P}$
  any          Publish detection(s) for attacks                      Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                       Defense              $\mathbf{P}$
  vendor       Pay attention to public reports                       SA                   $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                        Vul is public             \-
  any          Terminate any existing embargo                        Exploit is public         \-
  any          Terminate any existing embargo                        Attacks observed          \-
  any          Monitor for exploit refinement                        SA                        \-
  any          Monitor for additional attacks                        SA                        \-
  any          Publish mitigations                                   Defense                   \-
  any          Escalate response priority among responding parties   Coordination              \-

  : CVD Action Options for State $vfdPXA$
:::

## Vfdpxa {#sec:Vfdpxa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $VfdpxA$ (p.), $VfdpXa$ (p.), $VfdPxa$ (p.), $VFdpxa$
(p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Not Defined
(X), Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo
continuation is viable. Embargo initiation may be appropriate. SSVC v2
Exploitation: None. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.9](#tab:Vfdpxa_actions){== TODO fix ref to tab:Vfdpxa_actions ==} for actions.

::: {#tab:Vfdpxa_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Monitor for exploit publication                          SA                                                   \-
  any          Monitor for attacks                                      SA                                                   \-
  any          Maintain vigilance for embargo exit criteria             SA                                                   \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-
  any          Maintain any existing disclosure embargo                 Coordination                                         \-
  any          Negotiate or establish disclosure embargo                Coordination                                         \-
  any          Discourage exploit publication until at least F          Limit attacker advantage                             \-

  : CVD Action Options for State $Vfdpxa$
:::

## VfdpxA {#sec:VfdpxA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxA$ (p.), $Vfdpxa$ (p.)

*Next State(s):* $VfdpXA$ (p.), $VfdPxA$ (p.), $VFdpxA$ (p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Attack Type 2, Zero Day Attack
Type 3

*Other notes:* Attack success likely. CVSS 3.1 remediation level: Not
Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T).
Embargo is at risk. SSVC v2 Exploitation: Active. SSVC v2 Public Value
Added: Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier
Contacted: Yes. VEP does not apply. See Table
[10.10](#tab:VfdpxA_actions){== TODO fix ref to tab:VfdpxA_actions ==} for actions.

::: {#tab:VfdpxA_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Publish detection(s) for attacks                         Detection                                       $\mathbf{P}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  any          Publish vul and any mitigations                          Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Terminate any existing embargo                           Attacks observed                                     \-
  any          Monitor for exploit publication                          SA                                                   \-
  any          Monitor for additional attacks                           SA                                                   \-
  any          Escalate response priority among responding parties      Coordination                                         \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-

  : CVD Action Options for State $VfdpxA$
:::

## VfdpXa {#sec:VfdpXa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $Vfdpxa$ (p.)

*Next State(s):* $VfdPXa$ (p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 2, Zero Day
Exploit Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Not Defined (X), Unavailable (U), Workaround (W), or Temporary
Fix (T). Embargo is at risk. Expect Public awareness imminently. SSVC v2
Exploitation: PoC. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.11](#tab:VfdpXa_actions){== TODO fix ref to tab:VfdpXa_actions ==} for actions.

::: {#tab:VfdpXa_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Draw attention to published exploit(s)                   SA                                              $\mathbf{P}$
  any          Publish detection(s) for exploits                        Detection                                       $\mathbf{P}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  any          Publish vul and any mitigations                          Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Terminate any existing embargo                           Exploit is public                                    \-
  any          Monitor for exploit refinement                           SA                                                   \-
  any          Monitor for attacks                                      SA                                                   \-
  any          Escalate response priority among responding parties      Coordination                                         \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-

  : CVD Action Options for State $VfdpXa$
:::

## VfdpXA {#sec:VfdpXA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $VfdpxA$ (p.)

*Next State(s):* $VfdPXA$ (p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{P}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 2, Zero Day
Exploit Type 3, Zero Day Attack Type 2, Zero Day Attack Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Not Defined (X),
Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo is at
risk. Expect Public awareness imminently. SSVC v2 Exploitation: Active.
SSVC v2 Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC
v2 Supplier Contacted: Yes. VEP does not apply. See Table
[10.12](#tab:VfdpXA_actions){== TODO fix ref to tab:VfdpXA_actions ==} for actions.

::: {#tab:VfdpXA_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Draw attention to published exploit(s)                   SA                                              $\mathbf{P}$
  any          Publish detection(s) for exploits                        Detection                                       $\mathbf{P}$
  any          Publish detection(s) for attacks                         Detection                                       $\mathbf{P}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  any          Publish vul and any mitigations                          Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Terminate any existing embargo                           Exploit is public                                    \-
  any          Terminate any existing embargo                           Attacks observed                                     \-
  any          Monitor for exploit refinement                           SA                                                   \-
  any          Monitor for additional attacks                           SA                                                   \-
  any          Escalate response priority among responding parties      Coordination                                         \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-

  : CVD Action Options for State $VfdpXA$
:::

## VfdPxa {#sec:VfdPxa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $vfdPxa$ (p.), $Vfdpxa$ (p.)

*Next State(s):* $VfdPxA$ (p.), $VfdPXa$ (p.), $VFdPxa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{P}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Not Defined
(X), Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo is
no longer viable. SSVC v2 Exploitation: None. SSVC v2 Public Value
Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier
Contacted: Yes. VEP does not apply. See Table
[10.13](#tab:VfdPxa_actions){== TODO fix ref to tab:VfdPxa_actions ==} for actions.

::: {#tab:VfdPxa_actions}
  Role         Action                                                  Reason                       Transition
  ------------ ------------------------------------------------------- -------------------------- --------------
  vendor       Create fix                                              Defense                     $\mathbf{F}$
  any          Terminate any existing embargo                          Vul is public                    \-
  any          Monitor for exploit publication                         SA                               \-
  any          Monitor for attacks                                     SA                               \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination                 \-
  any          Publish mitigations                                     Defense                          \-
  any          Ensure any available mitigations are publicized         Defense                          \-
  any          Escalate response priority among responding parties     Coordination                     \-
  non-vendor   Encourage vendor to create fix                          Coordination                     \-
  non-vendor   Escalate fix priority with vendor                       Coordination                     \-
  any          Discourage exploit publication until at least F         Limit attacker advantage         \-

  : CVD Action Options for State $VfdPxa$
:::

## VfdPxA {#sec:VfdPxA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdPxA$ (p.), $VfdpxA$ (p.), $VfdPxa$ (p.)

*Next State(s):* $VfdPXA$ (p.), $VFdPxA$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3, Zero Day
Attack Type 2

*Other notes:* Attack success likely. CVSS 3.1 remediation level: Not
Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T).
Embargo is no longer viable. SSVC v2 Exploitation: Active. SSVC v2
Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.14](#tab:VfdPxA_actions){== TODO fix ref to tab:VfdPxA_actions ==} for actions.

::: {#tab:VfdPxA_actions}
  Role         Action                                                  Reason                 Transition
  ------------ ------------------------------------------------------- -------------------- --------------
  vendor       Create fix                                              Defense               $\mathbf{F}$
  any          Publish detection(s) for attacks                        Detection             $\mathbf{P}$
  any          Publish exploit code                                    Defense, Detection    $\mathbf{X}$
  any          Terminate any existing embargo                          Vul is public              \-
  any          Terminate any existing embargo                          Attacks observed           \-
  any          Monitor for exploit publication                         SA                         \-
  any          Monitor for additional attacks                          SA                         \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination           \-
  any          Publish mitigations                                     Defense                    \-
  any          Ensure any available mitigations are publicized         Defense                    \-
  any          Escalate response priority among responding parties     Coordination               \-
  non-vendor   Encourage vendor to create fix                          Coordination               \-
  non-vendor   Escalate fix priority with vendor                       Coordination               \-

  : CVD Action Options for State $VfdPxA$
:::

## VfdPXa {#sec:VfdPXa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $vfdPXa$ (p.), $VfdpXa$ (p.), $VfdPxa$ (p.)

*Next State(s):* $VfdPXA$ (p.), $VFdPXa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3, Zero Day
Exploit Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Not Defined (X), Unavailable (U), Workaround (W), or Temporary
Fix (T). Embargo is no longer viable. SSVC v2 Exploitation: PoC. SSVC v2
Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.15](#tab:VfdPXa_actions){== TODO fix ref to tab:VfdPXa_actions ==} for actions.

::: {#tab:VfdPXa_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  vendor       Create fix                                              Defense              $\mathbf{F}$
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Terminate any existing embargo                          Vul is public             \-
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for attacks                                     SA                        \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination          \-
  any          Publish mitigations                                     Defense                   \-
  any          Ensure any available mitigations are publicized         Defense                   \-
  any          Escalate response priority among responding parties     Coordination              \-
  non-vendor   Encourage vendor to create fix                          Coordination              \-
  non-vendor   Escalate fix priority with vendor                       Coordination              \-

  : CVD Action Options for State $VfdPXa$
:::

## VfdPXA {#sec:VfdPXA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $vfdPXA$ (p.), $VfdpXA$ (p.), $VfdPxA$ (p.),
$VfdPXa$ (p.)

*Next State(s):* $VFdPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3, Zero Day
Exploit Type 2, Zero Day Attack Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Not Defined (X),
Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo is no
longer viable. SSVC v2 Exploitation: Active. SSVC v2 Public Value Added:
Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier Contacted: Yes.
VEP does not apply. See Table
[10.16](#tab:VfdPXA_actions){== TODO fix ref to tab:VfdPXA_actions ==} for actions.

::: {#tab:VfdPXA_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  vendor       Create fix                                              Defense              $\mathbf{F}$
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish detection(s) for attacks                        Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Terminate any existing embargo                          Vul is public             \-
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Terminate any existing embargo                          Attacks observed          \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for additional attacks                          SA                        \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination          \-
  any          Publish mitigations                                     Defense                   \-
  any          Ensure any available mitigations are publicized         Defense                   \-
  any          Escalate response priority among responding parties     Coordination              \-
  non-vendor   Encourage vendor to create fix                          Coordination              \-
  non-vendor   Escalate fix priority with vendor                       Coordination              \-

  : CVD Action Options for State $VfdPXA$
:::

## VFdpxa {#sec:VFdpxa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $Vfdpxa$ (p.)

*Next State(s):* $VFdpxA$ (p.), $VFdpXa$ (p.), $VFdPxa$ (p.), $VFDpxa$
(p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Embargo continuation is viable. Embargo
initiation may be appropriate. Embargo initiation with careful
consideration only. SSVC v2 Exploitation: None. SSVC v2 Public Value
Added: Ampliative. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.17](#tab:VFdpxa_actions){== TODO fix ref to tab:VFdpxa_actions ==} for actions.

::: {#tab:VFdpxa_actions}
  Role               Action                                                              Reason                    Transition
  ------------------ ------------------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                            Defense                  $\mathbf{D}$
  any                Publish vul and any mitigations (if no active embargo)              Defense                  $\mathbf{P}$
  any                Publish vul and fix details                                         Accelerate deployment    $\mathbf{P}$
  any                Monitor for exploit publication                                     SA                            \-
  any                Monitor for attacks                                                 SA                            \-
  any                Maintain vigilance for embargo exit criteria                        SA                            \-
  any                Maintain any existing disclosure embargo                            Coordination                  \-
  any                Negotiate or establish disclosure embargo                           Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)                        Coordination                  \-
  any                Scrutinize appropriateness of initiating a new disclosure embargo   Coordination                  \-

  : CVD Action Options for State $VFdpxa$
:::

## VFdpxA {#sec:VFdpxA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $VfdpxA$ (p.), $VFdpxa$ (p.)

*Next State(s):* $VFdpXA$ (p.), $VFdPxA$ (p.), $VFDpxA$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Attack Type 3

*Other notes:* Attack success likely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is at risk. SSVC v2
Exploitation: Active. SSVC v2 Public Value Added: Ampliative. SSVC v2
Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.18](#tab:VFdpxA_actions){== TODO fix ref to tab:VFdpxA_actions ==} for actions.

::: {#tab:VFdpxA_actions}
  Role               Action                                                   Reason                    Transition
  ------------------ -------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                 Defense                  $\mathbf{D}$
  any                Publish detection(s) for attacks                         Detection                $\mathbf{P}$
  any                Publish vul and any mitigations (if no active embargo)   Defense                  $\mathbf{P}$
  any                Publish vul and any mitigations                          Defense                  $\mathbf{P}$
  any                Publish vul and fix details                              Accelerate deployment    $\mathbf{P}$
  any                Terminate any existing embargo                           Attacks observed              \-
  any                Monitor for exploit publication                          SA                            \-
  any                Monitor for additional attacks                           SA                            \-
  any                Escalate response priority among responding parties      Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)             Coordination                  \-

  : CVD Action Options for State $VFdpxA$
:::

## VFdpXa {#sec:VFdpXa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $VFdpxa$ (p.)

*Next State(s):* $VFdPXa$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is at risk. Expect
Public awareness imminently. SSVC v2 Exploitation: PoC. SSVC v2 Public
Value Added: Ampliative. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.19](#tab:VFdpXa_actions){== TODO fix ref to tab:VFdpXa_actions ==} for actions.

::: {#tab:VFdpXa_actions}
  Role               Action                                                   Reason                    Transition
  ------------------ -------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                 Defense                  $\mathbf{D}$
  any                Draw attention to published exploit(s)                   SA                       $\mathbf{P}$
  any                Publish detection(s) for exploits                        Detection                $\mathbf{P}$
  any                Publish vul and any mitigations (if no active embargo)   Defense                  $\mathbf{P}$
  any                Publish vul and any mitigations                          Defense                  $\mathbf{P}$
  any                Publish vul and fix details                              Accelerate deployment    $\mathbf{P}$
  any                Terminate any existing embargo                           Exploit is public             \-
  any                Monitor for exploit refinement                           SA                            \-
  any                Monitor for attacks                                      SA                            \-
  any                Escalate response priority among responding parties      Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)             Coordination                  \-

  : CVD Action Options for State $VFdpXa$
:::

## VFdpXA {#sec:VFdpXA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $VFdpxA$ (p.)

*Next State(s):* $VFdPXA$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{P}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3, Zero Day Attack
Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is at risk. Expect Public awareness
imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value Added:
Ampliative. SSVC v2 Public Value Added: Precedence. SSVC v2 Report
Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply. See
Table [10.20](#tab:VFdpXA_actions){== TODO fix ref to tab:VFdpXA_actions ==} for actions.

::: {#tab:VFdpXA_actions}
  Role               Action                                                   Reason                    Transition
  ------------------ -------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                 Defense                  $\mathbf{D}$
  any                Draw attention to published exploit(s)                   SA                       $\mathbf{P}$
  any                Publish detection(s) for exploits                        Detection                $\mathbf{P}$
  any                Publish detection(s) for attacks                         Detection                $\mathbf{P}$
  any                Publish vul and any mitigations (if no active embargo)   Defense                  $\mathbf{P}$
  any                Publish vul and any mitigations                          Defense                  $\mathbf{P}$
  any                Publish vul and fix details                              Accelerate deployment    $\mathbf{P}$
  any                Terminate any existing embargo                           Exploit is public             \-
  any                Terminate any existing embargo                           Attacks observed              \-
  any                Monitor for exploit refinement                           SA                            \-
  any                Monitor for additional attacks                           SA                            \-
  any                Escalate response priority among responding parties      Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)             Coordination                  \-

  : CVD Action Options for State $VFdpXA$
:::

## VFdPxa {#sec:VFdPxa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $VfdPxa$ (p.), $VFdpxa$ (p.)

*Next State(s):* $VFdPxA$ (p.), $VFdPXa$ (p.), $VFDPxa$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC v2
Exploitation: None. SSVC v2 Public Value Added: Ampliative. SSVC v2
Public Value Added: Limited. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.21](#tab:VFdPxa_actions){== TODO fix ref to tab:VFdPxa_actions ==} for actions.

::: {#tab:VFdPxa_actions}
  Role       Action                                                Reason                                        Transition
  ---------- ----------------------------------------------------- ------------------------------------------- --------------
  deployer   Deploy fix                                            Defense                                      $\mathbf{D}$
  any        Publish exploit code                                  Defense, Detection, Accelerate deployment    $\mathbf{X}$
  any        Terminate any existing embargo                        Vul is public                                     \-
  any        Monitor for exploit publication                       SA                                                \-
  any        Monitor for attacks                                   SA                                                \-
  any        Escalate response priority among responding parties   Coordination                                      \-
  any        Promote fix deployment                                Accelerate deployment                             \-

  : CVD Action Options for State $VFdPxa$
:::

## VFdPxA {#sec:VFdPxA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $VfdPxA$ (p.), $VFdpxA$ (p.), $VFdPxa$ (p.)

*Next State(s):* $VFdPXA$ (p.), $VFDPxA$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{X}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Other notes:* Attack success likely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC
v2 Exploitation: Active. SSVC v2 Public Value Added: Ampliative. SSVC v2
Public Value Added: Limited. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.22](#tab:VFdPxA_actions){== TODO fix ref to tab:VFdPxA_actions ==} for actions.

::: {#tab:VFdPxA_actions}
  Role       Action                                                Reason                    Transition
  ---------- ----------------------------------------------------- ----------------------- --------------
  deployer   Deploy fix                                            Defense                  $\mathbf{D}$
  any        Publish detection(s) for attacks                      Detection                $\mathbf{P}$
  any        Terminate any existing embargo                        Vul is public                 \-
  any        Terminate any existing embargo                        Attacks observed              \-
  any        Monitor for exploit publication                       SA                            \-
  any        Monitor for additional attacks                        SA                            \-
  any        Escalate response priority among responding parties   Coordination                  \-
  any        Promote fix deployment                                Accelerate deployment         \-

  : CVD Action Options for State $VFdPxA$
:::

## VFdPXa {#sec:VFdPXa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $VfdPXa$ (p.), $VFdpXa$ (p.), $VFdPxa$ (p.)

*Next State(s):* $VFdPXA$ (p.), $VFDPXa$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{A}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is no longer
viable. SSVC v2 Exploitation: PoC. SSVC v2 Public Value Added:
Ampliative. SSVC v2 Public Value Added: Limited. SSVC v2 Report Public:
Yes. SSVC v2 Supplier Contacted: Yes. VEP does not apply. See Table
[10.23](#tab:VFdPXa_actions){== TODO fix ref to tab:VFdPXa_actions ==} for actions.

::: {#tab:VFdPXa_actions}
  Role       Action                                                Reason                    Transition
  ---------- ----------------------------------------------------- ----------------------- --------------
  deployer   Deploy fix                                            Defense                  $\mathbf{D}$
  any        Draw attention to published exploit(s)                SA                       $\mathbf{P}$
  any        Publish detection(s) for exploits                     Detection                $\mathbf{P}$
  any        Publish vul and any mitigations                       Defense                  $\mathbf{P}$
  any        Terminate any existing embargo                        Vul is public                 \-
  any        Terminate any existing embargo                        Exploit is public             \-
  any        Monitor for exploit refinement                        SA                            \-
  any        Monitor for attacks                                   SA                            \-
  any        Escalate response priority among responding parties   Coordination                  \-
  any        Promote fix deployment                                Accelerate deployment         \-

  : CVD Action Options for State $VFdPXa$
:::

## VFdPXA {#sec:VFdPXA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $VfdPXA$ (p.), $VFdpXA$ (p.), $VFdPxA$ (p.),
$VFdPXa$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is no longer viable. SSVC v2 Exploitation:
Active. SSVC v2 Public Value Added: Ampliative. SSVC v2 Public Value
Added: Limited. SSVC v2 Report Public: Yes. SSVC v2 Supplier Contacted:
Yes. VEP does not apply. See Table
[10.24](#tab:VFdPXA_actions){== TODO fix ref to tab:VFdPXA_actions ==} for actions.

::: {#tab:VFdPXA_actions}
  Role       Action                                                Reason                    Transition
  ---------- ----------------------------------------------------- ----------------------- --------------
  deployer   Deploy fix                                            Defense                  $\mathbf{D}$
  any        Draw attention to published exploit(s)                SA                       $\mathbf{P}$
  any        Publish detection(s) for exploits                     Detection                $\mathbf{P}$
  any        Publish detection(s) for attacks                      Detection                $\mathbf{P}$
  any        Publish vul and any mitigations                       Defense                  $\mathbf{P}$
  any        Terminate any existing embargo                        Vul is public                 \-
  any        Terminate any existing embargo                        Exploit is public             \-
  any        Terminate any existing embargo                        Attacks observed              \-
  any        Monitor for exploit refinement                        SA                            \-
  any        Monitor for additional attacks                        SA                            \-
  any        Escalate response priority among responding parties   Coordination                  \-
  any        Promote fix deployment                                Accelerate deployment         \-

  : CVD Action Options for State $VFdPXA$
:::

## VFDpxa {#sec:VFDpxa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. No exploits have been made public.
No attacks have been observed.

*Previous State(s):* $VFdpxa$ (p.)

*Next State(s):* $VFDpxA$ (p.), $VFDpXa$ (p.), $VFDPxa$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Do not initiate a new disclosure embargo,
but an existing embargo may continue. Embargo continuation is viable.
SSVC v2 Exploitation: None. SSVC v2 Public Value Added: Precedence. SSVC
v2 Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not
apply. See Table [10.25](#tab:VFDpxa_actions){== TODO fix ref to tab:VFDpxa_actions ==} for actions.

::: {#tab:VFDpxa_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Monitor for exploit publication                          SA                                    \-
  any    Monitor for attacks                                      SA                                    \-
  any    Maintain vigilance for embargo exit criteria             SA                                    \-
  any    Maintain any existing disclosure embargo                 Coordination                          \-

  : CVD Action Options for State $VFDpxa$
:::

## VFDpxA {#sec:VFDpxA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. No exploits have been made public.
Attacks have been observed.

*Previous State(s):* $VFdpxA$ (p.), $VFDpxa$ (p.)

*Next State(s):* $VFDpXA$ (p.), $VFDPxA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Attack Type 3

*Other notes:* Attack success unlikely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is at risk. SSVC v2
Exploitation: Active. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.26](#tab:VFDpxA_actions){== TODO fix ref to tab:VFDpxA_actions ==} for actions.

::: {#tab:VFDpxA_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Publish detection(s) for attacks                         Detection                        $\mathbf{P}$
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vul and any mitigations                          Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Terminate any existing embargo                           Attacks observed                      \-
  any    Monitor for exploit publication                          SA                                    \-
  any    Monitor for additional attacks                           SA                                    \-

  : CVD Action Options for State $VFDpxA$
:::

## VFDpXa {#sec:VFDpXa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. Exploit(s) have been made public. No
attacks have been observed.

*Previous State(s):* $VFDpxa$ (p.)

*Next State(s):* $VFDPXa$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is at risk. Expect
Public awareness imminently. SSVC v2 Exploitation: PoC. SSVC v2 Public
Value Added: Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier
Contacted: Yes. VEP does not apply. See Table
[10.27](#tab:VFDpXa_actions){== TODO fix ref to tab:VFDpXa_actions ==} for actions.

::: {#tab:VFDpXa_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Draw attention to published exploit(s)                   SA                               $\mathbf{P}$
  any    Publish detection(s) for exploits                        Detection                        $\mathbf{P}$
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vul and any mitigations                          Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Terminate any existing embargo                           Exploit is public                     \-
  any    Monitor for exploit refinement                           SA                                    \-
  any    Monitor for attacks                                      SA                                    \-

  : CVD Action Options for State $VFDpXa$
:::

## VFDpXA {#sec:VFDpXA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. Exploit(s) have been made public.
Attacks have been observed.

*Previous State(s):* $VFDpxA$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{P}$

*Desiderata blocked:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3, Zero Day Attack
Type 3

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is at risk. Expect Public awareness
imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value Added:
Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier Contacted: Yes.
VEP does not apply. See Table
[10.28](#tab:VFDpXA_actions){== TODO fix ref to tab:VFDpXA_actions ==} for actions.

::: {#tab:VFDpXA_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Draw attention to published exploit(s)                   SA                               $\mathbf{P}$
  any    Publish detection(s) for exploits                        Detection                        $\mathbf{P}$
  any    Publish detection(s) for attacks                         Detection                        $\mathbf{P}$
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vul and any mitigations                          Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Terminate any existing embargo                           Exploit is public                     \-
  any    Terminate any existing embargo                           Attacks observed                      \-
  any    Monitor for exploit refinement                           SA                                    \-
  any    Monitor for additional attacks                           SA                                    \-

  : CVD Action Options for State $VFDpXA$
:::

## VFDPxa {#sec:VFDPxa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. No exploits have been made public. No
attacks have been observed.

*Previous State(s):* $VFdPxa$ (p.), $VFDpxa$ (p.)

*Next State(s):* $VFDPxA$ (p.), $VFDPXa$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC v2
Exploitation: None. SSVC v2 Public Value Added: Limited. SSVC v2 Report
Public: Yes. SSVC v2 Supplier Contacted: Yes. VEP does not apply. See
Table [10.29](#tab:VFDPxa_actions){== TODO fix ref to tab:VFDPxa_actions ==} for actions.

::: {#tab:VFDPxa_actions}
  Role   Action                                      Reason                        Transition
  ------ ------------------------------------------- ---------------------------- ------------
  any    Terminate any existing embargo              Vul is public                     \-
  any    Monitor for exploit publication             SA                                \-
  any    Monitor for attacks                         SA                                \-
  any    Close case (unless monitoring for X or A)   No further action required        \-

  : CVD Action Options for State $VFDPxa$
:::

## VFDPxA {#sec:VFDPxA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. No exploits have been made public.
Attacks have been observed.

*Previous State(s):* $VFdPxA$ (p.), $VFDpxA$ (p.), $VFDPxa$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{X} \prec \mathbf{A}$

*Other notes:* Attack success unlikely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC
v2 Exploitation: Active. SSVC v2 Public Value Added: Limited. SSVC v2
Report Public: Yes. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.30](#tab:VFDPxA_actions){== TODO fix ref to tab:VFDPxA_actions ==} for actions.

::: {#tab:VFDPxA_actions}
  Role   Action                                 Reason                         Transition
  ------ -------------------------------------- ---------------------------- --------------
  any    Publish detection(s) for attacks       Detection                     $\mathbf{P}$
  any    Terminate any existing embargo         Vul is public                      \-
  any    Terminate any existing embargo         Attacks observed                   \-
  any    Monitor for exploit publication        SA                                 \-
  any    Monitor for additional attacks         SA                                 \-
  any    Close case (unless monitoring for X)   No further action required         \-

  : CVD Action Options for State $VFDPxA$
:::

## VFDPXa {#sec:VFDPXa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. Exploit(s) have been made public. No
attacks have been observed.

*Previous State(s):* $VFdPXa$ (p.), $VFDpXa$ (p.), $VFDPxa$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is no longer
viable. SSVC v2 Exploitation: PoC. SSVC v2 Public Value Added: Limited.
SSVC v2 Report Public: Yes. SSVC v2 Supplier Contacted: Yes. VEP does
not apply. See Table [10.31](#tab:VFDPXa_actions){== TODO fix ref to tab:VFDPXa_actions ==} for actions.

::: {#tab:VFDPXa_actions}
  Role   Action                                   Reason                         Transition
  ------ ---------------------------------------- ---------------------------- --------------
  any    Draw attention to published exploit(s)   SA                            $\mathbf{P}$
  any    Publish detection(s) for exploits        Detection                     $\mathbf{P}$
  any    Publish vul and any mitigations          Defense                       $\mathbf{P}$
  any    Terminate any existing embargo           Vul is public                      \-
  any    Terminate any existing embargo           Exploit is public                  \-
  any    Monitor for exploit refinement           SA                                 \-
  any    Monitor for attacks                      SA                                 \-
  any    Close case (unless monitoring for A)     No further action required         \-

  : CVD Action Options for State $VFDPXa$
:::

## VFDPXA {#sec:VFDPXA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. Exploit(s) have been made public.
Attacks have been observed.

*Previous State(s):* $VFdPXA$ (p.), $VFDpXA$ (p.), $VFDPxA$ (p.),
$VFDPXa$ (p.)

*Next State(s):* N/A

*Desiderata met:* N/A

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is no longer viable. SSVC v2 Exploitation:
Active. SSVC v2 Public Value Added: Limited. SSVC v2 Report Public: Yes.
SSVC v2 Supplier Contacted: Yes. VEP does not apply. See Table
[10.32](#tab:VFDPXA_actions){== TODO fix ref to tab:VFDPXA_actions ==} for actions.

::: {#tab:VFDPXA_actions}
  Role   Action                                   Reason                         Transition
  ------ ---------------------------------------- ---------------------------- --------------
  any    Draw attention to published exploit(s)   SA                            $\mathbf{P}$
  any    Publish detection(s) for exploits        Detection                     $\mathbf{P}$
  any    Publish detection(s) for attacks         Detection                     $\mathbf{P}$
  any    Publish vul and any mitigations          Defense                       $\mathbf{P}$
  any    Terminate any existing embargo           Vul is public                      \-
  any    Terminate any existing embargo           Exploit is public                  \-
  any    Terminate any existing embargo           Attacks observed                   \-
  any    Monitor for exploit refinement           SA                                 \-
  any    Monitor for additional attacks           SA                                 \-
  any    Close case                               No further action required         \-

  : CVD Action Options for State $VFDPXA$
:::

