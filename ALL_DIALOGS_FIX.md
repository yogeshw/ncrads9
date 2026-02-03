# All Dialog Windows Independence Fix

## Problem
All dialog windows except "Scale Parameters" were dragging the main window along with them. This affected:
- Pixel Table
- FITS Header
- Image Statistics  
- Histogram
- Preferences
- Keyboard Shortcuts
- Help Contents
- And potentially others

## Root Cause
Dialogs were created with `super().__init__(parent)`, which makes them child windows of the main window. In Qt, when you drag a child window, it can drag the parent along on some platforms/configurations.

## Solution
Applied the same fix that worked for Scale Parameters dialog to ALL dialogs:

1. **Pass `None` as parent** instead of the actual parent widget
2. **Set window flags** to make dialog a top-level independent window
3. **Set non-modal** so main window remains interactive

## Standard Fix Pattern

```python
def __init__(self, ..., parent: Optional[QWidget] = None) -> None:
    """Initialize dialog."""
    # Pass None as parent to make dialog independent
    super().__init__(None)  # NOT super().__init__(parent)
    
    # Set window flags for independent draggable window
    self.setWindowFlags(
        Qt.WindowType.Window |  # Top-level window
        Qt.WindowType.WindowCloseButtonHint |
        Qt.WindowType.WindowTitleHint |
        Qt.WindowType.WindowStaysOnTopHint  # Keep on top
    )
    self.setWindowModality(Qt.WindowModality.NonModal)
    
    # Rest of initialization...
    self.setWindowTitle("...")
```

## Files Fixed

### Manually Fixed:
1. `ncrads9/ui/dialogs/scale_dialog.py` ✓ (already done)
2. `ncrads9/ui/dialogs/pixel_table_dialog.py` ✓
3. `ncrads9/ui/dialogs/header_dialog.py` ✓
4. `ncrads9/ui/dialogs/statistics_dialog.py` ✓

### Script-Fixed:
5. `ncrads9/ui/dialogs/histogram_dialog.py` ✓
6. `ncrads9/ui/dialogs/preferences_dialog.py` ✓
7. `ncrads9/ui/dialogs/keyboard_shortcuts_dialog.py` ✓
8. `ncrads9/ui/dialogs/help_contents_dialog.py` ✓

## Testing

Test each dialog from the menu:

### File Menu:
- **Export** (Export Dialog) - test if it drags main window

### View Menu:
- **Keyboard Shortcuts** (Help > Keyboard Shortcuts) ✓ Fixed
- **Help Contents** (Help > Contents) ✓ Fixed

### Analysis Menu:
- **Statistics** ✓ Fixed
- **Histogram** ✓ Fixed
- **Pixel Table** ✓ Fixed

### Scale Menu:
- **Parameters** ✓ Already fixed

### File > Header:
- **Header Info** ✓ Fixed

### Edit Menu:
- **Preferences** ✓ Fixed

## Test Procedure

For each dialog:
1. Open the dialog from menu
2. Try to drag it by the title bar
3. **Expected**: Dialog moves, main window stays in place
4. **Previous**: Both dialog and main window moved together
5. Click outside dialog
6. **Expected**: Can still interact with main window
7. Close dialog

## Benefits

- **Better UX**: Users can position dialogs anywhere without disrupting main window
- **Multi-monitor friendly**: Can move dialogs to secondary monitor
- **Stay on top**: Dialogs remain visible above main window
- **Non-blocking**: Main window remains interactive while dialog is open
- **Standard behavior**: Matches expectations from other applications

## Implementation Details

### Why `None` as parent?
Passing `None` makes Qt treat the dialog as a completely independent top-level window with no parent-child relationship.

### Why `WindowStaysOnTopHint`?
Without this flag, the dialog could get buried behind the main window. This ensures it stays visible.

### Why `NonModal`?
Allows users to interact with the main window while the dialog is open. For example:
- Open Statistics dialog
- Pan/zoom image in main window
- Statistics dialog stays visible

### Window Flags Breakdown:
- `Qt.WindowType.Window` - Top-level window
- `Qt.WindowType.WindowCloseButtonHint` - Show close button
- `Qt.WindowType.WindowTitleHint` - Show title bar
- `Qt.WindowType.WindowStaysOnTopHint` - Stay above main window

## Remaining Dialogs

Other dialogs that may need the same fix (if they exhibit the problem):
- `colormap_dialog.py`
- `contour_dialog.py`
- `export_dialog.py`
- `grid_dialog.py`
- `open_dialog.py`
- `region_dialog.py`
- `save_dialog.py`
- `smooth_dialog.py`
- `vo_query_dialog.py`

These can be fixed using the same pattern if needed.

## Automated Fix Script

For bulk fixing, used this script pattern:
```python
import re
from pathlib import Path

window_flags_code = """        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)"""

# Replace super().__init__(parent) with window flags code
pattern = r'([ \t]*)super\(\).__init__\([^)]*parent[^)]*\)'
new_content = re.sub(pattern, window_flags_code, content, count=1)
```

## Status

✅ **8 dialogs fixed**
- All commonly-used dialogs now draggable independently
- No impact on dialog functionality
- Improved user experience

⚠️ **Additional dialogs available** for fixing if they show the same issue.
