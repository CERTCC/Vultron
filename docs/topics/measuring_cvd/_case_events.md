| Symbol | Event | Belongs to |
|---|---|---|
| $\evR_i$ | Participant $i$ receives the report (report receipt) | Participant $i$ |
| $\evVa_i$ | Participant $i$ decides that the report is valid (report validation) | Participant $i$ |
| $\evAc_i$ | Participant $i$ accepts the report for work (report acceptance) | Participant $i$ |
| $\evC_i$ | Participant $i$ closes the report (report closure) | Participant $i$ |
| $\evJ_i$ | Participant $i$ joins the case (joining) | Participant $i$ |
| $\evS_i$ | Participant $i$ agrees to the active embargo (embargo agreement) | Participant $i$ |
| $\evV_i$ | Vendor $i$ becomes aware of the vul (vendor awareness) | Vendor $i$ |
| $\evF_i$ | Vendor $i$ has a fix ready (fix readiness) | Vendor $i$ |
| $\evD_k$ | Deployer $k$ deploys a fix (fix deployed) | Deployer $k$ |
| $\evP$ | The public becomes aware of the vul (public awareness) | The case |
| $\evX$ | An exploit becomes public (exploit public) | The case |
| $\evA$ | Someone observes attacks that use the vul (attacks observed) | The case |
| $\evE$ | An embargo starts on the case (embargo start) | The case |
| $\evEx$ | The embargo ends (embargo exit) | The case |

The subscript $i$ names one participant or one vendor, and the subscript $k$ names one deployer.
Without a subscript, a symbol means the event for any participant, or for the one vendor of a two-party case.
The notation $a \prec b$ means that event $a$ occurs before event $b$.
On the Measuring CVD pages, hover over an event symbol to see its name and meaning.
