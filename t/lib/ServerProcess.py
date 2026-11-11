import http.client
import os
import signal
import socket
import subprocess
import sys
import time

import ServerStart


# A server of the dependency group "servers", started in a process of its own on a free port, for the tests in
# t/servers


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


# A port below the ephemeral ones, which no other socket takes before the server binds it
free_port = ServerStart.port


class Server:
    def __init__(self, dir, command, port=None, env=None):
        # The command is a list of the program and its arguments, which name the port as {port}, a free one unless it
        # is given, and env adds variables to its environment, or removes the ones that it gives as None
        self.port = port or free_port()
        args = [arg.format(port=self.port) for arg in command]
        # The warnings of the servers and their libraries are not ours, so they are neither errors nor shown there, as
        # in CI
        environ = {k: v for k, v in os.environ.items() if k not in ('PYTHONDEVMODE', 'PYTHONWARNINGS')} | {
            'PYTHONPATH': os.pathsep.join([dir, ROOT])
        }
        environ = {k: v for k, v in (environ | (env or {})).items() if v is not None}
        self.log = open(os.path.join(dir, 'server.log'), 'w+')
        self.process = subprocess.Popen(
            args,
            cwd=dir,
            env=environ,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                socket.create_connection(('127.0.0.1', self.port), 0.2).close()
                return
            except OSError:
                time.sleep(0.1)
        output = self.output()
        self.close()
        raise RuntimeError(f'the server did not start: {output}')

    def close(self):
        # Windows terminates only the launcher of a virtual environment, whose interpreter ends after it, with the log
        # still open, and Ctrl-Break stops every process of the group of the server, the interpreter before the launcher
        self.process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32' else signal.SIGTERM)
        try:
            self.process.wait(10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()

    def output(self):
        self.log.seek(0)
        return self.log.read()

    def request(self, method, path, body=None, headers=None, chunked=False, timeout=10):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        try:
            if chunked:
                # The request with the chunks of its body in one write, as a server that does not read them, as uWSGI
                # with --http-socket, closes the connection after its response, where the write of the next chunk of
                # http.client would fail with a broken pipe
                lines = [f'{method} {path} HTTP/1.1', f'Host: 127.0.0.1:{self.port}', 'Transfer-Encoding: chunked']
                lines += [f'{name}: {value}' for name, value in (headers or {}).items()]
                data = b''.join(b'%x\r\n%s\r\n' % (len(chunk), chunk) for chunk in body or () if chunk)
                conn.connect()
                conn.sock.sendall('\r\n'.join([*lines, '', '']).encode('latin-1') + data + b'0\r\n\r\n')
                res = http.client.HTTPResponse(conn.sock, method=method)
                res.begin()
            else:
                conn.request(method, path, body=body, headers=headers or {})
                res = conn.getresponse()
            return res.status, res.headers, res.read()
        finally:
            conn.close()

    def websocket(self, path):
        from websockets.sync.client import connect

        return connect(f'ws://127.0.0.1:{self.port}{path}', open_timeout=10, close_timeout=2)


if __name__ == '__main__':
    from Pyjo.Test import plan

    plan(skip_all='helper module, not a test')
