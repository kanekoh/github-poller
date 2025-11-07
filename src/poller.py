#!/usr/bin/env python3
"""
GitHub Repository Poller for Kubernetes
Monitors GitHub repositories and triggers Tekton pipelines on changes.
"""

import os
import sys
import logging
import yaml
from datetime import datetime
from typing import Dict, List, Optional
from github import Github, GithubException
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitHubPoller:
    """Polls GitHub repositories and triggers Tekton pipelines on changes."""
    
    def __init__(self):
        """Initialize the poller with Kubernetes and GitHub clients."""
        self.namespace = os.getenv('NAMESPACE', 'default')
        self.configmap_name = os.getenv('CONFIGMAP_NAME', 'github-poller-config')
        self.github_token = self._get_github_token()
        
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            # Fallback to local kubeconfig for development
            config.load_kube_config()
        
        self.k8s_core_client = client.CoreV1Api()
        self.k8s_custom_client = client.CustomObjectsApi()
        self.github_client = Github(self.github_token)
        
    def _get_github_token(self) -> str:
        """Get GitHub token from environment or Secret."""
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            token_file = os.getenv('GITHUB_TOKEN_FILE', '/secrets/github-token')
            try:
                with open(token_file, 'r') as f:
                    token = f.read().strip()
            except FileNotFoundError:
                logger.error(f"GitHub token not found. Set GITHUB_TOKEN env var or provide {token_file}")
                sys.exit(1)
        return token
    
    def get_configmap(self) -> Dict:
        """Retrieve the ConfigMap containing repository configurations."""
        try:
            configmap = self.k8s_core_client.read_namespaced_config_map(
                name=self.configmap_name,
                namespace=self.namespace
            )
            data = configmap.data.get('config.yaml', '{}')
            return yaml.safe_load(data)
        except ApiException as e:
            logger.error(f"Failed to read ConfigMap: {e}")
            sys.exit(1)
    
    def update_configmap(self, config_data: Dict) -> None:
        """Update the ConfigMap with new SHA values."""
        try:
            configmap = self.k8s_core_client.read_namespaced_config_map(
                name=self.configmap_name,
                namespace=self.namespace
            )
            configmap.data['config.yaml'] = yaml.dump(config_data)
            self.k8s_core_client.replace_namespaced_config_map(
                name=self.configmap_name,
                namespace=self.namespace,
                body=configmap
            )
            logger.info(f"Updated ConfigMap: {self.configmap_name}")
        except ApiException as e:
            logger.error(f"Failed to update ConfigMap: {e}")
            raise
    
    def get_latest_commit_sha(self, repo_url: str, branch: str) -> Optional[str]:
        """
        Get the latest commit SHA for a repository branch using GitHub API.
        
        Args:
            repo_url: GitHub repository URL (e.g., https://github.com/org/repo)
            branch: Branch name
            
        Returns:
            Latest commit SHA or None if error occurs
        """
        try:
            # Extract owner/repo from URL
            parts = repo_url.rstrip('/').split('/')
            owner, repo_name = parts[-2], parts[-1]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            repo = self.github_client.get_repo(f"{owner}/{repo_name}")
            branch_obj = repo.get_branch(branch)
            sha = branch_obj.commit.sha
            
            logger.info(f"Retrieved SHA for {owner}/{repo_name}@{branch}: {sha[:7]}")
            return sha
            
        except GithubException as e:
            logger.error(f"GitHub API error for {repo_url}@{branch}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting commit SHA for {repo_url}@{branch}: {e}")
            return None
    
    def _expand_placeholders(self, value: str, repo_config: Dict) -> str:
        """
        Expand placeholders in parameter values.
        
        Supported placeholders:
        - ${repo.url}: Repository URL
        - ${repo.branch}: Branch name
        - ${repo.name}: Repository name
        
        Args:
            value: Value that may contain placeholders
            repo_config: Repository configuration
            
        Returns:
            Value with placeholders expanded
        """
        if not isinstance(value, str):
            return value
        
        replacements = {
            '${repo.url}': repo_config.get('url', ''),
            '${repo.branch}': repo_config.get('branch', 'main'),
            '${repo.name}': repo_config.get('name', ''),
        }
        
        result = value
        for placeholder, replacement in replacements.items():
            result = result.replace(placeholder, replacement)
        
        return result
    
    def trigger_tekton_pipeline(self, repo_config: Dict) -> bool:
        """
        Trigger a Tekton pipeline by creating a PipelineRun resource.
        
        Args:
            repo_config: Repository configuration containing pipeline details
            
        Returns:
            True if pipeline was triggered successfully, False otherwise
        """
        pipeline_name = repo_config.get('pipeline')
        if not pipeline_name:
            logger.error(f"No pipeline specified for repository: {repo_config.get('name')}")
            return False
        
        repo_name = repo_config.get('name', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        pipelinerun_name = f"{pipeline_name}-{repo_name}-{timestamp}".lower()[:63]
        
        # Build PipelineRun spec
        pipeline_run = {
            "apiVersion": "tekton.dev/v1beta1",
            "kind": "PipelineRun",
            "metadata": {
                "name": pipelinerun_name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "github-poller",
                    "github-poller/repository": repo_name,
                    "tekton.dev/pipeline": pipeline_name
                }
            },
            "spec": {
                "pipelineRef": {
                    "name": pipeline_name
                }
            }
        }
        
        # Add service account if specified
        service_account = repo_config.get('serviceAccount')
        if service_account:
            pipeline_run['spec']['serviceAccountName'] = service_account
        
        # Add parameters with placeholder expansion
        params = repo_config.get('params', [])
        if params:
            pipeline_run['spec']['params'] = []
            for param in params:
                param_name = param.get('name')
                param_value = param.get('value')
                if param_name and param_value is not None:
                    # Expand placeholders in parameter value
                    expanded_value = self._expand_placeholders(str(param_value), repo_config)
                    pipeline_run['spec']['params'].append({
                        "name": param_name,
                        "value": expanded_value
                    })
        
        # Add workspaces if specified
        workspaces = repo_config.get('workspaces', [])
        if workspaces:
            pipeline_run['spec']['workspaces'] = []
            for workspace in workspaces:
                ws_name = workspace.get('name')
                ws_claim = workspace.get('claimName')
                if ws_name and ws_claim:
                    pipeline_run['spec']['workspaces'].append({
                        "name": ws_name,
                        "persistentVolumeClaim": {
                            "claimName": ws_claim
                        }
                    })
        
        # Add timeout if specified
        timeout = repo_config.get('timeout')
        if timeout:
            pipeline_run['spec']['timeout'] = timeout
        
        # Create PipelineRun using Kubernetes API
        try:
            logger.info(f"Creating PipelineRun: {pipelinerun_name}")
            logger.debug(f"PipelineRun spec: {yaml.dump(pipeline_run)}")
            
            result = self.k8s_custom_client.create_namespaced_custom_object(
                group="tekton.dev",
                version="v1beta1",
                namespace=self.namespace,
                plural="pipelineruns",
                body=pipeline_run
            )
            
            logger.info(f"PipelineRun created successfully: {pipelinerun_name}")
            return True
            
        except ApiException as e:
            logger.error(f"Failed to create PipelineRun: {e}")
            logger.error(f"Response body: {e.body}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating PipelineRun: {e}", exc_info=True)
            return False
    
    def poll_repositories(self) -> None:
        """Main polling logic: check all repositories and trigger pipelines on changes."""
        config_data = self.get_configmap()
        repositories = config_data.get('repositories', [])
        
        if not repositories:
            logger.warning("No repositories configured in ConfigMap")
            return
        
        logger.info(f"Polling {len(repositories)} repositories...")
        config_updated = False
        
        for repo_config in repositories:
            repo_name = repo_config.get('name', 'unknown')
            repo_url = repo_config.get('url')
            branch = repo_config.get('branch', 'main')
            last_sha = repo_config.get('lastCheckedSHA', '')
            
            if not repo_url:
                logger.warning(f"Repository '{repo_name}' has no URL, skipping")
                continue
            
            logger.info(f"Checking repository: {repo_name} ({branch})")
            
            # Get latest commit SHA
            current_sha = self.get_latest_commit_sha(repo_url, branch)
            if not current_sha:
                logger.warning(f"Could not retrieve SHA for {repo_name}, skipping")
                continue
            
            # Check if there's a change
            if last_sha and current_sha == last_sha:
                logger.info(f"No changes detected for {repo_name}")
                continue
            
            if not last_sha:
                logger.info(f"First check for {repo_name}, recording SHA: {current_sha[:7]}")
            else:
                logger.info(f"Change detected for {repo_name}: {last_sha[:7]} -> {current_sha[:7]}")
                
                # Trigger pipeline
                if self.trigger_tekton_pipeline(repo_config):
                    logger.info(f"Successfully triggered pipeline for {repo_name}")
                else:
                    logger.error(f"Failed to trigger pipeline for {repo_name}")
                    continue
            
            # Update SHA in config
            repo_config['lastCheckedSHA'] = current_sha
            config_updated = True
        
        # Save updated ConfigMap if any changes were detected
        if config_updated:
            try:
                self.update_configmap(config_data)
                logger.info("ConfigMap updated with new SHA values")
            except Exception as e:
                logger.error(f"Failed to update ConfigMap: {e}")
    
    def run(self) -> None:
        """Run the poller."""
        logger.info("Starting GitHub Poller...")
        logger.info(f"Namespace: {self.namespace}")
        logger.info(f"ConfigMap: {self.configmap_name}")
        
        try:
            self.poll_repositories()
            logger.info("Polling completed successfully")
        except Exception as e:
            logger.error(f"Polling failed with error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point."""
    poller = GitHubPoller()
    poller.run()


if __name__ == '__main__':
    main()

