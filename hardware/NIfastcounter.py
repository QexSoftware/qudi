# Hossein PIcoharp
# -*- coding: utf-8 -*-
"""
This file contains the Qudi hardware module for the PicoHarp300.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import ctypes
from ctypes import byref, POINTER
import numpy as np
import time
from qtpy import QtCore
import PyDAQmx as daq

from core.module import Base
from core.configoption import ConfigOption
from core.util.modules import get_main_dir
from core.util.mutex import Mutex
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints
from interface.slow_counter_interface import CountingMode
from interface.fast_counter_interface import FastCounterInterface



class NIFastCounter(Base, SlowCounterInterface, FastCounterInterface):
    """ Hardware class to use the NI card as a fast counter.

    Written by Hossein Babashah, Hoda Shirzad

    Example config for copy-paste:

    NIfastcounter:
        module.Class: 'NIfastcounter.NIFastCounter'
    """

    sigReadoutNI = QtCore.Signal()
    sigStart = QtCore.Signal()

    def __init__(self, config, **kwargs):
        print('__init__')
        # Modify ONLY for PulsedMeasurements
        self.useNIcard = 0# analog input, APD
        self.useNIcardDI = 1 # photon counter, SPC
        super().__init__(config=config, **kwargs)

        # Just some default values:
        self._bin_width_ns = 2
        self._record_length_ns = 100 *1e9

        self._photon_source2 = None #for compatibility reasons with second APD
        self._count_channel = 1

        #locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        print('on_activate')

        """ Activate and establish the connection to NI card and initialize.
        """


        self.sigStart.connect(self.start_measure)
        self.sigReadoutNI.connect(self.get_fresh_data_loop, QtCore.Qt.QueuedConnection) # ,QtCore.Qt.QueuedConnection
        self.result = []
        time.sleep(0.2)

    def on_deactivate(self):
        print('on_deactivate')

        """ Deactivates and disconnects the device.
        """

        self.sigReadoutNI.disconnect()



    def start(self, acq_time):
        print('start')

        """ Start acquisition for 'acq_time' ms.
        """

        if self.useNIcard == 1:#Analog
            self.analog_input2 = daq.Task()
            self.read2 = daq.int32()
            self.myNIdata = np.zeros((self.NumberofSamples * self.Nchannel,), dtype=np.float64)
            self.analog_input2.CreateAIVoltageChan("Dev1/ai3", "myChannelai3", daq.DAQmx_Val_Diff, self.VoltageMin,
                                                   self.VoltageMax,
                                                   daq.DAQmx_Val_Volts, None)  # SYNC
            self.analog_input2.CreateAIVoltageChan("Dev1/ai2", "myChannelai2", daq.DAQmx_Val_Diff, self.VoltageMin,
                                                   self.VoltageMax,
                                                   daq.DAQmx_Val_Volts, None)  # PD
            self.analog_input2.CfgAnlgEdgeStartTrig("myChannelai3", daq.DAQmx_Val_RisingSlope, 1)  # SYNC theshold

            self.analog_input2.CfgSampClkTiming("", self.Sampling_rate, daq.DAQmx_Val_Falling,
                                                daq.DAQmx_Val_FiniteSamps,
                                                self.NumberofSamples)

            self.analog_input2.StartTask()

        if self.useNIcardDI == 1: #digital

            try:
                self.Counter1.StopTask()
                self.Counter1.ClearTask()
                self.Counter2.StopTask()
                self.Counter2.ClearTask()
                self.Clock.StopTask()
                self.Clock.ClearTask()
                #print('task stoped1')
            except:
                pass

            self.Counter1 = daq.Task()
            self.Counter2 = daq.Task()
            self.Clock = daq.Task()
            read = daq.c_ulong()
            read2 = daq.c_uint64()
            rate = 1000
            n_samples = 1000
            duty_cycle = 0.5

            my_clock_channel = '/Dev3/Ctr2' #Hoda: '/Dev1/Ctr2' Hossein:'/Dev3/Ctr2' (should go to the config file)
            self.Clock.CreateCOPulseChanFreq(my_clock_channel,
                                             "myClockTask",
                                             daq.DAQmx_Val_Hz,
                                             daq.DAQmx_Val_Low,
                                             0,
                                             1 / float(self.period),
                                             duty_cycle,
                                             )

            self.Clock.CfgImplicitTiming(
                daq.DAQmx_Val_ContSamps,
                1000  # the buffer size
            )

            ch2 ='/Dev3/Ctr1' #Hoda: '/Dev1/Ctr1' Hossein: '/Dev3/Ctr1'
            self.Counter2.CreateCISemiPeriodChan(
                ch2,
                'Counter Channel 1',  # The name to assign to the created virtual channel.
                0,  # Expected minimum count value
                2,  # Expected maximum count value

                daq.DAQmx_Val_Ticks,  # The units to use to return the measurement. Here are timebase ticks
                ''
            )
            #Hossein:
            self.Counter2.SetCISemiPeriodTerm(
                ch2,  # assign a named Terminal
                '/Dev3/Ctr2' + 'InternalOutput')
            self.Counter2.SetCICtrTimebaseSrc(ch2,
                                              '/Dev3/PFI1')  # PFI7 is for dev1 and PFI1 for dev3 (It is for photon Counter(


            # Hoda:
            '''
            self.Counter2.SetCISemiPeriodTerm(
                ch2,  # assign a named Terminal
                '/Dev1/Ctr2' + 'InternalOutput')
            self.Counter2.SetCICtrTimebaseSrc(ch2,
                                              '/Dev1/PFI8')  # photon source
            '''
            self.Counter2.CfgImplicitTiming(daq.DAQmx_Val_ContSamps,
                                            2 ** 25
                                            # 2**30 is maximum. buffer length which stores  temporarily the number of generated samples
                                            )
            ch = '/Dev3/Ctr0'#Hoda: '/Dev1/Ctr0', Hossein: '/Dev3/Ctr0'
            self.Counter1.CreateCISemiPeriodChan(
                ch,  # use this counter channel. The name of the counter to use to create virtual channels.
                'Counter Channel 1',  # The name to assign to the created virtual channel.
                0,  # Expected minimum count value
                2,  # Expected maximum count value

                daq.DAQmx_Val_Ticks,  # The units to use to return the measurement. Here are timebase ticks
                ''  # customScaleName, in case of different units(DAQmx_Val_FromCustomScale).
                )
            '''
            self.Counter1.SetCISemiPeriodTerm(
                ch,
                '/Dev1/Ctr2' + 'InternalOutput')
            self.Counter1.SetCICtrTimebaseSrc(ch,
                                        '/Dev1/PFI0') #sync
            '''
            #Hossein:
            self.Counter1.SetCISemiPeriodTerm(
                ch,
                '/Dev3/Ctr2' + 'InternalOutput')
            self.Counter1.SetCICtrTimebaseSrc(ch,
                                              '/Dev3/PFI2')  # for Dev1 was PFI0


            self.Counter1.CfgImplicitTiming(daq.DAQmx_Val_ContSamps,
                                            2 ** 25
                                            # 2**30 is maximum.
                                            )
            try:
                self.Counter1.StartTask()
                self.Counter2.StartTask()

            except Exception as e:
                print('exception Happened')
                print(e)
                self.Clock.StopTask()
                self.Clock.ClearTask()
            self.Clock.StartTask()


    def stop_device(self):


        """ Stop the measurement."""
        self.meas_run = False
        self.firsttimeNI = 1
        try:
            self.Counter1.StopTask()
            self.Counter1.ClearTask()
            self.Counter2.StopTask()
            self.Counter2.ClearTask()
            self.Clock.StopTask()
            self.Clock.ClearTask()
            print('Task Stopped2')
        except:
            pass
        self.analog_input2.StopTask()
        self.analog_input2.ClearTask()


    # =========================================================================
    #  Functions for the SlowCounter Interface
    # =========================================================================

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        print('set_up_clock')
        """Ensure Interface compatibility.
        """

        return 0

    def set_up_counter(self, counter_channels=1, sources=None,
                       clock_channel=None):

        """ Ensure Interface compatibility. The counter allows no set up.

        @param string counter_channel: Set the actual channel which you want to
                                       read out. Default it is 0. It can
                                       also be 1.
        @param string photon_source: is not needed, arg will be omitted.
        @param string clock_channel: is not needed, arg will be omitted.

        @return int: error code (0:OK, -1:error)
        """
        self._count_channel = counter_channels

        return 0

    def get_counter_channels(self):
        print('get_counter_channels')
        """ Return one counter channel. """
        return ['Ctr0']

    def get_constraints(self):
        print('get_constraints')
        """ Get hardware limits of NI device.

        @return SlowCounterConstraints: constraints class for slow counter

        FIXME: ask hardware for limits when module is loaded
        """
        constraints = dict()
        print('get constraints1')
        print('get constraints2')
        # the unit of those entries are seconds per bin. In order to get the
        # current binwidth in seonds use the get_binwidth method.
        constraints['hardware_binwidth_list'] = [1e-9, 10e-9, 50e-9, 100e-9, 0.5e-6, 1e-6, 1.5e-6, 2e-6]
        # TODO: think maybe about a software_binwidth_list, which will
        #      postprocess the obtained counts. These bins must be integer
        #      multiples of the current hardware_binwidth

        return constraints

    def get_counter(self, samples=None):

        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return float: the photon counts per second
        """
        time.sleep(0.05)
        #return [self.get_count_rate(self._count_channel)]
        return 0

    def close_counter(self):

        """ this command will do
        nothing and is only here for SlowCounterInterface compatibility.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def close_clock(self):
        """this command will do
        nothing and is only here for SlowCounterInterface compatibility.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    # =========================================================================
    #  Functions for the FastCounter Interface
    # =========================================================================

    # FIXME: The interface connection to the fast counter must be established!

    def configure(self, bin_width_ns, record_length_ns, number_of_gates=0):
        print('configure')
        self.startSweep = 0
        self.mycounter = 1
        self.numberofsweeps = 1
        """
        Configuration of the fast counter.
        bin_width_ns: Length of a single time bin in the time trace histogram
                      in nanoseconds.
        record_length_ns: Total length of the timetrace/each single gate in
                          nanoseconds.
        number_of_gates: Number of gates in the pulse sequence. Ignore for
                         ungated counter.
        """
        ''' Just to check:
        self.Hmode = 0
        if self.Hmode == 1:
            self.outputfile = open("HosTest.out", "wb+")
            
        '''
        #print(self.get_binwidth())
        self.testStatue = 0
        self._bin_width_ns = bin_width_ns * 1e9  # the input is in second I believe and not nanosecond
        self._record_length_ns = record_length_ns * 1e9  #

        self.mybins = np.arange(0, self._record_length_ns * 1e3, self._bin_width_ns * 1e3, dtype='float')  # picosecond
        self.data_trace = np.zeros(int(np.size(self.mybins)) - 1, dtype=np.int64)  # modified
        self.data_trace_helper = self.data_trace  # modified
        self.data_trace_helper20 = np.array([], dtype=np.int64)

        self._number_of_gates = number_of_gates
        self.startflag = 0
        # FIXME: actualle only an unsigned array will be needed. Change that later. WE fixed it!Not sure though!

        self.count = int(number_of_gates)
        print('Picoharp/binwidth=')
        print(self._bin_width_ns)
        print(self.get_binwidth())
        print(self._bin_width_ns * 1e3)
        print(self._record_length_ns * 1e3)
        print('Hello')
        self.mybins[0] = 1e-12
        self.firsttimeNI = 1
        self.result = []

        ####################### NI Card
        Resolution = self._bin_width_ns * 1e-9  # it should be in seconds
        Tm = self._record_length_ns * 1e-9  # it should be in seconds
        self.ACQtime = self._record_length_ns * 1e-9  # 10 second is ok, ACQ time in seconds
        print('resolution')
        print(self._bin_width_ns * 1e-9)
        self.period = Resolution * 2  # period/2 is the resolution
        self.NumberofSamples = int(np.ceil(Tm / Resolution))
        self.Sampling_rate = np.floor(1 / Resolution)
        self.numSampsPerChan = self.NumberofSamples
        self.Nchannel = 2
        self.myNIdata = np.zeros((self.NumberofSamples * self.Nchannel,), dtype=np.float64) #(Hoda: , seems to be unnecessary)
        self.VoltageMin = 0
        self.VoltageMax = 5

        print('configuration is complete!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        return bin_width_ns, record_length_ns, number_of_gates

    def get_status(self):
        """
        Receives the current status of the Fast Counter and outputs it as
        return value.
        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        if self.useNIcard or self.useNIcardDI == 1:
            return 1
        else:
            return -1

    def pause_measure(self):
        print('pause_measure')

        """
        Pauses the current measurement if the fast counter is in running state.
        """
        try:
            self.stop_measure()
            self.meas_run = False
            print('pause measure l275')
        except:
            print('measurement not pauses')

    def continue_measure(self):
        print('continue_measure')

        """
        Continues the current measurement if the fast counter is in pause state.
        """
        self.meas_run = True
        self.start(self._record_length_ns / 1e6)  # /1e6 was here

    def is_gated(self):
        # print('is_gated')

        """
        Boolean return value indicates if the fast counter is a gated counter
        (TRUE) or not (FALSE).
        """
        return False

    def get_binwidth(self):
        print('get_binwidth')
        """
        returns the width of a single timebin in the timetrace in seconds
        """
        width_in_seconds = self._bin_width_ns * 1e-9
        print('inside get binwidth width in sec')
        print(width_in_seconds)

        # FIXME: Must be implemented
        return width_in_seconds



    def get_data_trace(self):
        """
        in this method for Analog signal, we find the pulses, and add the new mwasured data for each pulse at each sweep.


        """

        timeout = 10.0


        if self.useNIcard == 1:
           # time.sleep(0.01)
            self.analog_input2.ReadAnalogF64(self.numSampsPerChan, timeout, daq.DAQmx_Val_GroupByChannel, self.myNIdata,
                                             self.NumberofSamples * self.Nchannel, ctypes.byref(self.read2), None)

        if self.useNIcard == 1: #Analog
            print('NIcard')
            Sync = self.myNIdata[0:self.NumberofSamples] #first half o myNIdata array
            Laser = self.myNIdata[self.NumberofSamples:self.NumberofSamples * 2] #second half of myNIdata array
            a = np.argwhere(Sync > 1.5) #a column contains of the indexes of sync array's elements which have values above 1.5
            # print(a)
            try:
                ArraySize = np.max(np.diff(np.transpose(a), 1)) #the difference between the indexes of each 2 sync in a row gives us the pulse length.
                LaserSum = np.zeros(ArraySize + 1) # we add one to the pulse length to compensate any possible mistake in previous steps (specially finding a sync)

                for i in range(np.size(a) - 1): #for each sync except the last one:
                    # print(a[i])f
                    if i != int(np.size(a)) - 1: #adding all the pulses in one sweep togeather
                        LaserSum[0:int(a[i + 1]) - int(a[i]) + 1] = LaserSum[0:int(a[i + 1]) - int(a[i]) + 1] + Laser[int(a[i]):int(a[i + 1]) + 1]
                if self.firsttimeNI == 1:
                    self.LaserSumhelper = np.zeros(ArraySize + 1)
                    self.firsttimeNI = 0
                self.LaserSumhelper = LaserSum + self.LaserSumhelper
                self.data_trace = self.LaserSumhelper #?Hoda: adding all pulses in all sweeps togeather?
                self.analog_input2.StopTask()
                self.analog_input2.ClearTask()
                if self.numberofsweeps < 30000 and self.meas_run:  # NI card number of Sweeps
                    self.numberofsweeps = self.numberofsweeps + 1
                    self.start_measure()
            except:
                if np.size(a) == 1:
                    print('Increase the acq time')
                else:
                    print('Not able to measure, check sync')




        if self.useNIcardDI == 1:
            _RWTimeout = 2
            n_read_samples = daq.int32()

            samples = np.int(np.ceil(self.ACQtime / self.period)) # (ACQtime/resolution)/2

            self.count_data = np.empty((1, 2 * samples), dtype=np.uint32)
            self.count_data2 = np.empty((1, 2 * samples), dtype=np.uint32)

            self.Counter1.ReadCounterU32(2 * samples,
                                         _RWTimeout,
                                         self.count_data[0],
                                         2 * samples,
                                         byref(n_read_samples),
                                         None)
            self.Counter2.ReadCounterU32(2 * samples,
                                         _RWTimeout,
                                         self.count_data2[0],
                                         2 * samples,
                                         byref(n_read_samples),
                                         None)  # PFI7

        if not self.meas_run:
            print('measurement is done2')
        # self.sigReadoutNI.emit() # loop

        if self.useNIcardDI == 1:

            Sync = self.count_data[0, :]
            Laser = self.count_data2[0, :]
            a = np.argwhere(Sync > 0.5)
            print(a)
            try:
                LaserSum = np.zeros(1) #Hoda: Akhe Chera? :))
                ArraySize = np.max(np.diff(np.transpose(a), 1))
                LaserSum = np.zeros(ArraySize + 1)
                for i in range(np.size(a) - 1):
                    if i != int(np.size(a)) - 1:
                        LaserSum[0:int(a[i + 1]) - int(a[i]) + 1] = LaserSum[0:int(a[i + 1]) - int(a[i]) + 1] + Laser[int(a[i]):int(a[i + 1]) + 1]
                if self.firsttimeNI == 1:
                    self.LaserSumhelper = np.zeros(ArraySize + 1)
                    self.firsttimeNI = 0
                self.LaserSumhelper[0:np.size(LaserSum)] = LaserSum + self.LaserSumhelper[0:np.size(LaserSum)]  # self.LaserSumhelper[0:np.size(LaserSum)]=LaserSum+self.LaserSumhelper[0:np.size(LaserSum)]
                self.data_trace = self.LaserSumhelper
                if self.numberofsweeps < 300000 and self.meas_run:  # NI card number of Sweeps
                    self.numberofsweeps = self.numberofsweeps + 1
                    self.start_measure()

            except:
                if np.size(a) == 1:
                    print('Increase the acq time')
                else:
                    print('Not able to measure, check sync')
        info_dict = {'elapsed_sweeps': self.numberofsweeps,
                     'elapsed_time': None}  # TODO : implement that according to hardware capabilities
        return self.data_trace, info_dict


    def start_measure(self):

        print('start_measure')


        self.meas_run = True  # to start the measurement u need to pass this serting

        self.start(int(self._record_length_ns / 1e6))  # Measurement time in millisec (unit ms) it is acq time which should be between 1 to... ms
        # print('start measure2')
        self.sigReadoutNI.emit()
        # print('start measure3')

    def stop_measure(self):
        try:
            self.Counter1.StopTask()
            self.Counter1.ClearTask()
            self.Counter2.StopTask()
            self.Counter2.ClearTask()
            self.Clock.StopTask()
            self.Clock.ClearTask()
            print('stop device stopeed')
        except:
            pass
        print('stop_measure')
        self.numberofsweeps = 0
        """ By setting the Flag, the measurement should stop.  """
        self.firsttimeNI = 1
        self.meas_run = False

    def get_fresh_data_loop(self):

        """ This method will be run infinitely until the measurement stops. """

        if not self.meas_run:
            with self.threadlock:
                # self.unlock()
                #    print('unlock should be defined') #unlock should be defined
                try:
                    self.stop_device()
                    self.numberofsweeps = 1
                    self.mycounter = 1
                # print('measurement is done')
                except:
                    print('measurement is not stopped')
                return














