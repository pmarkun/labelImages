# Runner Data Viewer - Modular Architecture

This document describes the refactoring of the original monolithic `viewer_app.py` into a modular, maintainable architecture.

## 📁 Project Structure

```
labelImages/
├── viewer_app.py                 # Original monolithic file (preserved)
├── viewer_app_modular.py         # New modular main application
├── main.py                       # Advanced modular controller (experimental)
├── 
├── core/                         # Business logic and data management
│   ├── __init__.py
│   ├── models.py                 # Data models and structures
│   └── data_manager.py           # Data operations and business logic
│
├── ui/                           # User interface components
│   ├── __init__.py
│   ├── widgets.py                # Custom UI widgets
│   ├── panels.py                 # UI panel components
│   ├── main_window.py            # Main window (experimental)
│   ├── tree_widget.py            # Tree management (experimental)  
│   └── image_display.py          # Image display management (experimental)
│
├── utils/                        # Utility functions
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   └── image_utils.py            # Image processing utilities
│
├── config.yaml                   # Application configuration
├── viewer_config.yaml            # Viewer-specific configuration
└── requirements.txt              # Python dependencies
```

## 🔧 Modular Components

### Core Module (`core/`)

**`models.py`**
- `Shoe`: Dataclass for shoe detection data
- `RunData`: Dataclass for runner/bib information  
- `ImageData`: Dataclass for image metadata
- `DataCache`: Performance cache for tree population
- `get_position_from_bib()`: Utility for bib number sorting

**`data_manager.py`**
- `DataManager`: Handles all data operations (load, save, undo, etc.)
- Business logic for image/data manipulation
- Cache management for performance
- Statistics collection

### UI Module (`ui/`)

**`widgets.py`**  
- `ClickableLabel`: Custom clickable image widget

**`panels.py` (experimental)**
- `LeftPanel`: Navigation tree and filters
- `CenterPanel`: Image display area
- `RightPanel`: Controls and details

**`main_window.py` (experimental)**
- `RunnerViewerMainWindow`: Main application window
- Signal-based communication with business logic

### Utils Module (`utils/`)

**`config.py`**
- `load_config()`: Load YAML configuration
- `save_config()`: Save YAML configuration

**`image_utils.py`**
- `crop_image()`: Image cropping utility
- `pil_to_qpixmap()`: PIL to Qt conversion

## 🚀 Usage

### Current Working Version
```bash
python viewer_app_modular.py
```

This version uses the modular components while maintaining compatibility with the original interface.

### Experimental Advanced Version
```bash
python main.py
```

This is a more advanced modular version that's still being developed.

## ✨ Benefits of Modularization

### 1. **Separation of Concerns**
- **UI logic** separated from **business logic**
- **Data operations** isolated in dedicated manager
- **Configuration** and **utilities** in separate modules

### 2. **Maintainability** 
- Smaller, focused files are easier to understand and modify
- Clear module boundaries make debugging easier
- Changes to one module don't affect others

### 3. **Testability**
- Individual components can be unit tested
- Business logic can be tested without UI dependencies
- Mock objects can easily replace real components

### 4. **Reusability**
- Core components can be reused in different contexts
- UI components can be used in other Qt applications
- Utilities can be shared across projects

### 5. **Performance**
- Optimized cache system in `DataCache`
- Lazy loading of tree child nodes
- Efficient image processing with utilities

## 🔄 Migration Strategy

The refactoring was done incrementally to maintain functionality:

1. **Phase 1**: Extract utilities (`config.py`, `image_utils.py`)
2. **Phase 2**: Create data models (`models.py`) 
3. **Phase 3**: Extract business logic (`data_manager.py`)
4. **Phase 4**: Create UI components (`widgets.py`, `panels.py`)
5. **Phase 5**: Create modular main application (`viewer_app_modular.py`)

## 🧪 Testing

The modular architecture allows for better testing:

```python
# Example: Testing data manager independently
from core.data_manager import DataManager

def test_data_loading():
    dm = DataManager()
    dm.load_json("test_data.json")
    assert len(dm.data) > 0

def test_undo_functionality():
    dm = DataManager()
    dm.load_json("test_data.json")
    dm.save_state(0)
    # Make changes...
    state = dm.undo()
    assert state is not None
```

## 📈 Future Improvements

### 1. **Complete Signal-Based Architecture**
- Move from direct method calls to Qt signals/slots
- Better decoupling between UI and business logic

### 2. **Plugin System**
- Modular export formats
- Pluggable image processing filters
- Custom UI themes

### 3. **Configuration Management**
- Environment-specific configurations
- User preference persistence
- Runtime configuration updates

### 4. **Advanced Caching**
- Disk-based cache for large datasets
- Intelligent cache invalidation
- Memory usage optimization

### 5. **Enhanced Testing**
- Automated UI testing with Qt Test Framework
- Performance benchmarking
- Integration tests for complete workflows

## 🔧 Development Guidelines

### Adding New Features

1. **Identify the appropriate module** (core, ui, utils)
2. **Follow existing patterns** and naming conventions
3. **Add unit tests** for new functionality
4. **Update documentation** and this README

### Code Style

- Follow PEP 8 for Python code style
- Use type hints for better code documentation
- Add docstrings for public methods and classes
- Keep functions small and focused on single responsibilities

### Error Handling

- Use try/catch blocks for file operations
- Show user-friendly error messages via QMessageBox
- Log detailed errors for debugging
- Graceful degradation when possible

## 📋 Dependencies

The modular version maintains the same dependencies as the original:

- **PyQt5**: GUI framework
- **PIL/Pillow**: Image processing  
- **PyYAML**: Configuration file handling
- **Standard library**: json, os, shutil, copy, etc.

## 🎯 Conclusion

The modular architecture provides a solid foundation for future development while maintaining all existing functionality. The separation of concerns makes the codebase more maintainable, testable, and extensible.

**Key Files:**
- `viewer_app_modular.py`: **Ready-to-use modular version**
- `main.py`: Advanced experimental version  
- `core/data_manager.py`: Core business logic
- `utils/`: Shared utilities

The refactoring successfully transforms a 2000-line monolithic file into a clean, modular architecture that follows software engineering best practices.
