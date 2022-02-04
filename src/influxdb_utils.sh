#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

wait_for_influxdb_start(){
  # InfluxDB can take some time to start
  # Retry `influx ping` until we receive confirmation that it is up and running
  # Influx commands need to be given the port of InfluxDB inside the container, which is always 8086 unless overridden inside the InfluxDB config
  CONTAINER_NAME=$1
  INFLUXDB_PORT=$2
  SERVER_PROTOCOL=$3
  SKIP_TLS_VERIFY=$4

  if [[ -z $CONTAINER_NAME || -z $INFLUXDB_PORT || -z $SERVER_PROTOCOL || -z $SKIP_TLS_VERIFY ]]; then
    echo 'Container name, InfluxDB port, server protocol, or skip TLS verify was not provided when waiting for InfluxDB to start!'
    exit 1
  fi

  SKIP_TLS_VERIFY_ARG=""
  if [ "$SKIP_TLS_VERIFY" == "true" ]; then
    SKIP_TLS_VERIFY_ARG="--skip-verify"
  fi

  CONTAINER_SETUP_STATUS=""
  RETRIES=0
  until [ "$CONTAINER_SETUP_STATUS" == "OK" ] || [ "$RETRIES" -eq 4 ]; do
    sleep 10
    echo "Attempt $RETRIES: Waiting until InfluxDB reports a status of OK..."
    if [ "$SERVER_PROTOCOL" == "http" ]; then
      CONTAINER_SETUP_STATUS=$(docker exec "$CONTAINER_NAME" influx ping --host "http://$CONTAINER_NAME:8086") || true
    elif [ "$SERVER_PROTOCOL" == "https" ]; then
      CONTAINER_SETUP_STATUS=$(docker exec "$CONTAINER_NAME" influx ping --host "https://$CONTAINER_NAME:8086" "${SKIP_TLS_VERIFY_ARG:+$SKIP_TLS_VERIFY_ARG}") || true
    fi
    echo "Container status: $CONTAINER_SETUP_STATUS"
    RETRIES="$((RETRIES+1))"
  done

  if [ "$CONTAINER_SETUP_STATUS" != "OK" ]; then
    echo "ERROR: Max retries exceeded while waiting for InfluxDB to start. Dumping InfluxDB Docker logs and exiting..."
    # Dump Docker logs before the container is removed
    docker logs "$CONTAINER_NAME"
    exit 1
  fi

  echo "Successfully waited for InfluxDB to start up!"
}

