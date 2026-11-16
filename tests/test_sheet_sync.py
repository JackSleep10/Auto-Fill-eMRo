"""Tests for Google Sheet sync filtering (PM vs CM separation)."""
from unittest.mock import patch
from scraper.gse_wo_creator import GSEWorkOrderCreator


def test_log_to_google_sheet_excludes_pm():
    """Verify that log_to_google_sheet filters out PM / SCHED items and does not send them to sheet บันทึกข้อมูล W/O."""
    pm_items = [
        {"success": True, "wo_number": "1001", "gse": "TLM-01", "priority": "SCHED", "description": "PM OCT"},
        {"success": True, "wo_number": "1002", "gse": "TLM-02", "priority": "PM", "description": "PM NOV"},
    ]

    with patch("requests.post") as mock_post:
        # With only PM items, requests.post should NOT be called at all
        res = GSEWorkOrderCreator.log_to_google_sheet(pm_items)
        assert res is True
        mock_post.assert_not_called()


def test_log_to_google_sheet_sends_only_cm():
    """Verify that log_to_google_sheet sends only CM / UNSCHED items to sheet บันทึกข้อมูล W/O."""
    mixed_items = [
        {"success": True, "wo_number": "1001", "gse": "TLM-01", "priority": "SCHED", "description": "PM OCT"},
        {"success": True, "wo_number": "2001", "gse": "TLM-03", "priority": "UNSCHED", "description": "ENGINE ISSUE"},
    ]

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        res = GSEWorkOrderCreator.log_to_google_sheet(mixed_items)
        assert res is True
        assert mock_post.call_count == 1
        payload = mock_post.call_args[1]["json"]
        assert payload["action"] == "append_wo_log"
        # Only the CM item should be sent
        assert len(payload["items"]) == 1
        assert payload["items"][0]["wo_number"] == "2001"
        assert payload["items"][0]["priority"] == "UNSCHED"


def test_sync_to_google_sheet_sends_only_pm():
    """Verify that sync_to_google_sheet sends only PM items to Monthly PM sheet."""
    mixed_items = [
        {"success": True, "wo_number": "1001", "gse": "TLM-01", "priority": "SCHED", "description": "PM OCT"},
        {"success": True, "wo_number": "2001", "gse": "TLM-03", "priority": "UNSCHED", "description": "ENGINE ISSUE"},
    ]

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        res = GSEWorkOrderCreator.sync_to_google_sheet(mixed_items)
        assert res is True
        assert mock_post.call_count == 1
        payload = mock_post.call_args[1]["json"]
        assert payload["action"] == "append_gse_wo"
        # Only the PM item should be sent
        assert len(payload["items"]) == 1
        assert payload["items"][0]["wo_number"] == "1001"

