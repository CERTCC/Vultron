<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Participant learns that the public knows of the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | the case manager | not yet checked | `pxaState` = `Pxa` | [Public awareness in a case status](../cs.md#public-awareness) |
| a Participant learns that an exploit for the vulnerability is public | `Add(CaseStatus)[target=VulnerabilityCase]` | the case manager | not yet checked | `pxaState` = `PXa` | [Exploit public in a case status](../cs.md#exploit-public) |
| a Participant observes attacks that exploit the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | the case manager | not yet checked | `pxaState` = `pxA` | [Attacks observed in a case status](../cs.md#attacks-observed) |
| a Vendor becomes aware of the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | the case manager | a participant (usually: vendor) | `vfState` = `Vf` | [Vendor Awareness (CV)](../cs.md#vendor-awareness) |
| a Vendor has a fix ready | `Add(ParticipantStatus)[target=CaseParticipant]` | the case manager | a participant (usually: vendor) | `vfState` = `VF` | [Fix Readiness (CF)](../cs.md#fix-readiness) |
| a Deployer has deployed the fix | `Add(ParticipantStatus)[target=CaseParticipant]` | the case manager | a participant (usually: deployer) | `dState` = `D` | [Fix Deployed (CD)](../cs.md#fix-deployed) |
| a Participant learns that the public knows of the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | the case manager | a participant | `caseStatus.pxaState` = `Pxa` | [Public awareness in a participant status](../cs.md#participant-public-awareness) |
| a Participant learns that an exploit for the vulnerability is public | `Add(ParticipantStatus)[target=CaseParticipant]` | the case manager | a participant | `caseStatus.pxaState` = `PXa` | [Exploit public in a participant status](../cs.md#participant-exploit-public) |
| a Participant observes attacks that exploit the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | the case manager | a participant | `caseStatus.pxaState` = `pxA` | [Attacks observed in a participant status](../cs.md#participant-attacks-observed) |
