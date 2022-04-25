import pyvisa
from interface.wainvam_interface.dummy_interface import dummy_interface

import os
import time
import numpy as np
import scipy.interpolate
from fnmatch import fnmatch
from collections import OrderedDict
from abc import abstractmethod
import re
import sys

from core.module import Base
from core.configoption import ConfigOption
from interface.pulser_interface import PulserInterface, PulserConstraints, SequenceOption
from core.util.modules import get_home_dir


class Scope_Char(Base, dummy_interface):
    """
    H.Babashah - Hardware code for Swabian Pulse streamer.
    """
    _instrument_visa_address = ConfigOption(name='instrument_visa_address', default='TCPIP0::192.168.1.111::inst0::INSTR', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """
        H.Babashah - Inspired from Qudi - Initialisation performed during activation of the module.
        """
        self.GLOBAL_TOUT = 10000  # IO time out in milliseconds

        self.TIME_TO_TRIGGER = 10  # Time in seconds

        self.TIME_BETWEEN_TRIGGERS = 0.025  # Time in seconds - for Average, Segmented, and Equivalent Time types/modes, else set to 0


        os.add_dll_directory("C:/Program Files/Keysight/IO Libraries Suite/bin")
        os.add_dll_directory("C:/Program Files (x86)/Keysight/IO Libraries Suite/bin")
        rm = pyvisa.ResourceManager(
            'C:\\Program Files (x86)\\IVI Foundation\\VISA\\WinNT\\agvisa\\agbin\\visa32.dll')  # this uses PyVisa

        try:
            self.KsInfiniiVisionX = rm.open_resource(self._instrument_visa_address)
            Name = self.KsInfiniiVisionX.query(":SYSTem:DIDentifier?")

            print("\n The connection with " + str(Name) + "has been successfully established. \n")
        except Exception:
            print("Unable to connect to oscilloscope at " + str(self._instrument_visa_address) + ". Aborting script.\n")
            sys.exit()

        ## Set Global Timeout
        ## This can be used wherever, but local timeouts are used for Arming, Triggering, and Finishing the acquisition... Thus it mostly handles IO timeouts
        self.KsInfiniiVisionX.timeout = self.GLOBAL_TOUT

        ## Clear the instrument bus
        self.KsInfiniiVisionX.clear()

        ## Clear all registers and errors
        ## Always stop scope when making any changes.
        self.KsInfiniiVisionX.query(":STOP;*CLS;*OPC?")
    def on_deactivate(self):
        """
        F.Beato - Inspired from Qudi - Required tasks to be performed during deactivation of the module.
        """

    # _____________________### DEFINE ACQUISITION METHODE ###______________________#

    ## Define a simple and fast function utilizing the blocking :DIGitize command in conjunction with *OPC?
        self.stop()
    def blocking_method(self):
        self.KsInfiniiVisionX.timeout = self.SCOPE_ACQUISITION_TIME_OUT  # Time in milliseconds (PyVisa uses ms) to wait for the scope to arm, trigger, finish acquisition, and finish any processing.
        ## Note that this is a property of the device interface, KsInfiniiVisionX.
        ## If doing repeated acquisitions, this should be done BEFORE the loop, and changed again after the loop if the goal is to achieve best throughput.

        start = time.time()
        # print("Acquiring signal(s)...\n")
        try:  # Set up a try/except block to catch a possible timeout and exit.
            self.KsInfiniiVisionX.query(
                ":DIGitize;*OPC?")  # Acquire the signal(s) with :DIGItize (blocking) and wait until *OPC? comes back with a one. There is no need to issue a *CLS before issuing the :DIGitize command as :DIGitize actually takes care of this for you.
            # print("Signal acquired in "+ str(round(time.time()-start,2)) + "s.\n")
            print('|     ' + str(round(time.time() - start, 2)) + 's    ', end='')
            self.KsInfiniiVisionX.timeout = self.GLOBAL_TOUT  # Reset timeout back to what it was, GLOBAL_TOUT.
        except Exception:  # Catch a possible timeout and exit.
            print(
                "The acquisition timed out, most likely due to no trigger, or improper setup causing no trigger. Properly closing scope connection and exiting script.\n")
            self.KsInfiniiVisionX.clear()  # Clear scope communications interface; a device clear aborts a digitize and clears the scope's IO interface..
            ## Don't do a *CLS.  If you do, you won't be able to do a meaningful :SYSTem:ERRor? query as *CLS clears the error queue
            self.KsInfiniiVisionX.close()  # Close communications interface to scope
            sys.exit("Exiting script.")

    def Acquire(self,Delay, MeasChan, TrigChan, ChanName, Filepath, Save=1, Plot=0, Average=64):
        try:

            DATA = {}

            self.KsInfiniiVisionX.query(":STOP;*OPC?")  # Scope always should be stopped when making changes.

            ## Whatever is needed

            ## For this example, the scope will be forced to trigger on the (power) LINE voltage so something happens
            self.KsInfiniiVisionX.write(
                ":TRIGger:SWEep NORMal")  # Always use normal trigger sweep, never auto (Except for DC)
            # KsInfiniiVisionX.write(":TRIGger:SWEep AUTO") # Always use normal trigger sweep, never auto (Except for DC)
            self.KsInfiniiVisionX.query(":TRIGger:EDGE:SOURce Chan" + str(
                TrigChan) + ";*OPC?")  # This line simply gives the scope something to trigger on

            ## Clear the display (only so the user can see the waveform being acquired, otherwise this is not needed at all)
            self.KsInfiniiVisionX.write(":CDISplay")

            ###############################################################################
            ## Calculate acquisition timeout/wait time by short, overestimate method

            ## Create some default variables
            N_AVERAGES = Average
            N_SEGMENTS = 1
            if Delay == 'No':
                Delay = float(self.KsInfiniiVisionX.query(":TIMebase:DELay?"))
            ## Get some info about the scope time base setup
            self.KsInfiniiVisionX.write(':TIMEBASE:DELAY ' + str(Delay))
            HO = float(self.KsInfiniiVisionX.query(":TRIGger:HOLDoff?"))
            T_RANGE = float(self.KsInfiniiVisionX.query(":TIMebase:RANGe?"))
            T_POSITION = float(self.KsInfiniiVisionX.query(":TIMebase:POSition?"))

            ## Determine Acquisition Type and Mode:
            ACQ_TYPE = str(self.KsInfiniiVisionX.query(":ACQuire:TYPE?").strip("\n"))
            ACQ_MODE = str(self.KsInfiniiVisionX.query(":ACQuire:MODE?").strip("\n"))
            if ACQ_MODE == "SEGM":
                N_SEGMENTS = float(self.KsInfiniiVisionX.query(":ACQuire:SEGMented:COUNt?"))
                ## Note that if there is a lot of analysis associated segments, e.g. serial data decode, the timeout will likely need to be longer than calculated.
                ## The user is encouraged to manually set up the scope in this case, as it will be used, and time it, and use that, with a little overhead.
                ## Blocking method is recommended for Segmented Memory mode.
            elif ACQ_TYPE == "AVER":
                self.KsInfiniiVisionX.write(":ACQuire:COUNt " + str(int(Average)))
                N_AVERAGES = float(self.KsInfiniiVisionX.query(":ACQuire:COUNt?"))  # Write if you want to change

            ## Calculate acuisition timeout by overestimate method:
            self.SCOPE_ACQUISITION_TIME_OUT = (float(self.TIME_TO_TRIGGER) * 1.1 + (
                        T_RANGE * 2.0 + abs(T_POSITION) * 2.0 + HO * 1.1 + float(
                    self.TIME_BETWEEN_TRIGGERS) * 1.1) * N_SEGMENTS * N_AVERAGES) * 1000.0  # Recall that PyVisa timeouts are in ms, so multiply by 1000
            ## Ensure the timeout is no less than 10 seconds
            if self.SCOPE_ACQUISITION_TIME_OUT < 10000.0:
                self.SCOPE_ACQUISITION_TIME_OUT = 10000.0

            ###############################################################################
            ## Acquire Signal

            self.blocking_method()

            ###############################################################################
            ## Do Something with data... save, export, additional analysis...

            ## For example, make a peak-peak voltage measurement on channel X + data acquisition:

            Vpp = str(self.KsInfiniiVisionX.query("MEASure:VPP? CHAN" + str(MeasChan))).strip(
                "\n")  # The result comes back with a newline, so remove it with .strip("\n")
            Vmean = str(self.KsInfiniiVisionX.query(":MEASure:VAVerage? CHAN" + str(MeasChan))).strip("\n")
            Vamp = str(self.KsInfiniiVisionX.query(":MEASure:VAMPlitude? CHAN" + str(MeasChan))).strip("\n")
            # Vmax = str(KsInfiniiVisionX.query(":MEASure:VMAX? CHAN"+str(MeasChan))).strip("\n")
            # Getting Data and converting for save/plots :

            self.KsInfiniiVisionX.write(':WAV:FORM ASC')
            self.KsInfiniiVisionX.write(':WAV:SOUR CHAN' + str(MeasChan))
            raw = self.KsInfiniiVisionX.query(':WAVeform:DATA?')

            try:
                DATA[ChanName] = [float(i) for i in raw[11:].split(',')]
                print('|     ' + str(len(DATA[ChanName])) + '    ', end='')
                print('|     ' + Vpp + '    |', end='')
                # print('\t\t\t\t\t\t Number of points : '+str(len(DATA[ChanName])) +"\t\t\t\t\t\t Vm Ch1 = " + Vmean + " V\n")
                # print('____________/-------------------')

            except:
                print(DATA.keys())
                print(raw)
                print("An error as occured during acquisition.\n")

            # Getting TimeBase :
            T = float(self.KsInfiniiVisionX.query(':TIM:SCAL?'))
            Timescale0 = [ka * T * 10 / len(DATA[ChanName]) for ka in range(len(DATA[ChanName]))]
            DATA['TimeScale'] = Timescale0

            # if Plot == 1 :
            #     plotT = [ht *1e3 for ht in Timescale0]
            #     plt.rc('xtick', labelsize=20)
            #     plt.rc('ytick', labelsize=20)
            #     plt.plot(plotT, DATA[ChanName])
            #     plt.title('Channel n°' + str(MeasChan) + ': ' + ChanName,fontsize=28)
            #     plt.xlabel("Time (ms)", fontsize=28)
            #     plt.ylabel("Amplitude (V)", fontsize=28)
            #     plt.grid()

            #     plt.show()

            # Saving DATA under .txt :
            if Save == 1:
                # Saving data #
                os.makedirs(os.path.dirname(Filepath), exist_ok=True)
                with open(Filepath, 'a') as f:
                    print(DATA, file=f)
                    time.sleep(1)

            #######################################################################
            ## Done - cleanup
            #######################################################################

            self.KsInfiniiVisionX.clear()  # Clear scope communications interface
            # KsInfiniiVisionX.close() # Close communications interface to scope
            # Do not close if repeated acquisitions
        except KeyboardInterrupt:
            self.KsInfiniiVisionX.clear()
            self.KsInfiniiVisionX.query(":STOP;*OPC?")
            self.KsInfiniiVisionX.write(":SYSTem:LOCK 0")
            self.KsInfiniiVisionX.clear()
            self.KsInfiniiVisionX.close()
            sys.exit("User Interupt.  Properly closing scope and aborting script.")
        except Exception:
            self.KsInfiniiVisionX.clear()
            self.KsInfiniiVisionX.query(":STOP;*OPC?")
            self.KsInfiniiVisionX.write(":SYSTem:LOCK 0")
            self.KsInfiniiVisionX.clear()
            self.KsInfiniiVisionX.close()
            sys.exit("Something went wrong.  Properly closing scope and aborting script.")

        return DATA[ChanName], Timescale0, Vmean



    def get_acquisition(self):
        """
        H. Babashah - get acquisition.
        """

        return np.linspace(1,100,300), np.random.rand(300)
    def set_parameter(self,parameter):
        """
        H. Babashah - get acquisition.
        """
        print(parameter)


    def stop(self):
        print("Exiting Scope properly.\n")
        self.KsInfiniiVisionX.clear()  # Clear scope communications interface; a device clear aborts a digitize and clears the scope's IO interface..
        ## Don't do a *CLS.  If you do, you won't be able to do a meaningful :SYSTem:ERRor? query as *CLS clears the error queue
        self.KsInfiniiVisionX.close()  # Close communications interface to scope
        sys.exit
