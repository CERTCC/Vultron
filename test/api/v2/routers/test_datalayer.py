#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from fastapi import status


def test_get_offers_returns_empty_dict_when_no_offers(client_datalayer):
    response = client_datalayer.get("/datalayer/Offers/")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert len(response.json()) == 0


def test_get_offers_includes_created_offer(client_datalayer, dl, offer):
    dl.create(object_to_record(offer))
    response = client_datalayer.get("/datalayer/Offers/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert offer.as_id in data


def test_get_offer_by_id_returns_offer_fields(client_datalayer, dl, offer):
    dl.create(object_to_record(offer))
    response = client_datalayer.get(
        "/datalayer/Offer/", params={"object_id": offer.as_id}
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["id"] == offer.as_id
    # actor key name comes from the router's encoding
    assert body.get("actor") == offer.actor


def test_get_vulnerability_reports_returns_empty_dict_when_no_reports(
    client_datalayer,
):
    response = client_datalayer.get("/datalayer/VulnerabilityReports/")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert len(response.json()) == 0


def test_get_vulnerability_reports_includes_created_report(
    client_datalayer, dl, report
):
    dl.create(report)
    response = client_datalayer.get("/datalayer/VulnerabilityReports/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert report.as_id in data


def test_reports_shortcut_endpoint_returns_same_results(
    client_datalayer, dl, report
):
    dl.create(report)
    response = client_datalayer.get("/datalayer/Reports/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert report.as_id in data


def test_get_report_by_id_returns_report(client_datalayer, dl, report):
    dl.create(report)
    response = client_datalayer.get(
        "/datalayer/Report/", params={"id": report.as_id}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == report.as_id


def test_reset_endpoint_clears_all_data(client_datalayer, dl, report, offer):
    dl.create(object_to_record(offer))
    dl.create(report)

    # sanity: ensure they exist before reset
    assert dl.by_type("Offer") is not None
    assert dl.by_type("VulnerabilityReport") is not None

    resp = client_datalayer.delete("/datalayer/reset/")
    assert resp.status_code == status.HTTP_200_OK

    resp_offers = client_datalayer.get("/datalayer/Offers/")
    assert resp_offers.status_code == status.HTTP_200_OK
    assert len(resp_offers.json()) == 0

    resp_reports = client_datalayer.get("/datalayer/Reports/")
    assert resp_reports.status_code == status.HTTP_200_OK
    assert len(resp_reports.json()) == 0
