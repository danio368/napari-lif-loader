import numpy as np
from readlif.reader import LifFile
from qtpy.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QLabel, QFileDialog
import napari


class LifLoaderWidget(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        self.viewer = viewer
        self.lif = None
        self.images = []

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

        # Status label
        self.status_label = QLabel("")
        self.layout().addWidget(self.status_label)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open LIF file", "", "LIF files (*.lif)")
        if not path:
            return

        self.lif = LifFile(path)
        self.images = list(self.lif.get_iter_image())

        self.file_label.setText(path.split("/")[-1])
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
        self.viewer.add_image(
            data,
            channel_axis=2,
            scale=(1, z_size, y_size, x_size),
            name=img.name
        )

        self.viewer.reset_view()
        self.status_label.setText(f"Loaded: {img.name}  |  shape: {data.shape}  |  scale: ({x_size:.3f}, {y_size:.3f}, {z_size:.3f})")