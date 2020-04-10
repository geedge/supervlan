测试一：
1. ./run_bfshell.sh -b ~/labs/super_vlan/bfrt_python/setup.py
## 测试两个sub_vlan之间ARP
方法一：
2. sudo ip addr add 192.168.1.254/24 dev veth3
3. sudo scapy
4. p = sr1(ARP(psrc='192.168.1.13',pdst='192.168.1.1'))
方法二：
5. 进入/super_vlan/pkt/目录
6. 运行发送数据包的脚本：sudo python ./twosub_send.py

## 测试同一个sub_vlan二层通信
7. 进入到/super_vlan/pkt/目录
8. 运行发送数据包的脚本：sudo python ./subin_send.py

测试二：
用ptf测试
./run_p4_tests.sh -p super_vlan_test -t ~/labs/super_vlan_test/ptf -s test.(ClassName)