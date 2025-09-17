#!/usr/bin/env python
"""
Extract notes from content
"""
#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

def extract_notes(content):
    # A note block looks like this:
    # !!! note ""
    # <blank line>
    # indented text
    # indented text
    # non-indented text is not part of the note

    lines = content.splitlines()
    notes = []
    in_note = False
    note_content = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith('!!! note \"\"'):
            in_note = True
            note_content = []
        elif in_note:
            if stripped_line == '':
                continue  # skip blank lines within the note
            if not line.startswith(' '):  # non-indented line ends the note
                in_note = False
                notes.append('\n'.join(note_content))
                note_content = []
            else:
                note_content.append(stripped_line)

    if in_note:  # if we end with an open note
        notes.append('\n'.join(note_content))
    # Here you can process the notes as needed, e.g., print or save them
    return notes


def main():
    docs_dir = 'docs'

    notes = []
    # walk through the docs directory and process each .md file
    for root, dirs, files in os.walk(docs_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Process the content to extract notes
                    # This is a placeholder for the actual extraction logic
                    extracted_notes = extract_notes(content)
                    notes.extend(extracted_notes)
    # Print or save the extracted notes
    outfile = "extracted_notes.txt"

    with open(outfile, 'w', encoding='utf-8') as f:
        for note in notes:
            print(note)
            print('---')  # Separator for clarity
            f.write(note + '\n---\n')


if __name__ == '__main__':
    main()