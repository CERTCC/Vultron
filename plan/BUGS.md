# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## ✅ FIXED: Test Fixture Isolation (2026-02-17)

**Status**: All 11 router tests now passing (372 total tests pass, 2 xfail)

**Problem**: Test fixture isolation - routers created separate data layer instances from test data.

**Root Causes**:
1. Routers called `get_datalayer()` directly without using FastAPI dependency injection
2. `get_datalayer()` created new instances instead of using singleton pattern
3. Test fixtures didn't override the dependency

**Solution Implemented**:
1. Converted all router endpoints to use `Depends(get_datalayer)` for dependency injection
2. Implemented singleton pattern in `get_datalayer()` with `reset_datalayer()` helper
3. Updated test fixtures to override `get_datalayer` dependency with test's in-memory instance

**Files Modified**:
- `vultron/api/v2/routers/datalayer.py`: Added `Depends(get_datalayer)` to all endpoints
- `vultron/api/v2/routers/actors.py`: Added `Depends(get_datalayer)` to all endpoints
- `vultron/api/v2/datalayer/tinydb_backend.py`: Implemented singleton pattern
- `test/api/v2/conftest.py`: Updated `client` fixture to override dependency
- `test/api/v2/routers/conftest.py`: Updated `client_actors` and `client_datalayer` fixtures

**Test Results**:
- Before: 361 passing, 11 failing, 2 xfailed
- After: 372 passing, 0 failing, 2 xfailed (100% pass rate)

---

## No open bugs at this time

All previously failing tests are now resolved.

