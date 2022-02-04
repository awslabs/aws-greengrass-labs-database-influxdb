# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import concurrent.futures
import logging
import json
import awsiot.greengrasscoreipc
import awsiot.greengrasscoreipc.client as client
from awsiot.greengrasscoreipc.model import (
    PublishToTopicRequest,
    PublishMessage,
    JsonMessage,
    SubscriptionResponseMessage,
    UnauthorizedError
)

TIMEOUT = 10
# Admin token description is in the format "USERNAME's Token"
ADMIN_TOKEN_IDENTIFIER = "'s Token"


class InfluxDBTokenStreamHandler(client.SubscribeToTopicStreamHandler):
    def __init__(self, influxdb_metadata_json, influxdb_token_json, publish_topic):
        super().__init__()
        # We need a separate IPC client for publishing
        self.influxDB_metadata_json = influxdb_metadata_json
        self.influxDB_token_json = influxdb_token_json
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
            message = event.json_message.message
            publish_json = self.get_publish_json(message)
            if not publish_json:
                logging.error("Failed to construct requested response for access")
                return
            self.publish_response(publish_json)
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

    def get_publish_json(self, message):
        """
        Parse the correct token based on the IPC message received, and construct the final JSON to publish.

        :param message: the received IPC messsage
        :return: the complete JSON, including token, to publish
        """

        loaded_token_json = json.loads(self.influxDB_token_json)
        publish_json = json.loads(self.influxDB_metadata_json)

        if not message['action'] == 'RetrieveToken':
            logging.warning('Unknown request type received over pub/sub')
            return None

        token = ''
        if message['accessLevel'] == 'RW':
            token = next(d for d in loaded_token_json if d['description'] == 'greengrass_readwrite')['token']
        elif message['accessLevel'] == 'RO':
            token = next(d for d in loaded_token_json if d['description'] == 'greengrass_read')['token']
        elif message['accessLevel'] == 'Admin':
            if not ADMIN_TOKEN_IDENTIFIER in loaded_token_json[0]['description']:
                logging.warning("InfluxDB admin token is missing or in an incorrect format")
                return None
            token = loaded_token_json[0]['token']
        else:
            logging.warning('Unknown token request type specified over pub/sub')
            return None

        if len(token) == 0:
            raise ValueError('Failed to parse InfluxDB {} token!'.format(message['accessLevel']))
        publish_json['InfluxDBTokenAccessType'] = message['accessLevel']
        publish_json['InfluxDBToken'] = token
        logging.info('Sending InfluxDB {} Token on the response topic'.format(message['accessLevel']))
        return publish_json

    def publish_response(self, publishMessage) -> None:
        """
        Publish the InfluxDB token on the token response topic.

        Parameters
        ----------
            publishMessage(str): the message to send including InfluxDB metadata and token

        Returns
        -------
            None
        """
        try:
            request = PublishToTopicRequest()
            request.topic = self.publish_topic
            publish_message = PublishMessage()
            publish_message.json_message = JsonMessage()
            publish_message.json_message.message = publishMessage
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
