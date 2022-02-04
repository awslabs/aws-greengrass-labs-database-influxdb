# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
import json
import pytest

from awsiot.greengrasscoreipc.model import (
    JsonMessage,
    SubscriptionResponseMessage
)

sys.path.append("src/")

testTokenJson = [
    {
        "id": "0895c16b9de9e000",
        "description": "test's Token",
        "token": "testAdminToken",
        "status": "active",
        "userName": "test",
        "userID": "0895c16b80a9e000",
        "permissions": [
            "read:authorizations",
            "write:authorizations"
        ]
    },
    {
        "id": "0895c16bfba9e000",
        "description": "greengrass_read",
        "token": "testROToken",
        "status": "active",
        "userName": "test",
        "userID": "0895c16b80a9e000",
        "permissions": [
            "read:orgs/d13dcc4c7cd25bf9/buckets/2f1dc2bba2275383"
        ]
    },
    {
        "id": "0895c16c8ee9e000",
        "description": "greengrass_readwrite",
        "token": "testRWToken",
        "status": "active",
        "userName": "test",
        "userID": "0895c16b80a9e000",
        "permissions": [
            "read:orgs/d13dcc4c7cd25bf9/buckets/2f1dc2bba2275383",
            "write:orgs/d13dcc4c7cd25bf9/buckets/2f1dc2bba2275383"
        ]
    }
]

testMetadataJson = {
    'InfluxDBContainerName': 'greengrass_InfluxDB',
    'InfluxDBOrg': 'greengrass',
    'InfluxDBBucket': 'greengrass-telemetry',
    'InfluxDBPort': '8086',
    'InfluxDBInterface': '127.0.0.1',
    'InfluxDBServerProtocol': 'https',
    'InfluxDBSkipTLSVerify': 'true',
}

testPublishJson = testMetadataJson
testPublishJson['InfluxDBTokenAccessType'] = "RW"
testPublishJson['InfluxDBToken'] = "testRWToken"


def testHandleValidStreamEvent(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps(testMetadataJson), json.dumps(testTokenJson), "test/topic")
    message = JsonMessage(message={"action": "RetrieveToken",  "accessLevel": "RW"})
    response_message = SubscriptionResponseMessage(json_message=message)
    t = handler.handle_stream_event(response_message)
    mock_publish_response.assert_called_with(testPublishJson)
    assert mock_ipc_client.call_count == 1
    assert mock_publish_response.call_count == 1


def testHandleInvalidStreamEvent(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps({}), json.dumps(testTokenJson), "test")
    message = JsonMessage(message={})
    response_message = SubscriptionResponseMessage(json_message=message)
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert not mock_publish_response.called


def testHandleInvalidRequestType(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps({}), json.dumps(testTokenJson), "test")
    message = JsonMessage(message={"action": "invalid",  "accessLevel": "RW"})
    response_message = SubscriptionResponseMessage(json_message=message)
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert not mock_publish_response.called


def testHandleInvalidTokenRequestType(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps({}), json.dumps(testTokenJson), "test")
    message = JsonMessage(message={"action": "RetrieveToken",  "accessLevel": "invalid"})
    response_message = SubscriptionResponseMessage(json_message=message)
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert not mock_publish_response.called


def testHandleNullStreamEvent(mocker):
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")
    mock_publish_response = mocker.patch('src.influxDBTokenStreamHandler.InfluxDBTokenStreamHandler.publish_response')

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps(testMetadataJson), json.dumps(testTokenJson), "test")
    response_message = None
    handler.handle_stream_event(response_message)
    assert mock_ipc_client.call_count == 1
    assert not mock_publish_response.called


def testGetValidPublishJson(mocker):

    mocker.patch("awsiot.greengrasscoreipc.connect")

    import src.influxDBTokenStreamHandler as streamHandler

    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps(testMetadataJson), json.dumps(testTokenJson), "test/topic")
    message = json.loads('{"action": "RetrieveToken",  "accessLevel": "RW"}')
    publish_json = handler.get_publish_json(message)
    assert publish_json == testPublishJson

    message = json.loads('{"action": "RetrieveToken",  "accessLevel": "RO"}')
    publish_json = handler.get_publish_json(message)
    testPublishJson['InfluxDBTokenAccessType'] = "RO"
    testPublishJson['InfluxDBToken'] = "testROToken"
    assert publish_json == testPublishJson

    message = json.loads('{"action": "RetrieveToken",  "accessLevel": "Admin"}')
    publish_json = handler.get_publish_json(message)
    testPublishJson['InfluxDBTokenAccessType'] = "Admin"
    testPublishJson['InfluxDBToken'] = "testAdminToken"
    assert publish_json == testPublishJson


def testGetInvalidPublishJson(mocker):

    mocker.patch("awsiot.greengrasscoreipc.connect")

    import src.influxDBTokenStreamHandler as streamHandler

    testTokenJson[0]['token'] = ""
    testTokenJson[1]['token'] = ""
    testTokenJson[2]['token'] = ""
    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps(testMetadataJson), json.dumps(testTokenJson), "test/topic")

    with pytest.raises(ValueError, match='Failed to parse InfluxDB RW token!'):
        message = json.loads('{"action": "RetrieveToken",  "accessLevel": "RW"}')
        handler.get_publish_json(message)

    with pytest.raises(ValueError, match='Failed to parse InfluxDB RO token!'):
        message = json.loads('{"action": "RetrieveToken",  "accessLevel": "RO"}')
        handler.get_publish_json(message)

    with pytest.raises(ValueError, match='Failed to parse InfluxDB Admin token!'):
        message = json.loads('{"action": "RetrieveToken",  "accessLevel": "Admin"}')
        handler.get_publish_json(message)

    testTokenJson[0]['description'] = ""
    handler = streamHandler.InfluxDBTokenStreamHandler(json.dumps(testMetadataJson), json.dumps(testTokenJson), "test/topic")
    message = json.loads('{"action": "RetrieveToken",  "accessLevel": "Admin"}')
    retval = handler.get_publish_json(message)
    assert retval is None
