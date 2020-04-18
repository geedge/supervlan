/* -*- P4_16 -*- */

#include <core.p4>
#include <tna.p4>

/*************************************************************************
 ************* C O N S T A N T S    A N D   T Y P E S  *******************
*************************************************************************/

/* Header Stuff */
enum bit<16> ether_type_t {
    TPID = 0x8100,
    IPV4 = 0x0800,
    ARP  = 0x0806,
    IPV6 = 0x86DD,
    MPLS = 0x8847
}

enum bit<8> ip_protocol_t {
    ICMP = 1,
    IGMP = 2,
    TCP  = 6,
    UDP  = 17
}

enum bit<16> arp_opcode_t {
    REQUEST = 1,
    REPLY   = 2
}


enum bit<8> icmp_type_t {
    ECHO_REPLY   = 0,
    ECHO_REQUEST = 8
}

typedef bit<48> mac_addr_t;
typedef bit<32> ipv4_addr_t;

/* Metadata and Table Stuff */
const int IPV4_HOST_SIZE = 65536;
const int IPV4_LPM_SIZE  = 12288;

#define NEXTHOP_ID_WIDTH 14
#define SUBVLAN_ID_WIDTH 12
#define SUPERVLAN_ID_WIDTH 8
typedef bit<NEXTHOP_ID_WIDTH> nexthop_id_t;
const int NEXTHOP_SIZE = 1 << NEXTHOP_ID_WIDTH;
typedef bit<SUBVLAN_ID_WIDTH> subvlan_id_t;
typedef bit<SUPERVLAN_ID_WIDTH> supervlan_id_t;
const int VLAN_SIZE = 512;

/*************************************************************************
 ***********************  H E A D E R S  *********************************
 *************************************************************************/
/*  Define all the headers the program will recognize             */
/*  The actual sets of headers processed by each gress can differ */

/* Standard ethernet header */
header ethernet_h {
    mac_addr_t    dst_addr;
    mac_addr_t    src_addr;
    ether_type_t  ether_type;
}

header vlan_tag_h {
    bit<16>  tpid;
    bit<3>        pcp;
    bit<1>        cfi;
    bit<12>       vid;
    ether_type_t  ether_type;
}

header ipv4_h {
    bit<4>          version;
    bit<4>          ihl;
    bit<8>          diffserv;
    bit<16>         total_len;
    bit<16>         identification;
    bit<3>          flags;
    bit<13>         frag_offset;
    bit<8>          ttl;
    ip_protocol_t   protocol;
    bit<16>         hdr_checksum;
    ipv4_addr_t     src_addr;
    ipv4_addr_t     dst_addr;
}

header ipv4_options_h {
    varbit<320> data;
}

header icmp_h {
    icmp_type_t msg_type;
    bit<8>      msg_code;
    bit<16>     checksum;
}

header arp_h {
    bit<16>       hw_type;
    ether_type_t  proto_type;
    bit<8>        hw_addr_len;
    bit<8>        proto_addr_len;
    arp_opcode_t  opcode;
} 

header arp_ipv4_h {
    mac_addr_t   src_hw_addr;
    ipv4_addr_t  src_proto_addr;
    mac_addr_t   dst_hw_addr;
    ipv4_addr_t  dst_proto_addr;
}

typedef bit<4> header_type_t; /* These fields can be coombined into one      */
typedef bit<4> header_info_t; /* 8-bit field as well. Exercise for the brave */
const header_type_t HEADER_TYPE_BRIDGE         = 0xB;

#define INTERNAL_HEADER         \
    header_type_t header_type;  \
    header_info_t header_info
    
header inthdr_h {
    INTERNAL_HEADER;
}

/*************************************************************************
 **************  I N G R E S S   P R O C E S S I N G   *******************
 *************************************************************************/
 
    /***********************  H E A D E R S  ************************/

header bridge_h {
    INTERNAL_HEADER;
    
    bit<7>    pad0;
    PortId_t  ingress_port;

    bit<3>        pcp;
    bit<1>        cfi;
    bit<12>       vid;
}

struct my_ingress_headers_t {
    bridge_h     bridge;

