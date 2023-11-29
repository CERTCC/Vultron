# Recommended Action Rules for CVD {#sec:cvd_action_rules}

Another application of the [CS model](../process_models/cs/cs_model.md) is to 
recommend actions for coordinating parties in CVD based on the subset of states that
currently apply to a case. What a coordinating party does depends on
their role and where they engage, as shown in the list below. As
described throughout this documentation, the Vultron protocol is intended
to synchronize state transitions across CVD stakeholders. 

## Defining CVD Action Rules

A significant portion of CVD can be formally described as a set of action 
rules based on this model. For our purposes, a CVD action rule consists of:

| Rule Component | Description                                                                             |
|----------------|-----------------------------------------------------------------------------------------|
| State subset   | The subset of states $Q^{cs} \in \mathcal{Q^{cs}}$ from which the action may be taken   |
| Role(s)        | The role(s) capable of performing the action                                            |
| Action         | A summary of the action to be taken                                                     |
| Reason         | The rationale for taking the action                                                     |
| Transition     | The state transition event $\sigma^{cs} \in \Sigma^{cs}$ induced by the action (if any) |


This rule structure follows a common user story pattern:

!!! example "Example CVD Action Rule"
    *When* a case is in a state $q^{cs} \in \mathcal{Q}^{cs}$, a *Role*
    can do *Action* for *Reason*, resulting in the transition event
    $\sigma \in \Sigma$

## CVD Action Suggestion Rules

We define a set of such rules in the table below.

