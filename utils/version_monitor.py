import json
import requests
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

class SDKVersionMonitor:
    """Monitors SDK package versions on PyPI and npm.
    
    Tracks versions of specified SDK packages and detects when
    new versions are released.
    
    Attributes:
        config_path: Path to version tracking config file
    """

    def __init__(self, config_path: str = "config/sdk_versions.json"):
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
    def load_current_versions(self) -> Dict[str, str]:
        """Load currently tracked SDK versions"""
        if not self.config_path.exists():
            return {}
        
        with open(self.config_path) as f:
            return json.load(f)
    
    def save_versions(self, versions: Dict[str, str]):
        """Save current versions to config file"""
        with open(self.config_path, 'w') as f:
            json.dump({
                'versions': versions,
                'last_checked': datetime.utcnow().isoformat()
            }, f, indent=2)
    
    async def get_pypi_version(self, package: str) -> Optional[str]:
        """Get latest version from PyPI"""
        try:
            response = requests.get(f"https://pypi.org/pypi/{package}/json")
            response.raise_for_status()
            return response.json()['info']['version']
        except Exception as e:
            self.logger.error(f"Error fetching PyPI version for {package}: {e}")
            return None
    
    async def get_npm_version(self, package: str) -> Optional[str]:
        """Get latest version from npm"""
        try:
            response = requests.get(f"https://registry.npmjs.org/{package}")
            response.raise_for_status()
            return response.json()['dist-tags']['latest']
        except Exception as e:
            self.logger.error(f"Error fetching npm version for {package}: {e}")
            return None
    
    async def check_versions(self) -> Dict[str, Dict[str, str]]:
        """Check for SDK version updates.
        
        Returns:
            Dict mapping package names to version info:
            {
                "package-name": {
                    "current": "1.0.0",
                    "latest": "1.1.0"
                }
            }
        """
        current_versions = self.load_current_versions()
        updates_needed = {}
        
        # Define packages to monitor
        packages = {
            'pypi': ['anthropic', 'anthropic-sdk'],
            'npm': ['@anthropic-ai/sdk']
        }
        
        # Check PyPI packages
        for pkg in packages['pypi']:
            latest = await self.get_pypi_version(pkg)
            if latest and latest != current_versions.get(pkg):
                updates_needed[pkg] = {
                    'current': current_versions.get(pkg),
                    'latest': latest
                }
        
        # Check npm packages
        for pkg in packages['npm']:
            latest = await self.get_npm_version(pkg)
            if latest and latest != current_versions.get(pkg):
                updates_needed[pkg] = {
                    'current': current_versions.get(pkg),
                    'latest': latest
                }
        
        return updates_needed

async def trigger_validation(updates: Dict[str, Dict[str, str]]):
    """Trigger documentation validation when updates are found.
    
    Args:
        updates: Dictionary of package updates detected
    """
    from build.build import validate_api_docs
    import os
    
    if not updates:
        return
    
    logging.info("SDK updates found, triggering documentation validation:")
    for pkg, versions in updates.items():
        logging.info(f"  {pkg}: {versions['current']} -> {versions['latest']}")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    await validate_api_docs(api_key)

async def main():
    """Entry point for version monitoring script.
    
    Checks for SDK updates and triggers documentation validation
    if changes are detected.
    """
    logging.basicConfig(level=logging.INFO)
    monitor = SDKVersionMonitor()
    
    updates = await monitor.check_versions()
    if updates:
        await trigger_validation(updates)
    
if __name__ == "__main__":
    asyncio.run(main())
