"""
Author : Mathieu Croizer alias Krounet : https://github.com/Krounet

Translate strings into the form CallSigns+Locations+Power to bytes for WSPR transmission
"""

import numpy as np
from gnuradio import gr
import pmt
import re
import time


txtCallsigns=''
txtLocation=''
txtPower=''


###Coding Tables for Callsigns and Location. No table for Power

callsignsCoding={'0':0,'1':1,'2':2,3:'3','4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'A':10,'B':11,'C':12,'D':13,'E':14,'F':15,'G':16,'H':17,'I':18,
                 'J':19,'K':20,'L':21,'M':22,'N':23,'O':24,'P':25,'Q':26,'R':27,'S':28,'T':29,'U':30,'V':31,'W':32,'X':33,'Y':34,'Z':35,' ':36}

locationCoding={'0':0,'1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'A':0,'B':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7,'I':8,
                'J':9,'K':10,'L':11,'M':12,'N':13,'O':14,'P':15,'Q':16,'R':17}
 





class mc_sync_block(gr.sync_block):
    """
    Reads input from 3 message ports : 1 ports for radio operator Callsigns + 1 ports for Location in Maidenhead grid Locator format + 1 port for Power of the transmitter in dBm [0 to 60 dBm]
    """
    def __init__(self):
        gr.sync_block.__init__(self,name='WSPR code',in_sig=None,out_sig=[np.byte])
        self.message_port_register_in(pmt.intern('Callsigns'))
        self.message_port_register_in(pmt.intern('Location'))
        self.message_port_register_in(pmt.intern('Power_dBm'))
        self.set_msg_handler(pmt.intern('Callsigns'),self.handle_msg_Callsigns)
        self.set_msg_handler(pmt.intern('Location'),self.handle_msg_Location)
        self.set_msg_handler(pmt.intern('Power_dBm'),self.handle_msg_Power)


    def handle_msg_Callsigns(self,msg):
        global txtCallsigns
        txtCallsigns=pmt.symbol_to_string(msg)
        print("debug "+txtCallsigns) #debug
        
    def handle_msg_Location(self,msg):
        global txtLocation
        txtLocation=pmt.symbol_to_string(msg)
        print("debug "+txtLocation) #debug

    def handle_msg_Power(self,msg):
        global txtPower
        txtPower=pmt.symbol_to_string(msg)
        print("debug "+txtPower) #debug


    def transform_Callsigns(self):
        global txtCallsigns
        global callsignsCoding
        """
        Callsigns must be 6 characters long.
        1) If the second character is a number, a space must be introduced at the beginning. Ex : 'K1JT' become ' K1JT'
        2) If Callsigns is less than 6 characters, even if a space is introduced at the beginnong, the chain must be completed with space. Ex : ' K1JT' become ' K1JT '
        """

        if len(txtCallsigns)>6:
            print("Error : Callsigns uses 6 characters max")

        if re.search('[0-9]',txtCallsigns)==None:
            print("Error : Callsigns must contained a number minimum")

        if re.search('[0-9]',txtCallsigns[1]):
            txtCallsigns=' '+txtCallsigns # in WSPR transmission Callsigns must be in the format [A-Z][A-Z][0-9]XXX, with X = [A-Z] or [0-9] or space. If the second character is a number, a space is introduced at the beginning

        if len(txtCallsigns)<6: #Complete Callsigns with space if txtCallsigns length <6
            
            for n in range(6-len(txtCallsigns)):
                txtCallsigns=txtCallsigns+' '

        
        #Let's code the Callsigns in binary
        n1=callsignsCoding[txtCallsigns[0]] 
        n2=n1*36+callsignsCoding[txtCallsigns[1]]
        n3=n2*10+callsignsCoding[txtCallsigns[2]]
        n4=27*n3+callsignsCoding[txtCallsigns[3]]-10
        n5=27*n4+callsignsCoding[txtCallsigns[4]]-10
        n6=27*n5+callsignsCoding[txtCallsigns[5]]-10
        n=np.binary_repr(n6,28)
        return n



    def transform_Location(self):
        global txtLocation
        global locationCoding
        global txtPower        
        
        if len(txtLocation)>4:

            print("Error : Location uses 4 characters max")

        if re.search('[A-Z]',txtLocation[0]) is None or re.search('[A-Z]',txtLocation[1]) is None:
            print ("Error : The two first characters of Locator must be letters")


        if re.search('[0-9]',txtLocation[2]) is None or re.search('[0-9]',txtLocation[3]) is None:
            print ("Error : The two last characters of Locator must be numbers")

        #Let's code the Locator in binary
        
        m1=(179-10*locationCoding[txtLocation[0]]-locationCoding[txtLocation[2]])*180+10*locationCoding[txtLocation[1]]+locationCoding[txtLocation[3]]
        m=np.binary_repr(m1*128+int(txtPower)+64,22)
        return m







    def work(self,input_items,output_items):
        
        """
        What do we do here ? :

        _ The Callsigns and the Location + Power are compressed in two integer N and M
        _ N is calculated with these equations :
            * N1 = [Ch1] -> [Chn] is the n character in decimal of the Callsigns modified by the function transform_Callsigns()
            * N2 = N1 * 36 + [Ch2]
            * N3 = N2 * 10 + [Ch3]
            * N4 = 27 * N3 + [Ch4] - 10
            * N5 = 27 * N4 + [Ch5] - 10
            * N = N6 = 27 * N5 + [Ch6] - 10

        _ M is calculated with these equations :
            * M1= (179 - 10 * [Loc1] - [Loc3]) * 180 + 10 * [Loc2] + [Loc4] -> [Locn] is the n character in decimal of the Location modified by the function transform_Location()
            * M = M1 * 128 + [Pwr] + 64 -> [Pwr] is the power in dBm
        """
        #time.sleep(5)
        codingN=self.transform_Callsigns()
        codingM=self.transform_Location()
        #creating the 88 elements array to encode. The array will be packed then in 11 8-bits bytes array c[0] to c[6] will contain the informations to transmit.c[6] will contain the 2 two las bit of M and is completed by zeroes. c[7] to c[10] is filled with zeroes
        #serializing N
        n_Serial=np.byte([bit for bit in codingN])
        #serializing M
        m_Serial=np.hstack((np.byte([bit for bit in codingM]),np.byte([0,0,0,0,0,0])))
        #creating c[7] to c[10]
        c7toc10bin=np.binary_repr(0,32)
        c7toc10=np.byte([bit for bit in c7toc10bin])

        #stacking the arrays
        bitstreams=np.hstack((n_Serial,m_Serial,c7toc10))
        #output_items[0]=bitstreams
        for x in range(len(bitstreams)):
            output_items[0]=bitstreams[x]
            print(output_items[0])
        #print("length of the Block Output: "+str(len(output_items[0])))
        return len(bitstreams)



