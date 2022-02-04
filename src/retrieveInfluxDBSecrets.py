# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import json
import logging
from argparse import Namespace
import awsiot.greengrasscoreipc
from awsiot.greengrasscoreipc.model import GetSecretValueRequest, UnauthorizedError

TIMEOUT = 10
logging.basicConfig(level=logging.INFO)


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
    parser.add_argument("--secret_arn", type=str, required=True)
    return parser.parse_args()


def get_secret_over_ipc(secret_arn) -> str:
    """
    Parse arguments.

    Parameters
    ----------
        secret_arn(str): The ARN of the secret to retrieve from Secret Manager.

    Returns
    -------
        secret_string(str): Retrieved IPC secret.
    """

    try:
        ipc_client = awsiot.greengrasscoreipc.connect()
        request = GetSecretValueRequest()
        request.secret_id = secret_arn
        operation = ipc_client.new_get_secret_value()
        operation.activate(request)
        futureResponse = operation.get_response()
        response = futureResponse.result(TIMEOUT)
        return response.secret_value.secret_string
    except concurrent.futures.TimeoutError as e:
        logging.error("Timeout occurred while getting secret: {}".format(secret_arn), exc_info=True)
        raise e
    except UnauthorizedError as e:
        logging.error("Unauthorized error while getting secret: {}".format(secret_arn), exc_info=True)
        raise e
    except Exception as e:
        logging.error("Exception while getting secret: {}".format(secret_arn), exc_info=True)
        raise e


def retrieve_secret(secret_arn):
    try:
        response = get_secret_over_ipc(secret_arn)
        secret_json = json.loads(response)
        return "{} {}".format(secret_json["influxdb_username"], secret_json["influxdb_password"])
    except Exception as e:
        logging.error("Exception while retrieving secret: {}".format(secret_arn), exc_info=True)
        raise e


if __name__ == "__main__":
    args = parse_arguments()
    print(retrieve_secret(args.secret_arn))