    ethernet_h         ethernet;
    vlan_tag_h[2]      vlan_tag;
    arp_h              arp;
    arp_ipv4_h         arp_ipv4;
    ipv4_h             ipv4;
    icmp_h             icmp;
}

    /******  G L O B A L   I N G R E S S   M E T A D A T A  *********/

struct my_ingress_metadata_t {
    bit<3>        pcp;
    bit<1>        cfi;
    bit<12>       vid;
    PortId_t ingress_port;

    ipv4_addr_t   dst_ipv4;
    mac_addr_t    dst_mac;
    subvlan_id_t  src_subvid;
    bit<1>        ipv4_csum_err;
}

    /***********************  P A R S E R  **************************/

parser IngressParser(packet_in      pkt,
    /* User */
    out my_ingress_headers_t          hdr,
    out my_ingress_metadata_t         meta,
    /* Intrinsic */
    out ingress_intrinsic_metadata_t  ig_intr_md)
{
    Checksum() ipv4_checksum;
    
    /* This is a mandatory state, required by Tofino Architecture */
    state start {
        pkt.extract(ig_intr_md);
        pkt.advance(PORT_METADATA_SIZE);
        transition meta_init;
    }

    state meta_init {
        meta.pcp            = 0;
        meta.cfi            = 0;
        meta.vid            = 0;

        meta.src_subvid    = 0;
        meta.ipv4_csum_err = 0;
        meta.dst_ipv4      = 0;
        meta.dst_mac       = 0;
        transition parse_ethernet;
    }
    
    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type) {
            ether_type_t.TPID :  parse_vlan_tag;
            ether_type_t.IPV4 :  parse_ipv4;
            ether_type_t.ARP  :  parse_arp;
            default:  accept;
        }
    }

    state parse_vlan_tag {
        pkt.extract(hdr.vlan_tag.next);
        transition select(hdr.vlan_tag.last.ether_type) {
            ether_type_t.TPID :  parse_vlan_tag;
            ether_type_t.IPV4 :  parse_ipv4;
            ether_type_t.ARP  :  parse_arp;
            default: accept;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        meta.dst_ipv4 = hdr.ipv4.dst_addr;
        
        ipv4_checksum.add(hdr.ipv4);
        meta.ipv4_csum_err = (bit<1>)ipv4_checksum.verify();
        
        transition select(
            hdr.ipv4.ihl,
            hdr.ipv4.frag_offset,
            hdr.ipv4.protocol)
        {
            (5, 0, ip_protocol_t.ICMP) : parse_icmp;
            default: accept;
        }
    }

    state parse_icmp {
        pkt.extract(hdr.icmp);
        transition accept;
    }

    state parse_arp {
        pkt.extract(hdr.arp);
        transition select(hdr.arp.hw_type, hdr.arp.proto_type) {
            (0x0001, ether_type_t.IPV4) : parse_arp_ipv4;
            default: reject; // Currently the same as accept
        }
    }

    state parse_arp_ipv4 {
        pkt.extract(hdr.arp_ipv4);
        meta.dst_ipv4 = hdr.arp_ipv4.dst_proto_addr;
        transition accept;
    }        
}

    /***************** M A T C H - A C T I O N  *********************/

