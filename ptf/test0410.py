
"""
Simple PTF test for super_vlan
"""

######### STANDARD MODULE IMPORTS ########
import unittest
import logging 
import grpc   
import pdb

######### PTF modules for BFRuntime Client Library APIs #######
import ptf
from ptf.testutils import *
from bfruntime_client_base_tests import BfRuntimeTest
import bfrt_grpc.bfruntime_pb2 as bfruntime_pb2
import bfrt_grpc.client as gc

########## Basic Initialization ############
class BaseProgramTest(BfRuntimeTest):
    # The setUp() method is used to prepare the test fixture. Typically
    # you would use it to establich connection to the gRPC Server
    #
    # You can also put the initial device configuration there. However,
    # if during this process an error is encountered, it will be considered
    # as a test error (meaning the test is incorrect),
    # rather than a test failure
    #
    # Here is the stuff we set up that is ready to use
    #  client_id
    #  p4_name
    #  bfrt_info
    #  dev
    #  dev_tgt
    #  allports
    #  tables    -- the list of tables
    #     Individual tables of the program with short names
    #     ipv4_host
    #     ipv4_lpm
    #     nexthop
    def setUp(self):
        self.client_id = 0
        self.p4_name = "super_vlan_test"
        self.dev      = 0
        self.dev_tgt  = gc.Target(self.dev, pipe_id=0xFFFF)
        
        print("\n")
        print("Test Setup")
        print("==========")

        BfRuntimeTest.setUp(self, self.client_id, self.p4_name)
        self.bfrt_info = self.interface.bfrt_info_get(self.p4_name)

        print("    Connected to Device: {}, Program: {}, ClientId: {}".format(
            self.dev, self.p4_name, self.client_id))

        # Since this class is not a test per se, we can use the setup method
        # for common setup. For example, we can have our tables and annotations
        # ready
        self.is_l2_switch = self.bfrt_info.table_get("Ingress.is_l2_switch")
        self.is_l2_switch.info.key_field_annotation_add(
            "hdr.ethernet.dst_addr", "mac")
        
        self.Trunk_switch = self.bfrt_info.table_get("Ingress.Trunk_switch")
        self.Trunk_switch.info.key_field_annotation_add(
            "hdr.ethernet.dst_addr", "mac")
        
        self.Port_to_srcvid = self.bfrt_info.table_get("Ingress.Port_to_srcvid")
        self.Port_to_srcvid.info.key_field_annotation_add(
            "ig_intr_md.ingress_port", "int")

        self.dstIP_to_dstvid = self.bfrt_info.table_get("Ingress.dstIP_to_dstvid")
        self.dstIP_to_dstvid.info.key_field_annotation_add(
            "meta.dst_ipv4", "ipv4")
        
        self.src_supervid_to_mac = self.bfrt_info.table_get("Ingress.src_supervid_to_mac")
        self.src_supervid_to_mac.info.data_field_annotation_add(
            "new_mac_switch", "Ingress.set_super_MAC", "mac")

        self.ipv4_host = self.bfrt_info.table_get("Ingress.ipv4_host")
        self.ipv4_host.info.key_field_annotation_add(
            "meta.dst_ipv4", "ipv4")

        self.ipv4_lpm = self.bfrt_info.table_get("Ingress.ipv4_lpm")
        self.ipv4_lpm.info.key_field_annotation_add(
            "meta.dst_ipv4", "ipv4")

        self.nexthop = self.bfrt_info.table_get("Ingress.nexthop")
        self.nexthop.info.data_field_annotation_add(
            "new_mac_da", "Ingress.l3_switch", "mac")
        self.nexthop.info.data_field_annotation_add(
            "new_mac_sa", "Ingress.l3_switch", "mac")

        self.tables = [ self.is_l2_switch, self.Trunk_switch, self.Port_to_srcvid, self.dstIP_to_dstvid, self.src_supervid_to_mac, self.ipv4_host, self.ipv4_lpm, self.nexthop ]

        # Create a list of all ports available on the device
        self.swports = []
        for (device, port, ifname) in ptf.config['interfaces']:
            self.swports.append(port)
        self.swports.sort()

        # Optional, but highly recommended
        self.cleanUp()

    # Use Cleanup Method to clear the tables before and after the test starts
    # (the latter is done as a part of tearDown()
    def cleanUp(self):
        print("\n")
        print("Table Cleanup:")
        print("==============")

        try:
            for t in self.tables:
                print("  Clearing Table {}".format(t.info.name_get()))
                keys = []
                for (d, k) in t.entry_get(self.dev_tgt):
                    if k is not None:
                        keys.append(k)
                t.entry_del(self.dev_tgt, keys)
                # Not all tables support default entry
                try:
                    t.default_entry_reset(self.dev_tgt)
                except:
                    pass
        except Exception as e:
            print("Error cleaning up: {}".format(e))

    # Use tearDown() method to return the DUT to the initial state by cleaning
    # all the configuration and clearing up the connection
    def tearDown(self):
        print("\n")
        print("Test TearDown:")
        print("==============")

        self.cleanUp()
        
        # Call the Parent tearDown
        BfRuntimeTest.tearDown(self)

