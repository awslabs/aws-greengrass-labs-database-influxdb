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


def retrieve_influxDB_token(args) -> str:
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
    dockerExecProcess = ""
    authListCommand = ['docker', 'exec', '-t', args.influxdb_container_name, 'influx', 'auth', 'list', '--json']
    if args.server_protocol == "https":
        authListCommand.append('--host')
        authListCommand.append('https://{}:{}'.format(args.influxdb_container_name, args.influxdb_port))

    if bool(strtobool(args.skip_tls_verify)):
        authListCommand.append('--skip-verify')

    logging.info("Running the following docker exec command to retrieve the InfluxDB token: " + str(authListCommand))

    dockerExecProcess = subprocess.run(authListCommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    token_json = dockerExecProcess.stdout

    if dockerExecProcess.stderr:
        logging.error(dockerExecProcess.stderr)
    if(len(token_json) == 0):
        logging.error('Failed to retrieve InfluxDB RW token data from Docker! Retrieved token was: {}'.format(token_json))
        exit(1)
    influxdb_rw_token = next(d for d in json.loads(token_json) if d['description'] == 'greengrass_readwrite')['token']
    if(len(influxdb_rw_token) == 0):
        logging.error('Failed to parse InfluxDB RW token! Retrieved token was: {}'.format(influxdb_rw_token))
        exit(1)

    return influxdb_rw_token


def listen_to_token_requests(args, influxdb_rw_token) -> None:
    """
    Setup a new IPC subscription over local pub/sub to listen to token requests and vend tokens.

    Parameters
    ----------
        args(Namespace): Parsed arguments
        influxdb_rw_token(str): InfluxDB RW token

    Returns
    -------
        None
    """

    try:
        influxDB_data = {}
        influxDB_data['InfluxDBContainerName'] = args.influxdb_container_name
        influxDB_data['InfluxDBOrg'] = args.influxdb_org
        influxDB_data['InfluxDBBucket'] = args.influxdb_bucket
        influxDB_data['InfluxDBPort'] = args.influxdb_port
        influxDB_data['InfluxDBInterface'] = args.influxdb_interface
        influxDB_data['InfluxDBRWToken'] = influxdb_rw_token
        influxDB_data['InfluxDBServerProtocol'] = args.server_protocol
        influxDB_data['InfluxDBSkipTLSVerify'] = args.skip_tls_verify
        influxDB_json = json.dumps(influxDB_data)

        logging.info('Successfully retrieved InfluxDB parameters!')

        ipc_client = awsiot.greengrasscoreipc.connect()
        request = SubscribeToTopicRequest()
        request.topic = args.subscribe_topic
        handler = InfluxDBTokenStreamHandler(influxDB_json, args.publish_topic)
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
        influxdb_rw_token = retrieve_influxDB_token(args)
        listen_to_token_requests(args, influxdb_rw_token)
        # Keep the main thread alive, or the process will exit.
        while True:
            time.sleep(10)
    except InterruptedError:
        logging.error('Subscribe interrupted.', exc_info=True)
        exit(1)
    except Exception:
        logging.error('Exception occurred when using IPC.', exc_info=True)
        exit(1)
