# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
import json

from awsiot.greengrasscoreipc.model import (
    BinaryMessage,
    SubscriptionResponseMessage
)

sys.path.append("src/")


def testHandleValidStreamEvent(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps("{}"), "test")
    binary_message = BinaryMessage(message=str.encode("GetInfluxDBData"))
    response_message = SubscriptionResponseMessage(binary_message=binary_message)
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert mock_publish_response.call_count == 1


def testHandleInvalidStreamEvent(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps("{}"), "test")
    binary_message = BinaryMessage(message=str.encode("test"))
    response_message = SubscriptionResponseMessage(binary_message=binary_message)
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert not mock_publish_response.called


def testHandleNullStreamEvent(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps("{}"), "test")
    response_message = None
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert not mock_publish_response.called
