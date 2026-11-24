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

## Testing

To test the server has the right configuration, on the client:

```bash
[root@client ~]# cd tests-scripts
[root@client tests-scripts]# ./tls1.3-handshake-check.sh 
TLS 1.3 handshake verification against 192.0.2.10

=== A1 - X25519MLKEM768 + ML-DSA-65  (192.0.2.10:10443) ===
  Protocol           : TLSv1.3    [OK]
  KEX expected       : X25519MLKEM768
  KEX negotiated     : X25519MLKEM768 [OK]
  Signature expected : ML-DSA-65
  Cert Public Key    : ML-DSA-65
  Cert Signature     : ML-DSA-65          [OK]
  CertVerify (online): mldsa65 / n/a (hash embedded)
  Suite expected     : TLS_AES_256_GCM_SHA384
  Suite negotiated   : TLS_AES_256_GCM_SHA384 [OK]
    -> Cipher (AEAD) : AES_256_GCM            [OK]
    -> Hash          : SHA384                 [OK]
  RESULT: PASS

=== A2 - NIST P-384 + ECDSA-SHA384  (192.0.2.10:8443) ===
  Protocol           : TLSv1.3    [OK]
  KEX expected       : secp384r1
  KEX negotiated     : secp384r1 (forced; handshake OK) [OK]
  Signature expected : ecdsa-with-SHA384
  Cert Public Key    : id-ecPublicKey
  Cert Signature     : ecdsa-with-SHA384  [OK]
  CertVerify (online): ecdsa_secp384r1_sha384 / SHA384
  Suite expected     : TLS_AES_256_GCM_SHA384
  Suite negotiated   : TLS_AES_256_GCM_SHA384 [OK]
    -> Cipher (AEAD) : AES_256_GCM            [OK]
    -> Hash          : SHA384                 [OK]
  RESULT: PASS

=== B1 - X25519MLKEM768 + SLH-DSA-SHA2-192s  (192.0.2.10:11443) ===
  Protocol           : TLSv1.3    [OK]
  KEX expected       : X25519MLKEM768
  KEX negotiated     : X25519MLKEM768 [OK]
  Signature expected : SLH-DSA-SHA2-192s
  Cert Public Key    : ML-DSA-65
  Cert Signature     : SLH-DSA-SHA2-192s  [OK]
  CertVerify (online): mldsa65 / n/a (hash embedded)
  Suite expected     : TLS_AES_256_GCM_SHA384
  Suite negotiated   : TLS_AES_256_GCM_SHA384 [OK]
    -> Cipher (AEAD) : AES_256_GCM            [OK]
    -> Hash          : SHA384                 [OK]
  RESULT: PASS

=== C1 - ML-KEM-1024 + ML-DSA-87  (192.0.2.10:12443) ===
  Protocol           : TLSv1.3    [OK]
  KEX expected       : MLKEM1024
  KEX negotiated     : MLKEM1024  [OK]
  Signature expected : ML-DSA-87
  Cert Public Key    : ML-DSA-87
  Cert Signature     : ML-DSA-87          [OK]
  CertVerify (online): mldsa87 / n/a (hash embedded)
  Suite expected     : TLS_AES_256_GCM_SHA384
  Suite negotiated   : TLS_AES_256_GCM_SHA384 [OK]
    -> Cipher (AEAD) : AES_256_GCM            [OK]
    -> Hash          : SHA384                 [OK]
  RESULT: PASS

=== C2 - NIST P-521 + ECDSA-SHA512  (192.0.2.10:9443) ===
  Protocol           : TLSv1.3    [OK]
  KEX expected       : secp521r1
  KEX negotiated     : secp521r1 (forced; handshake OK) [OK]
  Signature expected : ecdsa-with-SHA512
  Cert Public Key    : id-ecPublicKey
  Cert Signature     : ecdsa-with-SHA512  [OK]
  CertVerify (online): ecdsa_secp521r1_sha512 / SHA512
  Suite expected     : TLS_AES_256_GCM_SHA384
  Suite negotiated   : TLS_AES_256_GCM_SHA384 [OK]
    -> Cipher (AEAD) : AES_256_GCM            [OK]
    -> Hash          : SHA384                 [OK]
  RESULT: PASS

Summary: 5 PASS, 0 FAIL
[root@client tests-scripts]# 
```