#!/usr/bin/env python3

import threading
import time
import datetime
import math
import numpy as np

import rclpy
import rclpy.node

from perception_msgs.msg import Transcript
from audio_utils_msgs.msg import AudioFrame, VoiceActivity
from std_msgs.msg import Bool
import hbba_lite

from google.cloud import speech
from google.api_core import exceptions as core_exceptions


SUPPORTED_AUDIO_FORMAT = 'signed_16'
SUPPORTED_CHANNEL_COUNT = 1


class GoogleSpeechToTextNode(rclpy.node.Node):
    def __init__(self):
        super().__init__('google_speech_to_text_node')

        self._sampling_frequency = self.declare_parameter('sampling_frequency', 16000).get_parameter_value().integer_value
        self._frame_sample_count = self.declare_parameter('frame_sample_count', 92).get_parameter_value().integer_value
        self._request_frame_count = self.declare_parameter('request_frame_count', 20).get_parameter_value().integer_value
        

        language = self.declare_parameter('language', 'en').get_parameter_value().string_value
        self._language_code = self._convert_language_to_language_code(language)

        self._buffer_duration = (self._request_frame_count * self._frame_sample_count / self._sampling_frequency)
        self._sleeping_duration = self._buffer_duration

        self._prebuffing_buffer_duration = 5.0
        self._prebuffing_buffer_number =  math.ceil(self._prebuffing_buffer_duration / self._buffer_duration)

        self.max_audio_duration = 45.0
        self._max_buffer_number =  math.ceil(self.max_audio_duration / self._buffer_duration)


        self._is_enabled = False
        self._is_voice = False
        
        self.buffer_mutex = threading.Lock()
        self._frames_buffer = []
        self.frames_to_process_mutex = threading.Lock()
        self._frames_to_process = None

        self._buffer = self._create_request_frame_buffer()
        self._current_buffer_index = 0
        self._total_samples_count = 0

        self._text_pub = self.create_publisher(Transcript, 'transcript', 10)
        self._processing_pub = self.create_publisher(Bool, 'processing_audio', 1)
        self._audio_sub = hbba_lite.OnOffHbbaSubscriber(self, AudioFrame, 'audio_in', self._audio_cb, 10)
        self._audio_sub.on_filter_state_changed(self._filter_state_changed_cb)
        self._voice_activity_sub = self.create_subscription(VoiceActivity, 'voice_activity', self._voice_activity_cb, 10)

        self._speech_client = speech.SpeechClient()

    def _voice_activity_cb(self, msg):
        last_is_voice = self._is_voice
        self._is_voice = msg.is_voice

        if last_is_voice and not self._is_voice:
            self._end_sequence()

    def _end_sequence(self):
        with self.frames_to_process_mutex:
            if self._frames_to_process is None:
                with self.buffer_mutex:
                    if len(self._frames_buffer)>0:
                        self._frames_to_process = self._frames_buffer
                        self._frames_buffer = []

                        start_processing_msg = Bool()
                        start_processing_msg.data = True
                        self._processing_pub.publish(start_processing_msg)

    def _convert_language_to_language_code(self, language):
        if language == 'en':
            return 'en-US'
        elif language == 'fr':
            return 'fr-CA'

    def _create_request_frame_buffer(self):
        return np.zeros(self._frame_sample_count * self._request_frame_count, dtype=np.int16)

    def _audio_cb(self, msg):
        if self._is_enabled:

            if msg.format != SUPPORTED_AUDIO_FORMAT or \
                    msg.channel_count != SUPPORTED_CHANNEL_COUNT or \
                    msg.sampling_frequency != self._sampling_frequency or \
                    msg.frame_sample_count != self._frame_sample_count:
                self.get_logger().error(
                    f'Invalid audio frame (msg.format={msg.format}, msg.channel_count={msg.channel_count}' +
                    f', msg.sampling_frequency={msg.sampling_frequency}, msg.frame_sample_count={msg.frame_sample_count})')
                return

            audio_frame = np.frombuffer(msg.data, dtype=np.int16)
            self._buffer[self._current_buffer_index:self._current_buffer_index +
                            self._frame_sample_count] = audio_frame

            self._current_buffer_index += self._frame_sample_count

            if self._current_buffer_index >= self._buffer.shape[0]:
                self._current_buffer_index = 0

                with self.buffer_mutex:

                    self._frames_buffer.append(self._buffer.copy())

                    if not self._is_voice and len(self._frames_buffer) > self._prebuffing_buffer_number:
                        self._frames_buffer = self._frames_buffer[-self._prebuffing_buffer_number:]
                    
                    if len(self._frames_buffer) > self._max_buffer_number:
                        self._frames_buffer = self._frames_buffer[-self._max_buffer_number:]


    def _filter_state_changed_cb(self, previous_is_filtering_all_messages, new_is_filtering_all_messages):
        if previous_is_filtering_all_messages and not new_is_filtering_all_messages:
            self._current_buffer_index = 0
            self._is_enabled = True
            with self.buffer_mutex:
                self._frames_buffer = []

        elif not previous_is_filtering_all_messages and new_is_filtering_all_messages:
            self._is_enabled = False
            with self.buffer_mutex:
                self._frames_buffer = []

    def run(self):
        speech_to_text_thread = threading.Thread(target=self._speech_to_text_thread_run)
        speech_to_text_thread.start()

        rclpy.spin(self)

        self._filter_state_changed_cb(self._audio_sub.is_filtering_all_messages, True)
        speech_to_text_thread.join()

    def _speech_to_text_thread_run(self):
        config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self._sampling_frequency,
                language_code=self._language_code,
                model="latest_short",
                speech_contexts=[speech.SpeechContext(phrases=["t-top"], boost=20.0)])
        
        while rclpy.ok():

            ready = True
            if not self._is_enabled:
                ready = False
            
            with self.frames_to_process_mutex:
                if self._frames_to_process is None:
                    ready = False
            
            if not ready:
                time.sleep(self._sleeping_duration)
                continue

            start_timestamp = datetime.datetime.now()
            response = self._speech_client.recognize(config=config, audio=self._request_frame_generator())

            if response.results:
                msg = Transcript()
                msg.text = response.results[0].alternatives[0].transcript
                msg.is_final = True
                msg.processing_time_s = (datetime.datetime.now() - start_timestamp).total_seconds()
                msg.total_samples_count = self._total_samples_count
                self._text_pub.publish(msg)

            self._total_samples_count = 0

            start_processing_msg = Bool()
            start_processing_msg.data = False
            self._processing_pub.publish(start_processing_msg)

    def _request_frame_generator(self):
        self._total_samples_count = 0
        with self.frames_to_process_mutex:
            speech.RecognitionAudio()
            audio_content = np.concatenate(self._frames_to_process)
            self._total_samples_count += audio_content.shape[0]
            self._frames_to_process = None
            return speech.RecognitionAudio(content=audio_content.tobytes())
            


def main():
    rclpy.init()

    google_speech_to_text_node = GoogleSpeechToTextNode()

    try:
        while rclpy.ok():
            try:
                google_speech_to_text_node.run()
            except (core_exceptions.InvalidArgument,
                    core_exceptions.Unknown,
                    core_exceptions.DeadlineExceeded,
                    core_exceptions.OutOfRange) as e:
                google_speech_to_text_node.get_logger().error(f'google_speech_to_text_node has failed ({e})')
    except KeyboardInterrupt:
        pass
    finally:
        google_speech_to_text_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
