| Symbol | Event | Belongs to |
|---|---|---|
| $\mathbf{R}_i$ | Participant $i$ receives the report (report receipt) | Participant $i$ |
| $\mathbf{Va}_i$ | Participant $i$ decides that the report is valid (report validation) | Participant $i$ |
| $\mathbf{Ac}_i$ | Participant $i$ accepts the report for work (report acceptance) | Participant $i$ |
| $\mathbf{C}_i$ | Participant $i$ closes the report (report closure) | Participant $i$ |
| $\mathbf{J}_i$ | Participant $i$ joins the case (joining) | Participant $i$ |
| $\mathbf{S}_i$ | Participant $i$ agrees to the active embargo (embargo agreement) | Participant $i$ |
| $\mathbf{V}_i$ | Vendor $i$ becomes aware of the vul (vendor awareness) | Vendor $i$ |
| $\mathbf{F}_i$ | Vendor $i$ has a fix ready (fix readiness) | Vendor $i$ |
| $\mathbf{D}_k$ | Deployer $k$ deploys a fix (fix deployment) | Deployer $k$ |
| $\mathbf{P}$ | The public becomes aware of the vul (public awareness) | The case |
| $\mathbf{X}$ | An exploit becomes public (a public exploit) | The case |
| $\mathbf{A}$ | Someone observes attacks that use the vul (observed attacks) | The case |
| $\mathbf{E}$ | An embargo starts on the case (embargo start) | The case |
| $\mathbf{E_x}$ | The embargo ends (embargo exit) | The case |

The subscript $i$ names one participant or one vendor, and the subscript $k$ names one deployer.
Without a subscript, a symbol means the event for any participant, or for the one vendor of a two-party case.
The notation $a \prec b$ means that event $a$ occurs before event $b$.
