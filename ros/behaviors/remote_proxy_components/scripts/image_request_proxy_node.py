#!/usr/bin/env python3

from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Bool
from rclpy.node import Node
import rclpy
from cv_bridge import CvBridge
from threading import Thread, Lock
import time

class VolatileImageStreamNode(Node):
    def __init__(self):
        super().__init__('image_request_proxy')

        qos_policy = rclpy.qos.QoSProfile(reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT,
                                                history=rclpy.qos.HistoryPolicy.KEEP_LAST,
                                                depth=1)
        
        self.img_lock = Lock()
        self.cv_bridge = CvBridge()
        self.cv_image = None

        self.ttop_camera_compressed_subscriber = self.create_subscription( CompressedImage, 'ttop_remote_proxy/image_request_proxy_input/compressed', self.input_cb, qos_profile=qos_policy)
        self.ttop_camera_compressed_publisher = self.create_publisher( CompressedImage, 'ttop_remote_proxy/image_request_proxy_output/compressed', qos_profile=qos_policy)
        self._request_subscriber = self.create_subscription(Bool, 'ttop_remote_proxy/image_request_input/request', self.request_cb, 1)

        self._img_requiered = True

    def input_cb(self, msg:CompressedImage):

        if self._img_requiered:
            self._img_requiered = False
            self.ttop_camera_compressed_publisher.publish(msg)

    def request_cb(self, msg:Bool):
        self._img_requiered = msg.data

def main(args=None):
    rclpy.init()
    node = VolatileImageStreamNode()
    rclpy.spin(node)
    rclpy.shutdown()



if __name__ == '__main__':
    main()