#
# Individual tests can now be subclassed from BaseProgramTest
#

############################################################################
################# I N D I V I D U A L    T E S T S #########################
############################################################################

class HostSend(BaseProgramTest):
    def runTest(self):
        ingress_port = test_param_get("ingress_port",  0)
        ipv4_dst     = test_param_get("ipv4_dst",      "192.168.1.2")
        dst_addr     = test_param_get("dst_addr", "00:00:02:00:00:02")
        egress_port  = test_param_get("egress_port",   4)
        nexthop_id   = test_param_get("nexthop_id",  100)
        same_flag    = test_param_get("same_flag", True)
        
        print("\n")
        print("Test Run")
        print("========")

        #
        # Program an entry in nexthop: nexthop_id --> send(egress_port)
        #
        key_list = [
            self.nexthop.make_key([
                gc.KeyTuple('nexthop_id', nexthop_id)])
            ]

        data_list = [
            self.nexthop.make_data([], "Ingress.send")
            ]

        self.nexthop.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to nexthop: {} --> send()".format(
            nexthop_id))

        #
        # Program an entry in ipv4_host: ipv4_dst --> set_nexthop(nexthop_id)
        #

        key_list = [
            self.ipv4_host.make_key([
                gc.KeyTuple('same_flag', same_flag),
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.ipv4_host.make_data([
                gc.DataTuple('nexthop', nexthop_id)], "Ingress.set_nexthop")
            ]

        self.ipv4_host.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to ipv4_host: {},{} --> set_nexthop({})".
              format(same_flag, ipv4_dst, nexthop_id))
            
        #
        # Program an entry in is_l2_switch: dst_mac --> l2_switch
        #
        key_list = [
            self.is_l2_switch.make_key([
                gc.KeyTuple('hdr.ethernet.dst_addr', dst_addr)])
            ]

        data_list = [
            self.is_l2_switch.make_data([
                gc.DataTuple('port', egress_port)], "Ingress.l2_switch")
            ]

        self.is_l2_switch.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to is_l2_switch: {} --> l2_switch({})".
              format(dst_addr, egress_port))

        #
        # Send a test packet
        #
        print("  Sending packet with IPv4 DST ADDR={} into port {}"
              .format(ipv4_dst, ingress_port))
        pkt = simple_tcp_packet(eth_dst=dst_addr,
                                eth_src='00:00:02:00:00:01',
                                ip_dst=ipv4_dst,
                                ip_id=101,
                                ip_ttl=64,
                                ip_ihl=5)
        send_packet(self, ingress_port, pkt)

        #
        # Wait for the egress packet and verify it
        #
        print("  Expecting the packet to be forwarded to port {}"
              .format(egress_port))
        verify_packet(self, pkt, egress_port)
        print("  Packet received of port {}".format(egress_port))
        

