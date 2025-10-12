import unittest
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime, date
import json
import os

from src.module import updateTracker
from googleapiclient.errors import HttpError


class TestUpdateTracker(unittest.TestCase):

    def setUp(self):
        self.test_spreadsheet_id = "test_spreadsheet_id"
        self.test_range = "Control!A1"
        self.test_file_path = "test_update_file.json"
        self.test_date = date(2025, 6, 24)

    @patch('src.module.updateTracker.authenticate')
    @patch('src.module.updateTracker.build')
    def test_get_last_update_from_sheets_success(self, mock_build, mock_auth):
        """Test successful retrieval of last update date from Google Sheets."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['2025-06-24']]
        }

        result = updateTracker.get_last_update_from_sheets(
            self.test_spreadsheet_id, self.test_range
        )

        self.assertEqual(result, self.test_date)
        mock_service.spreadsheets().values().get.assert_called_once_with(
            spreadsheetId=self.test_spreadsheet_id, range=self.test_range
        )

    @patch('src.module.updateTracker.authenticate')
    @patch('src.module.updateTracker.build')
    def test_get_last_update_from_sheets_empty(self, mock_build, mock_auth):
        """Test when Google Sheets cell is empty."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': []
        }

        result = updateTracker.get_last_update_from_sheets(
            self.test_spreadsheet_id, self.test_range
        )

        self.assertIsNone(result)

    @patch('src.module.updateTracker.authenticate')
    @patch('src.module.updateTracker.build')
    def test_get_last_update_from_sheets_http_error(self, mock_build, mock_auth):
        """Test handling of HTTP errors from Google Sheets API."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.side_effect = \
            HttpError(resp=MagicMock(status=404), content=b'Not found')

        result = updateTracker.get_last_update_from_sheets(
            self.test_spreadsheet_id, self.test_range
        )

        self.assertIsNone(result)

    @patch('src.module.updateTracker.authenticate')
    @patch('src.module.updateTracker.build')
    def test_update_last_update_in_sheets_success(self, mock_build, mock_auth):
        """Test successful update of last update date in Google Sheets."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().update().execute.return_value = {}

        result = updateTracker.update_last_update_in_sheets(
            self.test_spreadsheet_id, self.test_range, self.test_date
        )

        self.assertTrue(result)
        mock_service.spreadsheets().values().update.assert_called_once()

    @patch('src.module.updateTracker.authenticate')
    @patch('src.module.updateTracker.build')
    def test_update_last_update_in_sheets_http_error(self, mock_build, mock_auth):
        """Test handling of HTTP errors when updating Google Sheets."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().update().execute.side_effect = \
            HttpError(resp=MagicMock(status=403), content=b'Forbidden')

        result = updateTracker.update_last_update_in_sheets(
            self.test_spreadsheet_id, self.test_range, self.test_date
        )

        self.assertFalse(result)

    @patch('os.path.isfile')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_last_update_from_local_file_success(self, mock_file, mock_isfile):
        """Test successful retrieval of last update date from local file."""
        mock_isfile.return_value = True
        test_data = {"update_time": "2025-06-24"}
        mock_file.return_value.read.return_value = json.dumps(test_data)

        with patch('json.load', return_value=test_data):
            result = updateTracker.get_last_update_from_local_file(
                self.test_file_path
            )

        self.assertEqual(result, self.test_date)

    @patch('os.path.isfile')
    def test_get_last_update_from_local_file_not_found(self, mock_isfile):
        """Test when local file doesn't exist."""
        mock_isfile.return_value = False

        result = updateTracker.get_last_update_from_local_file(
            self.test_file_path
        )

        self.assertIsNone(result)

    @patch('builtins.open', new_callable=mock_open)
    def test_update_last_update_in_local_file_success(self, mock_file):
        """Test successful update of last update date in local file."""
        result = updateTracker.update_last_update_in_local_file(
            self.test_file_path, self.test_date
        )

        self.assertTrue(result)
        mock_file.assert_called_once_with(self.test_file_path, 'w')

    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_update_last_update_in_local_file_io_error(self, mock_file):
        """Test handling of IO errors when updating local file."""
        result = updateTracker.update_last_update_in_local_file(
            self.test_file_path, self.test_date
        )

        self.assertFalse(result)

    @patch('src.module.updateTracker.get_last_update_from_sheets')
    @patch('src.module.updateTracker.get_last_update_from_local_file')
    def test_get_last_update_date_sheets_priority(self, mock_local, mock_sheets):
        """Test that Google Sheets is prioritized over local file."""
        mock_sheets.return_value = self.test_date
        mock_local.return_value = date(2025, 6, 23)  # Different date

        result = updateTracker.get_last_update_date(
            self.test_spreadsheet_id, self.test_range, self.test_file_path
        )

        self.assertEqual(result, self.test_date)
        mock_sheets.assert_called_once()

    @patch('src.module.updateTracker.get_last_update_from_sheets')
    @patch('src.module.updateTracker.get_last_update_from_local_file')
    def test_get_last_update_date_fallback_to_local(self, mock_local, mock_sheets):
        """Test fallback to local file when Google Sheets unavailable."""
        mock_sheets.return_value = None
        mock_local.return_value = self.test_date

        result = updateTracker.get_last_update_date(
            self.test_spreadsheet_id, self.test_range, self.test_file_path
        )

        self.assertEqual(result, self.test_date)
        mock_sheets.assert_called_once()
        mock_local.assert_called_once()

    @patch('src.module.updateTracker.get_last_update_from_sheets')
    @patch('src.module.updateTracker.get_last_update_from_local_file')
    def test_get_last_update_date_none_found(self, mock_local, mock_sheets):
        """Test when no update date is found anywhere."""
        mock_sheets.return_value = None
        mock_local.return_value = None

        result = updateTracker.get_last_update_date(
            self.test_spreadsheet_id, self.test_range, self.test_file_path
        )

        self.assertIsNone(result)

    @patch('src.module.updateTracker.update_last_update_in_sheets')
    @patch('src.module.updateTracker.update_last_update_in_local_file')
    def test_update_last_update_date_both_success(self, mock_local, mock_sheets):
        """Test successful update in both Google Sheets and local file."""
        mock_sheets.return_value = True
        mock_local.return_value = True

        result = updateTracker.update_last_update_date(
            self.test_spreadsheet_id, self.test_range, 
            self.test_file_path, self.test_date
        )

        self.assertTrue(result)
        mock_sheets.assert_called_once()
        mock_local.assert_called_once()

    @patch('src.module.updateTracker.update_last_update_in_sheets')
    @patch('src.module.updateTracker.update_last_update_in_local_file')
    def test_update_last_update_date_sheets_fails(self, mock_local, mock_sheets):
        """Test when Google Sheets update fails but local file succeeds."""
        mock_sheets.return_value = False
        mock_local.return_value = True

        result = updateTracker.update_last_update_date(
            self.test_spreadsheet_id, self.test_range, 
            self.test_file_path, self.test_date
        )

        self.assertTrue(result)  # Should still return True if one succeeds

    @patch('src.module.updateTracker.update_last_update_in_sheets')
    @patch('src.module.updateTracker.update_last_update_in_local_file')
    def test_update_last_update_date_both_fail(self, mock_local, mock_sheets):
        """Test when both Google Sheets and local file updates fail."""
        mock_sheets.return_value = False
        mock_local.return_value = False

        result = updateTracker.update_last_update_date(
            self.test_spreadsheet_id, self.test_range, 
            self.test_file_path, self.test_date
        )

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()