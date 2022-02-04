# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
import pytest
import json
import subprocess

sys.path.append("src/")


def test_parse_valid_args(mocker):
    mock_parse_args = mocker.patch(
        "argparse.ArgumentParser.parse_args", return_value=argparse.Namespace(
            subscribe_topic="test/subscribe",
            publish_topic="test/publish",
            influxdb_container_name="test_containername",
            influxdb_org="testorg",
            influxdb_bucket="testbucket",
            influxdb_port="testport",
            influxdb_interface="testinterface",
            server_protocol="testprotocol",
            skip_tls_verify="testskipverify"
            )
    )
    import src.influxDBTokenPublisher as publisher

    args = publisher.parse_arguments()
    assert args.subscribe_topic == "test/subscribe"
    assert args.publish_topic == "test/publish"
    assert args.influxdb_container_name == "test_containername"
    assert args.influxdb_org == "testorg"
    assert args.influxdb_bucket == "testbucket"
    assert args.influxdb_port == "testport"
    assert args.influxdb_interface == "testinterface"
    assert args.server_protocol == "testprotocol"
    assert args.skip_tls_verify == "testskipverify"

    assert mock_parse_args.call_count == 1


def test_parse_no_args(mocker):
    import src.influxDBTokenPublisher as publisher

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        publisher.parse_arguments()
    assert pytest_wrapped_e.type == SystemExit


def test_retrieve_secret_valid_response(mocker):

    testArgs = argparse.Namespace(
        subscribe_topic="test/subscribe",
        publish_topic="test/publish",
        influxdb_container_name="test_containername",
        influxdb_org="testorg",
        influxdb_bucket="testbucket",
        influxdb_port="testport",
        influxdb_interface="testinterface",
        server_protocol="https",
        skip_tls_verify="true"
        )

    testProcessOutput = [{
        "id": "testID",
        "description": "greengrass_readwrite",
        "token": "testToken",
        "status": "active",
        "userName": "test",
        "userID": "testID",
        "permissions": [
            "read:orgs/7testorg",
            "write:orgs/76ae57693d25fabf/buckets/testbucket"
        ]
    }]
    completed_process = subprocess.CompletedProcess(args=[], stdout=json.dumps(testProcessOutput), returncode=0)
    mock_subprocess_call = mocker.patch("subprocess.run", return_value=completed_process)

    import src.influxDBTokenPublisher as publisher

    json_output = json.loads(publisher.retrieve_influxDB_token_json(testArgs))[0]
    assert json_output['description'] == "greengrass_readwrite"
    assert json_output['token'] == "testToken"
    assert mock_subprocess_call.call_count == 1


def test_retrieve_secret_invalid_response(mocker):

    testArgs = argparse.Namespace(
        subscribe_topic="test/subscribe",
        publish_topic="test/publish",
        influxdb_container_name="test_containername",
        influxdb_org="testorg",
        influxdb_bucket="testbucket",
        influxdb_port="testport",
        influxdb_interface="testinterface",
        server_protocol="https",
        skip_tls_verify="true"
        )

    testProcessOutput = [{
        "description": "greengrass_readwrite",
        "token": "",
    }]

    completed_process = subprocess.CompletedProcess(
        args=[],
        stdout=json.dumps(testProcessOutput),
        stderr="error",
        returncode=0)
    mocker.patch("subprocess.run", return_value=completed_process)

    import src.influxDBTokenPublisher as publisher

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        publisher.retrieve_influxDB_token_json(testArgs)
    assert pytest_wrapped_e.type == SystemExit


def test_retrieve_secret_failed_response(mocker):

    testArgs = argparse.Namespace(
        subscribe_topic="test/subscribe",
        publish_topic="test/publish",
        influxdb_container_name="test_containername",
        influxdb_org="testorg",
        influxdb_bucket="testbucket",
        influxdb_port="testport",
        influxdb_interface="testinterface",
        server_protocol="https",
        skip_tls_verify="true"
        )

    completed_process = subprocess.CompletedProcess(args=[], stdout="", stderr="error", returncode=0)
    mocker.patch("subprocess.run", return_value=completed_process)

    import src.influxDBTokenPublisher as publisher

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        publisher.retrieve_influxDB_token_json(testArgs)
        assert pytest_wrapped_e.type == SystemExit


def test_listen_to_token_requests(mocker):
    testArgs = argparse.Namespace(
        subscribe_topic="test/subscribe",
        publish_topic="test/publish",
        influxdb_container_name="test_containername",
        influxdb_org="testorg",
        influxdb_bucket="testbucket",
        influxdb_port="testport",
        influxdb_interface="testinterface",
        server_protocol="https",
        skip_tls_verify="true"
        )
    test_influxdb_rw_token = "testToken"
    mock_ipc_client = mocker.patch("awsiot.greengrasscoreipc.connect")

    import src.influxDBTokenPublisher as publisher
    publisher.listen_to_token_requests(testArgs, test_influxdb_rw_token)
    assert mock_ipc_client.call_count == 2


def test_no_ipc_connection(mocker):

    testArgs = argparse.Namespace(
        subscribe_topic="test/subscribe",
        publish_topic="test/publish",
        influxdb_container_name="test_containername",
        influxdb_org="testorg",
        influxdb_bucket="testbucket",
        influxdb_port="testport",
        influxdb_interface="testinterface",
        server_protocol="https",
        skip_tls_verify="true"
    )
    test_influxdb_rw_token = "testToken"
    mocker.patch("awsiot.greengrasscoreipc.connect", side_effect=TimeoutError("test"))

    import src.influxDBTokenPublisher as publisher

    with pytest.raises(TimeoutError, match='test'):
        publisher.listen_to_token_requests(testArgs, test_influxdb_rw_token)
