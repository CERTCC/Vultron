# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## test_check_server_availability_logs_retry_attempts failure:

```shell
FAILED [ 94%]
test/scripts/test_health_check_retry.py:79 (test_check_server_availability_logs_retry_attempts)
'Checking server at' != ''

Expected :''
Actual   :'Checking server at'
<Click to see difference>

caplog = <_pytest.logging.LogCaptureFixture object at 0x10e456f20>

    def test_check_server_availability_logs_retry_attempts(caplog):
        """Test that health check logs retry attempts."""
        client = DataLayerClient(base_url="http://test:7999/api/v2")
    
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
    
        side_effects = [
            requests.exceptions.ConnectionError("Connection refused"),
            mock_response,
        ]
    
        with patch("requests.get", side_effect=side_effects):
            result = check_server_availability(
                client, max_retries=3, retry_delay=0.1
            )
    
        assert result is True
        # Should see retry attempt logs
>       assert (
            "Retrying in" in caplog.text
            or "Checking server availability" in caplog.text
            or "Checking server at" in caplog.text
        )
E       AssertionError: assert ('Retrying in' in '' or 'Checking server availability' in '' or 'Checking server at' in '')
E        +  where '' = <_pytest.logging.LogCaptureFixture object at 0x10e456f20>.text
E        +  and   '' = <_pytest.logging.LogCaptureFixture object at 0x10e456f20>.text
E        +  and   '' = <_pytest.logging.LogCaptureFixture object at 0x10e456f20>.text

scripts/test_health_check_retry.py:99: AssertionError
```