control Ingress(
    /* User */
    inout my_ingress_headers_t                       hdr,
    inout my_ingress_metadata_t                      meta,
    /* Intrinsic */
    in    ingress_intrinsic_metadata_t               ig_intr_md,
    in    ingress_intrinsic_metadata_from_parser_t   ig_prsr_md,
    inout ingress_intrinsic_metadata_for_deparser_t  ig_dprsr_md,
    inout ingress_intrinsic_metadata_for_tm_t        ig_tm_md)
{
    nexthop_id_t    nexthop_id  = 0;
    mac_addr_t      mac_da      = 0;
    mac_addr_t      mac_sa      = 0;
    PortId_t        egress_port = 511; /* Non-existent port */
    bit<8>          ttl_dec     = 0;
    subvlan_id_t tmp_vid = 0;
    subvlan_id_t src_subvid = 0;
    subvlan_id_t dst_subvid = 0;
    supervlan_id_t src_supervid = 0;
    supervlan_id_t dst_supervid = 0;
    supervlan_id_t tmp_supervid = 0;
    bool same_flag = false;
    bool l3_flag = false;
    bit<48> switch_mac = 0;

    action l2_switch(PortId_t port){
        egress_port = port;
        mac_da      = hdr.ethernet.dst_addr;
        mac_sa      = hdr.ethernet.src_addr;
        ttl_dec     = 0;
    }
    action set_l3_flag(){
        l3_flag = true;
    }

    table is_l2_switch {
        key = {
            hdr.ethernet.dst_addr : exact;
        }
        actions = {l2_switch; set_l3_flag;@defaultonly NoAction;}
        size = 512;
        const default_action = NoAction();
    }


    action set_trunk_port(PortId_t port){
        egress_port = port;
        mac_da      = hdr.ethernet.dst_addr;
        mac_sa      = hdr.ethernet.src_addr;
        ttl_dec     = 0;
    }
    action drop() {
        ig_dprsr_md.drop_ctl = 1;
    }

    table Trunk_switch{
        key = {
            hdr.ethernet.dst_addr : exact;
        }
        actions = {set_trunk_port; drop;}
        size           = 512;
        default_action = drop();
    }


    action set_src_vid(subvlan_id_t subvid, supervlan_id_t supervid){
        meta.src_subvid = subvid;
        src_supervid = supervid;
    }
    table Port_to_srcvid {
        key = {ig_intr_md.ingress_port : exact;}
        actions = {set_src_vid; @defaultonly NoAction; }
        size = VLAN_SIZE;
        const default_action = NoAction();
    }


    action set_dst_vid(subvlan_id_t subvid, supervlan_id_t supervid){
        dst_subvid = subvid;
        dst_supervid = supervid;
    }
    table dstIP_to_dstvid {
        key = {
            meta.dst_ipv4 : exact;
        }
        actions = {set_dst_vid;  @defaultonly NoAction; }
        size = 512;
        const default_action = NoAction();
    }


    action set_super_MAC(bit<48> new_mac_switch){
        switch_mac = new_mac_switch;
    }
    table src_supervid_to_mac{
        key = {
            src_supervid : exact;
        }
        actions = {set_super_MAC; @defaultonly NoAction; }
        size = 512;
        const default_action = NoAction();
    }

/****************** IPv4 Lookup ********************/
    action set_nexthop(nexthop_id_t nexthop) {
        nexthop_id = nexthop;
    }
    
    table ipv4_host {
        key     = {
            same_flag : exact; 
            meta.dst_ipv4 : exact; 
            }
        actions = { set_nexthop;  @defaultonly NoAction; }
        size    = IPV4_HOST_SIZE;
        const default_action = NoAction();
    }

    table ipv4_lpm {
        key            = { 
            same_flag : exact;
            meta.dst_ipv4 : lpm; 
        }
        actions        = { set_nexthop; }
        
        default_action = set_nexthop(0);
        size           = IPV4_LPM_SIZE;
    }

    /****************** Nexthop ********************/
    action send(PortId_t port) {                 
        mac_da      = hdr.ethernet.dst_addr;
        mac_sa      = hdr.ethernet.src_addr;
        egress_port = port;
        ttl_dec     = 0;
    }

    action l3_switch(PortId_t port, bit<48> new_mac_da, bit<48> new_mac_sa) {
        mac_da      = new_mac_da;
        mac_sa      = new_mac_sa; /*目的ip对应的交换机MAC*/
        egress_port = port;
        ttl_dec     = 1;        
    }

    table nexthop {
        key            = { nexthop_id : exact; }
        actions        = { send; drop; l3_switch; }
        size           = NEXTHOP_SIZE;
        default_action = drop();
    }

        /****************** Metadata Processing ********************/
    action send_back() {
        ig_tm_md.ucast_egress_port = ig_intr_md.ingress_port;
    }

    action forward_ipv4() {
        hdr.ethernet.dst_addr      = mac_da;
        hdr.ethernet.src_addr      = mac_sa;
        hdr.ipv4.ttl               = hdr.ipv4.ttl |-| ttl_dec;
        ig_tm_md.ucast_egress_port = egress_port;
    }

    action send_arp_reply_in() {
        hdr.ethernet.dst_addr = hdr.arp_ipv4.src_hw_addr;
        hdr.ethernet.src_addr = mac_da;       /*ARP请求同一个sub_vlan中的主机MAC,把主机的真实MAC作为源MAC回复*/

        hdr.arp.opcode = arp_opcode_t.REPLY;
        hdr.arp_ipv4.dst_hw_addr    = hdr.arp_ipv4.src_hw_addr;
        hdr.arp_ipv4.dst_proto_addr = hdr.arp_ipv4.src_proto_addr;
        hdr.arp_ipv4.src_hw_addr    = mac_da;
        hdr.arp_ipv4.src_proto_addr = meta.dst_ipv4;

        send_back();
    }

    action send_arp_reply_out() {
        hdr.ethernet.dst_addr = hdr.arp_ipv4.src_hw_addr;
        hdr.ethernet.src_addr = switch_mac;       /*ARP请求不同sub_vlan中的主机MAC,把交换机的MAC作为源MAC回复*/

        hdr.arp.opcode = arp_opcode_t.REPLY;
        hdr.arp_ipv4.dst_hw_addr    = hdr.arp_ipv4.src_hw_addr;
        hdr.arp_ipv4.dst_proto_addr = hdr.arp_ipv4.src_proto_addr;
        hdr.arp_ipv4.src_hw_addr    = mac_sa;
        hdr.arp_ipv4.src_proto_addr = meta.dst_ipv4;

        send_back();
    }

    table forward_or_respond {
        key = {
            same_flag               : exact;
            hdr.arp.isValid()       : exact;
            hdr.arp_ipv4.isValid()  : exact;
            hdr.ipv4.isValid()      : exact;
            hdr.arp.opcode          : ternary;
        }
        actions = {
            forward_ipv4;
            send_arp_reply_in;
            send_arp_reply_out;
            drop;
        }
        const entries = {
            (true, false, false, true, _) :
            forward_ipv4();
            (false, false, false, true, _) :
            forward_ipv4();
            (true, true,  true,  false, arp_opcode_t.REQUEST) :
            send_arp_reply_in();
            (false, true,  true,  false, arp_opcode_t.REQUEST) :
            send_arp_reply_out();
        }
        default_action = drop();
    }

    apply{
        if(meta.ipv4_csum_err == 0){
            if(!is_l2_switch.apply().hit){
                Trunk_switch.apply();
            }
            if(!l3_flag){
                same_flag = true;
            }
            if(!same_flag){
                Port_to_srcvid.apply();
                dstIP_to_dstvid.apply();
                if((src_supervid == dst_supervid)&&(meta.src_subvid == dst_subvid)){
                    same_flag = true;
                }
                src_supervid_to_mac.apply();
                if (!ipv4_host.apply().hit) {
                    ipv4_lpm.apply();
                }
                nexthop.apply();
            }
            forward_or_respond.apply();
        }

        hdr.bridge.setValid();
        hdr.bridge.header_type  = HEADER_TYPE_BRIDGE;
        hdr.bridge.header_info  = 0;                           /* Ignore */
        hdr.bridge.ingress_port = ig_intr_md.ingress_port;
        hdr.bridge.pcp          = meta.pcp;
        hdr.bridge.cfi          = meta.cfi;
        hdr.bridge.vid          = meta.src_subvid;
    }
}

    /*********************  D E P A R S E R  ************************/

