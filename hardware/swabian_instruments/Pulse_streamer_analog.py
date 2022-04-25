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
from pulsestreamer import Sequence, OutputState
from pulsestreamer import PulseStreamer
from pulsestreamer import TriggerStart, TriggerRearm

from core.module import Base
from core.configoption import ConfigOption
from interface.pulser_interface import PulserInterface, PulserConstraints, SequenceOption
from core.util.modules import get_home_dir

class Streamer(Base, dummy_interface):
    """
    H.Babashah - Hardware code for Swabian Pulse streamer.
    """
    _instrument_ip = ConfigOption(name='instrument_ip', default='192.168.2.153', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """
        H.Babashah - Inspired from Qudi - Initialisation performed during activation of the module.
        """


        # import enum types

        # import class Sequence and OutputState for advanced sequence building
        self.pulser = PulseStreamer(self._instrument_ip)

    def on_deactivate(self):
        """
        H.Babashah - Inspired from Qudi - Required tasks to be performed during deactivation of the module.
        """


    def get_acquisition(self):
        """
        H. Babashah - get acquisition.
        """

        return np.linspace(1,100,300), np.random.rand(300)

    def hello(self):
        """
        H. Babashah - get acquisition.
        """

        print('hello')
    def set_ODMR(self,SweepStep,Npts):
        LaserCh = 6
        OscopeCh = 0
        MWChTrig = 2
        SwitchCh = 1
        # MW channel is one
        # define digital levels
        HIGH = 1
        LOW = 0
        NumberOfrepeats = 3000
        SweepTime = Npts * SweepStep + 4 * SweepStep;
        Lowtime = 200e-6;  # Level sensitive
        LaserChseq = [(SweepTime * 1e9, HIGH)] * NumberOfrepeats  # 0
        OscopeTirgChseq = [((SweepTime - Lowtime) * 1e9, HIGH), (Lowtime * 1e9, LOW)] * NumberOfrepeats  # 0
        MWChTrigseq = [((SweepTime - Lowtime) * 1e9, HIGH), (Lowtime * 1e9, LOW)] * NumberOfrepeats  # 0
        SwitchChseq = [(SweepTime * 1e9, HIGH)] * NumberOfrepeats  #

        self.seq = Sequence()

        # set digital channels
        self.seq.setDigital(LaserCh, LaserChseq)
        self.seq.setDigital(OscopeCh, OscopeTirgChseq)
        self.seq.setDigital(MWChTrig, MWChTrigseq)
        self.seq.setDigital(SwitchCh, SwitchChseq)




        # reset the device - all outputs 0V
        self.pulser.reset()

        # set constant state of the device
        self.pulser.constant(OutputState.ZERO())  # all outputs 0V

        # define the final state of the Pulsestreamer - the device will enter this state when the sequence is finished
        self.final = OutputState.ZERO()

        self.start = TriggerStart.IMMEDIATE
        self.rearm = TriggerRearm.MANUAL

        self.pulser.setTrigger(start=self.start, rearm=self.rearm)
        print('ODMR is set')


    def set_confocal(self,Xvalue,Yvalue):
        LaserCh = 6
        AnalogXCh = 0
        AnalogYCh = 1
        OscopeCh = 0

        HIGH = 1
        LOW = 0
        NumberOfrepeats = 100
        dtime = 1e-3;
        pulsetype = 'Confocal'
        Lowtime = 200e-6;  # Level sensitive
        Xvalue = 1
        Yvalue = 1
        LaserChseq = [(dtime * 1e9, HIGH)] * NumberOfrepeats  # 0
        AnalogXChseq = [(dtime * 1e9, Xvalue)] * NumberOfrepeats
        AnalogYChseq = [(dtime * 1e9, Yvalue)] * NumberOfrepeats
        OscopeTirgChseq = [((dtime - Lowtime) * 1e9, HIGH), (Lowtime * 1e9, LOW)] * NumberOfrepeats  # 0
        self.seq = Sequence()

        # set digital channels
        self.seq.setDigital(LaserCh, LaserChseq)
        self.seq.setAnalog(AnalogXCh, AnalogXChseq)
        self.seq.setAnalog(AnalogYCh, AnalogYChseq)
        self.seq.setDigital(OscopeCh, OscopeTirgChseq)

        # run the sequence only once
        n_runs = 100
        # n_runs = 'INFIITE' # repeat the sequence all the time

        # reset the device - all outputs 0V
        self.pulser.reset()

        # set constant state of the device
        self.pulser.constant(OutputState.ZERO())  # all outputs 0V

        # define the final state of the Pulsestreamer - the device will enter this state when the sequence is finished
        self.final = OutputState.ZERO()

        self.start = TriggerStart.IMMEDIATE
        self.rearm = TriggerRearm.MANUAL

        self.pulser.setTrigger(start=self.start, rearm=self.rearm)

    def set_pulse_measurement(self, Variable,pulsetype):
        wl = 100e-6  # LaserPulseWidth in second

        LaserCh = 6
        OscopeCh = 0
        MWCh = 1
        # MW channel is one

        # define digital levels
        HIGH = 1
        LOW = 0
        NumberOfrepeats = 3000

        if pulsetype == 'T1':
            LaserChseq = [(wl * 1e9, HIGH), (Variable * 1e9, LOW)] * NumberOfrepeats  # 0
            OscopeTirgChseq = [(wl * 1e9, HIGH), (Variable * 1e9, LOW)] * NumberOfrepeats  # 0
            # MWChseq = [(wl*1e9+Variable*1e9, LOW)]*NumberOfrepeats #0

        self.seq = Sequence()

        if pulsetype == 'Rabi':
            tau = 100e-6
            LaserChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            OscopeTirgChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            MWChseq = [(wl * 1e9 + Variable * 1e9, LOW)] * NumberOfrepeats  # 0
            MWChseq = [(wl * 1e9 + tau * 1e9 / 2 - Variable * 1e9 / 2, LOW), (Variable * 1e9, HIGH),
                       (tau * 1e9 / 2 - Variable * 1e9 / 2, LOW)] * NumberOfrepeats  #
            self.seq.setDigital(MWCh, MWChseq)

        if pulsetype == 'Ramsey':
            pihalf = 1e-6;
            tau = 100e-6
            LaserChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            OscopeTirgChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            NIChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            MWChseq = [(wl * 1e9 + tau * 1e9 / 2 - Variable * 1e9 / 2 - pihalf * 1e9, LOW), (pihalf * 1e9, HIGH),
                       (Variable * 1e9, LOW), (pihalf * 1e9, HIGH),
                       (tau * 1e9 / 2 - Variable * 1e9 / 2 - pihalf, LOW)] * NumberOfrepeats  # 0
            self.seq.setDigital(MWCh, MWChseq)
        if pulsetype == 'Hahn_echo':
            piPulse = 255e-9;  # 235 orginal
            pihalf = piPulse / 2;
            tau = 100e-6
            LaserChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            OscopeTirgChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            NIChseq = [(wl * 1e9, HIGH), (tau * 1e9, LOW)] * NumberOfrepeats  # 0
            MWChseq = [(wl * 1e9 + tau * 1e9 / 2 - piPulse * 1e9 - Variable * 1e9 / 2, LOW), (pihalf * 1e9, HIGH),
                       (Variable * 1e9 / 2, LOW), (piPulse * 1e9, HIGH), (Variable * 1e9 / 2, LOW),
                       (pihalf * 1e9, HIGH),
                       (tau * 1e9 / 2 - 2 * Variable * 1e9 / 2 - 2 * piPulse * 1e9, LOW)] * NumberOfrepeats  # 0
            self.seq.setDigital(MWCh, MWChseq)

        # set digital channels
        self.seq.setDigital(LaserCh, LaserChseq)
        self.seq.setDigital(OscopeCh, OscopeTirgChseq)

        # run the sequence only once
        self.n_runs = 5
        # n_runs = 'INFIITE' # repeat the sequence all the time

        # reset the device - all outputs 0V
        self.pulser.reset()

        # set constant state of the device
        self.pulser.constant(OutputState.ZERO())  # all outputs 0V

        # define the final state of the Pulsestreamer - the device will enter this state when the sequence is finished
        self.final = OutputState.ZERO()

        self.start = TriggerStart.IMMEDIATE
        self.rearm = TriggerRearm.MANUAL

        self.pulser.setTrigger(start=self.start, rearm=self.rearm)
        self.log.info('Pulse streamer is prepared for\n{0}'.format(pulsetype))

    def start_stream(self):
        # run the sequence only once
        self.n_runs = 10
        # n_runs = 'INFIITE' # repeat the sequence all the time
        # Start Streaming
        self.pulser.stream(self.seq, self.n_runs, self.final)
    def set_parameter(self,parameter):
        """
        H. Babashah - get acquisition.
        """
        print(parameter)