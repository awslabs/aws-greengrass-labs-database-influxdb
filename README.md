## Greengrass Labs InfluxDB Component - `aws.greengrass.labs.database.InfluxDB`

## Overview
This AWS IoT Greengrass component allows you to provision and manage an [InfluxDB database](https://www.influxdata.com/) on your device. 

At a high level, the component will do the following:

1. Pull down the official InfluxDB v2 Docker image from Dockerhub.
2. By default, will create new self-signed certificates and use them for HTTPS. You can toggle on/off both the certificate generation and HTTPS support separately, in case you would like to bring your own certificates to use with HTTPS, or if you would like to just use HTTP.
3. Retrieve a pre-configured secret containing a username and password from AWS Secret Manager via the `aws.greengrass.SecretManager` Greengrass component. These secrets will be used to setup InfluxDB.
3. Create a new InfluxDB container using the self-signed certificates and retrieved username/password, persisting the database by mounting it to a location of your choice on your host machine.
4. Validate the status of the InfluxDB instance.
5. Create a new InfluxDB auth token with read/write bucket privileges, and set up a local IPC pub/sub subscription to a configurable response topic to vend this auth token, along with other InfluxDB metadata. 
	 * Other Greengrass components on your device can send a pub/sub request to a configurable request topic to retrieve this data, and use it to connect to InfluxDB on their own. If you would like to view an example, see [the `aws.greengrass.labs.telemetry.InfluxDBPublisher` component, which relays Greengrass system health telemetry to InfluxDB](https://github.com/awslabs/aws-greengrass-labs-telemetry-influxdbpublisher).

## Configuration
The `aws.greengrass.labs.database.InfluxDB` component supports the following configuration options. By default, `AutoProvision` is set to `True`, which will require you to provide the configuration for `SecretArn` but leave the remainder of the configuration as the default.

* `AutoProvision` - Retrieves a username/password from Secret Manager in order to provision InfluxDB. If turned off, an InfluxDB instance will still be set up, but you will need to [provision the instance on your own](https://docs.influxdata.com/influxdb/v2.0/install/?t=Docker).
	*   (`true`|`false`)
	* default: `true` 
* `SecretArn` - The ARN of the AWS Secret Manager secret containing your desired InfluxDB username/password.
	* (`string`)
	* default: `arn:aws:secretsmanager:<region>:<account>:secret:<name>`
*  `InfluxDBMountPath` - Absolute path of a directory on your host machine that will be used to persist InfluxDB data and certs.
	* (`string`)
	* default: `/home/ggc_user/dashboard`
* `InfluxDBContainerName` - The name of the InfluxDB Docker container.
	* (`string`)
	*  default:  `greengrass_InfluxDB`
* `InfluxDBOrg` - The default InfluxDB organization to use.
	* (`string`)
	*  default : `greengrass`
* `InfluxDBBucket` - The default InfluxDB bucket to use to store data.
	* (`string`)
	*  default: `greengrass-telemetry`
* `InfluxDBInterface` - The IP for the InfluxDB container to bind on. 
	* (`string`)
	*  default: `127.0.0.1`
* `InfluxDBPort` -The port for the InfluxDB Docker container to bind to.
	 *  (`string`)
	 * default: `8086`
* `BridgeNetworkName` - The Docker bridge network to create and use for the InfluxDB Docker container.
	* (`string`)
	*  default:`greengrass-telemetry-bridge`
* `ServerProtocol`- The protocol to use.
	*  (`https` | `http`)
	*  default: `https`
* `GenerateSelfSignedCert` - Generates self-signed certs for HTTPS if they do not already exist. If set to false while using HTTPS, the component will look for the following two files to use: `{configuration:/InfluxDBMountPath}/influxdb2_certs/influxdb/influxdb.crt` and `{configuration:/InfluxDBMountPath}/influxdb2_certs/influxdb/influxdb.key`
	* (`true` | `false` )
	*  default: `true`
* `SkipTLSVerify`: Skip TLS verification (if using self-signed certificates for HTTPS).
	* (`true` | `false` )
	*  default: `true`
 * `HTTPSCertExpirationDays` - The number of days you would like the auto-generated self-signed certificates to be valid for.
	 * (`string`)
	 *  default: `365`
 * `TokenRequestTopic` - The local pub/sub topic you would like the component to subscribe to in order to listen for requests for the InfluxDB R/W token.
	 * (`string`)
	 *  default: `greengrass/influxdb/token/request`
 * `TokenResponseTopic` - The local pub/sub topic you would like the component to respond on when handling a request for the InfluxDB R/W token.
	 * (`string`)
	 *  default: `greengrass/influxdb/token/response`
 * `accessControl` - [Greengrass Access Control Policy](https://docs.aws.amazon.com/greengrass/v2/developerguide/interprocess-communication.html#ipc-authorization-policies), required for secret retrieval and pub/sub token vending.

## Setup
TBD

When specifying a mount path, note that this mount path will be used to store sensitive data, including secrets and certs used for InfluxDB auth. You are responsible for securing this directory on your device. Ensure that the `ggc_user:ggc_group` has read/write/execute access to this directory with the following command: `namei -m <path>`.

If you would like to connect InfluxDB to Grafana or another application with read-only access, you can do so with the following commands to create a separate read-only token that will restrict access. Add `--skip-verify` to these commands if using self-signed certificates with HTTPS.

1. Retrieve the InfluxDB admin token:
```
docker exec -it greengrass_InfluxDB influx auth list
```

2. Retrieve the Bucket ID:

```
docker exec -it greengrass_InfluxDB influx bucket list --name greengrass-telemetry 
```

2. Use the admin token to create a read-only token
```
docker exec -it greengrass_InfluxDB influx auth create \
  --read-bucket <bucket ID> --token <admin token> --description "Read-only token"
 ```

## Troubleshooting
TBD


## Certificate Management and Expiry

* Customers should use their own certs; self-signed is less secure.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.

This project also uses but does not distribute the InfluxDBv2 Docker image from Dockerhub, which is under the MIT License. You can view the InfluxDB license [here on Github](https://github.com/influxdata/influxdb/blob/master/LICENSE).

