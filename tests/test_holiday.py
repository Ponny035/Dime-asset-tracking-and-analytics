import unittest
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime
from src.module import checkThaiHoliday  # Adjust import path as needed
from requests.exceptions import RequestException


class TestCheckThaiHoliday(unittest.TestCase):

    @patch('requests.get')
    def test_get_holidays_success(self, mock_get):
        """Test successful response from the BOT API returns valid data structure."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "result": {
                "timestamp": "2025-05-20 10:00:00",
                "data": [{"Date": "2025-01-01"}]
            }
        }

        result = checkThaiHoliday.get_financial_institutions_holidays_api("dummy_id")
        self.assertIsInstance(result, dict)
        self.assertIn("timestamp", result)
        self.assertIn("data", result)

    @patch('requests.get')
    def test_get_holidays_failure(self, mock_get):
        """Test that an exception in the API call returns None."""
        mock_get.side_effect = RequestException("API down")
        result = checkThaiHoliday.get_financial_institutions_holidays_api("dummy_id")
        self.assertIsNone(result)

    @patch('src.module.checkThaiHoliday.get_financial_institutions_holidays_api')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.module.checkThaiHoliday.os.path.isfile')
    @patch('json.load')
    @patch('src.module.checkThaiHoliday.json.dump')
    def test_update_already_updated_today(
        self, mock_dump, mock_json_load, mock_isfile, mock_open_fn, mock_api
    ):
        """Test that no API call is made if the local file is already updated today."""
        today = datetime.now().strftime('%Y-%m-%d')
        mock_isfile.return_value = True
        mock_json_load.return_value = {
            "update_time": f"{today} 08:00:00"
        }

        result = checkThaiHoliday.update_financial_institutions_holidays("dummy_id")
        self.assertTrue(result)
        mock_api.assert_not_called()

    @patch('src.module.checkThaiHoliday.get_financial_institutions_holidays_api')
    @patch('builtins.open', new_callable=mock_open)
    @patch('src.module.checkThaiHoliday.os.path.isfile')
    @patch('src.module.checkThaiHoliday.json.dump')
    def test_update_triggers_api_and_writes_file(
        self, mock_dump, mock_isfile, mock_open_fn, mock_api
    ):
        """Test that the API is called and data is written when update is needed."""
        mock_isfile.return_value = False
        mock_api.return_value = {
            "timestamp": "2025-05-21 10:00:00",
            "data": [
                {"Date": "2025-01-01"},
                {"Date": "2025-02-14"}
            ]
        }

        result = checkThaiHoliday.update_financial_institutions_holidays("dummy_id")
        self.assertTrue(result)
        mock_dump.assert_called_once()


if __name__ == '__main__':
    unittest.main()
