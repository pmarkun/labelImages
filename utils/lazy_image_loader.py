"""
Lazy loading image manager for better performance with large datasets.
"""
import os
import threading
import weakref
from typing import Dict, Any, Optional, Callable
from PIL import Image
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QPixmap
from utils.image_utils import load_image_cached, draw_bounding_boxes, pil_to_qpixmap


class LazyImageLoader(QThread):
    """Background thread for loading images."""
    
    image_loaded = pyqtSignal(str, object)  # path, image
    
    def __init__(self):
        super().__init__()
        self.queue = []
        self.running = True
        self.lock = threading.Lock()
    
    def add_to_queue(self, img_path: str, priority: int = 0):
        """Add image to loading queue with priority."""
        with self.lock:
            # Remove existing entry for same path
            self.queue = [(p, path, prio) for p, path, prio in self.queue if path != img_path]
            # Add with priority (lower number = higher priority)
            self.queue.append((priority, img_path, threading.current_thread().ident))
            self.queue.sort(key=lambda x: x[0])
    
    def run(self):
        """Background loading loop."""
        while self.running:
            if self.queue:
                with self.lock:
                    if self.queue:
                        priority, img_path, thread_id = self.queue.pop(0)
                    else:
                        continue
                
                try:
                    img = load_image_cached(img_path)
                    self.image_loaded.emit(img_path, img)
                except Exception as e:
                    print(f"Error loading {img_path}: {e}")
                    self.image_loaded.emit(img_path, None)
            else:
                self.msleep(10)  # Sleep for 10ms when queue is empty
    
    def stop(self):
        """Stop the loader thread."""
        self.running = False


class LazyImageCache:
    """Intelligent cache with lazy loading and memory management."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache = {}  # path -> (image, access_count, last_access)
        self._loading = set()  # paths currently being loaded
        self._callbacks = {}  # path -> list of callbacks
        self._loader = LazyImageLoader()
        self._loader.image_loaded.connect(self._on_image_loaded)
        self._loader.start()
        
        # Access counter for LRU
        self._access_counter = 0
    
    def get_image(self, img_path: str, callback: Optional[Callable] = None, priority: int = 0) -> Optional[Image.Image]:
        """Get image with lazy loading. Returns immediately if cached, otherwise loads in background."""
        self._access_counter += 1
        
        # Check if already in cache
        if img_path in self._cache:
            img, access_count, _ = self._cache[img_path]
            self._cache[img_path] = (img, access_count + 1, self._access_counter)
            if callback:
                callback(img_path, img)
            return img
        
        # Check if currently loading
        if img_path in self._loading:
            if callback:
                if img_path not in self._callbacks:
                    self._callbacks[img_path] = []
                self._callbacks[img_path].append(callback)
            return None
        
        # Start loading
        self._loading.add(img_path)
        if callback:
            if img_path not in self._callbacks:
                self._callbacks[img_path] = []
            self._callbacks[img_path].append(callback)
        
        self._loader.add_to_queue(img_path, priority)
        return None
    
    def _on_image_loaded(self, img_path: str, img: Optional[Image.Image]):
        """Handle image loaded from background thread."""
        self._loading.discard(img_path)
        
        if img is not None:
            # Add to cache
            self._cache[img_path] = (img, 1, self._access_counter)
            self._access_counter += 1
            
            # Manage cache size
            if len(self._cache) > self.max_size:
                self._evict_lru()
        
        # Call callbacks
        if img_path in self._callbacks:
            for callback in self._callbacks[img_path]:
                try:
                    callback(img_path, img)
                except Exception as e:
                    print(f"Callback error for {img_path}: {e}")
            del self._callbacks[img_path]
    
    def _evict_lru(self):
        """Remove least recently used items."""
        if len(self._cache) <= self.max_size:
            return
        
        # Sort by last access time and remove oldest
        items = list(self._cache.items())
        items.sort(key=lambda x: x[1][2])  # Sort by last_access
        
        num_to_remove = len(self._cache) - self.max_size + 10  # Remove extra for buffer
        for i in range(min(num_to_remove, len(items))):
            path, _ = items[i]
            del self._cache[path]
    
    def preload(self, img_paths: list, priority: int = 10):
        """Preload multiple images in background."""
        for path in img_paths:
            if path not in self._cache and path not in self._loading:
                self._loading.add(path)
                self._loader.add_to_queue(path, priority)
    
    def clear(self):
        """Clear the cache."""
        self._cache.clear()
        self._loading.clear()
        self._callbacks.clear()
    
    def shutdown(self):
        """Shutdown the loader thread."""
        self._loader.stop()
        self._loader.wait()


# Global lazy cache instance
_lazy_cache = LazyImageCache()


def get_lazy_cache() -> LazyImageCache:
    """Get the global lazy cache instance."""
    return _lazy_cache


def shutdown_lazy_cache():
    """Shutdown the lazy cache (call on app exit)."""
    _lazy_cache.shutdown()
