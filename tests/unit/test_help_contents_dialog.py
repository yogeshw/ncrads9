from ncrads9.ui.dialogs.help_contents_dialog import HelpContentsDialog


def test_help_contents_mentions_current_zoom_and_large_image_features():
    html = HelpContentsDialog.HELP_HTML

    assert "Invert X" in html
    assert "Pan Zoom Rotate Parameters" in html
    assert "Blink" in html
    assert "tiled GPU rendering" in html
    assert "https://github.com/ncra/ncrads9" in html
