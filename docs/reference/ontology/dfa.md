# Deterministic Finite Automata Ontology

{% include-markdown "../../includes/not_normative.md" %}

We have developed a non-normative ontology that defines the parts of a
Deterministic Finite Automata (DFA). The ontology is available in the `ontology`
directory.
This ontology is used to describe the DFAs that underpin the
the Vultron protocol.

&nbsp;

&nbsp;

&nbsp;

=== "Markdown Documentation"

    {% include-markdown "../../includes/ontology_tips.md" %}

    ```python exec="true" idprefix=""
    from vultron.scripts.ontology2md import main
    
    ontology = "ontology/deterministicfiniteautomata.ttl"
    lines = main(infile=ontology)
    print("\n".join(lines))
    ```

=== "Turtle Ontology"

    {% include-markdown "../../includes/use_protege.md" %}

    ```turtle
    {% include-markdown "../../../ontology/deterministicfiniteautomata.ttl" %}
    ```
