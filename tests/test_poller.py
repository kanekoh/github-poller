"""
GitHub Poller のユニットテスト
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import yaml

# テスト対象のモジュールをインポート
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from poller import GitHubPoller


class TestGitHubPoller:
    """GitHubPoller クラスのテスト"""
    
    @pytest.fixture
    def mock_env(self, monkeypatch):
        """環境変数のモック"""
        monkeypatch.setenv('NAMESPACE', 'test-namespace')
        monkeypatch.setenv('CONFIGMAP_NAME', 'test-configmap')
        monkeypatch.setenv('GITHUB_TOKEN', 'test-token-123')
    
    @pytest.fixture
    def poller(self, mock_env):
        """GitHubPoller インスタンスを作成"""
        with patch('poller.config.load_incluster_config'):
            with patch('poller.client.CoreV1Api'):
                with patch('poller.client.CustomObjectsApi'):
                    with patch('poller.Github'):
                        poller = GitHubPoller()
                        return poller
    
    def test_expand_placeholders(self, poller):
        """プレースホルダー展開のテスト"""
        repo_config = {
            'name': 'test-repo',
            'url': 'https://github.com/test-org/test-repo',
            'branch': 'develop'
        }
        
        # URL のプレースホルダー
        result = poller._expand_placeholders('${repo.url}', repo_config)
        assert result == 'https://github.com/test-org/test-repo'
        
        # ブランチのプレースホルダー
        result = poller._expand_placeholders('${repo.branch}', repo_config)
        assert result == 'develop'
        
        # 名前のプレースホルダー
        result = poller._expand_placeholders('${repo.name}', repo_config)
        assert result == 'test-repo'
        
        # 複数のプレースホルダー
        result = poller._expand_placeholders(
            'Building ${repo.name} from ${repo.url}@${repo.branch}',
            repo_config
        )
        assert result == 'Building test-repo from https://github.com/test-org/test-repo@develop'
        
        # プレースホルダーなし
        result = poller._expand_placeholders('plain text', repo_config)
        assert result == 'plain text'
    
    def test_expand_placeholders_with_default_branch(self, poller):
        """デフォルトブランチでのプレースホルダー展開"""
        repo_config = {
            'name': 'test-repo',
            'url': 'https://github.com/test-org/test-repo'
            # branch が指定されていない
        }
        
        result = poller._expand_placeholders('${repo.branch}', repo_config)
        assert result == 'main'  # デフォルト値
    
    def test_get_latest_commit_sha_success(self, poller):
        """GitHub API からコミット SHA を取得するテスト（成功）"""
        # GitHub API のモック
        mock_commit = Mock()
        mock_commit.sha = 'abc123def456'
        
        mock_branch = Mock()
        mock_branch.commit = mock_commit
        
        mock_repo = Mock()
        mock_repo.get_branch.return_value = mock_branch
        
        poller.github_client.get_repo.return_value = mock_repo
        
        # テスト実行
        sha = poller.get_latest_commit_sha(
            'https://github.com/test-org/test-repo',
            'main'
        )
        
        # 検証
        assert sha == 'abc123def456'
        poller.github_client.get_repo.assert_called_once_with('test-org/test-repo')
        mock_repo.get_branch.assert_called_once_with('main')
    
    def test_get_latest_commit_sha_with_git_extension(self, poller):
        """.git 拡張子付き URL のテスト"""
        mock_commit = Mock()
        mock_commit.sha = 'xyz789'
        
        mock_branch = Mock()
        mock_branch.commit = mock_commit
        
        mock_repo = Mock()
        mock_repo.get_branch.return_value = mock_branch
        
        poller.github_client.get_repo.return_value = mock_repo
        
        sha = poller.get_latest_commit_sha(
            'https://github.com/test-org/test-repo.git',
            'develop'
        )
        
        assert sha == 'xyz789'
        poller.github_client.get_repo.assert_called_once_with('test-org/test-repo')
    
    def test_get_latest_commit_sha_github_error(self, poller):
        """GitHub API エラー時のテスト"""
        from github import GithubException
        
        poller.github_client.get_repo.side_effect = GithubException(
            404, {'message': 'Not Found'}
        )
        
        sha = poller.get_latest_commit_sha(
            'https://github.com/test-org/nonexistent',
            'main'
        )
        
        assert sha is None
    
    def test_trigger_tekton_pipeline_basic(self, poller):
        """基本的な PipelineRun 作成のテスト"""
        poller.namespace = 'test-namespace'
        poller.k8s_custom_client.create_namespaced_custom_object.return_value = {
            'metadata': {'name': 'test-run'}
        }
        
        repo_config = {
            'name': 'test-repo',
            'url': 'https://github.com/test-org/test-repo',
            'branch': 'main',
            'pipeline': 'test-pipeline',
            'params': [
                {'name': 'repo-url', 'value': '${repo.url}'},
                {'name': 'branch', 'value': '${repo.branch}'}
            ]
        }
        
        result = poller.trigger_tekton_pipeline(repo_config)
        
        # 成功を確認
        assert result is True
        
        # API 呼び出しを確認
        poller.k8s_custom_client.create_namespaced_custom_object.assert_called_once()
        call_args = poller.k8s_custom_client.create_namespaced_custom_object.call_args
        
        assert call_args[1]['group'] == 'tekton.dev'
        assert call_args[1]['version'] == 'v1beta1'
        assert call_args[1]['plural'] == 'pipelineruns'
        assert call_args[1]['namespace'] == 'test-namespace'
        
        # PipelineRun の内容を確認
        pipeline_run = call_args[1]['body']
        assert pipeline_run['spec']['pipelineRef']['name'] == 'test-pipeline'
        assert len(pipeline_run['spec']['params']) == 2
        assert pipeline_run['spec']['params'][0]['value'] == 'https://github.com/test-org/test-repo'
        assert pipeline_run['spec']['params'][1]['value'] == 'main'
    
    def test_trigger_tekton_pipeline_with_workspace(self, poller):
        """ワークスペース指定ありの PipelineRun 作成"""
        poller.namespace = 'test-namespace'
        poller.k8s_custom_client.create_namespaced_custom_object.return_value = {}
        
        repo_config = {
            'name': 'test-repo',
            'pipeline': 'test-pipeline',
            'workspaces': [
                {'name': 'source', 'claimName': 'test-pvc'}
            ]
        }
        
        result = poller.trigger_tekton_pipeline(repo_config)
        assert result is True
        
        call_args = poller.k8s_custom_client.create_namespaced_custom_object.call_args
        pipeline_run = call_args[1]['body']
        
        assert 'workspaces' in pipeline_run['spec']
        assert len(pipeline_run['spec']['workspaces']) == 1
        assert pipeline_run['spec']['workspaces'][0]['name'] == 'source'
        assert pipeline_run['spec']['workspaces'][0]['persistentVolumeClaim']['claimName'] == 'test-pvc'
    
    def test_trigger_tekton_pipeline_with_serviceaccount(self, poller):
        """ServiceAccount 指定ありの PipelineRun 作成"""
        poller.namespace = 'test-namespace'
        poller.k8s_custom_client.create_namespaced_custom_object.return_value = {}
        
        repo_config = {
            'name': 'test-repo',
            'pipeline': 'test-pipeline',
            'serviceAccount': 'pipeline-sa'
        }
        
        result = poller.trigger_tekton_pipeline(repo_config)
        assert result is True
        
        call_args = poller.k8s_custom_client.create_namespaced_custom_object.call_args
        pipeline_run = call_args[1]['body']
        
        assert pipeline_run['spec']['serviceAccountName'] == 'pipeline-sa'
    
    def test_trigger_tekton_pipeline_with_timeout(self, poller):
        """タイムアウト指定ありの PipelineRun 作成"""
        poller.namespace = 'test-namespace'
        poller.k8s_custom_client.create_namespaced_custom_object.return_value = {}
        
        repo_config = {
            'name': 'test-repo',
            'pipeline': 'test-pipeline',
            'timeout': '2h'
        }
        
        result = poller.trigger_tekton_pipeline(repo_config)
        assert result is True
        
        call_args = poller.k8s_custom_client.create_namespaced_custom_object.call_args
        pipeline_run = call_args[1]['body']
        
        assert pipeline_run['spec']['timeout'] == '2h'
    
    def test_trigger_tekton_pipeline_no_pipeline_name(self, poller):
        """パイプライン名なしの場合のテスト"""
        repo_config = {
            'name': 'test-repo'
            # pipeline キーがない
        }
        
        result = poller.trigger_tekton_pipeline(repo_config)
        assert result is False
    
    def test_trigger_tekton_pipeline_api_error(self, poller):
        """API エラー時のテスト"""
        from kubernetes.client.rest import ApiException
        
        poller.namespace = 'test-namespace'
        poller.k8s_custom_client.create_namespaced_custom_object.side_effect = ApiException(
            status=403,
            reason='Forbidden'
        )
        
        repo_config = {
            'name': 'test-repo',
            'pipeline': 'test-pipeline'
        }
        
        result = poller.trigger_tekton_pipeline(repo_config)
        assert result is False
    
    def test_get_configmap(self, poller):
        """ConfigMap 読み取りのテスト"""
        mock_configmap = Mock()
        mock_configmap.data = {
            'config.yaml': yaml.dump({
                'repositories': [
                    {'name': 'repo1', 'url': 'https://github.com/org/repo1'}
                ]
            })
        }
        
        poller.k8s_core_client.read_namespaced_config_map.return_value = mock_configmap
        
        config = poller.get_configmap()
        
        assert 'repositories' in config
        assert len(config['repositories']) == 1
        assert config['repositories'][0]['name'] == 'repo1'
    
    def test_update_configmap(self, poller):
        """ConfigMap 更新のテスト"""
        mock_configmap = Mock()
        mock_configmap.data = {}
        
        poller.k8s_core_client.read_namespaced_config_map.return_value = mock_configmap
        poller.k8s_core_client.replace_namespaced_config_map.return_value = None
        
        config_data = {
            'repositories': [
                {'name': 'repo1', 'lastCheckedSHA': 'abc123'}
            ]
        }
        
        poller.update_configmap(config_data)
        
        # 更新が呼ばれたことを確認
        poller.k8s_core_client.replace_namespaced_config_map.assert_called_once()
    
    def test_poll_repositories_no_change(self, poller):
        """変更なしの場合のポーリングテスト"""
        config_data = {
            'repositories': [
                {
                    'name': 'test-repo',
                    'url': 'https://github.com/test-org/test-repo',
                    'branch': 'main',
                    'pipeline': 'test-pipeline',
                    'lastCheckedSHA': 'abc123'
                }
            ]
        }
        
        mock_configmap = Mock()
        mock_configmap.data = {'config.yaml': yaml.dump(config_data)}
        
        poller.k8s_core_client.read_namespaced_config_map.return_value = mock_configmap
        
        # 同じ SHA を返す
        poller.get_latest_commit_sha = Mock(return_value='abc123')
        poller.trigger_tekton_pipeline = Mock()
        
        poller.poll_repositories()
        
        # パイプラインは起動されないはず
        poller.trigger_tekton_pipeline.assert_not_called()
    
    def test_poll_repositories_with_change(self, poller):
        """変更ありの場合のポーリングテスト"""
        config_data = {
            'repositories': [
                {
                    'name': 'test-repo',
                    'url': 'https://github.com/test-org/test-repo',
                    'branch': 'main',
                    'pipeline': 'test-pipeline',
                    'params': [],
                    'lastCheckedSHA': 'old-sha'
                }
            ]
        }
        
        mock_configmap = Mock()
        mock_configmap.data = {'config.yaml': yaml.dump(config_data)}
        
        poller.k8s_core_client.read_namespaced_config_map.return_value = mock_configmap
        poller.k8s_core_client.replace_namespaced_config_map.return_value = None
        
        # 新しい SHA を返す
        poller.get_latest_commit_sha = Mock(return_value='new-sha')
        poller.trigger_tekton_pipeline = Mock(return_value=True)
        
        poller.poll_repositories()
        
        # パイプラインが起動されるはず
        poller.trigger_tekton_pipeline.assert_called_once()
        
        # ConfigMap が更新されるはず
        poller.k8s_core_client.replace_namespaced_config_map.assert_called_once()
    
    def test_poll_repositories_first_check(self, poller):
        """初回チェック（SHA なし）の場合のテスト"""
        config_data = {
            'repositories': [
                {
                    'name': 'test-repo',
                    'url': 'https://github.com/test-org/test-repo',
                    'branch': 'main',
                    'pipeline': 'test-pipeline',
                    'lastCheckedSHA': ''  # 初回
                }
            ]
        }
        
        mock_configmap = Mock()
        mock_configmap.data = {'config.yaml': yaml.dump(config_data)}
        
        poller.k8s_core_client.read_namespaced_config_map.return_value = mock_configmap
        poller.k8s_core_client.replace_namespaced_config_map.return_value = None
        
        poller.get_latest_commit_sha = Mock(return_value='first-sha')
        poller.trigger_tekton_pipeline = Mock(return_value=True)
        
        poller.poll_repositories()
        
        # 初回なのでパイプラインは起動されない
        poller.trigger_tekton_pipeline.assert_not_called()
        
        # ただし SHA は記録される
        poller.k8s_core_client.replace_namespaced_config_map.assert_called_once()
    
    def test_poll_repositories_github_error(self, poller):
        """GitHub API エラー時のテスト"""
        config_data = {
            'repositories': [
                {
                    'name': 'test-repo',
                    'url': 'https://github.com/test-org/test-repo',
                    'branch': 'main',
                    'pipeline': 'test-pipeline',
                    'lastCheckedSHA': 'abc123'
                }
            ]
        }
        
        mock_configmap = Mock()
        mock_configmap.data = {'config.yaml': yaml.dump(config_data)}
        
        poller.k8s_core_client.read_namespaced_config_map.return_value = mock_configmap
        
        # GitHub API がエラーを返す
        poller.get_latest_commit_sha = Mock(return_value=None)
        poller.trigger_tekton_pipeline = Mock()
        
        poller.poll_repositories()
        
        # パイプラインは起動されない
        poller.trigger_tekton_pipeline.assert_not_called()
        
        # ConfigMap は更新されない
        poller.k8s_core_client.replace_namespaced_config_map.assert_not_called()


class TestPipelineRunNaming:
    """PipelineRun の命名規則テスト"""
    
    def test_pipelinerun_name_format(self):
        """PipelineRun 名のフォーマットテスト"""
        with patch('poller.config.load_incluster_config'):
            with patch('poller.client.CoreV1Api'):
                with patch('poller.client.CustomObjectsApi') as mock_custom:
                    with patch('poller.Github'):
                        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test'}):
                            poller = GitHubPoller()
                            poller.namespace = 'test'
                            
                            mock_custom.return_value.create_namespaced_custom_object.return_value = {}
                            
                            repo_config = {
                                'name': 'my-app',
                                'pipeline': 'build-pipeline'
                            }
                            
                            poller.trigger_tekton_pipeline(repo_config)
                            
                            call_args = mock_custom.return_value.create_namespaced_custom_object.call_args
                            pipeline_run = call_args[1]['body']
                            
                            # 名前の形式を確認
                            name = pipeline_run['metadata']['name']
                            assert name.startswith('build-pipeline-my-app-')
                            assert len(name) <= 63  # Kubernetes の名前長制限

