from functools import wraps
from logging import getLogger

# Read the docs at https://github.com/eclipse/paho.mqtt.python
#  because eclipse.org has outdated information, which does not include MQTTv5
from paho.mqtt.client import Client as MqttClient, MQTTMessage, MQTTv5, MQTT_CLEAN_START_FIRST_ONLY
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCodes
from paho.mqtt.subscribeoptions import SubscribeOptions


log = getLogger(__name__)


class GenericMqttEndpoint:

    def __init__(self, client_kwargs: dict, password_auth: dict, server_kwargs: dict, tls: bool):
        """

        :param client_kwargs: See https://github.com/eclipse/paho.mqtt.python/blob/9c22a9c297c0cdc4e1aac13aa19073e09a822961/src/paho/mqtt/client.py#L517
        :param password_auth: See https://github.com/eclipse/paho.mqtt.python/blob/9c22a9c297c0cdc4e1aac13aa19073e09a822961/src/paho/mqtt/client.py#L1318
        :param server_kwargs: See https://github.com/eclipse/paho.mqtt.python/blob/9c22a9c297c0cdc4e1aac13aa19073e09a822961/src/paho/mqtt/client.py#L913
        :param tls: If true, enables TLS with https://github.com/eclipse/paho.mqtt.python/blob/9c22a9c297c0cdc4e1aac13aa19073e09a822961/src/paho/mqtt/client.py#L765
        """
        self.mqtt_client_kwargs = client_kwargs
        # Some features and parameters depend on this.
        self.mqtt_client_kwargs.update(protocol=MQTTv5)
        self.mqtt_tls = tls
        self.mqtt_password_auth = password_auth
        self.mqtt_server_kwargs = server_kwargs
        # This is specific to MQTTv5 (MQTTv311 has clean_session in the client_kwargs instead)
        self.mqtt_server_kwargs.update(clean_start=MQTT_CLEAN_START_FIRST_ONLY)

        self._mqttc = MqttClient(**self.mqtt_client_kwargs)

        if self.mqtt_tls:
            self._mqttc.tls_set()

        if self.mqtt_password_auth:
            self._mqttc.username_pw_set(**self.mqtt_password_auth)

        self._mqttc.on_connect = self._on_connect
        self._mqttc.on_disconnect = self._on_disconnect
        self._mqttc.on_message = self._on_message
        self._mqttc.on_log = self._on_log

        self._managed_subscriptions = dict()
        """
        This dictionary maps subscription topics to subscription options
        """

        for attribute in self.__class__.__dict__.values():
            if hasattr(attribute, _SUBSCRIBE_DECORATOR_NAME):
                decorated_function = attribute
                topic_gen, kwargs = getattr(decorated_function, _SUBSCRIBE_DECORATOR_NAME)
                if callable(topic_gen):
                    topic_pattern = topic_gen(self)
                elif isinstance(topic_gen, str):
                    topic_pattern = topic_gen
                else:
                    raise TypeError(f"The topic in subscribe_generator must be callable or a str, got {repr(topic_gen)}")

                if topic_pattern in self._managed_subscriptions:
                    raise Exception(
                        "A client cannot subscribe to an identical topic filter multiple times!")
                else:
                    self._managed_subscriptions[topic_pattern] = kwargs

                # This function introduces a scope,
                #  to avoid a changing decorated_function variable
                #  cause changing behaviour of call_decorated_function
                def create_caller(decorated_function, topic_pattern):
                    # the decorated_function has not yet a self object; thus we need this wrapper
                    @wraps(decorated_function)
                    def call_decorated_function(client, userdata, message):
                        variables = unpack_topic(topic_pattern, message.topic)
                        return decorated_function(self, client=client, userdata=userdata, message=message, *variables)
                    #print(f"Returing {call_decorated_function} for {decorated_function} with topic {topic_pattern} and kwargs {kwargs}")
                    return call_decorated_function

                # this is done only once, not on every reconnect / resubscribe.
                caller = create_caller(decorated_function, topic_pattern)
                print(f"Subscribing {caller} to {topic_pattern} with {kwargs}")
                self._mqttc.message_callback_add(topic_pattern, caller)

    def connect(self):
        # currently, this will retry first connects, we don't need bettermqtt
        self._mqttc.connect_async(**self.mqtt_server_kwargs)
        self._mqttc.loop_start()

    def _on_connect(self, client, userdata, flags, rc: ReasonCodes, properties: Properties = None):
        if flags['session present'] == 0:
            # This is a new session, and we need to resubscribe
            self._subscribe()
        elif flags['session present'] == 1:
            pass
        else:
            raise Exception("Unknown Session Present Flag")

    def _subscribe(self):
        # Edge case: This may fail if we disconnect when not subscribed to all channels; there seems to a case where
        #  subscribe() returns an error code that we currently do handle.
        #  With some luck, the subscription stays in the packet queue.

        # Other defaults are sane, we don't need Subscription Options

        # However, if our session expires (after long-lasting conection loss),
        #  we will unexpectedly re-receive all retained messages
        #  which is not bad, if they are idempotent

        # We MUST NOT add message callbacks here, otherwise, they may be added twice upon reconnect after session expiry
        for topic_filter, kwargs in self._managed_subscriptions.items():
            #print(topic_filter, kwargs)
            self._mqttc.subscribe(topic=topic_filter, **kwargs)

    def _on_disconnect(self, client, userdata, rc: ReasonCodes, properties: Properties = None):
        # Exceptions here seem to disrupt the automatic reconnect
        # Connection loss can be tested with:
        # sudo tc qdisc add dev lo root netem loss 100%
        # sudo tc qdisc del dev lo root
        pass

    def _on_message(self, client, userdata, message: MQTTMessage):
        message_dict = {attr: getattr(message, attr) for attr in dir(message) if not attr.startswith("_")}
        message_properties: Properties = message.properties
        message_properties_dict = {attr: getattr(message_properties, attr) for attr in dir(message_properties) if not attr.startswith("_")}


    def _on_log(self, client, userdata, level, buf):
        log.log(level, buf, extra=dict(userdata=userdata))


    @staticmethod
    def subscribe_decorator(topic, **kwargs):
        """
        Subscribes to topic and calls the decorated method when a matching message is received.
        This must be the outermost decorator (except for other similar nop-decorators)

        If topic is function, it is called with the GenericMqttEndpoint instance as argument to produce the topic.
        This is done in GenericMqttEndpoint.__init__.
        example: @subscribe_decorator(lambda self: f"door/{self.id}/+")

        Avoid overlapping subscriptions or handle duplicates.
        Uses the same kwargs as paho.mqtt.client.Client.subscribe()
        Try qos=2 or options=SubscriptionOptions()

        Your function should have the signature func(var1, var2, vars, *, client,userdata,message)
        with a positional variable for each + or # in the pattern
        """

        def _subscribe_decorator(func):
            setattr(func, _SUBSCRIBE_DECORATOR_NAME, (topic, kwargs))
            # no @wraps
            return func

        return _subscribe_decorator

    def publish(self, topic_pattern, *topic_data, **kwargs):
        """
        :param topic_pattern: A topic pattern, e.g. a/+/c/#
        :param topic_data: some elements matching the pattern, e.g. "b", ("d", "e")
        :param kwargs: Passed to Client.publish(self, topic, payload=None, qos=0, retain=False, properties=None)
        :return:
        """
        topic = pack_topic(topic_pattern, *topic_data)
        return self._mqttc.publish(topic, **kwargs)