class HostDrop(BaseProgramTest):
    def runTest(self):
        ingress_port = test_param_get("ingress_port",  0)
        ipv4_dst     = test_param_get("ipv4_dst",      "192.168.1.3")
        dst_addr     = test_param_get("dst_addr", "00:00:02:00:00:03")
        egress_port  = test_param_get("egress_port",   5)
        nexthop_id   = test_param_get("nexthop_id",  102)
        same_flag    = test_param_get("same_flag", True)

        print("\n")
        print("Test Run")
        print("========")
        
        #
        # Program an entry in nexthop: nexthop_id --> drop()
        #
        key_list = [
            self.nexthop.make_key([
                gc.KeyTuple('nexthop_id', nexthop_id)])
            ]

        data_list = [
            self.nexthop.make_data([], "Ingress.drop")
            ]

        self.nexthop.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to nexthop: {} --> drop()".
              format(nexthop_id))

        #
        # Program an entry in ipv4_host: ipv4_dst --> set_nexthop(nexthop_id)
        #
        key_list = [
            self.ipv4_host.make_key([
                gc.KeyTuple('same_flag', same_flag),
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.ipv4_host.make_data([
                gc.DataTuple('nexthop', nexthop_id)], "Ingress.set_nexthop")
            ]

        self.ipv4_host.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to ipv4_host: {},{} --> set_nexthop({})".
              format(same_flag, ipv4_dst, nexthop_id))

        #
        # Program an entry in is_l2_switch: dst_mac --> l2_switch
        #
        key_list = [
            self.is_l2_switch.make_key([
                gc.KeyTuple('hdr.ethernet.dst_addr', dst_addr)])
            ]

        data_list = [
            self.is_l2_switch.make_data([
                gc.DataTuple('port', egress_port)], "Ingress.l2_switch")
            ]

        self.is_l2_switch.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to is_l2_switch: {} --> l2_switch({})".
              format(dst_addr, egress_port))


        #
        # Send a test packet
        #
        print("  Sending packet with IPv4 DST ADDR={} into port {}"
              .format(ipv4_dst, ingress_port))
        pkt = simple_tcp_packet(eth_dst=dst_addr,
                                eth_src='00:00:02:00:00:01',
                                ip_dst=ipv4_dst,
                                ip_id=101,
                                ip_ttl=64,
                                ip_ihl=5)
        send_packet(self, ingress_port, pkt)
        print("  Expecting No packets anywhere")
        
        #
        # Wait to make sure no packet egresses anywhere. self.swports is the
        # list of all ports the test is using. It is set up in the setUp()
        # method of the parent class
        #
        verify_no_packet_any(self, pkt, self.swports)
        print("  No packets received")


