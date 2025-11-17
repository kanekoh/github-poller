"""
GitHub 認証機能のテスト
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from poller import GitHubPoller


class TestAuthentication:
    """GitHub 認証のテスト"""
    
    @pytest.fixture
    def mock_k8s_clients(self):
        """Kubernetes クライアントをモック"""
        with patch('poller.config.load_incluster_config'):
            with patch('poller.client.CoreV1Api'):
                with patch('poller.client.CustomObjectsApi'):
                    yield
    
    def test_pat_authentication_from_env(self, monkeypatch, mock_k8s_clients):
        """環境変数からの PAT 認証"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'pat')
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_test_token_123')
        
        with patch('poller.Github') as mock_github:
            poller = GitHubPoller()
            
            assert poller.auth_type == 'pat'
            assert poller.github_token == 'ghp_test_token_123'
            mock_github.assert_called_once_with('ghp_test_token_123')
    
    def test_pat_authentication_from_file(self, monkeypatch, mock_k8s_clients):
        """ファイルからの PAT 認証"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'pat')
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        
        mock_file_content = 'ghp_file_token_456'
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            with patch('poller.Github') as mock_github:
                poller = GitHubPoller()
                
                assert poller.github_token == 'ghp_file_token_456'
                mock_github.assert_called_once_with('ghp_file_token_456')
    
    def test_github_app_authentication(self, monkeypatch, mock_k8s_clients):
        """GitHub Apps 認証"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'app')
        monkeypatch.setenv('GITHUB_APP_ID', '123456')
        monkeypatch.setenv('GITHUB_INSTALLATION_ID', '987654')
        monkeypatch.setenv('GITHUB_PRIVATE_KEY', '''-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890
-----END RSA PRIVATE KEY-----''')
        
        mock_response = Mock()
        mock_response.json.return_value = {
            'token': 'ghs_installation_token_xyz',
            'expires_at': '2025-01-01T00:00:00Z'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('poller.jwt.encode', return_value='jwt_token'):
            with patch('poller.requests.post', return_value=mock_response):
                with patch('poller.Github') as mock_github:
                    poller = GitHubPoller()
                    
                    assert poller.auth_type == 'app'
                    assert poller.github_token == 'ghs_installation_token_xyz'
                    mock_github.assert_called_once_with('ghs_installation_token_xyz')
    
    def test_github_app_jwt_generation(self, monkeypatch, mock_k8s_clients):
        """JWT 生成のテスト"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'app')
        monkeypatch.setenv('GITHUB_APP_ID', '123456')
        monkeypatch.setenv('GITHUB_INSTALLATION_ID', '987654')
        monkeypatch.setenv('GITHUB_PRIVATE_KEY', '''-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890
-----END RSA PRIVATE KEY-----''')
        
        mock_response = Mock()
        mock_response.json.return_value = {
            'token': 'ghs_token',
            'expires_at': '2025-01-01T00:00:00Z'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('poller.jwt.encode') as mock_jwt_encode:
            mock_jwt_encode.return_value = 'generated_jwt_token'
            with patch('poller.requests.post', return_value=mock_response):
                with patch('poller.Github'):
                    with patch('poller.time.time', return_value=1000000):
                        poller = GitHubPoller()
                        
                        # JWT の生成が呼ばれたことを確認
                        mock_jwt_encode.assert_called_once()
                        call_args = mock_jwt_encode.call_args
                        
                        # Payload を確認
                        payload = call_args[0][0]
                        assert payload['iss'] == '123456'
                        assert payload['iat'] == 1000000
                        assert payload['exp'] == 1000000 + 600
                        
                        # アルゴリズムを確認
                        assert call_args[1]['algorithm'] == 'RS256'
    
    def test_github_app_installation_token_fetch(self, monkeypatch, mock_k8s_clients):
        """Installation トークン取得のテスト"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'app')
        monkeypatch.setenv('GITHUB_APP_ID', '123456')
        monkeypatch.setenv('GITHUB_INSTALLATION_ID', '987654')
        monkeypatch.setenv('GITHUB_PRIVATE_KEY', '''-----BEGIN RSA PRIVATE KEY-----
KEY
-----END RSA PRIVATE KEY-----''')
        
        mock_response = Mock()
        mock_response.json.return_value = {
            'token': 'ghs_installation_token',
            'expires_at': '2025-01-01T00:00:00Z'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('poller.jwt.encode', return_value='jwt_token'):
            with patch('poller.requests.post') as mock_post:
                mock_post.return_value = mock_response
                with patch('poller.Github'):
                    poller = GitHubPoller()
                    
                    # API コールの確認
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    
                    # URL の確認
                    assert call_args[0][0] == 'https://api.github.com/app/installations/987654/access_tokens'
                    
                    # ヘッダーの確認
                    headers = call_args[1]['headers']
                    assert headers['Authorization'] == 'Bearer jwt_token'
                    assert headers['Accept'] == 'application/vnd.github+json'
    
    def test_github_app_fallback_to_pat(self, monkeypatch, mock_k8s_clients):
        """GitHub Apps 失敗時の PAT フォールバック"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'app')
        monkeypatch.setenv('GITHUB_APP_ID', '123456')
        monkeypatch.setenv('GITHUB_INSTALLATION_ID', '987654')
        monkeypatch.setenv('GITHUB_PRIVATE_KEY', 'invalid_key')
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_fallback_token')
        
        with patch('poller.jwt.encode', side_effect=Exception('JWT generation failed')):
            with patch('poller.Github') as mock_github:
                poller = GitHubPoller()
                
                # PAT にフォールバックしていることを確認
                assert poller.github_token == 'ghp_fallback_token'
                mock_github.assert_called_once_with('ghp_fallback_token')
    
    def test_default_auth_type_is_app(self, monkeypatch, mock_k8s_clients):
        """デフォルトの認証タイプが 'app' であることを確認"""
        # GITHUB_AUTH_TYPE を設定しない
        monkeypatch.delenv('GITHUB_AUTH_TYPE', raising=False)
        monkeypatch.setenv('GITHUB_APP_ID', '123456')
        monkeypatch.setenv('GITHUB_INSTALLATION_ID', '987654')
        monkeypatch.setenv('GITHUB_PRIVATE_KEY', '''-----BEGIN RSA PRIVATE KEY-----
KEY
-----END RSA PRIVATE KEY-----''')
        
        mock_response = Mock()
        mock_response.json.return_value = {
            'token': 'ghs_token',
            'expires_at': '2025-01-01T00:00:00Z'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('poller.jwt.encode', return_value='jwt'):
            with patch('poller.requests.post', return_value=mock_response):
                with patch('poller.Github'):
                    poller = GitHubPoller()
                    
                    assert poller.auth_type == 'app'
    
    def test_missing_pat_token(self, monkeypatch, mock_k8s_clients):
        """PAT トークンが見つからない場合のエラー"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'pat')
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        
        with patch('builtins.open', side_effect=FileNotFoundError):
            with pytest.raises(SystemExit):
                GitHubPoller()
    
    def test_missing_github_app_credentials(self, monkeypatch, mock_k8s_clients):
        """GitHub Apps 認証情報が見つからない場合"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'app')
        monkeypatch.delenv('GITHUB_APP_ID', raising=False)
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_fallback')  # フォールバック用
        
        with patch('builtins.open', side_effect=FileNotFoundError):
            with patch('poller.Github'):
                # ValueError が発生するが、PAT にフォールバック
                poller = GitHubPoller()
                assert poller.github_token == 'ghp_fallback'
    
    def test_read_secret_from_file(self, monkeypatch, mock_k8s_clients):
        """Secret ファイルからの読み込み"""
        monkeypatch.setenv('GITHUB_AUTH_TYPE', 'app')
        monkeypatch.delenv('GITHUB_APP_ID', raising=False)
        monkeypatch.delenv('GITHUB_INSTALLATION_ID', raising=False)
        monkeypatch.delenv('GITHUB_PRIVATE_KEY', raising=False)
        monkeypatch.setenv('GITHUB_TOKEN', 'ghp_fallback')
        
        mock_files = {
            '/secrets/app-id': '123456',
            '/secrets/installation-id': '987654',
            '/secrets/private-key': '-----BEGIN RSA PRIVATE KEY-----\nKEY\n-----END RSA PRIVATE KEY-----'
        }
        
        def mock_open_side_effect(filename, mode='r'):
            if filename in mock_files:
                from io import StringIO
                return StringIO(mock_files[filename])
            raise FileNotFoundError(f"No such file: {filename}")
        
        mock_response = Mock()
        mock_response.json.return_value = {
            'token': 'ghs_token',
            'expires_at': '2025-01-01T00:00:00Z'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('builtins.open', side_effect=mock_open_side_effect):
            with patch('poller.jwt.encode', return_value='jwt'):
                with patch('poller.requests.post', return_value=mock_response):
                    with patch('poller.Github'):
                        poller = GitHubPoller()
                        assert poller.auth_type == 'app'

