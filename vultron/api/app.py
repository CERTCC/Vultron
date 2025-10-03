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
from fastapi.responses import RedirectResponse

from vultron.api.v1 import router as v1_router

app = FastAPI()

app.include_router(v1_router, prefix="/api/v1")


# root should redirect to docs
# at least until we have something better to show
@app.get("/", include_in_schema=False)
async def redirect_root_to_docs():
    return RedirectResponse(url="/docs")


def main():
    # run the app with uvicorn
    import uvicorn

    uvicorn.run(app, host="localhost", port=7998)


if __name__ == "__main__":
    main()
