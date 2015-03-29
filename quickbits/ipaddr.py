#!/usr/bin/env python3
#  -*- coding: utf-8 -*-
__author__ = 'http://stackoverflow.com/users/844700/the-demz'
import socket
import fcntl
import struct


def get_ip_address(nicname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', nicname[:15].encode("UTF-8"))
    )[20:24])


def nic_info():
    """
    Return a list with tuples containing NIC and IPv4
    """
    nic = []
    for ix in socket.if_nameindex():
        name = ix[1]
        ip = get_ip_address(name)
        nic.append((name, ip))
    return nic


if __name__ == "__main__":
    print("\n".join(map(lambda x: "\t: ".join(x), nic_info())))
