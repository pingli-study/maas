# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.tcpip``."""

__all__ = []

from io import BytesIO
from random import randint
import time

from maastesting.factory import factory
from maastesting.matchers import DocTestMatches
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.network import hex_str_to_bytes
from provisioningserver.utils.pcap import PCAP
from provisioningserver.utils.tcpip import (
    decode_ethernet_udp_packet,
    IPv4,
    PacketProcessingError,
    UDP,
)
from testtools import ExpectedException
from testtools.matchers import Equals


def make_ipv4_packet(
        total_length=None, version=None, ihl=None, payload=None,
        truncated=False):
    """Construct an IPv4 packet using the specified parameters.

    If the specified `vid` is not None, it is interpreted as an integer VID,
    and the appropriate Ethertype fields are adjusted.
    """
    if payload is None:
        payload = b''
    if total_length is None:
        total_length = 20 + len(payload)
    if version is None:
        version = 4
    if ihl is None:
        ihl = 5
    version__ihl = ((version << 4) | ihl).to_bytes(1, "big")

    ipv4_packet = (
        # Version, IHL
        version__ihl +
        # TOS
        hex_str_to_bytes('00') +
        # Total length in bytes
        total_length.to_bytes(2, "big") +
        # Identification
        hex_str_to_bytes('0000') +
        # Flags, fragment offset
        hex_str_to_bytes('0000') +
        # TTL
        hex_str_to_bytes('00') +
        # Protocol (just make it UDP for now)
        hex_str_to_bytes('11') +
        # Header checksum
        hex_str_to_bytes('0000') +
        # Source address
        hex_str_to_bytes('00000000') +
        # Destination address
        hex_str_to_bytes('00000000')
        # No options.
    )
    assert len(ipv4_packet) == 20, "Length was %d" % len(ipv4_packet)
    if truncated:
        return ipv4_packet[:19]
    ipv4_packet = ipv4_packet + payload
    return ipv4_packet


class TestIPv4(MAASTestCase):

    def test__parses_ipv4_packet(self):
        payload = factory.make_bytes(48)
        packet = make_ipv4_packet(payload=payload)
        ipv4 = IPv4(packet)
        self.assertThat(ipv4.is_valid(), Equals(True))
        self.assertThat(ipv4.version, Equals(4))
        self.assertThat(ipv4.ihl, Equals(20))
        self.assertThat(ipv4.payload, Equals(payload))

    def test__fails_for_non_ipv4_packet(self):
        payload = factory.make_bytes(48)
        packet = make_ipv4_packet(payload=payload, version=5)
        ipv4 = IPv4(packet)
        self.assertThat(ipv4.is_valid(), Equals(False))
        self.assertThat(
            ipv4.invalid_reason, DocTestMatches("Invalid version..."))

    def test__fails_for_bad_ihl(self):
        payload = factory.make_bytes(48)
        packet = make_ipv4_packet(payload=payload, ihl=0)
        ipv4 = IPv4(packet)
        self.assertThat(ipv4.is_valid(), Equals(False))
        self.assertThat(
            ipv4.invalid_reason, DocTestMatches("Invalid IPv4 IHL..."))

    def test__fails_for_truncated_packet(self):
        packet = make_ipv4_packet(truncated=True)
        ipv4 = IPv4(packet)
        self.assertThat(ipv4.is_valid(), Equals(False))
        self.assertThat(
            ipv4.invalid_reason, DocTestMatches("Truncated..."))


def make_udp_packet(
        total_length=None, payload=None, truncated_header=False,
        truncated_payload=False):
    """Construct an IPv4 packet using the specified parameters.

    If the specified `vid` is not None, it is interpreted as an integer VID,
    and the appropriate Ethertype fields are adjusted.
    """
    if payload is None:
        payload = b''
    if total_length is None:
        total_length = 8 + len(payload)

    udp_packet = (
        # Source port
        hex_str_to_bytes('0000') +
        # Destination port
        hex_str_to_bytes('0000') +
        # UDP header length + payload length
        total_length.to_bytes(2, "big") +
        # Checksum
        hex_str_to_bytes('0000')
    )
    assert len(udp_packet) == 8, "Length was %d" % len(udp_packet)
    if truncated_header:
        return udp_packet[:7]
    udp_packet = udp_packet + payload
    if truncated_payload:
        return udp_packet[:-1]
    return udp_packet


class TestUDP(MAASTestCase):

    def test__parses_udp_packet(self):
        payload = factory.make_bytes(48)
        packet = make_udp_packet(payload=payload)
        udp = UDP(packet)
        self.assertThat(udp.is_valid(), Equals(True))
        self.assertThat(udp.payload, Equals(payload))

    def test__fails_for_truncated_udp_header(self):
        packet = make_udp_packet(truncated_header=True)
        udp = UDP(packet)
        self.assertThat(udp.is_valid(), Equals(False))
        self.assertThat(
            udp.invalid_reason, DocTestMatches("Truncated UDP header..."))

    def test__fails_for_bad_length(self):
        payload = factory.make_bytes(48)
        packet = make_udp_packet(total_length=0, payload=payload)
        udp = UDP(packet)
        self.assertThat(udp.is_valid(), Equals(False))
        self.assertThat(
            udp.invalid_reason, DocTestMatches(
                "Invalid UDP packet; got length..."))

    def test__fails_for_truncated_payload(self):
        payload = factory.make_bytes(48)
        packet = make_udp_packet(truncated_payload=True, payload=payload)
        udp = UDP(packet)
        self.assertThat(udp.is_valid(), Equals(False))
        self.assertThat(
            udp.invalid_reason, DocTestMatches("UDP packet truncated..."))


