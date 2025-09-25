import pytest


@pytest.mark.asyncio
async def test_events_list_empty_state(client, soup):
    resp = await client.get("/events/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")

    dom = soup(resp.text)

    # Heading is present
    h1 = dom.select_one("h1")
    assert h1 and "Events" in h1.text

    # Empty state is rendered
    empty_box = dom.select_one("div.border-dashed")
    assert empty_box is not None

    msg = empty_box.select_one("p.text-sm")
    assert msg and "No events yet." in msg.text

    # CTA exists and points to /events/new/
    cta = empty_box.select_one('a[href="/events/new/"]')
    assert cta is not None
    assert "Create your first event" in cta.text


@pytest.mark.asyncio
async def test_events_list(client, soup, sample_events):
    resp = await client.get("/events/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")

    dom = soup(resp.text)

    # Heading is present
    h1 = dom.select_one("h1")
    assert h1 and "Events" in h1.text

    for event in sample_events:
        assert event.title in dom.text


@pytest.mark.asyncio
async def test_event_wall_normal_messages(
    client, soup, single_event, normal_messages_for_single_event
):
    resp = await client.get(f"/events/{single_event.code}/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")

    dom = soup(resp.text)

    # Heading is present
    h1 = dom.select_one("h1")
    assert h1 and single_event.title in h1.text

    for msg in normal_messages_for_single_event:
        assert msg.text in dom.text


@pytest.mark.asyncio
async def test_event_wall_pinned_messages(
    client, soup, single_event, pinned_messages_for_single_event
):
    resp = await client.get(f"/events/{single_event.code}/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")

    dom = soup(resp.text)

    # Heading is present
    h1 = dom.select_one("h1")
    assert h1 and single_event.title in h1.text

    for msg in pinned_messages_for_single_event:
        assert msg.text in dom.text


@pytest.mark.asyncio
async def test_event_wall_pinned_on_top(client, soup, single_event, all_messages_for_single_event):
    resp = await client.get(f"/events/{single_event.code}/")
    assert resp.status_code == 200
    dom = soup(resp.text)

    # Collect pinned + non-pinned
    pinned = [m for m in all_messages_for_single_event if m.pinned]
    normal = [m for m in all_messages_for_single_event if not m.pinned]

    # Find DOM order (simplified: assuming messages render in a container with <li> or <div>)
    items = [el.get_text(strip=True) for el in dom.select(".message-text")]
    for idx, pinned_msg in enumerate(pinned):
        assert (
            pinned_msg.text in items[len(pinned) - (idx + 1)]
        )  # Reverse indexing is due to latest message will always be on top
    for idx, normal_msg in enumerate(normal, start=len(pinned)):
        assert (
            normal_msg.text in items[len(pinned) - (idx + 1)]
        )  # Reverse indexing is due to latest message will always be on top
