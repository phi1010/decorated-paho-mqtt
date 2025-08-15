import logging
import os
import signal
import socket
import time
from contextlib import contextmanager
import json
import pytest
import decorated_paho_mqtt
from pathlib import Path
from subprocess import run, Popen

from decorated_paho_mqtt import GenericMqttEndpoint


@contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield new_dir
    finally:
        os.chdir(previous_dir)


@pytest.fixture()
def mqtt_server():
    print("Starting MQTT server")
    with pushd(Path(__file__).parent):
        process = Popen(["docker", "compose", "up", "mqtt"])
    print("Waiting for MQTT server to be available")
    start = time.time()
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("localhost", 8080))
            s.close()
            print("Connected to MQTT server on port 8080")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("localhost", 1883))
            s.close()
            print("Connected to MQTT server on port 1883")
            break
        except:
            if time.time() - start > 30:
                print("MQTT server did not start in time, terminating process")
                process.terminate()
                time.sleep(2)
                process.kill()
                with pushd(Path(__file__).parent):
                    run(["docker", "compose", "down"], check=True)
                raise Exception("MQTT server did not start in time")
            continue
    yield process
    print("Stopping MQTT server")
    process.terminate()
    time.sleep(2)
    process.kill()
    with pushd(Path(__file__).parent):
        run(["docker", "compose", "down"], check=True)


def test_mqtt_client(mqtt_server):
    received = set()

    class MyMqtt(GenericMqttEndpoint):
        def __init__(self, *args, **kwargs):
            self.b = "b"
            super(MyMqtt, self).__init__(*args, **kwargs)

        # Using this decorator will automatically subscribe to the topic and provide the values as positional parameters
        # The paho parameters will be passed as named parameters.
        @GenericMqttEndpoint.subscribe_decorator("a1/+/c/#", qos=2)
        def receive_something1(self, b, d_e, *, client, userdata, message):
            print("Received something with constant topic:", b, d_e)
            assert b == "b"
            assert len(d_e) == 2
            assert d_e[0] == "d"
            assert d_e[1] == "e"
            received.add("static")

        @GenericMqttEndpoint.subscribe_decorator(lambda self: f"a2/{self.b}/c/#", qos=2)
        def receive_something2(self, d_e, *, client, userdata, message):
            print("Received something with lambda topic:", d_e)
            assert len(d_e) == 2
            assert d_e[0] == "d"
            assert d_e[1] == "e"
            received.add("lambda")

        def send_something(self, b, d, e):
            self.publish("a1/+/c/#", b, (d, e), qos=2, retain=False, payload=json.dumps(None))
            self.publish("a2/+/c/#", b, (d, e), qos=2, retain=False, payload=json.dumps(None))

        def _on_log(self, client, userdata, level, buf):
            super(MyMqtt, self)._on_log(client, userdata, level, buf)
            print(client, userdata, level, buf)

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
    while not mqtt._mqttc.is_connected():
        time.sleep(0.1)
    print("Connected to MQTT server")
    mqtt.send_something("b", "d", "e")
    time.sleep(5)

    assert received == {"static", "lambda"}
