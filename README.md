1. ./run_bfshell.sh -b ~/labs/super_vlan/bfrt_python/setup.py
## 测试两个sub_vlan之间ARP
2. sudo ip addr add 192.168.1.254/24 dev veth3
3. sudo scapy
4. p = sr1(ARP(psrc='192.168.1.13',pdst='192.168.1.1'))

## 测试同一个sub_vlan二层通信
5. 进入到/super_vlan/pkt/目录
6. 运行发送数据包的脚本：sudo python ./subin_send.py