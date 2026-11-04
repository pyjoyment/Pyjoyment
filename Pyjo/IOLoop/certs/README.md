# The default certificates for TLS

The certificate and key that a TLS server of `Pyjo.IOLoop.Server` uses when
it is given none, as `lib/Mojo/IOLoop/resources` in Mojolicious, and a
certificate of a client that the same CA signs, for the client
authentication of TLS in the tests of the distributions that have Pyjoyment
installed, without a certificate of their own. They are not secret and are
meant for development only.

| Files                      | Certificate                                                 |
| -------------------------- | ----------------------------------------------------------- |
| `ca.crt`                   | The CA that signs the others, `Pyjoyment Test CA`           |
| `server.crt`, `server.key` | `localhost` and `127.0.0.1`, for a server                   |
| `client.crt`, `client.key` | `client`, for a client, which a server with the CA verifies |

The key of the CA is not in the repository, as whoever trusts `ca.crt` would
trust any certificate that the key signs, for any name. The maintainer keeps
it outside of the repository, in `$keep`, and signs a certificate added to the
set with it, with `sign` below in that directory; without it, all of them are
made again, with a new CA. They are RSA 2048 keys, valid for a hundred years,
made with OpenSSL 3 in a temporary directory, from the root of the
repository:

```sh
certs=$PWD/Pyjo/IOLoop/certs
keep=$HOME/.config/pyjoyment/certs/ioloop
cd "$(mktemp -d)"

openssl req -x509 -newkey rsa:2048 -nodes -days 36500 \
  -keyout ca.key -out ca.crt -subj '/O=Pyjoyment/CN=Pyjoyment Test CA' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign' \
  -addext 'subjectKeyIdentifier=hash'

sign() {
  name=$1 cn=$2 ext=$3
  openssl req -newkey rsa:2048 -nodes -keyout "$name.key" -out "$name.csr" -subj "/O=Pyjoyment/CN=$cn"
  printf "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n$ext\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n" > "$name.ext"
  openssl x509 -req -days 36500 -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "$name.crt" -extfile "$name.ext"
}

sign server localhost 'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1'
sign client client 'extendedKeyUsage=clientAuth'

openssl verify -CAfile ca.crt server.crt client.crt
```

Then copy the certificates and their keys into `Pyjo/IOLoop/certs`, readable
by everyone, keep the key of the CA, readable by its owner only, and delete
the temporary directory:

```sh
chmod 644 server.key client.key
cp ca.crt {server,client}.{crt,key} "$certs/"
mkdir -p "$keep" && install -m 600 ca.key "$keep/" && cp ca.crt ca.srl "$keep/"
cd "$certs" && rm -rf "$OLDPWD"
```
