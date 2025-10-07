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

tags_metadata = [
    {
        "name": "Examples",
        "description": """Actors create Reports and Cases.
Cases manage the lifecycle of of response to a Report. Cases have Participants,
which are wrappers around Actors. Participants are scoped to the context of a
specific case, and have specific role(s) in the Case. Actors
can post Notes and Embargo Events to Cases. Cases have Statuses, 
as do individual Participants within the case.
     
- `GET` to see a sample object.
- `POST` an object to run it through the pydantic model validation.
""",
    },
]
app = FastAPI(openapi_tags=tags_metadata)

app.include_router(v1_router, prefix="/api/v1")


# root should redirect to docs
# at least until we have something better to show
@app.get("/", include_in_schema=False, description="Redirect to API docs")
async def redirect_root_to_docs():
    return RedirectResponse(url="/docs")


def main():
    from fastapi.routing import APIRoute

    # run the app with uvicorn
    # import uvicorn
    #
    # uvicorn.run(app, host="localhost", port=7998)
    routes_by_tag = dict()

    for route in app.routes:
        if isinstance(route, APIRoute):
            if not route.tags:
                route.tags = ["default"]

            for tag in route.tags:
                if tag not in routes_by_tag:
                    routes_by_tag[tag] = []
                routes_by_tag[tag].append(route)
    for tag, routes in routes_by_tag.items():
        print(f"## Tag: {tag}")
        for route in routes:
            for method in route.methods:
                print(f"- `{method} {route.path}` -> {route.description}")
        print()


if __name__ == "__main__":
    main()
