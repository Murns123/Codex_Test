from conftest import itin

from fttracker.classify import classify


def test_route_a_qantas_via_per():
    assert classify(itin(3000)) == "A"


def test_route_b_qantas_via_syd():
    it = itin(3000, out_route=[("MEL", "SYD", "QF"), ("SYD", "JNB", "QF"), ("JNB", "ELS", "4Z")],
              back_route=[("ELS", "JNB", "4Z"), ("JNB", "SYD", "QF"), ("SYD", "MEL", "QF")])
    assert classify(it) == "B"


def test_route_c_saa_via_per():
    it = itin(3000, out_route=[("MEL", "PER", "QF"), ("PER", "JNB", "SA"), ("JNB", "ELS", "SA")],
              back_route=[("ELS", "JNB", "SA"), ("JNB", "PER", "SA"), ("PER", "MEL", "QF")])
    assert classify(it) == "C"


def test_route_d_gulf_carrier():
    it = itin(3000, out_route=[("MEL", "DXB", "EK"), ("DXB", "DUR", "EK"), ("DUR", "ELS", "4Z")],
              back_route=[("ELS", "JNB", "4Z"), ("JNB", "DOH", "QR"), ("DOH", "MEL", "QR")])
    assert classify(it) == "D"


def test_route_e_self_transfer_wins():
    assert classify(itin(3000, single=False)) == "E"


def test_mixed_directions_show_both():
    it = itin(3000, back_route=[("ELS", "JNB", "4Z"), ("JNB", "SYD", "QF"), ("SYD", "MEL", "QF")])
    assert classify(it) == "A/B"


def test_unknown_single_ticket_is_x_not_forced():
    it = itin(3000, out_route=[("MEL", "HKG", "CX"), ("HKG", "JNB", "CX"), ("JNB", "ELS", "4Z")],
              back_route=[("ELS", "JNB", "4Z"), ("JNB", "HKG", "CX"), ("HKG", "MEL", "CX")])
    assert classify(it) == "X"
