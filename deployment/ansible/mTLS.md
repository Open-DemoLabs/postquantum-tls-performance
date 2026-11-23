# mTLS

Certificates to be used for mtls with P-384:

```bash
#!/bin/bash

openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-384 -nodes \
  -keyout client-ecdsa.key -out client-ecdsa.csr \
  -subj "/CN=client.lab.example.com" \
  -addext "subjectAltName=DNS:client.lab.example.com" 

openssl ca -batch -config /etc/pki/regular-A2-CA/openssl-regular-A2-ca.conf \
  -in client-ecdsa.csr -out client-ecdsa.crt

echo " "
echo "Checking the certificate:"
echo " "
echo " "

openssl ca -batch -config /etc/pki/regular-A2-CA/openssl-regular-A2-ca.conf -extensions mtls_client \
  -in client-ecdsa.csr -out client-ecdsa.crt
```

Certificates to be used for mtls with ML-DSA-65:

```bash
#!/bin/bash

openssl req -new -newkey ML-DSA-65 -nodes \
  -keyout client-mldsa.key -out client-mldsa.csr \
  -subj "/CN=client.lab.example.com" \
  -addext "subjectAltName=DNS:client.lab.example.com"

openssl ca -batch -config /etc/pki/regular-A1-CA/openssl-regular-A1-ca.conf \
  -in client-mldsla.csr -out client-mldsa.crt

echo " "
echo "Checking the certificate:"
echo " "
echo " "

openssl ca -batch -config /etc/pki/regular-A1-CA/openssl-regular-A1-ca.conf -extensions mtls_client \
  -in client-mldsa.csr -out client-mldsa.crt
```
