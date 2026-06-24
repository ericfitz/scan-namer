"""Unit tests for scan_namer.py pure helpers."""
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

import scan_namer


class PreferIPv4Tests(unittest.TestCase):
    def setUp(self):
        self._orig = socket.getaddrinfo
        self.addCleanup(setattr, socket, "getaddrinfo", self._orig)

    def test_reorders_ipv4_before_ipv6(self):
        v6 = (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443, 0, 0))
        v4 = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443))
        # Use a plain function (not a Mock) so the idempotency guard's attribute
        # lookup behaves like it does against the real builtin getaddrinfo.
        socket.getaddrinfo = lambda *a, **k: [v6, v4]
        scan_namer.prefer_ipv4()
        ordered = socket.getaddrinfo("example.com", 443)
        self.assertEqual(ordered[0][0], socket.AF_INET)
        self.assertEqual(ordered[1][0], socket.AF_INET6)

    def test_is_idempotent(self):
        scan_namer.prefer_ipv4()
        once = socket.getaddrinfo
        scan_namer.prefer_ipv4()
        self.assertIs(socket.getaddrinfo, once)


if __name__ == "__main__":
    unittest.main()
