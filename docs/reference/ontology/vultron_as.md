# Vultron ActivityStreams Ontology

{% include-markdown "../../includes/not_normative.md" %}

We have developed a non-normative extension of the ActivityStreams ontology to
describe the mapping of Vultron to ActivityStreams. The ontology is available in
the `ontology` directory.

&nbsp;

&nbsp;

&nbsp;

=== "Markdown Documentation"

    {% include-markdown "../../includes/ontology_tips.md" %}
    
    ```python exec="true" idprefix=""
    from vultron.scripts.ontology2md import main
    
    ontology = "ontology/vultron_activitystreams.ttl"
    lines = main(infile=ontology)
    print("\n".join(lines))
    ```

=== "Turtle Ontology"

    {% include-markdown "../../includes/use_protege.md" %}

    ```turtle
    {% include-markdown "../../../ontology/vultron_activitystreams.ttl" %}
    ```
