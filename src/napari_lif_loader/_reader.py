import napari


def get_reader(path):
    if isinstance(path, list):
        # Only handle a single dropped file
        if len(path) != 1:
            return None
        path = path[0]
    if not str(path).lower().endswith(".lif"):
        return None
    return read_lif


def read_lif(path):
    if isinstance(path, list):
        path = path[0]

    # Open (or reuse) the LIF Loader widget and list the file's images in it
    viewer = napari.current_viewer()
    dock, widget = viewer.window.add_plugin_dock_widget(
        "napari-lif-loader", "LIF Loader"
    )
    dock.show()
    widget.open_path(str(path))

    # Images are added by the widget, so return napari's "empty file" sentinel
    return [(None,)]
