#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

set -eu

AUTO_PROVISION=$1
CONTAINER_NAME=$2
BUCKET_NAME=$3
ORG_NAME=$4
ARTIFACT_PATH=$5
SECRET_ARN=$6
INFLUXDB_PORT=$7
TOKEN_REQUEST_TOPIC=$8
TOKEN_RESPONSE_TOPIC=$9
SERVER_PROTOCOL=${10}
BRIDGE_NETWORK_NAME=${11}
INFLUXDB_MOUNT_PATH=${12}
INFLUXDB_INTERFACE=${13}
SKIP_TLS_VERIFY=${14}

if [[ -z $AUTO_PROVISION \
  || -z $CONTAINER_NAME \
  || -z $BUCKET_NAME \
  || -z $ORG_NAME \
  || -z $ARTIFACT_PATH \
  || -z $SECRET_ARN \
  || -z $INFLUXDB_PORT \
  || -z $TOKEN_REQUEST_TOPIC \
  || -z $TOKEN_RESPONSE_TOPIC \
  || -z $SERVER_PROTOCOL \
  || -z $BRIDGE_NETWORK_NAME \
  || -z $INFLUXDB_MOUNT_PATH \
  || -z $INFLUXDB_INTERFACE \
  || -z $SKIP_TLS_VERIFY ]]; then
  echo 'Missing one or more arguments when trying to provision InfluxDB!'
  exit 1
fi

# Source our utils
. "$ARTIFACT_PATH/influxdb_utils.sh"

# If auto-provisioning, provision the container and begin vending the token
child_pid=""
if [ "$AUTO_PROVISION" == "true" ]; then
  echo "Using InfluxDB in auto-provisioning mode..."
  provision_influxdb $CONTAINER_NAME $BUCKET_NAME $ORG_NAME $ARTIFACT_PATH $SECRET_ARN $INFLUXDB_PORT $SERVER_PROTOCOL $BRIDGE_NETWORK_NAME $INFLUXDB_MOUNT_PATH $INFLUXDB_INTERFACE $SKIP_TLS_VERIFY

  python3 -u "$ARTIFACT_PATH/influxDBTokenPublisher.py" \
    --subscribe_topic $TOKEN_REQUEST_TOPIC \
    --publish_topic $TOKEN_RESPONSE_TOPIC \
    --influxdb_container_name $CONTAINER_NAME \
    --influxdb_org $ORG_NAME \
    --influxdb_bucket $BUCKET_NAME \
    --influxdb_port $INFLUXDB_PORT \
    --influxdb_interface $INFLUXDB_INTERFACE \
    --server_protocol $SERVER_PROTOCOL \
    --skip_tls_verify $SKIP_TLS_VERIFY &

  child_pid="$!"
else
  echo "Auto-provisioning is disabled, skippping..."
  setup_blank_influxdb_with_http $CONTAINER_NAME $INFLUXDB_PORT $BRIDGE_NETWORK_NAME $INFLUXDB_MOUNT_PATH $INFLUXDB_INTERFACE
  wait_for_influxdb_start $CONTAINER_NAME $INFLUXDB_PORT $SERVER_PROTOCOL $SKIP_TLS_VERIFY
fi

echo "InfluxDB is running..."
# This will keep the component running and retrieving Docker logs
docker logs --follow $CONTAINER_NAME 2>&1 

if [ ! -z "${child_pid}" ]; then
  # If started, wait for the Python background process to exit
  echo "Killing publisher subprocess with PID ${child_pid}"
  wait "${child_pid}"
fi