| State Subset<br/>($q^{cs} \in Q^{cs}$) |     Role(s)      | Action                                                 | Reason                                       | $\sigma$ |
|:--------------------------------------:|:----------------:|--------------------------------------------------------|----------------------------------------------|:--------:|
|     $\cdot\cdot\cdot p \cdot\cdot$     |       any        | Terminate any existing embargo                         | Exit criteria met                            |    -     |
|     $\cdot\cdot\cdot\cdot X \cdot$     |       any        | Terminate any existing embargo                         | Exit criteria met                            |    -     |
|     $\cdot\cdot\cdot\cdot\cdot A$      |       any        | Terminate any existing embargo                         | Exit criteria met                            |    -     |
|     $\cdot\cdot\cdot\cdot x\cdot$      |       any        | Monitor for exploit publication                        | SA                                           |    -     |
|     $\cdot\cdot\cdot\cdot X\cdot$      |       any        | Monitor for exploit refinement                         | SA                                           |    -     |
|     $\cdot\cdot\cdot\cdot\cdot a$      |       any        | Monitor for attacks                                    | SA                                           |    -     |
|     $\cdot\cdot\cdot\cdot\cdot A$      |       any        | Monitor for additional attacks                         | SA                                           |    -     |
|            $vfdP\cdot\cdot$            |      vendor      | Pay attention to public reports                        | SA                                           |  **V**   |
|       $\cdot\cdot\cdot pX\cdot$        |       any        | Draw attention to published exploit(s)                 | SA                                           |  **P**   |
|       $\cdot\cdot\cdot PX\cdot$        |       any        | Draw attention to published exploit(s)                 | SA                                           |  **P**   |
|         $\cdot\cdot\cdot pxa$          |       any        | Maintain vigilance for embargo exit criteria           | SA                                           |    -     |
|            $VfdP\cdot\cdot$            |       any        | Escalate vigilance for exploit publication or attacks  | SA, Coordination                             |    -     |
|     $\cdot\cdot\cdot\cdot X\cdot$      |       any        | Publish detection(s) for exploits                      | Detection                                    |  **P**   |
|     $\cdot\cdot\cdot\cdot\cdot A$      |       any        | Publish detection(s) for attacks                       | Detection                                    |  **P**   |
|       $V\cdot\cdot p\cdot\cdot$        |       any        | Publish vul and any mitigations (if no active embargo) | Defense                                      |  **P**   |
|         $\cdot fdP \cdot\cdot$         |       any        | Publish mitigations                                    | Defense                                      |    -     |
|       $\cdot\cdot\cdot pX \cdot$       |       any        | Publish vul and any mitigations                        | Defense                                      |  **P**   |
|       $\cdot\cdot\cdot PX \cdot$       |       any        | Publish vul and any mitigations                        | Defense                                      |  **P**   |
|       $\cdot\cdot\cdot p\cdot A$       |       any        | Publish vul and any mitigations                        | Defense                                      |  **P**   |
|            $VfdP\cdot\cdot$            |       any        | Publish mitigations                                    | Defense                                      |    -     |
|            $vfdp\cdot\cdot$            |       any        | Publish vul and any mitigations (if no vendor exists)  | Defense                                      |  **P**   |
|            $VfdP\cdot\cdot$            |       any        | Ensure any available mitigations are publicized        | Defense                                      |    -     |
|          $Vfd\cdot\cdot\cdot$          |      vendor      | Create fix                                             | Defense                                      |  **F**   |
|            $VFdp\cdot\cdot$            | vendor, deployer | Deploy fix (if possible)                               | Defense                                      |  **D**   |
|            $VFdP\cdot\cdot$            |     deployer     | Deploy fix                                             | Defense                                      |  **D**   |
|             $\cdot fdPxA$              |       any        | Publish exploit code                                   | Defense, Detection                           |  **X**   |
|                $VFdPxa$                |       any        | Publish exploit code                                   | Defense, Detection, Accelerate deployment    |  **X**   |
|          $vfd\cdot\cdot\cdot$          |    non-vendor    | Notify vendor                                          | Coordination                                 |  **V**   |
|       $\cdot\cdot dP\cdot\cdot$        |       any        | Escalate response priority among responding parties    | Coordination                                 |    -     |
|       $\cdot\cdot d\cdot X\cdot$       |       any        | Escalate response priority among responding parties    | Coordination                                 |    -     |
|       $\cdot\cdot d\cdot\cdot A$       |       any        | Escalate response priority among responding parties    | Coordination                                 |    -     |
|          $Vfd\cdot\cdot\cdot$          |    non-vendor    | Encourage vendor to create fix                         | Coordination                                 |    -     |
|         $\cdot\cdot\cdot pxa$          |       any        | Maintain any existing disclosure embargo               | Coordination                                 |    -     |
|           $\cdot\cdot dpxa$            |       any        | Negotiate or establish disclosure embargo              | Coordination                                 |    -     |
|            $VfdP\cdot\cdot$            |    non-vendor    | Escalate fix priority with vendor                      | Coordination                                 |    -     |
|            $Vfdp\cdot\cdot$            |    non-vendor    | Publish vul                                            | Coordination, Motivate vendor to fix         |  **P**   |
|            $Vfdp\cdot\cdot$            |       any        | Publish vul                                            | Coordination, Motivate deployers to mitigate |  **P**   |
|            $VFdp\cdot\cdot$            |    non-vendor    | Encourage vendor to deploy fix (if possible)           | Coordination                                 |    -     |
|                $VFdpxa$                |       any        | Scrutinize appropriateness of initiating a new embargo | Coordination                                 |    -     |
|            $VFdp\cdot\cdot$            |       any        | Publish vul and fix details                            | Accelerate deployment                        |  **P**   |
|            $VFdP\cdot\cdot$            |       any        | Promote fix deployment                                 | Accelerate deployment                        |    -     |
|            $VFDp\cdot\cdot$            |       any        | Publish vulnerability                                  | Document for future reference                |  **P**   |
|            $VFDp\cdot\cdot$            |       any        | Publish vulnerability                                  | Acknowledge contributions                    |  **P**   |
|           $\cdot\cdot fdxa$            |       any        | Discourage exploit publication until at least **F**    | Limit attacker advantage                     |    -     |
|              $vfdpx\cdot$              |     US Gov't     | Initiate VEP (if applicable)                           | Policy                                       |    -     |
|                $VFDPXA$                |       any        | Close case                                             | No action required                           |    -     |
|                $VFDPxa$                |       any        | Close case (unless monitoring for X or A)              | No action required                           |    -     |
|                $VFDPXa$                |       any        | Close case (unless monitoring for A)                   | No action required                           |    -     |
|                $VFDPxA$                |       any        | Close case (unless monitoring for X)                   | No action required                           |    -     |

## CVD Action Suggestion Rules Engine

The rules listed in the table above can be built into a rules engine that
translates each state in the model to a set of suggested CVD actions.
The detailed [case state listings](../../reference/case_states.md) in the 
references section show these rules applied to each $q^{cs}$ state.
