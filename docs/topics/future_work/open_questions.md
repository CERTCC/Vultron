# Open questions

This page collects every unresolved design question in the Future Work section.
Each one also appears inline on the page where it first matters, so a reader who meets a gap in context sees it there rather than only here.

An entry on this page means one of two things.
Either the design decision has not been made, or it has been made for the prototype and does not bind a production deployment.
Neither means the capability has been ruled out.

Most of these questions concern how Vultron's ActivityStreams 2.0 (AS2) vocabulary travels between organizations, and what a production deployment owes that the prototype does not.

---

## Federation

{% include-markdown "./_oq-activitypub-depth.md" %}

{% include-markdown "./_oq-actor-discovery.md" %}

{% include-markdown "./_oq-vocabulary-governance.md" %}

---

## Cases and participants

{% include-markdown "./_oq-case-manager-migration.md" %}

{% include-markdown "./_oq-report-object-model.md" %}

{% include-markdown "./_oq-participant-routing.md" %}

---

## History and delivery

{% include-markdown "./_oq-distributed-ledger.md" %}

{% include-markdown "./_oq-fanout-ordering.md" %}

{% include-markdown "./_oq-delivery-receipts.md" %}

---

## Security

{% include-markdown "./_oq-message-security.md" %}
