#!/usr/bin/env python3

from PyQt5 import QtWidgets
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
import cv2
import numpy as np

from sensor_msgs.msg import Image, CompressedImage
from rclpy.node import Node
import rclpy
from cv_bridge import CvBridge
from threading import Thread, Lock
import time
import sys

class ScaledImage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self._cv_image = None
        self._qpixmap = None
        self._image_label = QtWidgets.QLabel()

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._image_label)
        self.setLayout(self._layout)

        self._img_size = 0.85

    def _convert_cv_qt(self, cv_img, size:float=0.75):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(int(self.width()*size), int(self.height()*size), Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)
    
    def _setImageWithSize(self, cv_image:np.ndarray, size:float=0.75):
        self._cv_image = cv_image
        self._qpixmap = self._convert_cv_qt(cv_image, size)
        self._image_label.setPixmap(self._qpixmap)

    def setImage(self, cv_image:np.ndarray):
        self._setImageWithSize(cv_image, self._img_size)

    def resizeEvent(self, event):
        out = super().resizeEvent(event)
        if self._cv_image is not None:
            self._setImageWithSize(self._cv_image, self._img_size)

        return out

class DisplayNode(Node):
    def __init__(self):
        super().__init__('display')

        qos_policy = rclpy.qos.QoSProfile(reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT,
                                                history=rclpy.qos.HistoryPolicy.KEEP_LAST,
                                                depth=1)
        
        self.widget = ScaledImage()
        self.widget.showFullScreen()
        
        self.img_lock = Lock()
        self.cv_bridge = CvBridge()
        self.cv_image = None

        self.pub = self.create_publisher(Image, 'interactive_yolo/image_rect', qos_profile=qos_policy)
        self.pub_compressed = self.create_publisher(CompressedImage, 'interactive_yolo/image_rect/compressed', qos_profile=qos_policy)

        self.ttop_camera_raw_subscriber = self.create_subscription( Image, 'interactive_yolo/display_input', self.input_raw_cb, qos_profile=qos_policy)
        self.ttop_camera_raw_subscriber = self.create_subscription( CompressedImage, 'interactive_yolo/display_input_compressed', self.input_compressed_cb, qos_profile=qos_policy)

        self.thread = Thread(target=self.rect_camera_loop, daemon=True)
        self.thread.start()

    def rect_camera_loop(self):

        while True:
            time.sleep(0.01)
            cv_image = None

            with self.img_lock:
                if( self.cv_image is not None ):
                    cv_image = self.cv_image
                    self.cv_image = None
                else:
                    continue

            self.widget.setImage(cv_image)

    def input_raw_cb(self, msg:Image):

        with self.img_lock:
            self.cv_image = self.cv_bridge.imgmsg_to_cv2(msg, "bgr8")

    def input_compressed_cb(self, msg:CompressedImage):

        with self.img_lock:
            self.cv_image = self.cv_bridge.compressed_imgmsg_to_cv2(msg, "bgr8")

def main(args=None):
    app = QtWidgets.QApplication([])
    rclpy.init()

    node = DisplayNode()

    def rclpy_thread_fun():
        rclpy.spin(node)
        rclpy.shutdown()

    rclpy_thread = Thread(target = rclpy_thread_fun, daemon=True)
    rclpy_thread.start()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()