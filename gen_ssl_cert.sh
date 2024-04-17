#!/bin/bash -x
rm -rf certificates
mkdir certificates
cd certificates || exit 1

# create CA key
openssl genrsa 2048 > ca-key.pem

# create CA cert
openssl req -new -x509 -nodes -days 15 \
   -key ca-key.pem \
   -out ca-cert.pem \
   -subj "/C=IN/ST=KA/L=BLR/O=PESU/OU=CS/CN=pesuacademy.CA.com"

# create server key
openssl req -newkey rsa:2048 -nodes -days 15 \
   -keyout server-key.pem \
   -out server-req.pem \
   -subj "/C=IN/ST=KA/L=BLR/O=PESU/OU=CS/CN=pesuacademy.server.com"

# create server cert and sign from CA
openssl x509 -req -days 15 -set_serial 01 \
   -in server-req.pem \
   -out server-cert.pem \
   -CA ca-cert.pem \
   -CAkey ca-key.pem

# create client key
openssl req -newkey rsa:2048 -nodes -days 15 \
   -keyout client-key.pem \
   -out client-req.pem \
   -subj "/C=IN/ST=KA/L=BLR/O=PESU/OU=CS/CN=pesuacademy.client.com"

# create c;ient cert and sign from CA
openssl x509 -req -days 15 -set_serial 01 \
   -in client-req.pem \
   -out client-cert.pem \
   -CA ca-cert.pem \
   -CAkey ca-key.pem

# verify server CA chain
openssl verify -CAfile ca-cert.pem \
   ca-cert.pem \
   server-cert.pem

# cerify client cert chain
openssl verify -verbose -CAfile ca-cert.pem \
   ca-cert.pem \
   client-cert.pem