control IngressDeparser(packet_out pkt,
    /* User */
    inout my_ingress_headers_t                       hdr,
    in    my_ingress_metadata_t                      meta,
    /* Intrinsic */
    in    ingress_intrinsic_metadata_for_deparser_t  ig_dprsr_md)
{
    Checksum() ipv4_checksum;
    
    apply {
        hdr.ipv4.hdr_checksum = ipv4_checksum.update({
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.total_len,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.frag_offset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr
                /* Adding hdr.ipv4_options.data results in an error */
            });
        pkt.emit(hdr);
    }
}


/*************************************************************************
 ****************  E G R E S S   P R O C E S S I N G   *******************
 *************************************************************************/

    /***********************  H E A D E R S  ************************/

struct my_egress_headers_t {
    ethernet_h ethernet;
    vlan_tag_h vlan_tag;
}

    /********  G L O B A L   E G R E S S   M E T A D A T A  *********/

struct my_egress_metadata_t {
    bridge_h          bridge;

    PortId_t          ingress_port;
    bit<3>            pcp;
    bit<1>            cfi;
    bit<12>           vid;
}

    /***********************  P A R S E R  **************************/

parser EgressParser(packet_in        pkt,
    /* User */
    out my_egress_headers_t          hdr,
    out my_egress_metadata_t         meta,
    /* Intrinsic */
    out egress_intrinsic_metadata_t  eg_intr_md)
{
    /* This is a mandatory state, required by Tofino Architecture */
    inthdr_h inthdr;
    
    /* This is a mandatory state, required by Tofino Architecture */
    state start {
        pkt.extract(eg_intr_md);
        inthdr = pkt.lookahead<inthdr_h>();
        transition select(inthdr.header_type, inthdr.header_info) {
            ( HEADER_TYPE_BRIDGE,         _ ) : parse_bridge;
            default : reject;
        }
    }

    state parse_bridge {
        pkt.extract(meta.bridge);
        meta.ingress_port = meta.bridge.ingress_port;
        meta.pcp = meta.bridge.pcp;
        meta.cfi = meta.bridge.cfi;
        meta.vid = meta.bridge.vid;
        transition parse_ethernet;
    }
    
    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(pkt.lookahead<bit<16>>()) {
            (bit<16>)ether_type_t.TPID &&& 0xEFFF: parse_vlan_tag;
            default: accept;
        }
    }
    state parse_vlan_tag {
        pkt.extract(hdr.vlan_tag);
        transition accept;
    }
}

    /***************** M A T C H - A C T I O N  *********************/

