from ipaddress import ip_address

p4 = bfrt.super_vlan_test.pipe

# This function can clear all the tables and later on other fixed objects
# once bfrt support is added.
def clear_all(verbose=True, batching=True):
    global p4
    global bfrt
    
    def _clear(table, verbose=False, batching=False):
        if verbose:
            print("Clearing table {:<40} ... ".
                  format(table['full_name']), end='', flush=True)
        try:    
            entries = table['node'].get(regex=True, print_ents=False)
            try:
                if batching:
                    bfrt.batch_begin()
                for entry in entries:
                    entry.remove()
            except Exception as e:
                print("Problem clearing table {}: {}".format(
                    table['name'], e.sts))
            finally:
                if batching:
                    bfrt.batch_end()
        except Exception as e:
            if e.sts == 6:
                if verbose:
                    print('(Empty) ', end='')
        finally:
            if verbose:
                print('Done')

        # Optionally reset the default action, but not all tables
        # have that
        try:
            table['node'].reset_default()
        except:
            pass
    
    # The order is important. We do want to clear from the top, i.e.
    # delete objects that use other objects, e.g. table entries use
    # selector groups and selector groups use action profile members
    

    # Clear Match Tables
    for table in p4.info(return_info=True, print_info=False):
        if table['type'] in ['MATCH_DIRECT', 'MATCH_INDIRECT_SELECTOR']:
            _clear(table, verbose=verbose, batching=batching)

    # Clear Selectors
    for table in p4.info(return_info=True, print_info=False):
        if table['type'] in ['SELECTOR']:
            _clear(table, verbose=verbose, batching=batching)
            
    # Clear Action Profiles
    for table in p4.info(return_info=True, print_info=False):
        if table['type'] in ['ACTION_PROFILE']:
            _clear(table, verbose=verbose, batching=batching)
    
#clear_all()

is_l2_switch = p4.Ingress.is_l2_switch
is_l2_switch.add_with_l2_switch(dst_addr=0x000002000002, port=11)
is_l2_switch.add_with_set_l3_flag(dst_addr=0xFFFFFFFFFFFF)

Port_to_srcvid = p4.Ingress.Port_to_srcvid
Port_to_srcvid.add_with_set_src_vid(ingress_port=0, subvid=2, supervid=10)

dstIP_to_dstvid = p4.Ingress.dstIP_to_dstvid
dstIP_to_dstvid.add_with_set_dst_vid(dst_addr=ip_address('192.168.1.1'), subvid=3, supervid=10)

src_supervid_to_mac = p4.Ingress.src_supervid_to_mac
src_supervid_to_mac.add_with_set_super_MAC(src_supervid=10, new_mac_switch=0x00000A00000A)

ipv4_host = p4.Ingress.ipv4_host
ipv4_host.add_with_set_nexthop(
    same_flag=True, dst_addr=ip_address('192.168.1.2'), nexthop=0)
ipv4_host.add_with_set_nexthop(
    same_flag=False, dst_addr=ip_address('192.168.1.1'), nexthop=100)

ipv4_lpm = p4.Ingress.ipv4_lpm
ipv4_lpm.add_with_set_nexthop(
    same_flag=True, dst_addr=ip_address('192.168.1.0'), dst_addr_p_length=24, nexthop=0)

nexthop = p4.Ingress.nexthop
nexthop.add_with_send(nexthop_id=0)
nexthop.add_with_l3_switch(nexthop_id=100,port=2, new_mac_da=0x000003000003,new_mac_sa=0x00000A00000A)

bfrt.complete_operations()

# Final programming
print("""
******************* PROGAMMING RESULTS *****************
""")
print ("Table is_l2_switch:")
is_l2_switch.dump(table=True)
print ("Table Port_to_srcvid:")
Port_to_srcvid.dump(table=True)
print ("Table dstIP_to_dstvid:")
dstIP_to_dstvid.dump(table=True)
print ("Table src_supervid_to_mac:")
src_supervid_to_mac.dump(table=True)
print ("Table ipv4_host:")
ipv4_host.dump(table=True)
print ("Table ipv4_lpm:")
ipv4_lpm.dump(table=True)
print ("Table nexthop:")
nexthop.dump(table=True)

                       
