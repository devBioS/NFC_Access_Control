#---------------------------------------------------
# NFC Door Access Control
#---------------------------------------------------
# Copyright (c) 2020 devBioS 
# With enough persistence everything is possible
# https://github.com/devBioS/NFC_Access_Control
#
# Licensed under the MIT License
#---------------------------------------------------

import mfrc522
from os import uname
import time
import ubinascii
import ujson
import urequests
import sys
import machine, neopixel
import micropython
import keypad_timer

#-----------General Config--------------------
authurl = 'https://your-server/rfid-auth2/auth.php'
device_id = 'frontdoor' #deviceid used in server's config file to distingush operations for multiple devices

#-----------NeoPixel Config--------------------
pin_neopixel = 21

#-----------RFID / NFC Config--------------------
#if you set useNFC to False, you can only use PIN+GAuth
useNFC = True
pin_nfc_sck=14
pin_nfc_mosi=13
pin_nfc_miso=12
pin_nfc_rst=26
pin_nfc_cs=27

#Message to write on each card, that is readable by any device
#Use as a welcoming message and tell the people to fuck off
#Must be exactly 17 characters!
nfc_writemessage = b"Go Away!         "

#-----------GoogleAuth Config--------------------
#if you disable GoogleAuth here, you cannot use GoogleAuth only. However if the server requests additional GoogleAuth it is still possible.
useGoogleAuth = True
pins_keypad_rows = [ 15, 2, 0, 4 ]
pins_keypad_cols = [ 16, 17, 5, 18 ]

#-----------Debug Mode---------------------------
#Enable debugmode to print debug messages to the serial console
debugmode = True

#****************END CONFIG***********************
from machine import WDT
wd_timeout = 30000 # Watchdog resets the chip after 30 seconds if it hangs or crashed
WHITE = 1
RED = 2
BLUE = 3
GREEN = 4
PINK = 6
OFF = 5
YELLOW = 7
BLUEYELL = 8 #for GAuth after NFC
YELLBLUE = 9 #for GAuth after NFC

lastled = -1
defaultkey = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
defaultkeystr = b"\xff\xff\xff\xff\xff\xff"

def log(txt):
    if debugmode:
        print(txt)

def init(rdr,answerjs,raw_uid):
    log("INIT!")
    log(answerjs)
    if (answerjs["setantiblk"] != ""):
        log("initializing sector 0...")
        if rdr.auth(rdr.AUTHENT1A, 2, defaultkey, raw_uid) == rdr.OK:
            rdr.write(2, nfc_writemessage)

        for i in range(1,16):
            log("writing sector %s" % i)
            if rdr.auth(rdr.AUTHENT1A, i*4, defaultkey, raw_uid) == rdr.OK:
                #log("auth ok")
                for x in range(0,3):
                    #write filler data or real hash 
                    numblk = (i*4)+x
                    numfiller = ((i-4)*4)+x #Array begins at 0 but blocks begin at 4
                    if numblk == int(answerjs["setantiblk"]):
                        log("writing hash to block: %s" % numblk)
                        rdr.write(int(answerjs["setantiblk"]), answerjs["txt"].encode())
                    else:
                        #log("writing filler to block: %s" % numblk)
                        rdr.write(numblk,answerjs["filler"][numfiller].encode())

                rdr.setKey(i,ubinascii.unhexlify(answerjs["keya"][i]),ubinascii.unhexlify(answerjs["keyb"][i]))
                log("key set complete")
            else:
                log("auth error")
    else:
        log("server response error...")

def reset(rdr,answerjs,raw_uid):
    log("RESET!")
    log(answerjs)
    if (answerjs["keyb"] != ""):
        log("resetting sector 0...")
        if rdr.auth(rdr.AUTHENT1B, 2, defaultkey, raw_uid) == rdr.OK:
            rdr.write(2, b"\x00"*17)

        for i in range(1,16):
            log("setting key for sector %s" % i)
            if rdr.auth(rdr.AUTHENT1B, i*4, [c for c in ubinascii.unhexlify(answerjs["keyb"][i])], raw_uid) == rdr.OK:
                log("auth ok")
                #Fill the contents with 0's
                for x in range(0,3):
                    numblk = (i*4)+x
                    rdr.write(numblk,b"\x00"*17)
                
                rdr.reSetKeyOpen(i,defaultkeystr,defaultkeystr)
                log("key reset complete")
            else:
                log("auth error")
    else:
        log("server response error...")    

