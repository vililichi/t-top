#!/usr/bin/env python3

import hbba_lite

from perception_msgs.msg import Transcript
from audio_utils_msgs.msg import VoiceActivity
from std_msgs.msg import String, Bool

from rclpy.node import Node
from rclpy.qos import QoSProfile
import rclpy.executors

class STTPoxyNode(Node):
    def __init__(self):
        super().__init__('stt_proxy')

        self._executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)

        # Subscriber
        self._transcript_sub = self.create_subscription(
            Transcript,
            "listen/transcript",
            self._on_transcript_received_cb,
            qos_profile=QoSProfile(history=1, depth=1)
        )

        self._is_listening_sub = self.create_subscription(
            Bool,
            "listen/activated",
            self._is_listening_cb,
            1
        )

        self._talk_input_sub = self.create_subscription(
            Bool,
            "ttop_remote_proxy/start_stt",
            self._on_start_stt_cb,
            1
        )

        self._voice_activity_sub = self.create_subscription(VoiceActivity, 'voice_activity', self._voice_activity_cb, 10)

        self._processing_sub = self.create_subscription(Bool, 'processing_audio', self._on_start_processing_cb, 1)

        # publisher
        self._text_pub = self.create_publisher(String, "ttop_remote_proxy/stt", 1)
        self._start_listen_pub = self.create_publisher(Bool, "listen/start", 1)
        self._is_listening_pub = self.create_publisher(Bool, "ttop_remote_proxy/is_listening", 1)
        self._voice_pub = self.create_publisher(Bool, "ttop_remote_proxy/voice_detected", 1)
        self._processing_pub = self.create_publisher(Bool, 'ttop_remote_proxy/processing_audio', 1)

        self._is_voice = False

    def _voice_activity_cb(self, msg):
        if self._is_voice != msg.is_voice:
            self._is_voice = msg.is_voice
            proxy_msg = Bool()
            proxy_msg.data = msg.is_voice
            self._voice_pub.publish(proxy_msg)

    def _on_transcript_received_cb(self, msg: Transcript):
        if len(msg.text) and msg.is_final:
            self.get_logger().info(f"Transcript received: {msg.text}")
            out_msg = String()
            out_msg.data = msg.text
            self._text_pub.publish(out_msg)

    def _is_listening_cb(self, msg: Bool):
        self.get_logger().info(f"Is listening: {msg.data}")
        self._is_listening_pub.publish(msg)

    def _on_start_stt_cb(self, msg: Bool):
        self.get_logger().info(f"Starting to listen: {msg.data}")
        self._start_listen_pub.publish(msg)

    def _on_start_processing_cb(self, msg: Bool):
        self._processing_pub.publish(msg)

def main(args=None):
    rclpy.init()
    node = STTPoxyNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()