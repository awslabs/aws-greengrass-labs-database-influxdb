# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import concurrent.futures
import time
import json
import subprocess
import logging
import argparse
from argparse import Namespace
from distutils.util import strtobool

import awsiot.greengrasscoreipc
from awsiot.greengrasscoreipc.model import (
    SubscribeToTopicRequest,
    UnauthorizedError
)
from influxDBTokenStreamHandler import InfluxDBTokenStreamHandler

logging.basicConfig(level=logging.INFO)
TIMEOUT = 10
# Influx commands need to be given the port of InfluxDB inside the container, which is always 8086 unless
# overridden inside the InfluxDB config
INFLUX_CONTAINER_PORT = 8086


def parse_arguments() -> Namespace:
    """
    Parse arguments.

    Parameters
    ----------
        None

    Returns
    -------
        args(Namespace): Parsed arguments
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--subscribe_topic", type=str, required=True)
    parser.add_argument("--publish_topic", type=str, required=True)
    parser.add_argument("--influxdb_container_name", type=str, required=True)
    parser.add_argument("--influxdb_org", type=str, required=True)
    parser.add_argument("--influxdb_bucket", type=str, required=True)
    parser.add_argument("--influxdb_port", type=str, required=True)
    parser.add_argument("--influxdb_interface", type=str, required=True)
    parser.add_argument("--server_protocol", type=str, required=True)
    parser.add_argument("--skip_tls_verify", type=str, required=True)
    return parser.parse_args()


def retrieve_influxDB_token_json(args) -> str:
    """
    Retrieve the created RW token from InfluxDB.

    Parameters
    ----------
        args(Namespace): Parsed arguments

    Returns
    -------
        influxdb_rw_token(str): Parsed InfluxDB RW token.
    """

    token_json = ""
    authListCommand = ['docker', 'exec', '-t', args.influxdb_container_name, 'influx', 'auth', 'list', '--json']
    if args.server_protocol == "https":
        authListCommand.append('--host')
        authListCommand.append('https://{}:{}'.format(args.influxdb_container_name, INFLUX_CONTAINER_PORT))

    if bool(strtobool(args.skip_tls_verify)):
        authListCommand.append('--skip-verify')

    logging.info("Running the following docker exec command to retrieve the InfluxDB token: " + str(authListCommand))

    dockerExecProcess = subprocess.run(authListCommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    token_json = dockerExecProcess.stdout

    if dockerExecProcess.stderr:
        logging.error(dockerExecProcess.stderr)
    if(len(token_json) == 0):
        logging.error('Failed to retrieve InfluxDB RW token data from Docker! Retrieved data was: {}'.format(token_json))
        exit(1)
    influxdb_token = json.loads(token_json)[0]['token']
    if(len(influxdb_token) == 0):
        logging.error('Retrieved InfluxDB tokens was empty!')
        exit(1)

    return token_json


def listen_to_token_requests(args, influxdb_token_json) -> None:
    """
    Setup a new IPC subscription over local pub/sub to listen to token requests and vend tokens.

    Parameters
    ----------
        args(Namespace): Parsed arguments
        influxdb_token_json(str): InfluxDB token JSON string

    Returns
    -------
        None
    """

    try:
        influxdb_metadata = {}
        influxdb_metadata['InfluxDBContainerName'] = args.influxdb_container_name
        influxdb_metadata['InfluxDBOrg'] = args.influxdb_org
        influxdb_metadata['InfluxDBBucket'] = args.influxdb_bucket
        influxdb_metadata['InfluxDBPort'] = args.influxdb_port
        influxdb_metadata['InfluxDBInterface'] = args.influxdb_interface
        influxdb_metadata['InfluxDBServerProtocol'] = args.server_protocol
        influxdb_metadata['InfluxDBSkipTLSVerify'] = args.skip_tls_verify
        influxdb_metadata_json = json.dumps(influxdb_metadata)

        logging.info('Successfully retrieved InfluxDB parameters!')

        ipc_client = awsiot.greengrasscoreipc.connect()
        request = SubscribeToTopicRequest()
        request.topic = args.subscribe_topic
        handler = InfluxDBTokenStreamHandler(influxdb_metadata_json, influxdb_token_json, args.publish_topic)
        operation = ipc_client.new_subscribe_to_topic(handler)
        operation.activate(request)
        logging.info('Successfully subscribed to topic: {}'.format(args.subscribe_topic))
        logging.info("InfluxDB has been successfully set up; now listening to token requests...")
    except concurrent.futures.TimeoutError as e:
        logging.error('Timeout occurred while subscribing to topic: {}'.format(args.subscribe_topic), exc_info=True)
        raise e
    except UnauthorizedError as e:
        logging.error('Unauthorized error while subscribing to topic: {}'.format(args.subscribe_topic), exc_info=True)
        raise e
    except Exception as e:
        logging.error('Exception while subscribing to topic: {}'.format(args.subscribe_topic), exc_info=True)
        raise e


if __name__ == "__main__":
    try:
        args = parse_arguments()
        influxdb_token_json = retrieve_influxDB_token_json(args)
        listen_to_token_requests(args, influxdb_token_json)
        # Keep the main thread alive, or the process will exit.
        while True:
            time.sleep(10)
    except InterruptedError:
        logging.error('Subscribe interrupted.', exc_info=True)
        exit(1)
    except Exception:
        logging.error('Exception occurred when using IPC.', exc_info=True)
        exit(1)
