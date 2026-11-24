# Deployment

To deploy fill the **host** file with the proper data:

* **Server** will be the host with the apache server.
* **Client** will be the client where tests can be launch.

The following has been tested on RHEL 9.8.

## Server

You must configure the ansible variable **playbook_user** with the name of the user who runs the playbook due to some tasks will be done locally.

The following will configure the CAs used to sign and issue certificates for the Apache virtual hosts,  and the Apache virtual hosts will be created as well:

```bash
$ ansible-playbook -i hosts deploy-server.yaml
``` 

If policy for PQC is not enabled it will be enabled and the server will be rebooted.

## Client

Client configuration must be done from the machine where server was configured, the certificates will be in the local directory configured in the ansible variable **export_cas_certs_dir** and will be copied by the role.

Yoy will also need to configure the ansible variable **webserver** with the Apache server ip.

The following will configure the client machine, copying the ca certificates to the client machine and creating the test scripts:

```bash
$ ansible-playbook -i hosts deploy-client.yaml
```

If policy for PQC is not enabled it will be enabled and the client will be rebooted.