control Egress(
    /* User */
    inout my_egress_headers_t                          hdr,
    inout my_egress_metadata_t                         meta,
    /* Intrinsic */    
    in    egress_intrinsic_metadata_t                  eg_intr_md,
    in    egress_intrinsic_metadata_from_parser_t      eg_prsr_md,
    inout egress_intrinsic_metadata_for_deparser_t     eg_dprsr_md,
    inout egress_intrinsic_metadata_for_output_port_t  eg_oport_md)
{
    action drop() {
        eg_dprsr_md.drop_ctl = eg_dprsr_md.drop_ctl | 1;
    }

    action send_tagged() {
        hdr.vlan_tag.setValid();
        hdr.vlan_tag.tpid = (bit<16>)ether_type_t.TPID;
#ifdef P4C_1719_FIXED
        hdr.vlan_tag.pcp  = meta.pcp;
        hdr.vlan_tag.cfi  = meta.cfi;
#else
        hdr.vlan_tag.pcp  = 0;
        hdr.vlan_tag.cfi  = 0;
#endif
        hdr.vlan_tag.vid  = meta.vid;
    }
    
    action send_untagged() {
        hdr.vlan_tag.setInvalid();
    }

    action not_a_member() {
        drop();
    }
    
    table egr_vlan_port {
        key = {
            meta.vid                    : exact;
            eg_intr_md.egress_port[6:0] : exact @name("egress_port");
        }
        actions = {
            send_tagged;
            send_untagged;
            not_a_member;
        }
        default_action = not_a_member();
        size = 512;
    }
    
    apply {       
#ifdef P4_SOURCE_PRUNING
        if (meta.ingress_port == eg_intr_md.egress_port) {
            drop();
        } else {
#endif
            egr_vlan_port.apply();
#ifdef P4_SOURCE_PRUNING
        }
#endif
    }
}

    /*********************  D E P A R S E R  ************************/

control EgressDeparser(packet_out pkt,
    /* User */
    inout my_egress_headers_t                       hdr,
    in    my_egress_metadata_t                      meta,
    /* Intrinsic */
    in    egress_intrinsic_metadata_for_deparser_t  eg_dprsr_md)
{
    apply {
        pkt.emit(hdr);
    }
}


/************ F I N A L   P A C K A G E ******************************/
Pipeline(
    IngressParser(),
    Ingress(),
    IngressDeparser(),
    EgressParser(),
    Egress(),
    EgressDeparser()
) pipe;

Switch(pipe) main;
