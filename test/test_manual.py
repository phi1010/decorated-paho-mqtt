#pip install -i https://test.pypi.org/simple/ decorated-paho-mqtt==1.0.0
import json
from signal import pause
from icecream import ic
from decorated_paho_mqtt import GenericMqttEndpoint


class MyMqtt(GenericMqttEndpoint):

    # Using this decorator will automatically subscribe to the topic and provide the values as positional parameters
    # The paho parameters will be passed as named parameters.
    @GenericMqttEndpoint.subscribe_decorator("a/+/c/#", qos=2)
    def receive_something(self, b, d_e, *, client, userdata, message):
        assert b == "b"
        assert len(d_e) == 2
        assert d_e[0] == "d"
        assert d_e[1] == "e"

    def send_something(self, b, d, e):
        self.publish("a/+/c/#", (b, (d, e)), qos=2, retain=False, payload=json.dumps(None))

    def _on_log(self, client, userdata, level, buf):
        super(MyMqtt, self)._on_log(client, userdata, level, buf)
        ic(client, userdata, level, buf)


mqtt = MyMqtt(
    # Same parameters as paho's MqttClient()
    dict(transport="tcp"),
    # None or same parameters as paho's MqttClient.username_pw_set()
    dict(username="username", password="password"),
    # Same parameters as paho's MqttClient.connect_async()
    dict(host="127.0.0.1", port=1883, keepalive=10),
    # Whether to activate TLS
    False
)

# Non-Blocking, callbacks will return in another thread:
mqtt.connect()
pause()