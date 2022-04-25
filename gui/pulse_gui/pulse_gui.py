import numpy as np
import os
import pyqtgraph as pg

from core.connector import Connector

from gui.guibase import GUIBase

from qtpy import QtCore, QtWidgets, uic

from qtpy import uic


class PULSE_MainWindow(QtWidgets.QMainWindow):
    """
    H.Babashah - class for using dummy_gui
    """
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'pulse_gui.ui')

        # Load it
        super(PULSE_MainWindow, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()


class PULSEGUI(GUIBase):
    """
    H.Babashah - This is the GUI Class for Dummy graphical interface. Easy written to learn.
    """

    # declare connectors
    pulselogic = Connector(interface='PULSElogic')
    savelogic = Connector(interface='SaveLogic')

    #Define Signals
    SigStartAcquisition = QtCore.Signal()
    SigPcwChanged = QtCore.Signal(float)
    SigSetPulseChanged = QtCore.Signal(float,float,float)
    SigPulseAnalysisChanged = QtCore.Signal(float,float,float)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)


    def on_activate(self):
        """
        F.Beato - Definition, configuration and initialisation of the FFT GUI.

        This init connects all the graphic modules, which were created in the
        *.ui file and configures the event handling between the modules.
        """

        self._pulselogic = self.pulselogic()

        # Use the inherited class 'Ui_ODMRGuiUI' to create now the GUI element:
        self._mw = PULSE_MainWindow()

        # Define data plots
        self.pulse_exp_image = pg.PlotDataItem()
        # Add the display item to the xy and xz ViewWidget, which was defined in the UI file.
        self._mw.pulse_exp_graph.addItem(self.pulse_exp_image)
        self._mw.pulse_exp_graph.setLabel(axis='left', text='Amplitude', units='a.u.')
        self._mw.pulse_exp_graph.setLabel(axis='bottom', text='Time', units='s')
        self._mw.pulse_exp_graph.showGrid(x=True, y=True, alpha=0.8)


        ########################################################################
        #                       Connect signals                                #
        ########################################################################
        # Internal user input changed signals
        self._mw.actionStart.triggered.connect(self.start_data_acquisition)
        self._mw.pcw_doubleSpinBox.editingFinished.connect(self.change_pcw)
        self._mw.time_stop_doubleSpinBox.editingFinished.connect(self.change_pulse_analysis_param)
        self._mw.npts_doubleSpinBox.editingFinished.connect(self.change_pulse_analysis_param)
        self._mw.time_start_doubleSpinBox.editingFinished.connect(self.change_pulse_analysis_param)


        self._mw.threshold_doubleSpinBox.editingFinished.connect(self.change_pulse_analysis_param)
        self._mw.time_reference_doubleSpinBox.editingFinished.connect(self.change_pulse_analysis_param)
        self._mw.time_signal_doubleSpinBox.editingFinished.connect(self.change_pulse_analysis_param)


        # Connections to logic
        self._mw.fft_window_comboBox.currentTextChanged.connect(self._pulselogic.set_pulse_type)
        self.SigStartAcquisition.connect(self._pulselogic.start_data_acquisition)
        self._mw.time_start_doubleSpinBox.setValue(self._pulselogic.time_start) # Status var
        self.SigPcwChanged.connect(self._pulselogic.set_pcw, QtCore.Qt.QueuedConnection)
        self._mw.pcw_doubleSpinBox.setValue(self._pulselogic.pcw) # Status var
        self._mw.npts_doubleSpinBox.setValue(self._pulselogic.npts) # Status var
        self.SigSetPulseChanged.connect(self._pulselogic.set_pulse, QtCore.Qt.QueuedConnection)
        self._mw.time_stop_doubleSpinBox.setValue(self._pulselogic.time_stop) # Status var
        self.SigPulseAnalysisChanged.connect(self._pulselogic.set_pulse_analysi_param, QtCore.Qt.QueuedConnection)
        self._mw.time_reference_doubleSpinBox.setValue(self._pulselogic.time_reference) # Status var
        self._mw.threshold_doubleSpinBox.setValue(self._pulselogic.threshold) # Status var
        self._mw.time_signal_doubleSpinBox.setValue(self._pulselogic.time_signal) # Status var
        # Update connections from logic
        self._pulselogic.SigDataUpdated.connect(self.update_plot, QtCore.Qt.QueuedConnection)


        # Show the Main FFT GUI:
        self.show()


    def on_deactivate(self):
        """
        H.Babashah & F. Baeto - Reverse steps of activation and also close the main window and do whatever when a module is closed using closed btn in task manager

        @return int: error code (0:OK, -1:error)
        """
        # Disconnect signals
        self._mw.fft_window_comboBox.currentTextChanged.disconnect()
        self._mw.time_start_doubleSpinBox.editingFinished.disconnect()
        self._mw.pcw_doubleSpinBox.editingFinished.disconnect()
        self.SigPcwChanged.disconnect()
        self._mw.npts_doubleSpinBox.editingFinished.disconnect()
        self._mw.time_stop_doubleSpinBox.editingFinished.disconnect()
        self._mw.threshold_doubleSpinBox.editingFinished.disconnect()
        self._mw.time_reference_doubleSpinBox.editingFinished.disconnect()
        self._mw.time_signal_doubleSpinBox.editingFinished.disconnect()
        self._mw.close()
        return 0


    def start_data_acquisition(self):
        """
        F.Beato - Send user order to start acquisition to the logic.
        """
        #self._mw.actionStart.setEnabled(False)
        #self._mw.actionStop.setEnabled(True)
        self.SigStartAcquisition.emit()#self._mw.multi_span_checkBox.isChecked()
    def change_pcw(self):


        pcw = self._mw.pcw_doubleSpinBox.value()
        self.SigPcwChanged.emit(pcw)


    def set_pulse(self):
        time_start = self._mw.time_start_doubleSpinBox.value()
        time_stop = self._mw.time_stop_doubleSpinBox.value()
        npts = self._mw.npts_doubleSpinBox.value()
        self.SigSetPulseChanged.emit(time_start,time_stop,npts)
    def change_pulse_analysis_param(self):


        threshold = self._mw.threshold_doubleSpinBox.value()
        time_reference = self._mw.time_reference_doubleSpinBox.value()
        time_signal = self._mw.time_signal_doubleSpinBox.value()

        self.SigPulseAnalysisChanged.emit(threshold,time_reference,time_signal)
    def update_plot(self, xdata, ydata):
        """
        F.Beato - Updates the plot.
        """

        self.pulse_exp_image.setData(xdata, ydata)

    def show(self):
        """
        F.Beato - Taken from Qudi - Make window visible and put it above all other windows.
        """
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()
