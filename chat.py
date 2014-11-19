#!./env/bin/python

from json import loads
from tornado import autoreload
from tornado.options import define, options, parse_command_line
from tornado.web import Application, RequestHandler
from tornado.websocket import WebSocketHandler
import zmq
from zmq.eventloop import ioloop, zmqstream


def broadcaster():
    ctx = zmq.Context()
    s = ctx.socket(zmq.PUB)
    s.bind("tcp://127.0.0.1:{}".format(options.in_port))
    r = ctx.socket(zmq.PULL)
    r.bind("tcp://127.0.0.1:{}".format(options.out_port))
    r.set_hwm(10)
    def on_recv(messages):
        for message in messages:
            s.send(message)
    zmqstream.ZMQStream(r).on_recv(on_recv)


class IndexHandler(RequestHandler):
    def get(self):
        self.write("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>chat</title>
    <script>
    window.onload = function() {
        document.getElementById("chatbox").onsubmit = function(e) {
            e.preventDefault();
            msg = document.getElementById("message");
            ws.send(msg.value);
            msg.value = "";
        };
        var ws = new WebSocket("ws://"+location.host+"/events");
        ws.onmessage = function(message) {
            document.getElementById("messages").innerHTML += "<p>"+message.data+"</p>";
        };
        ws.onclose = function() {
            setTimeout(function() {
                window.location = window.location;
            }, 1000);
        };
    };
    </script>
</head>

<body>
    <form id="chatbox"><input id="message" placeholder="Say hi..."><input type="submit"></form>
    <ul id="messages"></ul>
</body>
</html>
        """)


class EventsHandler(WebSocketHandler):
    def on_recv(self, messages):
        for message in messages:
            self.write_message(loads(message.decode("utf-8")))

    def open(self):
        self.r = zmq.Context().socket(zmq.SUB)
        self.r.connect("tcp://127.0.0.1:{}".format(options.in_port))
        self.r.setsockopt_string(zmq.SUBSCRIBE, "")
        zmqstream.ZMQStream(self.r).on_recv(self.on_recv)

    def on_message(self, message):
        s = zmq.Context().socket(zmq.PUSH)
        s.connect("tcp://127.0.0.1:{}".format(options.out_port))
        s.send_json(message)

    def on_close(self):
        self.r.close(0)


if __name__ == "__main__":
    ioloop.install()
    
    define("port", default=5000)
    define("in_port", default=5555)
    define("out_port", default=5556)
    parse_command_line()

    print("Starting server on port {}".format(options.port))
    Application([
        (r"/", IndexHandler),
        (r"/events", EventsHandler),
    ]).listen(options.port)

    broadcaster()

    autoreload.start()
    ioloop.IOLoop.instance().start()
