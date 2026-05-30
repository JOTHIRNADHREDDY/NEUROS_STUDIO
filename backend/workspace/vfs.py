import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger("neuros.workspace.vfs")

class VirtualFileSystem:
    """
    Manages safe interactions with the local filesystem for the IDE.
    Ensures that paths are locked to the workspace root to prevent directory traversal.
    """
    def __init__(self, workspace_root: str):
        self.root = os.path.abspath(workspace_root)
        if not os.path.exists(self.root):
            os.makedirs(self.root, exist_ok=True)
            logger.info(f"Created workspace root: {self.root}")

    def _safe_path(self, relative_path: str) -> str:
        """Resolves a relative path and ensures it remains inside the workspace root."""
        # Strip leading slashes to prevent absolute path injection
        clean_path = relative_path.lstrip('/')
        absolute_path = os.path.abspath(os.path.join(self.root, clean_path))
        
        if not absolute_path.startswith(self.root):
            raise PermissionError(f"Access denied: {relative_path} is outside the workspace.")
            
        return absolute_path

    def read_file(self, relative_path: str) -> str:
        safe_path = self._safe_path(relative_path)
        if not os.path.exists(safe_path):
            raise FileNotFoundError(f"File not found: {relative_path}")
            
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, relative_path: str, content: str) -> bool:
        safe_path = self._safe_path(relative_path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    def get_tree(self) -> List[Dict[str, Any]]:
        """Returns a nested dictionary representing the directory structure."""
        return self._build_tree(self.root)

    def _build_tree(self, current_dir: str) -> List[Dict[str, Any]]:
        tree = []
        try:
            for item in sorted(os.listdir(current_dir)):
                # Ignore hidden files/dirs like .git, .env
                if item.startswith('.'):
                    continue
                    
                full_path = os.path.join(current_dir, item)
                rel_path = os.path.relpath(full_path, self.root).replace('\\', '/')
                
                if os.path.isdir(full_path):
                    tree.append({
                        "name": item,
                        "type": "directory",
                        "path": rel_path,
                        "children": self._build_tree(full_path)
                    })
                else:
                    tree.append({
                        "name": item,
                        "type": "file",
                        "path": rel_path
                    })
        except Exception as e:
            logger.error(f"Error building tree for {current_dir}: {e}")
        return tree
