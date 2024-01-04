#!/usr/bin/env python
"""file: errors
author: adh
created_at: 2/17/23 1:49 PM
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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

from vultron.errors import VultronError


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  Copyright (c) 2023. Carnegie Mellon University. See LICENSE.md for details.
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class ActivityVocabularyError(VultronError):
    """Base class for all ActivityPub as_vocab errors."""


########################
# Serialization errors #
########################


# Raised when problems occur during serialization to JSON.
class SerializationError(ActivityVocabularyError):
    """Raised when a JSON object cannot be serialized."""


class IsoEncodingError(SerializationError):
    """Raised when an ISO encoding is not recognized."""


##########################
# Deserialization errors #
##########################

# Raised when problems occur during deserialization from JSON.


class DeserializationError(ActivityVocabularyError):
    """Raised when a JSON object cannot be deserialized."""


class MissingTypeError(DeserializationError):
    """Raised when a type is missing from a JSON object."""


class UnrecognizedTypeError(DeserializationError):
    """Raised when an unknown type is encountered."""


class IsoDecodingError(DeserializationError):
    """Raised when an ISO decoding is not recognized."""
