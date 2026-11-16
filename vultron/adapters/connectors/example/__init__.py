"""
Example connector plugins.

These reference implementations illustrate how to build a connector plugin
for an outside system. They are examples, NOT production connectors: none
declares an entry point in the ``vultron.connectors`` group, so the loader
(``loader.py``) never finds them, and nothing else imports them.  They exist
only to document the intended plugin pattern.

Modules:

- ``vince.py`` — A VINCE case reader: implements the core ``CaseReader``
  port and nothing else.
"""
