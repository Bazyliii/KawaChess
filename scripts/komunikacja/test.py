import xtelnet

telnet = xtelnet.Telnet_Session()

IP = "127.0.0.1"
PORT = 9105

telnet.connect(host=IP, new_line="\r\n", username="as", port=PORT)
x = telnet.execute("ZPOW OFF")
print(x)