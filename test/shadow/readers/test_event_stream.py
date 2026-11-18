"""Server-sent events read from a stream's lines as a browser reads them."""

from vultron.shadow.readers.event_stream import (
    MESSAGE,
    ServerSentEvent,
    server_sent_events,
)


def _events(text: str) -> list[ServerSentEvent]:
    return list(server_sent_events(text.split("\n")))


def test_each_blank_line_dispatches_the_event_its_data_built():
    assert _events("id: 0\ndata: a\n\nid: 1\ndata: b\n\n") == [
        ServerSentEvent(type=MESSAGE, data="a", last_event_id="0"),
        ServerSentEvent(type=MESSAGE, data="b", last_event_id="1"),
    ]


def test_data_lines_join_by_newline_and_one_leading_space_is_dropped():
    (event,) = _events("data:a\ndata:  b\n\n")
    assert event.data == "a\n b"


def test_an_event_names_its_type_and_an_empty_data_line_still_dispatches():
    (event,) = _events("event: close\ndata: \n\n")
    assert (event.type, event.data) == ("close", "")


def test_comments_unknown_fields_and_dataless_events_dispatch_nothing():
    assert _events(": hi\n\nretry: 5\nfoo: x\n\nevent: ping\n\n") == []


def test_the_last_event_id_carries_over_to_events_without_one():
    first, second = _events("id: 7\ndata: a\n\ndata: b\n\n")
    assert first.last_event_id == second.last_event_id == "7"


def test_an_id_holding_nul_is_ignored():
    (event,) = _events("id: 1\n\nid: 2\0\ndata: a\n\n")
    assert event.last_event_id == "1"


def test_an_event_cut_off_by_the_end_of_the_stream_is_not_dispatched():
    assert _events("data: a\n\ndata: b") == [
        ServerSentEvent(type=MESSAGE, data="a", last_event_id=None)
    ]


def test_a_field_with_no_colon_is_a_field_with_an_empty_value():
    (event,) = _events("data\n\n")
    assert event.data == ""
