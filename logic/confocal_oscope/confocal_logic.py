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

class Confocallogic(GenericLogic):

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
    xmin = StatusVar('xmin', 0)# sweep x min
    xmax = StatusVar('xmax', 1e-6)# sweep x max
    xnpts = StatusVar('xnpts', 10)# sweep x points
    ymin = StatusVar('ymin', 0)# sweep y min
    ymax = StatusVar('ymax', 1e-6)# sweep y max
    ynpts = StatusVar('ynpts', 10)# sweep y points
    xpos = StatusVar('xpos', 0)# x position
    ypos = StatusVar('ypos', 0)# y position

    # Update signals
    SigDataUpdated = QtCore.Signal(np.ndarray, np.ndarray)
    SigConfocalDataUpdated= QtCore.Signal(np.ndarray)
    SigToggleAction= QtCore.Signal()
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
         V2C_coef=0.1*1e6 # It should be calibrated based on the acquired image
         V_Xvaluemin = self.xmin*V2C_coef
         V_Xvaluemax = self.xmax*V2C_coef
         V_Xvaluepoints = self.xnpts
         V_Yvaluemin = self.ymin*V2C_coef
         V_Yvaluemax = self.ymax*V2C_coef
         V_Yvaluepoints = self.ynpts
         V_XvalueRange = np.linspace(V_Xvaluemin, V_Xvaluemax, int(V_Xvaluepoints))
         V_YvalueRange = np.linspace(V_Yvaluemin, V_Yvaluemax, int(V_Yvaluepoints))
         i = -1;8
         a = np.zeros((int(np.size(V_XvalueRange)), int(np.size(V_YvalueRange))))
         self._scope.set_Auto_Offset(1)
         self._scope.set_Auto_Vscale(1)
         IntegrationTime=2e-6
         self._scope.set_Center_Tscale(1,IntegrationTime/1.25) # 1.25*10
         self._scope.set_trigger_sweep(1) # set normal mode for ACQ of Oscope
         ChannelNumber = 1 # ACQ Chan Number
         ChannelTrigNumber = 2 # ACQ_chan trigger
         self._scope.set_trigger_source(ChannelTrigNumber)
         #AutoVscale=True
         for V_Xvalue in V_XvalueRange:
             i = i + 1
             j = -1
             for V_Yvalue in V_YvalueRange:
                 j = j + 1

                 self._pulser.set_confocal(V_Xvalue,V_Yvalue)

                 self._pulser.start_stream()
                 #if AutoVscale == True:
                 #    self._scope.set_Auto_Vscale(1)
                 #    AutoVscale = False
                 DATA = self._scope.get_data([ChannelNumber])#(Delay, MeasChan, TrigChan, ChanName, Filepath, Save, Plot,
                                       #Average=2);
                 a[i,j] = np.mean(DATA[ChannelNumber])
                 self.SigConfocalDataUpdated.emit(a) # np.random.rand(5, 5)
         self.SigDataUpdated.emit(np.array(DATA[0]), np.array(DATA[ChannelNumber]))
         self.SigToggleAction.emit()

    def set_cordinate_sparam(self,xmin,xmax,xnpts,ymin,ymax,ynpts):
        self.xmin = xmin
        self.xmax = xmax
        self.xnpts = xnpts
        self.ymin = ymin
        self.ymax = ymax
        self.ynpts = ynpts

    def set_move_to_position(self, xpos, ypos):
        self.xpos = xpos
        self.ypos = ypos
    def move_to_position(self):
        self._pulser.set_confocal(self.xpos, self.ypos)
        self._pulser.start_stream()

    def set_fcw(self, fcw):
        self._mw_device.set_fcw(fcw)
        self.fcw = fcw
    def set_pcw(self, pcw):
        self._mw_device.set_pcw(pcw)
        self.pcw = pcw
    def set_ODMR(self, stime,npts):
        self._pulser.set_ODMR(stime,npts)
      #  self._mw_device.set_ODMR(stime,npts)
        self.stime = stime
        self.npts = npts

    def set_sweep_param(self, fmin,fmax,fstep):
        self._mw_device.set_sweep_param(fmin,fmax,fstep)
        self.fmin = fmin
        self.fmax = fmax
        self.fstep = fstep