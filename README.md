# decorated_paho_mqtt

decorated_paho_mqtt is a wrapper to the Eclipse paho mqtt library ( https://pypi.org/project/paho-mqtt/ )

It is intended to be used with MQTTv5

# pack_topic

`pack_topic` takes an mqtt topic pattern, such as `a/+/c/#`, and additional parameters to fill in for the placeholders.

For each `+` placeholder, a string has to be passed; for a trailing `#`, a list/tuple has to be passed.

`pack_topic('a/+/c/#', "b", ("d","e"))` will return the topic `a/b/c/d/e`

Packing a topic with obviously invalid characters as parameters will raise an exception.

Known Bug: Packing a topic with an empty tuple as parameter for a `#` placeholder will not remove the trailing slash.
pack_topic and unpack_topic are not yet completely symmetrical.

# unpack_topic

`unpack_topic` takes an mqtt topic pattern, such as `a/+/c/#`, and an actual topic, such as `a/b/c/d/e`.

It will match the topic against the pattern, and for each placeholder in the pattern, yield the actual values.

`list(unpack_topic('a/+/c/#','a/b/c/d/e'))` will return `["b", ["d","e"]]`

# GenericMqttEndpoint

`GenericMqttEndpoint` allows to specify topic subscriptions in a declarative way using decorators.
It wraps an paho mqtt client.

You can use the subscribe_decorator on methods of derived classes to receive messages.

You can use the publish method to publish messages.

Example:
```py
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
```