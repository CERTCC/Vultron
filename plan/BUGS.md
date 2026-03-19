# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## ~~mkdocs errors after vocab examples refactor~~ FIXED

mkdocs build reports the following error:

```text
WARNING -  markdown_exec: Execution of python code block exited with errors

           Code block is:

             from vultron.scripts.vocab_examples import close_report, json2md

             print(json2md(close_report()))

           Output is:

             Traceback (most recent call last):
               File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/markdown_exec/_internal/formatters/python.py", line 71, in _run_python
                 exec_python(code, code_block_id, exec_globals)
                 ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
               File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/markdown_exec/_internal/formatters/_exec_python.py", line 8, in exec_python
                 exec(compiled, exec_globals)  # noqa: S102
                 ~~~~^^^^^^^^^^^^^^^^^^^^^^^^
               File "<code block: n84>", line 1, in <module>
                 from vultron.scripts.vocab_examples import close_report, json2md
             ModuleNotFoundError: No module named 'vultron.scripts.vocab_examples'
```

This occurs in numerous files and is the result of `vultron.scripts.
vocab_examples` having been refactored into multiple submodules in  
`vultron/wire/as2/vocab/examples` Fix needs to made to all files in `docs` 
that have a python markdown_exec block that imports from  `vultron.scripts.
vocab_examples` to update the import path to the new location.
Done when `mkdocs build` completes without any markdown_exec errors.

