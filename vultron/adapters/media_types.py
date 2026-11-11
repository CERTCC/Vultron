#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""HTTP media types shared by the driving and driven adapters.

A driven adapter never imports a driving one, so a media type that both an
endpoint's response and an outbound request name lives here, below both.

- HTTP-01-004: a delivery POST names an ActivityStreams media type.
- HTTP-04-001: an endpoint returning an ActivityStreams object uses
  ``application/activity+json``.
"""

AS2_CONTENT_TYPE = "application/activity+json"
"""The ActivityStreams media type Vultron sends, accepts and serves."""
