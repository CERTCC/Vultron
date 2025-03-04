#!/usr/bin/env python
"""
Provides helpers to generate a markdown summary of an OWL ontology
"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import os

import owlready2

seen_things = set()


def _listify(x):
    # sometimes the things in x are redundant
    # so we need to make sure they are unique
    return list(set([_linkify(str(y)) for y in x]))


def thing2md(thing: owlready2.ThingClass, hdrlevel: int = 2) -> list[str]:
    """
    Turns an owlready2.ThingClass into a markdown blob for inclusion in a
    markdown file.

    Args:
        thing: an owlready2.ThingClass
        hdrlevel: the markdown header level to use for the thing name

    Returns:
        a list of strings that can be joined with newlines to create a markdown
        blob
    """
    lines = []
    hdr = "#" * hdrlevel

    lines.append(f"{hdr} {thing.name}")
    lines.append("")

    comment = " ".join(thing.comment)
    comment = _linkify(comment)

    if comment:
        lines.append(comment)
        lines.append("")

    lines.append("| Attribute | Value |")
    lines.append("| --------- | ----- |")

    data = {
        "Name": thing.name,
        "IRI": thing.iri,
        "Description": comment,
    }

    if len(thing.equivalent_to):
        data["Equivalent To"] = "<br/>".join(_listify(thing.equivalent_to))

    if len(thing.is_a):
        data["Superclasses"] = "<br/>".join(_listify(thing.is_a))

    # add properties for Thing class
    try:
        properties = list(thing.get_properties())
    except (TypeError, AttributeError):
        properties = []

    if len(properties):
        data["Properties"] = "<br/>".join(_listify(properties))

    # add domains and ranges for properties
    # not all things have domains and ranges
    try:
        if len(thing.domain):
            data["Domain"] = "<br/>".join(_listify(thing.domain))
    except AttributeError:
        pass

    try:
        if len(thing.range):
            data["Range"] = "<br/>".join(_listify(thing.range))
    except AttributeError:
        pass

    subclasses = list(thing.subclasses())
    if len(subclasses):
        data["Subclasses"] = "<br/>".join(_listify(subclasses))

    # we have to be careful about pipe characters in the values
    mkrow = lambda k, v: f"| {k} | {v.replace('|',' or ')} |"

    # turn data into rows
    for k, v in data.items():
        lines.append(mkrow(k, v))

    return lines


def _linkify(line: str) -> str:
    """
    Turns a line of text into a markdown link if the line contains a known
    thing name.

    Args:
        line: a line of text

    Returns:
        a markdown linkified line of text
    """

    # split the line into tokens
    parts = line.split(",")
    parts = [p.strip() for p in parts]

    # for each token, if the token is in seen things, link the token
    for i, part in enumerate(parts):
        if part in seen_things:
            parts[i] = f"[{part}](#{part.lower()})"
        else:
            # if we didn't replace anything see if the seen thing is in the line
            longest_match = ""
            for thing in sorted(seen_things, key=len, reverse=True):
                if thing in part and len(thing) > len(longest_match):
                    longest_match = thing

            if longest_match:
                parts[i] = parts[i].replace(
                    longest_match,
                    f"[{longest_match}](#{longest_match.lower()})",
                )

    line = " ".join(parts)

    return line


def ttl2xml(infile: str, outfile: str) -> None:
    """
    Converts an OWL RDF/TTL file to an OWL RDF/XML file.

    Args:
        infile: an OWL RDF/TTL file
        outfile: an OWL RDF/XML file
    """

    # owlready2 can't load ttl files
    # so we need to use rdflib to convert the ttl to xml first
    # then we can load the xml with owlready2
    import rdflib

    g = rdflib.Graph()
    g.parse(infile, format="ttl")

    # serialize to xml and write to outfile
    g.serialize(destination=outfile, format="xml")

    return outfile


def main(infile: str = None) -> list[str]:
    """
    Reads an OWL RDF/XML file and returns a list of strings that can be joined
    with newlines to create a markdown blob summarizing the ontology.

    Args:
        infile: an OWL RDF/XML file

    Returns:
        a list of strings that can be joined with newlines to create a markdown blob
    """

    # owlready2 can't read ttl files, but rdflib can convert them to xml
    # so if we get a ttl file, convert it to xml first in a tempfile long enough
    # to load it with owlready2 then delete the tempfile

    # we need to create a temp dir
    # copy all the ttl files in ../../ontology to it
    # convert each of them to xml with ttl2xml
    # then load the one we want with owlready2

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # copy all the ttl files to the temp dir
        import shutil
        from pathlib import Path

        # figure out where ontology is. it's in "../../ontology" relative to this file
        # but we don't know where this file is being run from
        # so we need to use the path of this file to figure out where the ontology is
        # then we can copy the ontology files to the temp dir

        # get the path to this file
        thisfile = Path(__file__)
        # get the path to the ontology dir
        ontodir = thisfile.parent.parent.parent / "ontology"
        # copy all the ttl files to the temp dir
        for ttlfile in ontodir.glob("*.ttl"):
            shutil.copy(ttlfile, tmpdir)

        # add temp dir to owlready2 path
        owlready2.onto_path.append(tmpdir)

        # convert the files to xml
        # remember the name mapping
        name_map = {}
        for ttlfile in Path(tmpdir).glob("*.ttl"):
            xmlfile = ttlfile.with_suffix("")
            name_map[os.path.basename(ttlfile)] = xmlfile
            ttl2xml(ttlfile, xmlfile)

        # load the ontology
        # for k, v in name_map.items():
        #     print(k, v)
        xmlinfile = name_map[os.path.basename(infile)]
        # remove PosixPaths and convert to str
        xmlinfile = str(xmlinfile)

        # print(xmlinfile)
        onto = owlready2.get_ontology(f"file://{xmlinfile}").load()

    dropstr = ""
    # we need to drop the path to the ontology file from the names
    # dropstr = os.path.basename(xmlinfile) + "."

    lines = []

    lines.append("## Classes")
    lines.append("")
    lines.append("")

    # sort ontology classes by name
    classes: list[owlready2.ThingClass] = sorted(
        onto.classes(), key=lambda x: x.name
    )

    # dump the ontology properties as well
    # sort ontology properties by name
    properties: list[owlready2.ThingClass] = sorted(
        onto.properties(), key=lambda x: x.name
    )

    global seen_things

    # set this first so that thing2md can linkify properly
    seen_things = seen_things.union(set([thing.name for thing in classes]))
    seen_things = seen_things.union(set([thing.name for thing in properties]))

    for thing in classes:
        lines.extend(thing2md(thing))
        lines.append("")
        lines.append("")

    lines.append("## Properties")
    lines.append("")
    lines.append("")

    for thing in properties:
        lines.extend(thing2md(thing))
        lines.append("")
        lines.append("")

    # many strings will have the ontology file name in them
    # so we need to get rid of that
    lines = [line.replace(dropstr, "") for line in lines]

    return lines


if __name__ == "__main__":
    ontology_xml = "../../ontology/vultron_activitystreams.ttl"
    lines = main(infile=ontology_xml)
    print("\n".join(lines))