class HostL3Switch(BaseProgramTest):
    def runTest(self):
        ingress_port = test_param_get("ingress_port",  0)
        ipv4_dst     = test_param_get("ipv4_dst",      "192.168.1.13")
        dst_addr     = test_param_get("dst_addr", "00:00:00:00:00:01")
        new_mac_da   = test_param_get("new_mac_da",    "00:00:03:00:00:03")
        new_mac_sa   = test_param_get("new_mac_sa",    "00:00:00:00:00:01")
        egress_port  = test_param_get("egress_port",   4)
        nexthop_id   = test_param_get("nexthop_id",  101)
        same_flag    = test_param_get("same_flag", False)
        src_supervid = test_param_get("src_supervid", 10)
        switch_mac   = test_param_get("switch_mac",    "00:00:00:00:00:01")
        dst_subvid   = 3
        dst_supervid = 10
        src_subvid   = 2
        src_supervid = 10

        print("\n")
        print("Test Run")
        print("========")

        #
        # Program an entry in nexthop:
        #       nexthop_id --> l3_switch(egress_port. new_mac_da, new_mac_da)
        #
        key_list = [
            self.nexthop.make_key([
                gc.KeyTuple('nexthop_id', nexthop_id)])
            ]

        data_list = [
            self.nexthop.make_data([gc.DataTuple('port', egress_port),
                                    gc.DataTuple('new_mac_da', new_mac_da),
                                    gc.DataTuple('new_mac_sa', new_mac_sa)],
                                   "Ingress.l3_switch")
            ]

        self.nexthop.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to nexthop: {} --> send({})".
              format(nexthop_id, egress_port))

        #
        # Program an entry in IPv4: ipv4_dst --> set_nexthop(nexthop_id)
        #
        key_list = [
            self.ipv4_host.make_key([
                gc.KeyTuple('same_flag', same_flag),
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.ipv4_host.make_data([
                gc.DataTuple('nexthop', nexthop_id)], "Ingress.set_nexthop")
            ]

        self.ipv4_host.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to ipv4_host: {},{} --> set_nexthop({})".
              format(same_flag, ipv4_dst, nexthop_id))

        #
        # Program an entry in src_supervid_to_mac: super_vid --> mac
        #
        key_list = [
            self.src_supervid_to_mac.make_key([
                gc.KeyTuple('src_supervid', src_supervid)])
            ]

        data_list = [
            self.src_supervid_to_mac.make_data([
                gc.DataTuple('new_mac_switch', switch_mac)], "Ingress.set_super_MAC")
            ]

        self.src_supervid_to_mac.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to src_supervid_to_mac: VLAN IF{} --> super_mac({})".
              format(src_supervid, switch_mac))
        
        #
        # Program an entry in dstIP_to_dstvid: dst_ip --> dst_vid
        #
        key_list = [
            self.dstIP_to_dstvid.make_key([
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.dstIP_to_dstvid.make_data([
                gc.DataTuple('subvid', dst_subvid),
                gc.DataTuple('supervid', dst_supervid)], "Ingress.set_dst_vid")
            ]

        self.dstIP_to_dstvid.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to dstIP_to_dstvid: dst_ip{} --> set_dst_vid({},{})".
              format(ipv4_dst, dst_subvid, dst_supervid))

        #
        # Program an entry in Port_to_srcvid: dst_ip --> dst_vid
        #
        key_list = [
            self.Port_to_srcvid.make_key([
                gc.KeyTuple('ig_intr_md.ingress_port', ingress_port)])
            ]

        data_list = [
            self.Port_to_srcvid.make_data([
                gc.DataTuple('subvid', src_subvid),
                gc.DataTuple('supervid', src_supervid)], "Ingress.set_src_vid")
            ]

        self.Port_to_srcvid.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to Port_to_srcvid: dst_ip{} --> set_src_vid({},{})".
              format(ingress_port, src_subvid, src_supervid))

        #
        # Program an entry in is_l2_switch: dst_mac --> l2_switch
        #
        key_list = [
            self.is_l2_switch.make_key([
                gc.KeyTuple('hdr.ethernet.dst_addr', dst_addr)])
            ]

        data_list = [
            self.is_l2_switch.make_data([], "Ingress.set_l3_flag")
            ]

        self.is_l2_switch.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to is_l2_switch: {} --> l3_switch()".
              format(dst_addr))

        #
        # Prepare the test packet and the expected packet
        send_pkt = simple_tcp_packet(eth_dst=dst_addr,
                                eth_src='00:00:02:00:00:01',
                                ip_dst=ipv4_dst,
                                ip_id=101,
                                ip_ttl=64,
                                ip_ihl=5)
        exp_pkt = copy.deepcopy(send_pkt)
        exp_pkt[Ether].dst = new_mac_da
        exp_pkt[Ether].src = new_mac_sa
        exp_pkt[IP].ttl   -= 1
              
        #
        # Send a test packet
        #
        print("  Sending packet with IPv4 DST ADDR={} into port {}"
              .format(ipv4_dst, ingress_port))
              
        send_packet(self, ingress_port, send_pkt)

        #
        # Wait for the egress packet and verify it
        #
        print("  Expecting the modified packet to be forwarded to port {}"
              .format(egress_port))
        
        verify_packet(self, exp_pkt, egress_port)
        print("  Modified Packet received of port {}"
              .format(egress_port))


