from unittest.mock import patch, MagicMock

# Import the module to test
from ui import auth

@patch("ui.auth.os.getenv")
@patch("ui.auth.msal.ConfidentialClientApplication")
def test_get_msal_app_success(mock_msal, mock_getenv):
    # Setup mock env vars
    env_vars = {
        "UI_CLIENT_ID": "fake-client",
        "UI_CLIENT_SECRET": "fake-secret",
        "AZURE_TENANT_ID": "fake-tenant"
    }
    mock_getenv.side_effect = lambda k, d=None: env_vars.get(k, d)
    
    # Execute
    app = auth.get_msal_app()
    
    # Assert
    assert app is not None
    mock_msal.assert_called_once_with(
        "fake-client",
        authority="https://login.microsoftonline.com/fake-tenant",
        client_credential="fake-secret"
    )

@patch("ui.auth.os.getenv")
def test_get_msal_app_missing_vars(mock_getenv):
    # Setup mock env vars with missing secret
    env_vars = {
        "UI_CLIENT_ID": "fake-client",
        "UI_CLIENT_SECRET": None,
        "AZURE_TENANT_ID": "fake-tenant"
    }
    mock_getenv.side_effect = lambda k, d=None: env_vars.get(k, d)
    
    # Execute (using patch for st to prevent actual rendering during test)
    with patch("ui.auth.st") as mock_st:
        app = auth.get_msal_app()
        
    # Assert
    assert app is None
    mock_st.error.assert_called_once()


@patch("ui.auth.get_msal_app")
def test_get_login_url(mock_get_msal_app):
    mock_app = MagicMock()
    mock_app.get_authorization_request_url.return_value = "https://login.microsoftonline.com/auth"
    mock_get_msal_app.return_value = mock_app
    
    with patch("ui.auth.os.getenv", return_value="http://localhost:8501"):
        url = auth.get_login_url()
        
    assert url == "https://login.microsoftonline.com/auth"
    mock_app.get_authorization_request_url.assert_called_once_with(
        ["User.Read"],
        redirect_uri="http://localhost:8501"
    )