GOOD_ETHERNET_UDP_PCAP = (
    b'\xd4\xc3\xb2\xa1\x02\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00@\x00\x00\x01\x00\x00\x00v\xe19Y\xadF\x08\x00^\x00\x00\x00^\x00\x00'
    b'\x00\x01\x00^\x00\x00v\x00\x16>\x91zz\x08\x00E\x00\x00P\xe2E@\x00\x01'
    b'\x11\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xda\xc2\x14x\x00<h(4\x00\x00\x00'
    b'\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a7a\x00\x00')

GOOD_ETHERNET_UDP_PACKET = (
    b'\x01\x00^\x00\x00v\x00\x16>\x91zz\x08\x00E\x00\x00P\xe2E@\x00\x01'
    b'\x11\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xda\xc2\x14x\x00<h(4\x00\x00\x00'
    b'\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a7a\x00\x00')

TRUNCATED_UDP_PAYLOAD = (
    b'\x01\x00^\x00\x00v\x00\x16>\x91zz\x08\x00E\x00\x00P\xe2E@\x00\x01'
    b'\x11\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xda\xc2\x14x\x00<h(4\x00\x00\x00'
    b'\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a7a\x00')

BAD_ETHERTYPE = (
    b'\x01\x00^\x00\x00v\x00\x16>\x91zz\x07\xFFE\x00\x00P\xe2E@\x00\x01'
    b'\x11\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xda\xc2\x14x\x00<h(4\x00\x00\x00'
    b'\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a7a\x00\x00')

BAD_IPV4_UDP_HEADER = (
    b'\x01\x00^\x00\x00v\x00\x16>\x91zz\x08\x00E\x00\x00P\xe2E@\x00\x01'
    b'\x11\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xdb')

NOT_UDP_PROTOCOL = (
    b'\x01\x00^\x00\x00v\x00\x16>\x91zz\x08\x00E\x00\x00P\xe2E@\x00\x01'
    b'\x12\xe0\xce\xac\x10*\x02\xe0\x00\x00v\xda\xc2\x14x\x00<h(4\x00\x00\x00'
    b'\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a7a\x00\x00')

TRUNCATED_ETHERNET_HEADER = b'\x01\x00^\x00\x00v'

EXPECTED_PCAP_TIME = 1496965494

EXPECTED_PAYLOAD = (
    b'4\x00\x00\x00\x02uuid\x00%\x00\x00\x0078d1a4f0-4ca4-11e7-b2bb-00163e917a'
    b'7a\x00\x00'
)


class TestDecodeEthernetUDPPacket(MAASTestCase):

    def test__gets_time_from_pcap_header(self):
        pcap_file = BytesIO(GOOD_ETHERNET_UDP_PCAP)
        pcap = PCAP(pcap_file)
        for header, packet_bytes in pcap:
            packet = decode_ethernet_udp_packet(packet_bytes, header)
            self.expectThat(packet.timestamp, Equals(EXPECTED_PCAP_TIME))
            self.expectThat(packet.payload, Equals(EXPECTED_PAYLOAD))

    def test__decodes_from_bytes(self):
        expected_time = EXPECTED_PCAP_TIME + randint(1, 100)
        self.patch(time, "time").return_value = expected_time
        packet = decode_ethernet_udp_packet(GOOD_ETHERNET_UDP_PACKET)
        self.expectThat(packet.timestamp, Equals(expected_time))
        self.expectThat(packet.payload, Equals(EXPECTED_PAYLOAD))

    def test__fails_for_bad_ethertype(self):
        self.patch(time, "time").return_value = EXPECTED_PCAP_TIME
        with ExpectedException(PacketProcessingError, '.*Invalid ethertype.*'):
            decode_ethernet_udp_packet(BAD_ETHERTYPE)

    def test__fails_for_bad_ethernet_packet(self):
        self.patch(time, "time").return_value = EXPECTED_PCAP_TIME
        with ExpectedException(PacketProcessingError, '.*Invalid Ethernet.*'):
            decode_ethernet_udp_packet(TRUNCATED_ETHERNET_HEADER)

    def test__fails_for_bad_udp_header(self):
        self.patch(time, "time").return_value = EXPECTED_PCAP_TIME
        with ExpectedException(PacketProcessingError, '.*Truncated UDP.*'):
            decode_ethernet_udp_packet(BAD_IPV4_UDP_HEADER)

    def test__fails_if_not_udp_protocol(self):
        self.patch(time, "time").return_value = EXPECTED_PCAP_TIME
        with ExpectedException(PacketProcessingError, '.*Invalid protocol*'):
            decode_ethernet_udp_packet(NOT_UDP_PROTOCOL)

    def test__fails_if_udp_packet_truncated(self):
        self.patch(time, "time").return_value = EXPECTED_PCAP_TIME
        with ExpectedException(PacketProcessingError, '.*UDP packet trunc.*'):
            decode_ethernet_udp_packet(TRUNCATED_UDP_PAYLOAD)