class TrunkForward(BaseProgramTest):
    def runTest(self):
        ingress_port = test_param_get("ingress_port",  0)
        ipv4_dst     = test_param_get("ipv4_dst",      "192.168.2.1")
        dst_addr     = test_param_get("dst_addr", "01:00:02:00:00:01")
        egress_port  = test_param_get("egress_port",   5)

        print("\n")
        print("Test Run")
        print("========")
            
        #
        # Program an entry in Trunk_switch: dst_mac --> set_trunk_port
        #
        key_list = [
            self.Trunk_switch.make_key([
                gc.KeyTuple('hdr.ethernet.dst_addr', dst_addr)])
            ]

        data_list = [
            self.Trunk_switch.make_data([
                gc.DataTuple('port', egress_port)], "Ingress.set_trunk_port")
            ]

        self.Trunk_switch.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to Trunk_switch: {} --> set_trunk_port({})".
              format(dst_addr, egress_port))

        #
        # Send a test packet
        #
        print("  Sending packet with IPv4 DST ADDR={} into port {}"
              .format(ipv4_dst, ingress_port))
        pkt = simple_tcp_packet(eth_dst=dst_addr,
                                eth_src='00:00:02:00:00:01',
                                ip_dst=ipv4_dst,
                                ip_id=101,
                                ip_ttl=64,
                                ip_ihl=5)
        send_packet(self, ingress_port, pkt)

        #
        # Wait for the egress packet and verify it
        #
        print("  Expecting the packet to be forwarded to port {}"
              .format(egress_port))
        verify_packet(self, pkt, egress_port)
        print("  Packet received of port {}".format(egress_port))
        
class HostArp(BaseProgramTest):
    def runTest(self):
        ingress_port = test_param_get("ingress_port",  0)
        ipv4_dst     = test_param_get("ipv4_dst",      "192.168.1.13")
        #dst_addr     = test_param_get("dst_addr", "00:00:02:00:00:01")
        dst_addr   = test_param_get("dst_addr", "FF:FF:FF:FF:FF:FF")
        new_mac_da   = test_param_get("new_mac_da",    "00:00:03:00:00:03")
        new_mac_sa   = test_param_get("new_mac_sa",    "00:00:00:00:00:01")
        egress_port  = test_param_get("egress_port",   4)
        nexthop_id   = test_param_get("nexthop_id",  101)
        same_flag    = test_param_get("same_flag", False)
        src_supervid = test_param_get("src_supervid", 10)
        switch_mac   = test_param_get("switch_mac",    "00:00:00:00:00:01")
        dst_subvid   = 3
        dst_supervid = 10
        src_subvid   = 2
        src_supervid = 10
        print("\n")
        print("Test Run")
        print("========")
            
        #
        # Program an entry in nexthop:
        #       nexthop_id --> l3_switch(egress_port. new_mac_da, new_mac_da)
        #
        key_list = [
            self.nexthop.make_key([
                gc.KeyTuple('nexthop_id', nexthop_id)])
            ]

        data_list = [
            self.nexthop.make_data([gc.DataTuple('port', egress_port),
                                    gc.DataTuple('new_mac_da', new_mac_da),
                                    gc.DataTuple('new_mac_sa', new_mac_sa)],
                                   "Ingress.l3_switch")
            ]

        self.nexthop.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to nexthop: {} --> send({})".
              format(nexthop_id, egress_port))

        #
        # Program an entry in IPv4: ipv4_dst --> set_nexthop(nexthop_id)
        #
        key_list = [
            self.ipv4_host.make_key([
                gc.KeyTuple('same_flag', same_flag),
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.ipv4_host.make_data([
                gc.DataTuple('nexthop', nexthop_id)], "Ingress.set_nexthop")
            ]

        self.ipv4_host.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to ipv4_host: {},{} --> set_nexthop({})".
              format(same_flag, ipv4_dst, nexthop_id))

        #
        # Program an entry in src_supervid_to_mac: super_vid --> mac
        #
        key_list = [
            self.src_supervid_to_mac.make_key([
                gc.KeyTuple('src_supervid', src_supervid)])
            ]

        data_list = [
            self.src_supervid_to_mac.make_data([
                gc.DataTuple('new_mac_switch', switch_mac)], "Ingress.set_super_MAC")
            ]

        self.src_supervid_to_mac.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to src_supervid_to_mac: VLAN IF{} --> super_mac({})".
              format(src_supervid, switch_mac))
        
        #
        # Program an entry in dstIP_to_dstvid: dst_ip --> dst_vid
        #
        key_list = [
            self.dstIP_to_dstvid.make_key([
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.dstIP_to_dstvid.make_data([
                gc.DataTuple('subvid', dst_subvid),
                gc.DataTuple('supervid', dst_supervid)], "Ingress.set_dst_vid")
            ]

        self.dstIP_to_dstvid.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to dstIP_to_dstvid: dst_ip{} --> set_dst_vid({},{})".
              format(ipv4_dst, dst_subvid, dst_supervid))

        #
        # Program an entry in Port_to_srcvid: ingress_port --> src_vid
        #
        key_list = [
            self.Port_to_srcvid.make_key([
                gc.KeyTuple('ig_intr_md.ingress_port', ingress_port)])
            ]

        data_list = [
            self.Port_to_srcvid.make_data([
                gc.DataTuple('subvid', src_subvid),
                gc.DataTuple('supervid', src_supervid)], "Ingress.set_src_vid")
            ]

        self.Port_to_srcvid.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to Port_to_srcvid: dst_ip{} --> set_src_vid({},{})".
              format(ingress_port, src_subvid, src_supervid))

        #
        # Program an entry in is_l2_switch: dst_mac --> l2_switch
        #
        key_list = [
            self.is_l2_switch.make_key([
                gc.KeyTuple('hdr.ethernet.dst_addr', dst_addr)])
            ]

        data_list = [
            self.is_l2_switch.make_data([], "Ingress.set_l3_flag")
            ]

        self.is_l2_switch.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to is_l2_switch: {} --> l3_switch()".
              format(dst_addr))

 # Prepare the test packet and the expected packet
        
        pkt = simple_arp_packet(ip_tgt=ipv4_dst, pktlen=100)
        send_packet(self, ingress_port, pkt)

        arp_mac      = "00:00:00:00:00:01"
        exp_pkt = copy.deepcopy(pkt)
        exp_pkt[Ether].dst = pkt[ARP].hwsrc
        exp_pkt[Ether].src = arp_mac
        exp_pkt[ARP].op    = 2
        exp_pkt[ARP].hwsrc = arp_mac
        exp_pkt[ARP].psrc  = ipv4_dst
        exp_pkt[ARP].hwdst = pkt[ARP].hwsrc
        exp_pkt[ARP].pdst  = pkt[ARP].psrc
        print("Expecting ARP Reply for {} at port {}".
              format(ipv4_dst, ingress_port))
        verify_packet(self, exp_pkt, ingress_port)

        print("IP address {} is at {}".
              format(ipv4_dst, arp_mac))


