
from typing import Any, Callable, Dict, List, Optional, Union

def traverse_obj(
    obj: Any,
    *paths: Any,
    default: Any = None,
    expected_type: Optional[type] = None,
) -> Any:
    """
    Safely traverse a nested dictionary/list structure.
    Simplified version of yt-dlp's traverse_obj.
    
    Args:
        obj: The object to traverse.
        *paths: Paths to traverse. Each path is a list/tuple of keys/indices/functions.
        If multiple paths are provided, the first one that yields a non-None result is returned.
        default: Value to return if traversal fails.
        expected_type: transform the result to this type or return default if it fails.
    """
    for path in paths:
        current = obj
        try:
            if not isinstance(path, (list, tuple)):
                path = [path]
            
            for key in path:
                if callable(key):
                    current = key(current)
                elif isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, (list, tuple)) and isinstance(key, int):
                    if 0 <= key < len(current):
                        current = current[key]
                    else:
                        current = None
                else:
                    current = None
                
                if current is None:
                    break
            
            if current is not None:
                if expected_type:
                    try:
                        return expected_type(current)
                    except (ValueError, TypeError):
                        pass
                else:
                    return current
                    
        except Exception:
            pass
            
    return default
