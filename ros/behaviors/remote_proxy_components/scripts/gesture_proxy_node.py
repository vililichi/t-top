#!/usr/bin/env python3

import rclpy
import rclpy.node

from std_msgs.msg import String, Bool
from behavior_msgs.msg import GestureName, Done

class GestureProxyNode(rclpy.node.Node):
    def __init__(self):
        super().__init__('gesture_proxy')

        self._done_pub = self.create_publisher(Bool, 'ttop_remote_proxy/gesture/done', 5)
        self._gesture_sub = self.create_subscription(String, 'ttop_remote_proxy/gesture/name', self._on_gesture_cb, 5)

        self._done_sub = self.create_subscription(Done, 'gesture/done', self._on_done_cb, 5)
        self._gesture_pub = self.create_publisher(GestureName, 'gesture/name', 5)

    def _on_gesture_cb(self, msg:String):
        out_msg = GestureName()
        out_msg.name = msg.data
        self._gesture_pub.publish(out_msg)

    def _on_done_cb(self, msg:Done):
        out_msg = Bool()
        out_msg.data = msg.ok
        self._done_pub.publish(out_msg)


def main(args=None):
    rclpy.init()
    node = GestureProxyNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