create_token(){
  CONTAINER_NAME=$1
  INFLUXDB_PORT=$2
  BUCKET_NAME=$3
  ORG_NAME=$4
  SERVER_PROTOCOL=$5
  SKIP_TLS_VERIFY=$6
  ACCESS=$7

  if [[ -z $CONTAINER_NAME || -z $BUCKET_NAME || -z $ORG_NAME ||  -z $SERVER_PROTOCOL ||  -z $SKIP_TLS_VERIFY || -z $ACCESS ]]; then
    echo 'Missing one or more arguments when trying to create the token!'
    exit 1
  fi

  SKIP_TLS_VERIFY_ARG=""
  if [ "$SKIP_TLS_VERIFY" == "true" ]; then
    SKIP_TLS_VERIFY_ARG="--skip-verify"
  fi

  BUCKET_ID=""
  if [ "$SERVER_PROTOCOL" == "http" ]; then
    BUCKET_ID=$(docker exec -t "$CONTAINER_NAME" influx bucket list --json --name "$BUCKET_NAME" --host "http://$CONTAINER_NAME:8086" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
    echo "Retrieved bucket ID: $BUCKET_ID"
  elif [ "$SERVER_PROTOCOL" == "https" ]; then
    BUCKET_ID=$(docker exec -t "$CONTAINER_NAME" influx bucket list --json --name "$BUCKET_NAME" --host "https://$CONTAINER_NAME:8086" "${SKIP_TLS_VERIFY_ARG:+$SKIP_TLS_VERIFY_ARG}" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
    echo "Retrieved bucket ID: $BUCKET_ID"
  fi

  ACCESS_POLICY_ARGS=()
  DESCRIPTION=""
  if [ "$ACCESS" == "readonly" ]; then
    ACCESS_POLICY_ARGS=("--read-bucket" "${BUCKET_ID}")
    DESCRIPTION="greengrass_read"
  elif [ "$ACCESS" == "readwrite" ]; then
    ACCESS_POLICY_ARGS=("--read-bucket" "${BUCKET_ID}" "--write-bucket" "${BUCKET_ID}")
    DESCRIPTION="greengrass_readwrite"
  fi

  INFLUXDB_RW_TOKEN_METADATA=""
  if [ "$SERVER_PROTOCOL" == "http" ]; then
    INFLUXDB_RW_TOKEN_METADATA=$(docker exec -t "$CONTAINER_NAME" influx auth create --host "http://$CONTAINER_NAME:8086" "${ACCESS_POLICY_ARGS[@]}" --org "$ORG_NAME" --description "$DESCRIPTION" --hide-headers)
  elif [ "$SERVER_PROTOCOL" == "https" ]; then
    INFLUXDB_RW_TOKEN_METADATA=$(docker exec -t "$CONTAINER_NAME" influx auth create --host "https://$CONTAINER_NAME:8086" "${SKIP_TLS_VERIFY_ARG:+$SKIP_TLS_VERIFY_ARG}" "${ACCESS_POLICY_ARGS[@]}" --org "$ORG_NAME" --description "$DESCRIPTION" --hide-headers)
  fi

  if [ -z "$INFLUXDB_RW_TOKEN_METADATA" ]; then
    echo "Failed to create InfluxDB Token $ACCESS"
    exit 1
  fi

  echo "Successfully created InfluxDB token ${DESCRIPTION}"
}

validate_password(){
  INFLUXDB_PASSWORD=$1
  if [[ ${#INFLUXDB_PASSWORD} -ge 16 && "$INFLUXDB_PASSWORD" == *[A-Z]* && "$INFLUXDB_PASSWORD" == *[a-z]* && "$INFLUXDB_PASSWORD" == *[0-9]* && "$INFLUXDB_PASSWORD" == *[#$@%+*\&!^]* ]]; then
    echo "Validated password successfully."
  else
    echo "WARNING: Password must contain at least 16 characters, uppercase and lowercase letters, numbers, and special characters."
    exit 1
  fi
}

setup_blank_influxdb_with_http() {
  CONTAINER_NAME=$1
  INFLUXDB_PORT=$2
  BRIDGE_NETWORK_NAME=$3
  INFLUXDB_MOUNT_PATH=$4
  INFLUXDB_INTERFACE=$5

  if [[ -z $CONTAINER_NAME || -z $INFLUXDB_PORT || -z $BRIDGE_NETWORK_NAME || -z $INFLUXDB_MOUNT_PATH ]]; then
    echo 'Missing one or more arguments when trying to provision InfluxDB!'
    exit 1
  fi

  echo "Setting up a blank InfluxDB instance with HTTP..."

  docker run -d  \
    -p "$INFLUXDB_INTERFACE":"$INFLUXDB_PORT":8086 \
    --network="$BRIDGE_NETWORK_NAME" \
    --name "$CONTAINER_NAME" \
    --read-only \
    -v "$INFLUXDB_MOUNT_PATH"/influxdb2/data:/var/lib/influxdb2 \
    -v "$INFLUXDB_MOUNT_PATH"/influxdb2/config:/etc/influxdb2 \
    influxdb:2.0.9
}

provision_influxdb(){
  CONTAINER_NAME=$1
  BUCKET_NAME=$2
  ORG_NAME=$3
  ARTIFACT_PATH=$4
  SECRET_ARN=$5
  INFLUXDB_PORT=$6
  SERVER_PROTOCOL=$7
  BRIDGE_NETWORK_NAME=$8
  INFLUXDB_MOUNT_PATH=$9
  INFLUXDB_INTERFACE=${10}
  SKIP_TLS_VERIFY=${11}

  if [[ -z $CONTAINER_NAME \
    || -z $BUCKET_NAME \
    || -z $ORG_NAME \
    || -z $ARTIFACT_PATH \
    || -z $SECRET_ARN \
    || -z $INFLUXDB_PORT \
    || -z $SERVER_PROTOCOL \
    || -z $BRIDGE_NETWORK_NAME \
    || -z $INFLUXDB_MOUNT_PATH \
    || -z $INFLUXDB_INTERFACE
    || -z $SKIP_TLS_VERIFY ]]; then
    echo 'Missing one or more arguments when trying to provision InfluxDB!'
    exit 1
  fi

  if [ "$SERVER_PROTOCOL" == "https" ]; then

    echo "Setting up a blank InfluxDB instance with HTTPS..."
    docker run -d \
      -p "$INFLUXDB_INTERFACE":"$INFLUXDB_PORT":8086 \
      --network="$BRIDGE_NETWORK_NAME" \
      --name "$CONTAINER_NAME" \
      --read-only \
      -v "$INFLUXDB_MOUNT_PATH"/influxdb2/data:/var/lib/influxdb2 \
      -v "$INFLUXDB_MOUNT_PATH"/influxdb2/config:/etc/influxdb2 \
      -v "$INFLUXDB_MOUNT_PATH"/influxdb2_certs/:/etc/ssl/greengrass:ro \
      -e INFLUXD_TLS_CERT=/etc/ssl/greengrass/influxdb.crt \
      -e INFLUXD_TLS_KEY=/etc/ssl/greengrass/influxdb.key \
      influxdb:2.0.9

      wait_for_influxdb_start "$CONTAINER_NAME" "$INFLUXDB_PORT" "$SERVER_PROTOCOL" "$SKIP_TLS_VERIFY"
  else
    setup_blank_influxdb_with_http "$CONTAINER_NAME" "$INFLUXDB_PORT" "$BRIDGE_NETWORK_NAME" "$INFLUXDB_MOUNT_PATH" "$INFLUXDB_INTERFACE"
    wait_for_influxdb_start "$CONTAINER_NAME" "$INFLUXDB_PORT" "$SERVER_PROTOCOL" "$SKIP_TLS_VERIFY"
  fi

  SKIP_TLS_VERIFY_ARG=""
  if [ "$SKIP_TLS_VERIFY" == "true" ]; then
    SKIP_TLS_VERIFY_ARG="--skip-verify"
  fi

  # Check if auth tokens already exists
  SETUP_EXIT_CODE=0
  echo "Checking if auth tokens already exist..."
  if [ $SERVER_PROTOCOL == "http" ]; then
    docker exec $CONTAINER_NAME influx auth list --host "http://$CONTAINER_NAME:8086" > /dev/null 2>&1 || SETUP_EXIT_CODE=$?
  elif [ $SERVER_PROTOCOL == "https" ]; then
    docker exec $CONTAINER_NAME influx auth list --host "https://$CONTAINER_NAME:8086" "${SKIP_TLS_VERIFY_ARG:+$SKIP_TLS_VERIFY_ARG}" > /dev/null 2>&1 || SETUP_EXIT_CODE=$?
  fi

  if [ "$SETUP_EXIT_CODE" -eq 1 ]; then
    # Setup auth
    echo "Setting up InfluxDB with provided credentials..."
    INFLUXDB_CREDENTIALS=$(python3 "$ARTIFACT_PATH"/retrieveInfluxDBSecrets.py --secret_arn "$SECRET_ARN" )
    INFLUX_CREDENTIALS_ARRAY=($INFLUXDB_CREDENTIALS)
    INFLUXDB_USERNAME=${INFLUX_CREDENTIALS_ARRAY[0]}
    INFLUXDB_PASSWORD=${INFLUX_CREDENTIALS_ARRAY[1]}
    echo "Validating password..."
    validate_password "$INFLUXDB_PASSWORD"

    if [ $SERVER_PROTOCOL == "http" ]; then
      docker exec -t $CONTAINER_NAME influx setup --host "http://$CONTAINER_NAME:8086" --force --username $INFLUXDB_USERNAME --password $INFLUXDB_PASSWORD --org $ORG_NAME --bucket $BUCKET_NAME
    elif [ $SERVER_PROTOCOL == "https" ]; then
      docker exec -t $CONTAINER_NAME influx setup --host "https://$CONTAINER_NAME:8086" "${SKIP_TLS_VERIFY_ARG:+$SKIP_TLS_VERIFY_ARG}" --force --username $INFLUXDB_USERNAME --password $INFLUXDB_PASSWORD --org $ORG_NAME --bucket $BUCKET_NAME
    fi

    create_token "$CONTAINER_NAME" "$INFLUXDB_PORT" "$BUCKET_NAME" "$ORG_NAME" "$SERVER_PROTOCOL" "$SKIP_TLS_VERIFY" "readonly"
    create_token "$CONTAINER_NAME" "$INFLUXDB_PORT" "$BUCKET_NAME" "$ORG_NAME" "$SERVER_PROTOCOL" "$SKIP_TLS_VERIFY" "readwrite"
  else
    # Reuse auth
    echo "Reusing existing InfluxDB setup..."
  fi
}
