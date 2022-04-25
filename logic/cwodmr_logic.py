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

class CWODMRlogic(GenericLogic):

    # Connectors
    scope = Connector(interface='dummy_interface')
    mw_source = Connector(interface='dummy_interface')
    pulser= Connector(interface='dummy_interface')
    savelogic = Connector(interface='SaveLogic')
    taskrunner = Connector(interface='TaskRunner')
    fcw = StatusVar('fcw', 2.87e9)# CW frequency
    pcw = StatusVar('pcw', -10)# CW power
    fmin = StatusVar('fmin', 2.85e9)# sweep frequency min
    fmax = StatusVar('fmax', 2.89e9)# sweep frequency max
    fstep = StatusVar('fstep', 1e6)# sweep frequency step
    npts = StatusVar('npts', 40)# number of points
    stime = StatusVar('stime', 0.001)# Step time
    navg = StatusVar('navg', 40)# number of averages
    int_time = StatusVar('int_time', 100e-6)# integration time

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
     #   for i in range(30):
        self._mw_device.set_trigger_mode(1)

        self._mw_device.on()


        SweepStep = 5e-3;
        IntegrationTime = self.int_time;

        IntegrationTime = self.npts * self.stime + 5* self.stime;
        print(IntegrationTime)

        print(self.npts)

        print(self.stime)

        ChannelTrigNumber = 2  # ACQ_chan trigger
        self._scope.set_trigger_source(ChannelTrigNumber)
        self._scope.set_Center_Tscale(1, IntegrationTime / 1.25)  # 1.25*10
        self._scope.set_acquisition_type(1) #AVG type ACQ
        self._scope.set_acquisition_count(self.navg) # set the number of avg for oscope
        self._scope.set_trigger_sweep(1)  # set normal mode for ACQ of Oscope

        ChannelNumber = 1;

        self._pulser.set_ODMR(self.stime, self.npts)

        self._pulser.start_stream()
        print('asggggggg')
        DATA = self._scope.get_data([ChannelNumber])          # get the data from oscope
        self._mw_device.off()

    #      time.sleep(0.5)
        self.SigDataUpdated.emit(np.linspace(self.fmin,self.fmax,np.size(np.array(DATA[0]))), np.array(DATA[ChannelNumber]))
    def set_fcw(self, fcw):
        self._mw_device.set_fcw(fcw)
        self.fcw = fcw
    def set_pcw(self, pcw):
        self._mw_device.set_pcw(pcw)
        self.pcw = pcw
    def set_ODMR(self, stime,npts):
        self.stime = stime
        self.npts = npts
    def set_scope_param(self,int_time,navg):
        self.int_time = int_time
        self.navg = navg
        print('int set')
        print(self.int_time)

    def set_sweep_param(self, fmin,fmax,fstep):
        self._mw_device.set_sweep_param(fmin,fmax,fstep)
        self.fmin = fmin
        self.fmax = fmax
        self.fstep = fstep