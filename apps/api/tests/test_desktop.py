"""Desktop startup uses the real server, authentication and workspace lease."""

import urllib.error
import urllib.request

import pytest
from furnace.runtime.lease import WorkspaceBusy, WorkspaceLease
from furnace_api.desktop import DesktopService


def test_desktop_owns_lease_authenticates_and_stops_without_token_file(tmp_path):
    service = DesktopService(tmp_path)
    service.start()
    try:
        with pytest.raises(WorkspaceBusy), WorkspaceLease(tmp_path):
            pass
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(service.url + "/api/projects")
        assert error.value.code == 401
        request = urllib.request.Request(
            service.url + "/api/projects", headers={"x-furnace-session": service.token}
        )
        assert urllib.request.urlopen(request).read() == b"[]"
    finally:
        assert service.stop()
    assert all(
        service.token.encode() not in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    )
    with WorkspaceLease(tmp_path):
        pass


def test_second_desktop_does_not_take_over_a_workspace(tmp_path):
    first, second = DesktopService(tmp_path), DesktopService(tmp_path)
    first.start()
    try:
        with pytest.raises(RuntimeError, match="already be open"):
            second.start()
        assert first.server.started
    finally:
        assert first.stop()
