# Vultron Protocol Ontology

{% include-markdown "../../includes/not_normative.md" %}

We have developed a non-normative ontology to
describe the Vultron protocol. The ontology is available in
the `ontology` directory.

&nbsp;

&nbsp;

&nbsp;

&nbsp;

=== "Markdown Documentation"

    {% include-markdown "../../includes/ontology_tips.md" %}
    
    ```python exec="true" idprefix=""
    from vultron.scripts.ontology2md import main
    
    ontology = "ontology/vultron_protocol.ttl"
    lines = main(infile=ontology)
    print("\n".join(lines))
    ```

=== "Turtle Ontology"

    {% include-markdown "../../includes/use_protege.md" %}

    ```turtle
    {% include-markdown "../../../ontology/vultron_protocol.ttl" %}
    ```
