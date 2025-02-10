from pathlib import Path
import json
import time
import hashlib
import logging
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import tempfile

@dataclass
class FileState:
    """State information for a tracked file."""
    content_hash: str
    dependencies: List[str]
    validation_result: bool

class IncrementalTracker:
    """Tracks changes for incremental builds."""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        # Store cache in permanent location
        self.cache_dir = Path(".cache")  # Store in project root
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.cache_dir / "build_state.json"
        self.logger = logging.getLogger(__name__)
        self.state: Dict[str, FileState] = {}
        self._load_state()

    def _load_state(self):
        """Load previous build state."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.logger.debug(f"Loaded state from {self.state_file}: {data}")
                self.state = {
                    path: FileState(**state_data)
                    for path, state_data in data.items()
                }
            except Exception as e:
                self.logger.warning(f"Failed to load state file: {e}")
                self.state = {}
        else:
            self.logger.debug(f"No state file found at {self.state_file}")
            self.state = {}
            
    def save_state(self):
        """Save current build state."""
        try:
            serializable_state = {
                path: {
                    "content_hash": state.content_hash,
                    "dependencies": state.dependencies,
                    "validation_result": state.validation_result
                }
                for path, state in self.state.items()
            }
            self.state_file.write_text(json.dumps(serializable_state))
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def get_changed_files(self, files: List[Path]) -> List[Path]:
        """Identify which files have changed since last build."""
        changed = []
        for file in files:
            self.logger.debug(f"Checking file: {file}")
            if str(file) not in self.state:
                self.logger.debug(f"  -> New file, not in state")
                changed.append(file)
                continue
                
            current_hash = self.compute_file_hash(file)
            cached_hash = self.state[str(file)].content_hash
            self.logger.debug(f"  -> hash: {current_hash}, cached: {cached_hash}")
            if current_hash != cached_hash:
                self.logger.debug(f"  -> File changed")
                changed.append(file)
                
        self.logger.debug(f"Found {len(changed)} changed files: {changed}")
        return changed
    
    def update_state(self, file: Path, dependencies: List[str], validation_result: bool):
        """Update state for a file after processing."""
        try:
            if not file.exists():
                self.logger.warning(f"Attempted to update state for non-existent file: {file}")
                return
            
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            self.state[str(file)] = FileState(
                content_hash=self.compute_file_hash(file),
                dependencies=dependencies,
                validation_result=validation_result
            )
            self.save_state()
        except Exception as e:
            self.logger.error(f"Failed to update state for {file}: {e}")

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute hash of file contents."""
        if not file_path.exists():
            return ""
        
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_dependents(self, file: Path) -> Set[Path]:
        """Get all files that depend on the given file."""
        dependents = set()
        for path, state in self.state.items():
            if str(file) in state.dependencies:
                dependents.add(Path(path))
                # Recursively get dependents of dependents
                dependents.update(self.get_dependents(Path(path)))
        return dependents 