class LpmARP(BaseProgramTest):   
    def runTest(self):
        ingress_port = test_param_get("ingress_port",  0)
        lpm_addr     = test_param_get("lpm_addr",      "192.168.1.0/24")
        ipv4_dst     = test_param_get("ipv4_dst",      "192.168.1.13")
        #dst_addr     = test_param_get("dst_addr", "00:00:02:00:00:01")
        dst_addr   = test_param_get("dst_addr", "FF:FF:FF:FF:FF:FF")
        new_mac_da   = test_param_get("new_mac_da",    "00:00:03:00:00:03")
        new_mac_sa   = test_param_get("new_mac_sa",    "00:00:00:00:00:01")
        egress_port  = test_param_get("egress_port",   4)
        nexthop_id   = test_param_get("nexthop_id",  101)
        same_flag    = test_param_get("same_flag", False)
        src_supervid = test_param_get("src_supervid", 10)
        switch_mac   = test_param_get("switch_mac",    "00:00:00:00:00:01")
        dst_subvid   = 3
        dst_supervid = 10
        src_subvid   = 2
        src_supervid = 10
        arp_mac      = "00:00:00:00:00:01"
        (lpm_ipv4, lpm_p_len) = lpm_addr.split("/")

        print("\n")
        print("Test Run")
        print("========")
            
        #
        # Program an entry in nexthop:
        #       nexthop_id --> l3_switch(egress_port. new_mac_da, new_mac_da)
        #
        key_list = [
            self.nexthop.make_key([
                gc.KeyTuple('nexthop_id', nexthop_id)])
            ]

        data_list = [
            self.nexthop.make_data([gc.DataTuple('port', egress_port),
                                    gc.DataTuple('new_mac_da', new_mac_da),
                                    gc.DataTuple('new_mac_sa', new_mac_sa)],
                                   "Ingress.l3_switch")
            ]

        self.nexthop.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to nexthop: {} --> send({})".
              format(nexthop_id, egress_port))

        #
        # Program an entry in ipv4_lpm:
        #          lpm_addr/prefix --> set_nexthop(nexthop_id)
        # Note the extra named argument (prefix_len) to gc.KeyTuple(). 
        #
        key_list = [
            self.ipv4_lpm.make_key([
                gc.KeyTuple('same_flag', same_flag),
                gc.KeyTuple('meta.dst_ipv4',
                            value=lpm_ipv4, prefix_len=int(lpm_p_len))])
            ]

        data_list = [
            self.ipv4_lpm.make_data([
                gc.DataTuple('nexthop', nexthop_id)], "Ingress.set_nexthop")
            ]

        self.ipv4_lpm.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to ipv4_lpm: {}/{} --> set_nexthop({})".format(
            lpm_ipv4, lpm_p_len, nexthop_id))


        #
        # Program an entry in src_supervid_to_mac: super_vid --> mac
        #
        key_list = [
            self.src_supervid_to_mac.make_key([
                gc.KeyTuple('src_supervid', src_supervid)])
            ]

        data_list = [
            self.src_supervid_to_mac.make_data([
                gc.DataTuple('new_mac_switch', switch_mac)], "Ingress.set_super_MAC")
            ]

        self.src_supervid_to_mac.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to src_supervid_to_mac: VLAN IF{} --> super_mac({})".
              format(src_supervid, switch_mac))
        
        #
        # Program an entry in dstIP_to_dstvid: dst_ip --> dst_vid
        #
        key_list = [
            self.dstIP_to_dstvid.make_key([
                gc.KeyTuple('meta.dst_ipv4', ipv4_dst)])
            ]

        data_list = [
            self.dstIP_to_dstvid.make_data([
                gc.DataTuple('subvid', dst_subvid),
                gc.DataTuple('supervid', dst_supervid)], "Ingress.set_dst_vid")
            ]

        self.dstIP_to_dstvid.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to dstIP_to_dstvid: dst_ip{} --> set_dst_vid({},{})".
              format(ipv4_dst, dst_subvid, dst_supervid))

        #
        # Program an entry in Port_to_srcvid: ingress_port --> src_vid
        #
        key_list = [
            self.Port_to_srcvid.make_key([
                gc.KeyTuple('ig_intr_md.ingress_port', ingress_port)])
            ]

        data_list = [
            self.Port_to_srcvid.make_data([
                gc.DataTuple('subvid', src_subvid),
                gc.DataTuple('supervid', src_supervid)], "Ingress.set_src_vid")
            ]

        self.Port_to_srcvid.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to Port_to_srcvid: dst_ip{} --> set_src_vid({},{})".
              format(ingress_port, src_subvid, src_supervid))

        #
        # Program an entry in is_l2_switch: dst_mac --> l2_switch
        #
        key_list = [
            self.is_l2_switch.make_key([
                gc.KeyTuple('hdr.ethernet.dst_addr', dst_addr)])
            ]

        data_list = [
            self.is_l2_switch.make_data([], "Ingress.set_l3_flag")
            ]

        self.is_l2_switch.entry_add(self.dev_tgt, key_list, data_list);
        print("  Added an entry to is_l2_switch: {} --> l3_switch()".
              format(dst_addr))

 # Prepare the test packet and the expected packet
        
        pkt = simple_arp_packet(ip_tgt=ipv4_dst, pktlen=100)
        send_packet(self, ingress_port, pkt)

        exp_pkt = copy.deepcopy(pkt)
        exp_pkt[Ether].dst = pkt[ARP].hwsrc
        exp_pkt[Ether].src = arp_mac
        exp_pkt[ARP].op    = 2
        exp_pkt[ARP].hwsrc = arp_mac
        exp_pkt[ARP].psrc  = ipv4_dst
        exp_pkt[ARP].hwdst = pkt[ARP].hwsrc
        exp_pkt[ARP].pdst  = pkt[ARP].psrc
        print("Expecting ARP Reply for {} at port {}".
              format(ipv4_dst, ingress_port))
        verify_packet(self, exp_pkt, ingress_port)

        print("IP address {} is at {}".
              format(ipv4_dst, arp_mac))