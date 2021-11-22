# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import concurrent.futures
import logging

import awsiot.greengrasscoreipc
import awsiot.greengrasscoreipc.client as client
from awsiot.greengrasscoreipc.model import (
    PublishToTopicRequest,
    PublishMessage,
    BinaryMessage,
    SubscriptionResponseMessage,
    UnauthorizedError
)

TIMEOUT = 10


class InfluxDBTokenStreamHandler(client.SubscribeToTopicStreamHandler):
    def __init__(self, influxDB_json, publish_topic):
        super().__init__()
        # We need a separate IPC client for publishing
        self.influxDB_json = influxDB_json
        self.publish_topic = publish_topic
        self.publish_client = awsiot.greengrasscoreipc.connect()
        logging.info("Initialized InfluxDBTokenStreamHandler")

    def handle_stream_event(self, event: SubscriptionResponseMessage) -> None:
        """
        When we receive a message over IPC on the token request topic, publish the token on the response topic.

        Parameters
        ----------
            event(SubscriptionResponseMessage): The received IPC message

        Returns
        -------
            None
        """
        try:
            message = str(event.binary_message.message, "utf-8")
            if message == 'GetInfluxDBData':
                logging.info('Sending InfluxDB RW Token on the response topic')
                self.publish_response()
            else:
                logging.warning('Unknown request type received over pub/sub')
        except Exception:
            logging.error('Received an error', exc_info=True)

    def on_stream_event(self, event: SubscriptionResponseMessage) -> None:
        self.handle_stream_event(event)

    def on_stream_error(self, error: Exception) -> bool:
        """
        Log stream errors but keep the stream open.

        Parameters
        ----------
            error(Exception): The exception we see as a result of the stream error.

        Returns
        -------
            False(bool): Return False to keep the stream open.
        """
        logging.error('Received an error with the InfluxDB token publish stream', exc_info=True)
        return False

    def on_stream_closed(self) -> None:
        """
        Handle the stream closing.

        Parameters
        ----------
            None

        Returns
        -------
            None
        """
        logging.info('Subscribe to topic stream closed.')

    def publish_response(self) -> None:
        """
        Publish the InfluxDB token on the token response topic.

        Parameters
        ----------
            None

        Returns
        -------
            None
        """
        try:
            request = PublishToTopicRequest()
            request.topic = self.publish_topic
            publish_message = PublishMessage()
            publish_message.binary_message = BinaryMessage()
            publish_message.binary_message.message = bytes(self.influxDB_json, "utf-8")
            request.publish_message = publish_message
            operation = self.publish_client.new_publish_to_topic()
            operation.activate(request)
            futureResponse = operation.get_response()
            futureResponse.result(TIMEOUT)
            logging.info('Successfully published InfluxDB token response to topic: {}'.format(self.publish_topic))
        except concurrent.futures.TimeoutError as e:
            logging.error('Timeout occurred while publishing to topic: {}'.format(self.publish_topic), exc_info=True)
            raise e
        except UnauthorizedError as e:
            logging.error('Unauthorized error while publishing to topic: {}'.format(self.publish_topic), exc_info=True)
            raise e
        except Exception as e:
            logging.error('Exception while publishing to topic: {}'.format(self.publish_topic), exc_info=True)
            raise e
