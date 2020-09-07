# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(1)
import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(dhcp_hostname="NFC_Door")
if not wlan.isconnected():
    print('connecting to network...')
    
    wlan.connect('WIFI_Name', 'WIFI_Password')
    while not wlan.isconnected():
        pass
print('network config:', wlan.ifconfig())

#import webrepl
#webrepl.start()