_SUBSCRIBE_DECORATOR_NAME = name = __name__ + "." + GenericMqttEndpoint.subscribe_decorator.__qualname__

FORBIDDEN_CHARS = "/+#"


def pack_topic(pattern: str, *data):
    data = list(data)
    while "+" in pattern:
        if not data:
            raise Exception("Placeholder with no value to fill in")
        element = data.pop(0)
        check_data_is_sane(element)
        pattern = pattern.replace("+", element, 1)
    while "#" in pattern:
        if not data:
            raise Exception("Placeholder with no value to fill in")
        remainder = data.pop(0)
        if isinstance(remainder, str):
            raise Exception("You should provide a list or a tuple to replace a '#', not a string.")
        elements = list(remainder)
        for element in elements:
            check_data_is_sane(element)
        if len(elements) == 0:
            raise Exception("You should provide a non-empty list or tuple to replace a '#'.")
        pattern = pattern.replace("#", "/".join(elements), 1)
    if data:
        raise Exception("Unused placeholders are present")
    return pattern


def check_data_is_sane(element):
    for FORBIDDEN_CHAR in FORBIDDEN_CHARS:
        if FORBIDDEN_CHAR in element:
            raise Exception(f"Cannot fill in data containing a '{FORBIDDEN_CHAR}'")


def unpack_topic(pattern, topic):
    """
    returns one string for each "+", followed by a list of strings when a trailing "#" is present
    """
    pattern_parts = iter(pattern.split("/"))
    topic_parts = iter(topic.split("/"))
    while True:
        try:
            cur_pattern = next(pattern_parts)
        except StopIteration:
            try:
                cur_topic = next(topic_parts)
                raise Exception("The topic to be matched is longer than the pattern without an # suffix. "
                                "The first unmatched part is {!r}".format(cur_topic))
            except StopIteration:
                # no more elements in both sequences.
                return
        if cur_pattern == "#":
            yield list(topic_parts)
            try:
                cur_pattern = next(pattern_parts)
                raise Exception("The pattern has a component after a #: {!r}".format(cur_pattern))
            except StopIteration:
                # topic has been exhausted by list() enumeration, and pattern is empty, too.
                return
        else:
            try:
                cur_topic = next(topic_parts)
            except StopIteration:
                raise Exception("The topic lacks a component to match a non-#-component in the pattern.")
            else:
                if cur_pattern == "+":
                    yield cur_topic
                elif "+" in cur_pattern:
                    raise Exception(
                        "The single-level wildcard can be used at any level in the Topic Filter, including first and last levels. Where it is used, it MUST occupy an entire level of the filter.")
                elif "#" in cur_pattern:
                    raise Exception(
                        "The multi-level wildcard character MUST be specified either on its own or following a topic level separator. In either case it MUST be the last character specified in the Topic Filter.")
                elif cur_pattern != cur_topic:
                    raise Exception(
                        "The pattern {!r} is no wildcard, and the topic {!r} differs.".format(cur_pattern, cur_topic))
                else:  # pattern == topic and neither contain a # or +
                    # we do not yield return constant non-wildcards.
                    continue
