#!/usr/bin/env python
"""
Vultron API Application
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
from fastapi import FastAPI

from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/cases")
async def read_cases() -> list[VulnerabilityCase]:
    from vultron.scripts.vocab_examples import case

    case_list = [case for _ in range(5)]
    return case_list


def main():
    # run the app with uvicorn
    import uvicorn

    uvicorn.run(app, host="localhost", port=7998)


if __name__ == "__main__":
    main()
