import os

import numpy as np
from readlif.reader import LifFile
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton, QLabel, QFileDialog,
    QGroupBox, QFormLayout, QComboBox,
)
import napari
from napari.utils.colormaps import AVAILABLE_COLORMAPS

# Default LUT for each channel (cycled if there are more channels)
DEFAULT_LUTS = ["green", "magenta", "cyan", "yellow", "red", "blue", "gray"]

# Common LUTs shown first in the dropdowns, followed by all other napari colormaps
COMMON_LUTS = ["gray", "green", "magenta", "cyan", "yellow", "red", "blue",
               "gray_r", "viridis", "inferno", "magma", "plasma", "turbo"]


def _lut_names():
    available = list(AVAILABLE_COLORMAPS)
    common = [name for name in COMMON_LUTS if name in available]
    others = sorted(name for name in available if name not in common)
    return common + others


class LifLoaderWidget(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.viewer = viewer
        self.lif = None
        self.images = []
        self.channel_layers = []
        self.lut_combos = []
        # LUT chosen for each channel index, kept from one image to the next
        self.lut_choices = {}

        self.setLayout(QVBoxLayout())

        # Button to open file
        self.open_btn = QPushButton("Open .lif file")
        self.open_btn.clicked.connect(self.open_file)
        self.layout().addWidget(self.open_btn)

        # Label showing file name
        self.file_label = QLabel("No file loaded")
        self.layout().addWidget(self.file_label)

        # List of images
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.load_image)
        self.layout().addWidget(self.list_widget)

        # LUT selection, one dropdown per channel
        self.lut_box = QGroupBox("Channel LUTs")
        self.lut_box.setLayout(QFormLayout())
        self.lut_box.layout().addRow(QLabel("Load an image to choose LUTs"))
        self.layout().addWidget(self.lut_box)

        # Status label
        self.status_label = QLabel("")
        self.layout().addWidget(self.status_label)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open LIF file", "", "LIF files (*.lif)")
        if not path:
            return
        self.open_path(path)

    def open_path(self, path):
        self.lif = LifFile(path)
        self.images = list(self.lif.get_iter_image())

        self.file_label.setText(os.path.basename(path))
        self.list_widget.clear()
        for i, img in enumerate(self.images):
            self.list_widget.addItem(f"{i}: {img.name}")

        self.status_label.setText(f"{len(self.images)} images found")

    def load_image(self, item):
        idx = int(item.text().split(":")[0])
        img = self.images[idx]

        self.status_label.setText(f"Loading {img.name}...")
        self.repaint()

        # Detect channels
        C = 0
        while True:
            try:
                img.get_frame(z=0, t=0, c=C)
                C += 1
            except Exception:
                break

        T = img.dims.t or 1
        Z = img.dims.z or 1

        # Load data
        data = np.zeros((T, Z, C, img.dims.y, img.dims.x), dtype=np.uint16)
        for t in range(T):
            for z in range(Z):
                for c in range(C):
                    data[t, z, c] = img.get_frame(z=z, t=t, c=c)

        # Compute scaling
        x_size = 1 / img.info['scale_n'][1]
        y_size = 1 / img.info['scale_n'][2]
        if img.dims.z > 1:
            z_size = abs(
                (float(img.info['settings']['Begin']) - float(img.info['settings']['End']))
                / (img.dims.z - 1) * 1e6
            )
        else:
            z_size = 1.0

        # Clear existing layers
        self.viewer.layers.clear()

        # Add to napari
        layers = self.viewer.add_image(
            data,
            channel_axis=2,
            scale=(1, z_size, y_size, x_size),
            name=img.name,
            colormap=[self._lut_for_channel(c) for c in range(C)],
        )
        # add_image returns a single layer when there is only one channel
        self.channel_layers = layers if isinstance(layers, list) else [layers]
        self._build_lut_combos(C)

        self.viewer.reset_view()
        self.status_label.setText(f"Loaded: {img.name}  |  shape: {data.shape}  |  scale: ({x_size:.3f}, {y_size:.3f}, {z_size:.3f})")

    def _lut_for_channel(self, c):
        return self.lut_choices.get(c, DEFAULT_LUTS[c % len(DEFAULT_LUTS)])

    def _build_lut_combos(self, n_channels):
        form = self.lut_box.layout()
        while form.rowCount():
            form.removeRow(0)
        self.lut_combos = []

        names = _lut_names()
        for c in range(n_channels):
            combo = QComboBox()
            combo.addItems(names)
            combo.setCurrentText(self._lut_for_channel(c))
            combo.currentTextChanged.connect(
                lambda name, c=c: self._set_lut(c, name)
            )
            form.addRow(f"Channel {c + 1}", combo)
            self.lut_combos.append(combo)

    def _set_lut(self, c, name):
        self.lut_choices[c] = name
        # Apply to the currently displayed layer, if it still exists
        if c < len(self.channel_layers):
            layer = self.channel_layers[c]
            if layer in self.viewer.layers:
                layer.colormap = name