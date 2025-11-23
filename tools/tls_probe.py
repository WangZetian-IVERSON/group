import socket
import ssl

host = 'generativelanguage.googleapis.com'
port = 443

context = ssl.create_default_context()

print('Probing TLS handshake to', host)
try:
    with socket.create_connection((host, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            print('TLS handshake succeeded')
            print('Cipher:', ssock.cipher())
            print('Server cert subject:', cert.get('subject'))
except Exception as e:
    print('Exception during TLS probe:')
    import traceback
    traceback.print_exc()