PASSED [ 18%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Offers/ "HTTP/1.1 200 OK"
FAILED [ 18%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Offers/ "HTTP/1.1 200 OK"

test/api/v2/routers/test_datalayer.py:26 (test_get_offers_includes_created_offer)
0 != 1

Expected :1
Actual   :0
<Click to see difference>

client_datalayer = <starlette.testclient.TestClient object at 0x10c969f20>
dl = <vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer object at 0x10c7f3590>
offer = as_Offer(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_TransitiveActivityType.OFFER: 'Offer'>, as_id..., image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None))

    def test_get_offers_includes_created_offer(client_datalayer, dl, offer):
        dl.create(object_to_record(offer))
        response = client_datalayer.get("/datalayer/Offers/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
>       assert len(data) == 1
E       assert 0 == 1
E        +  where 0 = len({})

api/v2/routers/test_datalayer.py:31: AssertionError
FAILED [ 18%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Offer/?object_id=3086dfca-2bc8-47db-90ac-9b67097bcd27 "HTTP/1.1 404 Not Found"

test/api/v2/routers/test_datalayer.py:35 (test_get_offer_by_id_returns_offer_fields)
404 != 200

Expected :200
Actual   :404
<Click to see difference>

client_datalayer = <starlette.testclient.TestClient object at 0x10c98d950>
dl = <vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer object at 0x10c814950>
offer = as_Offer(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_TransitiveActivityType.OFFER: 'Offer'>, as_id..., image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None))

    def test_get_offer_by_id_returns_offer_fields(client_datalayer, dl, offer):
        dl.create(object_to_record(offer))
        response = client_datalayer.get(
            "/datalayer/Offer/", params={"object_id": offer.as_id}
        )
>       assert response.status_code == status.HTTP_200_OK
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code
E        +  and   200 = status.HTTP_200_OK

api/v2/routers/test_datalayer.py:40: AssertionError
FAILED [ 18%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/VulnerabilityReports/ "HTTP/1.1 200 OK"

test/api/v2/routers/test_datalayer.py:47 (test_get_vulnerability_reports_returns_empty_dict_when_no_reports)
1 != 0

Expected :0
Actual   :1
<Click to see difference>

client_datalayer = <starlette.testclient.TestClient object at 0x10c828950>

    def test_get_vulnerability_reports_returns_empty_dict_when_no_reports(
        client_datalayer,
    ):
        response = client_datalayer.get("/datalayer/VulnerabilityReports/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), dict)
>       assert len(response.json()) == 0
E       AssertionError: assert 1 == 0
E        +  where 1 = len({'11bcb760-5b25-4a0a-b658-1005e62f77cd': {'as_context': 'https://www.w3.org/ns/activitystreams', 'as_type': 'VulnerabilityReport', 'as_id': '11bcb760-5b25-4a0a-b658-1005e62f77cd', 'name': 'TEST-002', 'preview': None, 'media_type': None, 'replies': None, 'url': None, 'generator': None, 'context': None, 'tag': None, 'in_reply_to': None, 'duration': None, 'start_time': None, 'end_time': None, 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'Test vulnerability report', 'summary': None, 'icon': None, 'image': None, 'attachment': None, 'location': None, 'to': None, 'cc': None, 'bto': None, 'bcc': None, 'audience': None, 'attributed_to': None}})
E        +    where {'11bcb760-5b25-4a0a-b658-1005e62f77cd': {'as_context': 'https://www.w3.org/ns/activitystreams', 'as_type': 'VulnerabilityReport', 'as_id': '11bcb760-5b25-4a0a-b658-1005e62f77cd', 'name': 'TEST-002', 'preview': None, 'media_type': None, 'replies': None, 'url': None, 'generator': None, 'context': None, 'tag': None, 'in_reply_to': None, 'duration': None, 'start_time': None, 'end_time': None, 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'Test vulnerability report', 'summary': None, 'icon': None, 'image': None, 'attachment': None, 'location': None, 'to': None, 'cc': None, 'bto': None, 'bcc': None, 'audience': None, 'attributed_to': None}} = json()
E        +      where json = <Response [200 OK]>.json

api/v2/routers/test_datalayer.py:53: AssertionError
FAILED [ 19%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/VulnerabilityReports/ "HTTP/1.1 200 OK"

test/api/v2/routers/test_datalayer.py:56 (test_get_vulnerability_reports_includes_created_report)
'9a1ab83f-1599-46c5-917c-099ad90cdd1e' != {'11bcb760-5b25-4a0a-b658-1005e62f77cd': {'as_context': 'https://www.w3.org/ns/activitystreams',
                                          'as_id': '11bcb760-5b25-4a0a-b658-1005e62f77cd',
                                          'as_type': 'VulnerabilityReport',
                                          'attachment': None,
                                          'attributed_to': None,
                                          'audience': None,
                                          'bcc': None,
                                          'bto': None,
                                          'cc': None,
                                          'content': 'Test vulnerability '
                                                     'report',
                                          'context': None,
                                          'duration': None,
                                          'end_time': None,
                                          'generator': None,
                                          'icon': None,
                                          'image': None,
                                          'in_reply_to': None,
                                          'location': None,
                                          'media_type': None,
                                          'name': 'TEST-002',
                                          'preview': None,
                                          'published': '2026-02-17T19:30:58+00:00',
                                          'replies': None,
                                          'start_time': None,
                                          'summary': None,
                                          'tag': None,
                                          'to': None,
                                          'updated': '2026-02-17T19:30:58+00:00',
                                          'url': None}}

<Click to see difference>

client_datalayer = <starlette.testclient.TestClient object at 0x10c96e990>
dl = <vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer object at 0x10c815190>
report = VulnerabilityReport(as_context='https://www.w3.org/ns/activitystreams', as_type=<VultronObjectType.VULNERABILITY_REPOR...e, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None)

    def test_get_vulnerability_reports_includes_created_report(
        client_datalayer, dl, report
    ):
        dl.create(report)
        response = client_datalayer.get("/datalayer/VulnerabilityReports/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
>       assert report.as_id in data
E       AssertionError: assert '9a1ab83f-1599-46c5-917c-099ad90cdd1e' in {'11bcb760-5b25-4a0a-b658-1005e62f77cd': {'as_context': 'https://www.w3.org/ns/activitystreams', 'as_type': 'VulnerabilityReport', 'as_id': '11bcb760-5b25-4a0a-b658-1005e62f77cd', 'name': 'TEST-002', 'preview': None, 'media_type': None, 'replies': None, 'url': None, 'generator': None, 'context': None, 'tag': None, 'in_reply_to': None, 'duration': None, 'start_time': None, 'end_time': None, 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'Test vulnerability report', 'summary': None, 'icon': None, 'image': None, 'attachment': None, 'location': None, 'to': None, 'cc': None, 'bto': None, 'bcc': None, 'audience': None, 'attributed_to': None}}
E        +  where '9a1ab83f-1599-46c5-917c-099ad90cdd1e' = VulnerabilityReport(as_context='https://www.w3.org/ns/activitystreams', as_type=<VultronObjectType.VULNERABILITY_REPORT: 'VulnerabilityReport'>, as_id='9a1ab83f-1599-46c5-917c-099ad90cdd1e', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None).as_id

api/v2/routers/test_datalayer.py:64: AssertionError
FAILED [ 19%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Reports/ "HTTP/1.1 200 OK"

test/api/v2/routers/test_datalayer.py:67 (test_reports_shortcut_endpoint_returns_same_results)
'8db4e045-d2de-4865-9a21-a32896dad3c5' != {'11bcb760-5b25-4a0a-b658-1005e62f77cd': {'@context': 'https://www.w3.org/ns/activitystreams',
                                          'attachment': None,
                                          'attributedTo': None,
                                          'audience': None,
                                          'bcc': None,
                                          'bto': None,
                                          'cc': None,
                                          'content': 'Test vulnerability '
                                                     'report',
                                          'context': None,
                                          'duration': None,
                                          'endTime': None,
                                          'generator': None,
                                          'icon': None,
                                          'id': '11bcb760-5b25-4a0a-b658-1005e62f77cd',
                                          'image': None,
                                          'inReplyTo': None,
                                          'location': None,
                                          'mediaType': None,
                                          'name': 'TEST-002',
                                          'preview': None,
                                          'published': '2026-02-17T19:30:58+00:00',
                                          'replies': None,
                                          'startTime': None,
                                          'summary': None,
                                          'tag': None,
                                          'to': None,
                                          'type': 'VulnerabilityReport',
                                          'updated': '2026-02-17T19:30:58+00:00',
                                          'url': None}}

<Click to see difference>

client_datalayer = <starlette.testclient.TestClient object at 0x10c893d40>
dl = <vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer object at 0x10c8160f0>
report = VulnerabilityReport(as_context='https://www.w3.org/ns/activitystreams', as_type=<VultronObjectType.VULNERABILITY_REPOR...e, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None)

    def test_reports_shortcut_endpoint_returns_same_results(
        client_datalayer, dl, report
    ):
        dl.create(report)
        response = client_datalayer.get("/datalayer/Reports/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
>       assert report.as_id in data
E       AssertionError: assert '8db4e045-d2de-4865-9a21-a32896dad3c5' in {'11bcb760-5b25-4a0a-b658-1005e62f77cd': {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'VulnerabilityReport', 'id': '11bcb760-5b25-4a0a-b658-1005e62f77cd', 'name': 'TEST-002', 'preview': None, 'mediaType': None, 'replies': None, 'url': None, 'generator': None, 'context': None, 'tag': None, 'inReplyTo': None, 'duration': None, 'startTime': None, 'endTime': None, 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'Test vulnerability report', 'summary': None, 'icon': None, 'image': None, 'attachment': None, 'location': None, 'to': None, 'cc': None, 'bto': None, 'bcc': None, 'audience': None, 'attributedTo': None}}
E        +  where '8db4e045-d2de-4865-9a21-a32896dad3c5' = VulnerabilityReport(as_context='https://www.w3.org/ns/activitystreams', as_type=<VultronObjectType.VULNERABILITY_REPORT: 'VulnerabilityReport'>, as_id='8db4e045-d2de-4865-9a21-a32896dad3c5', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None).as_id

api/v2/routers/test_datalayer.py:75: AssertionError
FAILED [ 19%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Report/?id=486cb4a8-b4d6-449c-a771-e8efd0c12dc9 "HTTP/1.1 404 Not Found"

test/api/v2/routers/test_datalayer.py:78 (test_get_report_by_id_returns_report)
404 != 200

Expected :200
Actual   :404
<Click to see difference>

client_datalayer = <starlette.testclient.TestClient object at 0x10c8e6270>
dl = <vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer object at 0x10c8169f0>
report = VulnerabilityReport(as_context='https://www.w3.org/ns/activitystreams', as_type=<VultronObjectType.VULNERABILITY_REPOR...e, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None)

    def test_get_report_by_id_returns_report(client_datalayer, dl, report):
        dl.create(report)
        response = client_datalayer.get(
            "/datalayer/Report/", params={"id": report.as_id}
        )
>       assert response.status_code == status.HTTP_200_OK
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code
E        +  and   200 = status.HTTP_200_OK

api/v2/routers/test_datalayer.py:83: AssertionError
PASSED [ 20%]Using selector: KqueueSelector
HTTP Request: DELETE http://testserver/datalayer/reset/ "HTTP/1.1 200 OK"
Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Offers/ "HTTP/1.1 200 OK"
Using selector: KqueueSelector
HTTP Request: GET http://testserver/datalayer/Reports/ "HTTP/1.1 200 OK"

---

problems with test.api.v2.routers.test_actors

PASSED [ 16%]FAILED [ 16%]Using selector: KqueueSelector
results: []
results: []
HTTP Request: GET http://testserver/actors/ "HTTP/1.1 200 OK"

test/api/v2/routers/test_actors.py:26 (test_get_actors_list_returns_all_actors)
0 != 6

Expected :6
Actual   :0
<Click to see difference>

client_actors = <starlette.testclient.TestClient object at 0x10c8792b0>
created_actors = [as_Actor(as_context='https://www.w3.org/ns/activitystreams', as_type='Actor', as_id='a3925c12-344f-4766-9831-2faf05bf...ems=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None)]

    def test_get_actors_list_returns_all_actors(client_actors, created_actors):
        resp = client_actors.get("/actors/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, list)
>       assert len(data) == len(created_actors)
E       AssertionError: assert 0 == 6
E        +  where 0 = len([])
E        +  and   6 = len([as_Actor(as_context='https://www.w3.org/ns/activitystreams', as_type='Actor', as_id='a3925c12-344f-4766-9831-2faf05bfec06', name='Test Actor for List', preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, inbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='d35afdaf-01fc-4fe7-80a4-ebffd94ad243', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), outbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='73ca8cfc-524f-470a-9578-916b84fb4e35', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None), as_Organization(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_ActorType.ORGANIZATION: 'Organization'>, as_id='eda3387a-465b-4ebb-8589-c5d7c962e684', name='Test Actor for List', preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, inbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='2fb5f69f-2def-458f-8c8c-a7d6338f6368', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), outbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='69ad5267-95a7-428a-ba94-7afe89f8acb7', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None), as_Person(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_ActorType.PERSON: 'Person'>, as_id='990298c4-d3b0-4b1a-a944-cee43de60cee', name='Test Actor for List', preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, inbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='6940b1bb-28bd-451e-ac72-387fde3666c6', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), outbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='875dc195-1759-473b-8e2a-19b265a64e53', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None), as_Service(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_ActorType.SERVICE: 'Service'>, as_id='0ffc6179-d071-474b-8417-ab69f4858079', name='Test Actor for List', preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, inbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='519b66fa-d06a-4929-b755-8d870293b9de', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), outbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='29268164-e709-430b-b8a0-3b1233a6d6a9', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None), as_Application(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_ActorType.APPLICATION: 'Application'>, as_id='707a8235-10a5-47c8-a5d0-ac1c9b639fd9', name='Test Actor for List', preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, inbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='75398314-68c0-46a9-bed2-2a13ffef0f99', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), outbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='f3b85146-3ff9-4e26-9544-76edf3689564', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None), as_Group(as_context='https://www.w3.org/ns/activitystreams', as_type=<as_ActorType.GROUP: 'Group'>, as_id='ef12f697-1ec8-4abb-b86b-13ee7d5c1221', name='Test Actor for List', preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, inbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='1792d5cf-1cce-4da3-b7f1-331558ab2134', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), outbox=as_OrderedCollection(as_context='https://www.w3.org/ns/activitystreams', as_type='OrderedCollection', as_id='dc4df5eb-a38b-4d47-a13e-8ce2ee0d73f6', name=None, preview=None, media_type=None, replies=None, url=None, generator=None, context=None, tag=None, in_reply_to=None, duration=None, start_time=None, end_time=None, published=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), updated=datetime.datetime(2026, 2, 17, 19, 30, 58, tzinfo=datetime.timezone.utc), content=None, summary=None, icon=None, image=None, attachment=None, location=None, to=None, cc=None, bto=None, bcc=None, audience=None, attributed_to=None, items=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None)])

api/v2/routers/test_actors.py:31: AssertionError
FAILED [ 16%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/actors/bb7146bd-0a84-4cba-8d2e-c1d5bc0f0dcf "HTTP/1.1 404 Not Found"

test/api/v2/routers/test_actors.py:34 (test_get_actor_by_id_returns_actor_object)
404 != 200

Expected :200
Actual   :404
<Click to see difference>

client_actors = <starlette.testclient.TestClient object at 0x10c881d10>
created_actors = [as_Actor(as_context='https://www.w3.org/ns/activitystreams', as_type='Actor', as_id='bb7146bd-0a84-4cba-8d2e-c1d5bc0f...ems=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None)]

    def test_get_actor_by_id_returns_actor_object(client_actors, created_actors):
        for actor in created_actors:
            resp = client_actors.get(f"/actors/{actor.as_id}")
>           assert resp.status_code == status.HTTP_200_OK
E           assert 404 == 200
E            +  where 404 = <Response [404 Not Found]>.status_code
E            +  and   200 = status.HTTP_200_OK

api/v2/routers/test_actors.py:37: AssertionError
PASSED [ 17%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/actors/nonexistent-actor-id "HTTP/1.1 404 Not Found"
FAILED [ 17%]Using selector: KqueueSelector
HTTP Request: GET http://testserver/actors/d143ba83-8fa1-4ace-ae93-022d54517062/inbox "HTTP/1.1 404 Not Found"

test/api/v2/routers/test_actors.py:49 (test_get_actor_inbox_returns_mailbox_structure)
404 != 200

Expected :200
Actual   :404
<Click to see difference>

client_actors = <starlette.testclient.TestClient object at 0x10c8ed220>
created_actors = [as_Actor(as_context='https://www.w3.org/ns/activitystreams', as_type='Actor', as_id='d143ba83-8fa1-4ace-ae93-022d5451...ems=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None)]

    def test_get_actor_inbox_returns_mailbox_structure(
        client_actors, created_actors
    ):
        for actor in created_actors:
            resp = client_actors.get(f"/actors/{actor.as_id}/inbox")
>           assert resp.status_code == status.HTTP_200_OK
E           assert 404 == 200
E            +  where 404 = <Response [404 Not Found]>.status_code
E            +  and   200 = status.HTTP_200_OK

api/v2/routers/test_actors.py:54: AssertionError
FAILED [ 17%]Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Create', 'id': '78304d4a-07af-4946-8b1e-4d75f3052f5c', 'name': '9c6c5fb7-6e28-4e9b-a46f-e5ab22e4c53b Create None', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'actor': '9c6c5fb7-6e28-4e9b-a46f-e5ab22e4c53b', 'object': {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': '45e6f972-2a0d-497e-8ecc-068dc24f9f41', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Create', 'id': '78304d4a-07af-4946-8b1e-4d75f3052f5c', 'name': '9c6c5fb7-6e28-4e9b-a46f-e5ab22e4c53b Create None', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'actor': '9c6c5fb7-6e28-4e9b-a46f-e5ab22e4c53b', 'object': {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': '45e6f972-2a0d-497e-8ecc-068dc24f9f41', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}}
HTTP Request: POST http://testserver/actors/9c6c5fb7-6e28-4e9b-a46f-e5ab22e4c53b/inbox/ "HTTP/1.1 404 Not Found"

test/api/v2/routers/test_actors.py:61 (test_post_activity_to_actor_inbox_accepted)
404 != 202

Expected :202
Actual   :404
<Click to see difference>

client_actors = <starlette.testclient.TestClient object at 0x10c8ee9e0>
created_actors = [as_Actor(as_context='https://www.w3.org/ns/activitystreams', as_type='Actor', as_id='9c6c5fb7-6e28-4e9b-a46f-e5ab22e4...ems=[], current=0), following=None, followers=None, liked=None, streams=None, preferred_username=None, endpoints=None)]

    def test_post_activity_to_actor_inbox_accepted(client_actors, created_actors):
        for actor in created_actors:
            note = as_Note(content="This is a test note.")
            activity = as_Create(object=note, actor=actor.as_id)
            payload = jsonable_encoder(activity, exclude_none=True)
            resp = client_actors.post(
                f"/actors/{actor.as_id}/inbox/", json=payload
            )
>           assert resp.status_code == status.HTTP_202_ACCEPTED
E           assert 404 == 202
E            +  where 404 = <Response [404 Not Found]>.status_code
E            +  and   202 = status.HTTP_202_ACCEPTED

api/v2/routers/test_actors.py:69: AssertionError
PASSED [ 17%]Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
HTTP Request: POST http://testserver/actors/3866cb8e-e298-4f46-ad1b-1a9acfeaf265/inbox/ "HTTP/1.1 422 Unprocessable Entity"
Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
HTTP Request: POST http://testserver/actors/eecb3d1d-d4f0-42f5-a8b3-319431c0049f/inbox/ "HTTP/1.1 422 Unprocessable Entity"
Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
HTTP Request: POST http://testserver/actors/38dd7295-2553-4912-a272-aecfced53a42/inbox/ "HTTP/1.1 422 Unprocessable Entity"
Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
HTTP Request: POST http://testserver/actors/e5e76487-0f6c-405f-8ef8-156174e6a477/inbox/ "HTTP/1.1 422 Unprocessable Entity"
Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
HTTP Request: POST http://testserver/actors/425019ef-4fcf-4bc2-86d4-2b8083206347/inbox/ "HTTP/1.1 422 Unprocessable Entity"
Using selector: KqueueSelector
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Note', 'id': 'urn:uuid:test-note', 'published': '2026-02-17T19:30:58+00:00', 'updated': '2026-02-17T19:30:58+00:00', 'content': 'This is a test note.'}
HTTP Request: POST http://testserver/actors/aabea776-f7b9-4c45-9942-7c2266981b67/inbox/ "HTTP/1.1 422 Unprocessable Entity"

---

Problems with test.api.v2.test_v2_api.test_datalayer_get_existing_actor

Using selector: KqueueSelector
FAILED          [ 21%]HTTP Request: GET http://testserver/datalayer/95b774df-26dd-4ce7-a6c1-2336bf5d0807 "HTTP/1.1 404 Not Found"

test/api/v2/test_v2_api.py:65 (test_datalayer_get_existing_actor)
404 != 200

Expected :200
Actual   :404
<Click to see difference>

client = <starlette.testclient.TestClient object at 0x10cb03a10>
datalayer = <vultron.api.v2.datalayer.tinydb_backend.TinyDbDataLayer object at 0x10cb6c830>

    def test_datalayer_get_existing_actor(client, datalayer):
        """Test retrieving an existing actor directly by ID"""
        actor = as_Person(
            name="Test Person",
        )
        datalayer.create(object_to_record(actor))
    
        response = client.get(f"/datalayer/{actor.as_id}")
>       assert response.status_code == 200
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

api/v2/test_v2_api.py:73: AssertionError
