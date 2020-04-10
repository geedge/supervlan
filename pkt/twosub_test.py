#!/usr/bin/python

import os
import sys

if os.getuid() !=0:
    print """
ERROR: This script requires root privileges. 
       Use 'sudo' to run it.
"""
    quit()

from scapy.all import *

try:
    ip_dst = sys.argv[1]
except:
    ip_dst = "192.168.1.2"

print "Sending IP packet to", ip_dst
p = (Ether(dst="FF:FF:FF:FF:FF:FF", src="00:00:01:00:00:01")/
    ARP(psrc='192.168.1.13',pdst='192.168.1.1'))
sendp(p, iface="veth3") 