def led(np,stat):
    wdt.feed()
    if lastled != stat:
        np[0] = (0, 0, 0)
        np[1] = (0, 0, 0)
        np.write()         
        if stat == WHITE:
            np[0] = (255, 255, 255)
            np[1] = (255, 255, 255)
            np.write()
        elif stat == RED:
            np[0] = (255, 0, 0)
            np[1] = (255, 0, 0)
            np.write()
        elif stat == BLUE:
            np[0] = (0, 0, 255)
            np[1] = (0, 0, 255)
            np.write()
        elif stat == PINK:
            np[0] = (255, 0, 255)
            np[1] = (255, 0, 255)
            np.write()
        elif stat == GREEN:
            np[0] = (0, 255, 0)
            np[1] = (0, 255, 0)
            np.write()
        elif stat == YELLOW:
            np[0] = (255, 255, 0)
            np[1] = (255, 255, 0)
            np.write()
        elif stat == YELLBLUE:
            np[0] = (255, 255, 0)
            np[1] = (0, 0, 255)
            np.write()
        elif stat == BLUEYELL:
            np[0] = (0, 0, 255)
            np[1] = (255, 255, 0)
            np.write()
        elif stat == OFF:
            np[0] = (0, 0, 0)
            np[1] = (0, 0, 0)
            np.write()

def get_stage4_gcode(np,keypadnums):
    log("Keypad Entry Requested...")
    keypad.start()
    myled = BLUEYELL
    try:
            timecnt = 0
            loopme=True
            testkey = ""
            key = ""
            while loopme:
                wdt.feed()
                
                if len(testkey) == 0:
                    testkey = keypad.get_key()
                    if testkey:
                        key = testkey
                        log( "keystr: %s" % key )

                    if myled == BLUEYELL:
                        led(np,YELLBLUE)
                        myled = YELLBLUE
                    else:
                        led(np,BLUEYELL)
                        myled = BLUEYELL
            
                    time.sleep(0.5)
                    timecnt+=5
                else:
                    timecnt+=1
                    led(np,YELLOW)
                    #If key is lengthy enough
                    if len(key) >= keypadnums:
                        keypad.stop() #stop entry timer
                        led(np,OFF)
                        loopme = False
                        return key
                    else:
                        newkey = keypad.get_key()
                        if newkey:
                            timecnt = 0 #reset abort timer
                            if newkey == "#" or newkey == "*":
                                #abort
                                log( "Key entry aborted with key: %s" % newkey )
                                led(np,OFF)
                                loopme = False
                            else:
                                key += newkey
                                log( "keystr: %s" % key )
                                led(np,BLUE)
                        time.sleep(0.1)

                if timecnt >= 600:  #measured by hand ca 60 sec :)
                    #autoabort after 60 seconds no keypress
                    loopme = False
    except Exception as exc:
        log( "Exception in KeyPad enum: %s " % str( exc ) )
        pass
    keypad.stop()
    return "0"*keypadnums

