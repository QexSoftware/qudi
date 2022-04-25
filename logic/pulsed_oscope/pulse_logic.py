from qtpy import QtCore
from collections import OrderedDict
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge
import numpy as np
import time
import datetime
import matplotlib.pyplot as plt

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.connector import Connector
from core.configoption import ConfigOption
from core.statusvariable import StatusVar

class PULSElogic(GenericLogic):

    # Connectors
    scope = Connector(interface='dummy_interface')
    mw_source = Connector(interface='dummy_interface')
    pulser= Connector(interface='dummy_interface')
    savelogic = Connector(interface='SaveLogic')
    taskrunner = Connector(interface='TaskRunner')
    time_start = StatusVar('time_start', 0)# start time
    pcw = StatusVar('pcw', -10)# CW power
    threshold = StatusVar('threshold', 2.85e9)# sweep frequency min
    time_reference = StatusVar('time_reference', 1e-3)# sweep frequency max
    time_signal = StatusVar('time_signal', 1e6)# sweep frequency step
    npts = StatusVar('npts', 40)# number of points
    time_stop = StatusVar('time_stop', 0.001)# stop time
    pulse_type = StatusVar('pulse_type', 'T1')# stop time


    # Update signals
    SigDataUpdated = QtCore.Signal(np.ndarray, np.ndarray)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.threadlock = Mutex()

    def on_activate(self):

        # Get connectors
        self._mw_device = self.mw_source()
        self._scope = self.scope()
        self._pulser = self.pulser()
        self._save_logic = self.savelogic()
        self._taskrunner = self.taskrunner()

        """ Needs to be implemented
        # Get hardware constraints
        limits = self.get_hw_constraints()
        """

        self.data_freq = np.array([])
        self.data_spectrum = np.array([])

    def on_deactivate(self):
        """
        Deinitialisation performed during deactivation of the module.
        """
        # Disconnect signals
        #self.sigDataUpdated.disconnect()

    def start_data_acquisition(self):
        if self.pulse_type!='T1':
            self._mw_device.set_trigger_mode(0)
            self._mw_device.on()
            print('MW is on')


        Pulse_Length=100e-6
        self.navg=25
        ChannelTrigNumber = 2  # ACQ_chan trigger

        ChannelNumber = 1;

        self._scope.set_trigger_source(ChannelTrigNumber)
        self._scope.set_Center_Tscale(1, Pulse_Length)  # 1.25*10
        self._scope.set_acquisition_type(1)  # AVG type ACQ
        self._scope.set_acquisition_count(self.navg)  # set the number of avg for oscope
        self._scope.set_trigger_sweep(1)  # set normal mode for ACQ of Oscope


        var_sweep_type='linear'
        if var_sweep_type == 'log':
            var_range = np.logspace(np.log10(self.time_start), np.log10(self.time_stop), self.npts, base=10)
        else:
            var_range = np.linspace(self.time_start, self.time_stop, int(self.npts))

        VARResult = []
        for variable in var_range:
            self._pulser.set_pulse_measurement(variable, self.pulse_type)

            self._pulser.start_stream()

            DATA = self._scope.get_data([ChannelNumber])

            PulseAmp, PulseTime = DATA[ChannelNumber], DATA[0]
            # set min as zero
            minPulseAmp = min(PulseAmp)

            if minPulseAmp > 0:
                PulseAmp = [(ka - abs(minPulseAmp)) for ka in PulseAmp]
            else:
                PulseAmp = [(ka + abs(minPulseAmp)) for ka in PulseAmp]

            # Normalize to max avg
            maxindPulseAmp = np.argmax(PulseAmp)
            maxPulseAmpAvg = abs(np.mean(PulseAmp[int(maxindPulseAmp):int(maxindPulseAmp + 100)]))
            PulseAmp = [kar / abs(maxPulseAmpAvg) for kar in PulseAmp]
            # pl.plot(PulseAmp)

            ind_L_pulseAmp = self.ThresholdL(PulseAmp,  self.threshold)
            ind_R_pulseAmp = self.ThresholdR(PulseAmp,  self.threshold)
            Pulse_Dur = 100e-6
            TimeRes = PulseTime[4] - PulseTime[3]
            IntTimeSampleSignal = int(np.floor(self.time_signal / TimeRes))
            IntTimeSampleReference = int(np.floor(self.time_reference / TimeRes))
            Signal = np.trapz(PulseAmp[ind_L_pulseAmp:ind_L_pulseAmp + IntTimeSampleSignal], dx=5)  # Signal Window
            Reference = np.trapz(PulseAmp[ind_R_pulseAmp - IntTimeSampleReference:ind_R_pulseAmp], dx=5)  # Reference Window

            VARResult.append(Signal / Reference)

     #self._mw_device.off()
        self._pulser.start_stream()

        self.SigDataUpdated.emit(var_range, np.array(VARResult))
        if self.pulse_type!='T1':
            self._mw_device.off()
            print('MW is OFF')
    def set_pulse(self, time_start,time_stop,npts):
        #self._mw_device.set_time_start(time_start)
        self.time_start = time_start
        self.time_stop = time_stop
        self.npts = npts
    def set_pulse_type(self, pulse_type):
        self.pulse_type=pulse_type

    def set_pcw(self, pcw):
        #self._mw_device.set_pcw(pcw)
        self.pcw = pcw

    def set_pulse_analysi_param(self, threshold,time_reference,time_signal):
        #self._mw_device.set_sweep_param(threshold,time_reference,time_signal)
        self.threshold = threshold
        self.time_reference = time_reference
        self.time_signal = time_signal

    def ThresholdL(self,data,t_v):

        t_ind = 0
        for kop in range(len(data)) :
            if data[kop] >= t_v :
                t_ind = kop
                break
        if t_ind==0:
            print('Probably could not find the begining of the pulse, zero set as begining')
        return t_ind

    def ThresholdR(self,data,t_v):

        t_ind = -1
        for kop in range(len(data)) :
            if data[-kop-1] >= t_v :
                t_ind = -kop-1
                break
        if t_ind==-1:
            print('Probably could not find the begining of the pulse, zero set as begining')
        return t_ind
