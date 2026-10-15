<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Sent by | Distinguished by | Details |
|---|---|---|---|---|
| a Participant learns that the public knows of the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | not yet checked | `pxaState` = `Pxa` | [Public Awareness (CP)](../cs.md#public-awareness) |
| a Participant learns that an exploit for the vulnerability is public | `Add(CaseStatus)[target=VulnerabilityCase]` | not yet checked | `pxaState` = `PXa` | [Exploit Public (CX)](../cs.md#exploit-public) |
| a Participant observes attacks that exploit the vulnerability | `Add(CaseStatus)[target=VulnerabilityCase]` | not yet checked | `pxaState` = `pxA` | [Attacks Observed (CA)](../cs.md#attacks-observed) |
| a Vendor becomes aware of the vulnerability | `Add(ParticipantStatus)[target=CaseParticipant]` | a participant (usually: vendor) | `vfState` = `Vf` | [Vendor Awareness (CV)](../cs.md#vendor-awareness) |
| a Vendor has a fix ready | `Add(ParticipantStatus)[target=CaseParticipant]` | a participant (usually: vendor) | `vfState` = `VF` | [Fix Readiness (CF)](../cs.md#fix-readiness) |
| a Deployer has deployed the fix | `Add(ParticipantStatus)[target=CaseParticipant]` | a participant (usually: deployer) | `dState` = `D` | [Fix Deployed (CD)](../cs.md#fix-deployed) |
