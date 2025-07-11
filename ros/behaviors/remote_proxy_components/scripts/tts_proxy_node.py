#!/usr/bin/env python3

from behavior_msgs.msg import Done, Text

from rclpy.node import Node
import rclpy.executors
import rclpy.callback_groups

from std_msgs.msg import String, Bool

class TTSPoxyNode(Node):
    def __init__(self):
        super().__init__('tts_proxy')

        self._executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)
        self._talking = True

        self._subscriber_callback_group = (
            rclpy.callback_groups.MutuallyExclusiveCallbackGroup()
        )

        # Subscriber
        self._talk_done_sub = self.create_subscription(
            Done,
            "talk/done",
            self._on_talk_done_cb,
            1,
            callback_group=self._subscriber_callback_group,
        )
        self._talk_input_sub = self.create_subscription(
            String,
            "ttop_remote_proxy/tts",
            self._on_talk_input_cb,
            1,
            callback_group=self._subscriber_callback_group,
        )

        # publisher
        self._talk_text_pub = self.create_publisher(Text, "speak/text", 1)
        self._is_talking_pub = self.create_publisher(Bool, "ttop_remote_proxy/is_talking", 1)
        
        
    def _on_talk_done_cb(self, msg: Done):
        self.get_logger().info(f"Talk done : {msg.ok}")
        self._talking = False

        is_talking_msg = Bool()
        is_talking_msg.data = False
        self._is_talking_pub.publish(is_talking_msg)

    def _on_talk_input_cb(self, msg: String):
        self._talking = True
        is_talking_msg = Bool()
        is_talking_msg.data = True
        self._is_talking_pub.publish(is_talking_msg)

        talk_msg = Text()
        talk_msg.text = msg.data
        self.get_logger().info(f"Sending talk message: {talk_msg.text}")
        self._talk_text_pub.publish(talk_msg)

def main(args=None):
    rclpy.init()
    node = TTSPoxyNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()