def do_work():

    log("")
    log("Place card before reader...")
    log("")

    try:
        while True:
            wdt.feed()
            led(np,OFF)
            if useNFC:
                (stat, tag_type) = rdr.request(rdr.REQIDL)
                if stat == rdr.OK:
                    keypad.stop() #Stop keypad Timer, no presses recorded from here
                    led(np,WHITE)
                    if not rdr.checkChinaUID():
                        (stat, raw_uid) = rdr.anticoll()

                        if stat == rdr.OK:
                            wdt.feed()
                            log("New card detected")
                            log("  - tag type: 0x%02x" % tag_type)
                            log("  - uid	 : 0x%02x%02x%02x%02x" %
                                (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3]))
                            log("")

                            if rdr.select_tag(raw_uid) == rdr.OK:
                                log("Tag selected")
                                #stage1
                                log("Asking Access Control System (stage1)...")
                                uid = "%02x%02x%02x%02x" % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3]) #ubinascii.hexlify(bytes(raw_uid)).decode('UTF8')
                                try:
                                    r = urequests.post(authurl, data = ujson.dumps({"cmd":"stage1","device_id":device_id,"uid":uid}))
                                    log(r.text)
                                    answerjs = r.json()
                                    r.close()

                                    if answerjs["status"] == "k":
                                        log("status ok")
                                        log(answerjs)
                                        wdt.feed()
                                        rkey = ubinascii.unhexlify(answerjs["key"])
                                        rblock = int(answerjs["antiblk"])
                                        rlen = int(answerjs["len"])
                                        
                                        log("Reading %s Bytes from Block #%s, with KEY_A:%s" % (rlen,rblock,rkey))
                                        if rdr.auth(rdr.AUTHENT1A, rblock, [c for c in rkey], raw_uid) == rdr.OK:
                                            data = rdr.read(rblock) #rkey
                                            pdata = "".join(chr(i) for i in data)
                                            log("Found data: %s" % pdata)                                    
                                            
                                            #stage2 - check data against server
                                            log("Asking Access Control System (stage2)...")
                                            wdt.feed()
                                            try:
                                                r = urequests.post(authurl, data = ujson.dumps({"cmd":"stage2","device_id":device_id,"uid":uid,"key":pdata}))
                                                log(r.text)
                                                answerjs = r.json()
                                                r.close()
                                                log(answerjs)
                                                if answerjs["status"] == "kk":
                                                    log("stage 2 ok")
                                                    log("Entering stage3...")
                                                    #stage 3 - write data and give response
                                                    rwriteblock = int(answerjs["setantiblk"])
                                                    rwritekey = ubinascii.unhexlify(answerjs["key"])
                                                    rwritedata = answerjs["txt"]
                                                    
                                                    if rdr.auth(rdr.AUTHENT1B, rwriteblock, [c for c in rwritekey], raw_uid) == rdr.OK:
                                                        wdt.feed()
                                                        stat = rdr.write(rwriteblock, rwritedata.encode())
                                                        log(stat)
                                                        data = rdr.read(rwriteblock)
                                                        pdata = "".join(chr(i) for i in data)
                                                        log("Found new data: %s" % pdata)
                                                        
                                                        led(np,GREEN)
                                                        #open, or when closed also open
                                                        cmd = "open"
                                                        #time.sleep(2)
                                                        pdata2 = "nope"
                                                        for g in range(4):
                                                            try:
                                                                data2 = rdr.read(rwriteblock)
                                                                pdata2 = "".join(chr(i) for i in data2)
                                                                log("Still found new data: %s (%s)" % (pdata2,g))
                                                                time.sleep(1)
                                                            except: # Exception as e:
                                                                #print("Exception in recurring data fetch: %s" % e)
                                                                #sys.print_exception(e)
                                                                pdata2 = "nope"
                                                                break

                                                        if pdata2 == pdata:
                                                            #wait some sec, if same uid is still there, cmd is close (long tap)
                                                            cmd = "close"
                                                            led(np,PINK)
                                                        try:
                                                            log("Asking Access Control System (stage3) to %s..." % cmd)
                                                            r = urequests.post(authurl, data = ujson.dumps({"cmd":"stage3","device_id":device_id,"uid":uid,"key":pdata,"doorcmd":cmd}))
                                                            #log(r.text)
                                                            answerjs = r.json()
                                                            r.close()
                                                            #log(answerjs)
                                                            wdt.feed()
                                                            #Stage4 requested:
                                                            if (answerjs["status"] == "getcode"):
                                                                log("Access Control System is Requesting Google Authenticator... transistion into stage 4")
                                                                gcode_code = get_stage4_gcode(np,int(answerjs["num"]))
                                                                log("sending code... %s " % gcode_code)
                                                                r = urequests.post(authurl, data = ujson.dumps({"cmd":"stage4","device_id":device_id,"uid":uid,"key":pdata,"doorcmd":cmd,"gcode":gcode_code}))
                                                                answerjs = r.json()
                                                                if (answerjs["status"] == "done"):
                                                                    log("GoogleAuth code valid")
                                                                    led(np,GREEN)
                                                                else:
                                                                    log("GoogleAuth code NOT valid!")
                                                                    led(np,RED)
                                                                #finished...
                                                                log("Finished.. going to sleep...")                                                                
                                                                r.close()
                                                            else:
                                                                #finished...
                                                                log("Finished.. going to sleep...")

                                                            time.sleep(3)
                                                        except Exception as e:
                                                            log("Exception in stage3: %s" % e)
                                                            led(np,RED)
                                                            if debugmode:
                                                                sys.print_exception(e)
                                                            
                                                            r.close()
                                                            break  
                                                    else:
                                                        log("auth error stage3! (Card removed?)")
                                                        led(np,RED)
                                                else:
                                                    log("stage 2 status error (key wrong?)")
                                                    led(np,RED)
                                            except Exception as e:
                                                log("Exception in stage2: %s" % e)
                                                led(np,RED)
                                                if debugmode:
                                                    sys.print_exception(e)
                                                
                                                r.close()
                                                break    
                                        else:
                                            log("auth error stage1! (Card removed?)")
                                            led(np,RED)
                                    elif answerjs["status"] == "init":
                                        led(np,BLUE)
                                        init(rdr,answerjs,raw_uid)
                                        led(np,GREEN)
                                    elif answerjs["status"] == "reset":
                                        led(np,BLUE)
                                        reset(rdr,answerjs,raw_uid)
                                        led(np,GREEN)
                                    else:
                                        log("stage 1 status error (uid not auth?)!")
                                        led(np,RED)
                                except Exception as e:
                                    log("Exception in stage1: %s" % e)
                                    led(np,RED)
                                    if debugmode:
                                        sys.print_exception(e)
                                    
                                    r.close()
                                    break
                                rdr.stop_crypto1()     
                                time.sleep(3)
                            else:
                                log("Failed to select tag")
                                led(np,RED)
                    else:
                        log("Chinese UID found!")
                        led(np,RED)
                        try:
                            (stat, tag_type) = rdr.request(rdr.REQIDL)
                            (stat, raw_uid) = rdr.anticoll()
                            #rdr.halt()
                            if stat == rdr.OK:
                                uid = "%02x%02x%02x%02x" % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3])
                            else:
                                uid = "00000000"
                            log("Chinese UID %s found!" % uid)
                            r = urequests.post(authurl, data = ujson.dumps({"cmd":"chinauid","device_id":device_id,"uid":uid}))
                            r.close()
                        except:
                            pass
                        time.sleep(3)
                    keypad.start() #resume keypad presses
            if useGoogleAuth:
                #log("Check KeyPad Entry")
                try:
                    key = keypad.get_key()
                    if key:
                        #we got at least one key, check faster here for more keys or abort after 5 seconds
                        log( "keypad: got key: %s" % key )
                        timecnt = 0
                        loopme=True
                        while loopme:
                            wdt.feed()
                            timecnt+=1
                            led(np,YELLOW)
                            #If Key Len >= 10 chars
                            if len(key) >= 10:
                                keypad.stop() #stop entry timer
                                led(np,WHITE)
                                #send to server
                                try:
                                    r = urequests.post(authurl, data = ujson.dumps({"cmd":"keyauth","device_id":device_id,"key":key}))
                                    log(r.text)
                                    answerjs = r.json()
                                    r.close()
                                    log(answerjs)
                                    if answerjs["status"] == "kk":
                                        led(np,GREEN)
                                        time.sleep(1)
                                    else:
                                        led(np,RED)
                                        time.sleep(1)
                                except:
                                    led(np,RED)
                                    time.sleep(1)
                                    pass
                                
                                keypad.start() #resume keypad presses
                                loopme = False
                            else:
                                newkey = keypad.get_key()
                                if newkey:
                                    timecnt = 0 #reset abort timer
                                    if newkey == "#" or newkey == "*":
                                        #abort
                                        log( "Key entry aborted with key: %s" % newkey )
                                        led(np,OFF)
                                        loopme = False
                                    else:
                                        key += newkey
                                        log( "keystr: %s" % key )
                                        led(np,BLUE)

                                time.sleep(0.1)

                            if timecnt >= 100:  #measured by hand ca 10 sec :)
                                #autoabort after 10 seconds no keypress
                                loopme = False

                            

                except Exception as exc:
                    log( "Exception in KeyPad enum: %s" % str( exc ) )
                    pass
            machine.idle()
            time.sleep(1) 
    except KeyboardInterrupt:
        log("Bye")

micropython.alloc_emergency_exception_buf( 100 )
wdt = WDT(timeout=wd_timeout)
np = neopixel.NeoPixel(machine.Pin(pin_neopixel), 2)
led(np,PINK)
rdr = mfrc522.MFRC522(sck=pin_nfc_sck, mosi=pin_nfc_mosi, miso=pin_nfc_miso, rst=pin_nfc_rst, cs=pin_nfc_cs)
keypad = keypad_timer.Keypad_Timer(pins_row=pins_keypad_rows,pins_col=pins_keypad_cols)
if useGoogleAuth:
    keypad.start()
do_work()