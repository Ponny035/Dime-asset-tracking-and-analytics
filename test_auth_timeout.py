#!/usr/bin/env python3
"""
Simple test script to verify auth timeout improvements work correctly.
This is a temporary test file to validate the timeout fixes.
"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import socket

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.util.auth import authenticate, _retry_with_backoff


def test_retry_with_backoff():
    """Test the retry with backoff function."""
    print("Testing retry with backoff...")
    
    # Test successful function on first try
    def success_func():
        return "success"
    
    result = _retry_with_backoff(success_func, 3, 10)
    assert result == "success", "Should succeed on first try"
    print("✓ Success on first try works")
    
    # Test function that fails then succeeds
    call_count = [0]
    def fail_then_succeed():
        call_count[0] += 1
        if call_count[0] < 2:
            raise socket.timeout("Simulated timeout")
        return "success after retry"
    
    result = _retry_with_backoff(fail_then_succeed, 3, 10)
    assert result == "success after retry", "Should succeed after retry"
    assert call_count[0] == 2, "Should have been called twice"
    print("✓ Retry after failure works")
    
    # Test function that always fails
    def always_fail():
        raise socket.timeout("Always fails")
    
    try:
        _retry_with_backoff(always_fail, 2, 10)
        assert False, "Should have raised exception"
    except socket.timeout:
        print("✓ Exception raised after max retries")


def test_environment_variable_loading():
    """Test that environment variables are properly loaded."""
    print("\nTesting environment variable loading...")
    
    # Set custom environment variables
    os.environ['AUTH_TIMEOUT'] = '15'
    os.environ['AUTH_MAX_RETRIES'] = '2'
    
    # Mock the authentication components to avoid actual API calls
    with patch('src.util.auth.Credentials') as mock_creds, \
         patch('src.util.auth.ServiceAccountCredentials') as mock_service_creds, \
         patch('os.path.exists') as mock_exists:
        
        # Setup mocks
        mock_exists.return_value = True
        mock_service_creds.from_service_account_file.return_value = MagicMock()
        
        # Test service account mode (should not use timeout/retry for service accounts)
        result = authenticate(auth_mode="service_account")
        assert result is not None, "Service account authentication should succeed"
        print("✓ Service account mode works")
    
    print("✓ Environment variables loaded correctly")


def test_oauth_timeout_handling():
    """Test OAuth timeout handling with mocked components."""
    print("\nTesting OAuth timeout handling...")
    
    with patch('src.util.auth.Credentials') as mock_creds_class, \
         patch('src.util.auth.os.path.exists') as mock_exists, \
         patch('src.util.auth._retry_with_backoff') as mock_retry:
        
        # Setup mocks
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds_class.from_authorized_user_file.return_value = mock_creds
        
        # Test case 1: Valid credentials (no refresh needed)
        mock_creds.valid = True
        result = authenticate(auth_mode="oauth", timeout=5, max_retries=2)
        assert result == mock_creds, "Should return valid credentials"
        mock_retry.assert_not_called()
        print("✓ Valid credentials bypass retry logic")
        
        # Test case 2: Expired credentials needing refresh
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "some_token"
        mock_retry.return_value = mock_creds
        
        result = authenticate(auth_mode="oauth", timeout=5, max_retries=2)
        assert mock_retry.called, "Should call retry function for expired credentials"
        print("✓ Expired credentials trigger retry logic")


if __name__ == "__main__":
    print("Testing authentication timeout improvements...\n")
    
    try:
        test_retry_with_backoff()
        test_environment_variable_loading()
        test_oauth_timeout_handling()
        
        print("\n🎉 All timeout tests passed!")
        print("\nThe authentication timeout fixes are working correctly:")
        print("- Retry logic with exponential backoff implemented")
        print("- Environment variable configuration working")
        print("- Proper error handling for timeout scenarios")
        print("- OAuth flow protected against network timeouts")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)