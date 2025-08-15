import pytest

import decorated_paho_mqtt

TESTCASES_PASS = [
    ("a/b/c", [], "a/b/c"),
    ("+/b/c", ["x"], "x/b/c"),
    ("a/+/c", ["x"], "a/x/c"),
    ("a/b/+", ["x"], "a/b/x"),
    ("a/b/#", [["x", "y"]], "a/b/x/y"),
    ("+/+/#", ["0", "1", ["x", "y"]], "0/1/x/y"),
    ("+/+/#", ["", "", ["", ""]], "///"),
]
TESTCASES_PACK_FAIL = [
    ("a/+/c", []),
    ("a/+/c", ["+"]),
    ("a/+/c", ["#"]),
    ("+/b/c", ["x", "y"]),
    ("a/b/#", [[]]),
    ("a/b/#", [["+"]]),
    ("a/b/#", [["#"]]),
]
TESTCASES_UNPACK_FAIL = [
    ("a/+/c", "a/+/c"),
    ("a/+/c", "a/#/c"),
    ("a/+/c", "a/b/+"),
    ("a/+/c", "a/b/#"),
    ("a/b/#", "a/b/+"),
    ("a/b/#", "a/b/#"),
    ("a/b/#", "a/b/c/+"),
    ("a/b/#", "a/b/c/#"),
    ("a/b/#", "a/y/z"),
    ("a/b/+", "a/y/z"),
    ("a/b", "a/y"),
    ("a", "x"),
]


@pytest.mark.parametrize("pattern,args,packed", TESTCASES_PASS)
def test_pack(pattern, args, packed):
    expected = packed
    assert decorated_paho_mqtt.pack_topic(pattern, *args) == expected

@pytest.mark.parametrize("pattern,args", TESTCASES_PACK_FAIL)
def test_pack_fail(pattern, args):
    with pytest.raises(Exception) as e_info:
        print(list(decorated_paho_mqtt.pack_topic(pattern, *args)))

@pytest.mark.parametrize("pattern,topic", TESTCASES_PACK_FAIL)
def test_unpack_fail(pattern, topic):
    with pytest.raises(Exception) as e_info:
        print(list(decorated_paho_mqtt.unpack_topic(pattern, topic)))

@pytest.mark.parametrize("pattern,args,packed", TESTCASES_PASS)
def test_unpack(pattern, args, packed):
    expected = args
    assert list(decorated_paho_mqtt.unpack_topic(pattern, packed)) == expected
