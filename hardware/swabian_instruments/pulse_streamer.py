# -*- coding: utf-8 -*-
"""
Use Swabian Instruments PulseStreamer8/2 as a pulse generator.

Protobuf (pb2) and grpc files generated from pulse_streamer.proto
file available at https://www.swabianinstruments.com/static/documentation/PulseStreamer/sections/interface.html#grpc-interface.

Regenerate files for an update proto file using the following:
python3 -m grpc_tools.protoc -I=./ --python_out=. --grpc_python_out=. ./pulse_streamer.proto

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
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

from core.module import Base
from core.configoption import ConfigOption
from interface.pulser_interface import PulserInterface, PulserConstraints
from collections import OrderedDict
import pulsestreamer as ps
import os


class PulseStreamer(Base, PulserInterface):
    """ Methods to control PulseStreamer.

    Example config for copy-paste:

    pulse_streamer:
        module.Class: 'swabian_instruments.pulse_streamer.PulseStreamer'
        ip_address: '192.168.1.100'
        laser_channel: 0
        uw_x_channel: 2

    """

    _ip_address = ConfigOption('ip_address', '169.254.8.2', missing='warn')
    _laser_channel = ConfigOption('laser_channel', 'd_ch1', missing='warn')
    _uw_x_channel = ConfigOption('uw_x_channel', 'd_ch2', missing='warn')
    _uw_y_channel = ConfigOption('uw_y_channel', 'd_ch3', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.waveforms = dict()
        self._sequence = None
        self.current_status = -1
        self.sample_rate = 1e9
        self.current_loaded_asset = None
        self.pulse_streamer = None

    @staticmethod
    def numeric_channel(channel_name):
        # 8 channels so one digit will do
        return int(channel_name[-1])-1

    def on_activate(self):
        """ Establish connection to pulse streamer and tell it to cancel all operations """

        self.waveforms = dict()
        self.current_status = -1
        self.sample_rate = 1e9
        self.current_loaded_asset = None
        self._current_pulse_ensemble = None
        self.laser_channel = PulseStreamer.numeric_channel(self._laser_channel)
        self.uw_x_channel = PulseStreamer.numeric_channel(self._uw_x_channel)
        self.uw_y_channel = PulseStreamer.numeric_channel(self._uw_y_channel)

        self.pulse_streamer = ps.PulseStreamer(self._ip_address)
        self.pulser_off()
        self.current_status = 0

    def on_deactivate(self):
        del self.pulse_streamer

    def get_constraints(self):
        """ Retrieve the hardware constrains from the Pulsing device.

        @return dict: dict with constraints for the sequence generation and GUI

        Provides all the constraints (e.g. sample_rate, amplitude,
        total_length_bins, channel_config, ...) related to the pulse generator
        hardware to the caller.
        The keys of the returned dictionary are the str name for the constraints
        (which are set in this method). No other keys should be invented. If you
        are not sure about the meaning, look in other hardware files to get an
        impression. If still additional constraints are needed, then they have
        to be add to all files containing this interface.
        The items of the keys are again dictionaries which have the generic
        dictionary form:
            {'min': <value>,
             'max': <value>,
             'step': <value>,
             'unit': '<value>'}

        Only the keys 'activation_config' and differs, since it contain the
        channel configuration/activation information.

        If the constraints cannot be set in the pulsing hardware (because it
        might e.g. has no sequence mode) then write just zero to each generic
        dict. Note that there is a difference between float input (0.0) and
        integer input (0).
        ALL THE PRESENT KEYS OF THE CONSTRAINTS DICT MUST BE ASSIGNED!
        """
        constraints = PulserConstraints()

        # The file formats are hardware specific.
        constraints.waveform_format = ['pstream']
        constraints.sequence_format = []

        constraints.sample_rate.min = 1e9
        constraints.sample_rate.max = 1e9
        constraints.sample_rate.step = 0
        constraints.sample_rate.default = 1e9

        constraints.d_ch_low.min = 0.0
        constraints.d_ch_low.max = 0.0
        constraints.d_ch_low.step = 0.0
        constraints.d_ch_low.default = 0.0

        constraints.d_ch_high.min = 3.3
        constraints.d_ch_high.max = 3.3
        constraints.d_ch_high.step = 0.0
        constraints.d_ch_high.default = 3.3

        # sample file length max is not well-defined for PulseStreamer, which collates sequential identical pulses into
        # one. Total number of not-sequentially-identical pulses which can be stored: 1 M.
        constraints.waveform_length.min = 1
        constraints.waveform_length.max = 134217728
        constraints.waveform_length.step = 1
        constraints.waveform_length.default = 1

        # the name a_ch<num> and d_ch<num> are generic names, which describe UNAMBIGUOUSLY the
        # channels. Here all possible channel configurations are stated, where only the generic
        # names should be used. The names for the different configurations can be customary chosen.
        activation_config = OrderedDict()
        activation_config['all'] = {'d_ch1', 'd_ch2', 'd_ch3', 'd_ch4', 'd_ch5', 'd_ch6', 'd_ch7', 'd_ch8'}
        constraints.activation_config = activation_config

        return constraints

    def pulser_on(self):
        """ Switches the pulsing device on.

        @return int: error code (0:OK, -1:error)
        """
        # start the pulse sequence
        if self.current_loaded_asset is None:
            self.log.warn("Pulser cannot be started without loading a pulse sequence")
            return -1

        self.pulse_streamer.stream(self._sequence)
        self.log.info('Asset uploaded to PulseStreamer')
        self.pulse_streamer.startNow()
        self.current_status = 1
        return 0

    def pulser_off(self):
        """ Switches the pulsing device off.

        @return int: error code (0:OK, -1:error)
        """
        # stop the pulse sequence, set all channels LOW except laser and cw microwave x phase
        # set analogue outputs to 0V
        self.log.debug("Setting pulser off (laser channel {} & uw_x_channel {} set on".format(self.laser_channel, self.uw_x_channel))
        self.pulse_streamer.constant(([self.laser_channel, self.uw_x_channel], 0, 0))
        self.current_status = 0
        return 0

    def upload_asset(self, asset_name=None):
        """ Upload an already hardware conform file to the device.
            Does NOT load it into channels.

        @param name: string, name of the ensemble/sequence to be uploaded

        @return int: error code (0:OK, -1:error)
        """
        self.log.debug('PulseStreamer does not require upload of assets in preparation\n"upload_asset" call ignored.')
        return 0

    # gone
    def load_asset(self, asset_name, load_dict=None):
        """ Loads a sequence or waveform to the specified channel of the pulsing
            device.

        @param str asset_name: The name of the asset to be loaded

        @param dict load_dict:  a dictionary with keys being one of the
                                available channel numbers and items being the
                                name of the already sampled
                                waveform/sequence files.
                                Examples:   {1: rabi_Ch1, 2: rabi_Ch2}
                                            {1: rabi_Ch2, 2: rabi_Ch1}
                                This parameter is optional. If none is given
                                then the channel association is invoked from
                                the sequence generation,
                                i.e. the filename appendix (_Ch1, _Ch2 etc.)

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def clear_all(self):
        """ Clears all loaded waveforms from the pulse generators RAM.

        @return int: error code (0:OK, -1:error)

        Unused for digital pulse generators without storage capability
        (PulseBlaster, FPGA).
        """
        return 0

    def get_status(self):
        """ Retrieves the status of the pulsing hardware

        @return (int, dict): tuple with an interger value of the current status
                             and a corresponding dictionary containing status
                             description for all the possible status variables
                             of the pulse generator hardware.
        """
        status_dic = dict()
        status_dic[-1] = 'Failed Request or Failed Communication with device.'
        status_dic[0] = 'Device has stopped, but can receive commands.'
        status_dic[1] = 'Device is active and running.'

        return self.current_status, status_dic

    def get_sample_rate(self):
        """ Get the sample rate of the pulse generator hardware

        @return float: The current sample rate of the device (in Hz)

        Do not return a saved sample rate in a class variable, but instead
        retrieve the current sample rate directly from the device.
        """
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        """ Set the sample rate of the pulse generator hardware.

        @param float sample_rate: The sampling rate to be set (in Hz)

        @return float: the sample rate returned from the device.

        Note: After setting the sampling rate of the device, retrieve it again
              for obtaining the actual set value and use that information for
              further processing.
        """
        self.log.debug('PulseStreamer sample rate cannot be configured')
        return self.sample_rate

    def get_analog_level(self, amplitude=None, offset=None):
        """ Retrieve the analog amplitude and offset of the provided channels.

        @param list amplitude: optional, if a specific amplitude value (in Volt
                               peak to peak, i.e. the full amplitude) of a
                               channel is desired.
        @param list offset: optional, if a specific high value (in Volt) of a
                            channel is desired.

        @return: (dict, dict): tuple of two dicts, with keys being the channel
                               number and items being the values for those
                               channels. Amplitude is always denoted in
                               Volt-peak-to-peak and Offset in (absolute)
                               Voltage.
        """
        return {}, {}

    def set_analog_level(self, amplitude=None, offset=None):
        """ Set amplitude and/or offset value of the provided analog channel.

        @param dict amplitude: dictionary, with key being the channel and items
                               being the amplitude values (in Volt peak to peak,
                               i.e. the full amplitude) for the desired channel.
        @param dict offset: dictionary, with key being the channel and items
                            being the offset values (in absolute volt) for the
                            desired channel.

        @return (dict, dict): tuple of two dicts with the actual set values for
                              amplitude and offset.

        If nothing is passed then the command will return two empty dicts.
        """
        return {}, {}

    def get_digital_level(self, low=None, high=None):
        """ Retrieve the digital low and high level of the provided channels.

        @param list low: optional, if a specific low value (in Volt) of a
                         channel is desired.
        @param list high: optional, if a specific high value (in Volt) of a
                          channel is desired.

        @return: (dict, dict): tuple of two dicts, with keys being the channel
                               number and items being the values for those
                               channels. Both low and high value of a channel is
                               denoted in (absolute) Voltage.

        Note: Do not return a saved low and/or high value but instead retrieve
              the current low and/or high value directly from the device.

        If no entries provided then the levels of all channels where simply
        returned. If no digital channels provided, return just an empty dict.

        Example of a possible input:
            low = [1,4]
        to obtain the low voltage values of digital channel 1 an 4. A possible
        answer might be
            {1: -0.5, 4: 2.0} {}
        since no high request was performed.

        The major difference to analog signals is that digital signals are
        either ON or OFF, whereas analog channels have a varying amplitude
        range. In contrast to analog output levels, digital output levels are
        defined by a voltage, which corresponds to the ON status and a voltage
        which corresponds to the OFF status (both denoted in (absolute) voltage)

        In general there is no bijective correspondence between
        (amplitude, offset) and (value high, value low)!
        """
        if low is None:
            low = []
        if high is None:
            high = []
        low_dict = {}
        high_dict = {}
        if low is [] and high is []:
            for channel in range(8):
                low_dict[channel] = 0.0
                high_dict[channel] = 3.3
        else:
            for channel in low:
                low_dict[channel] = 0.0
            for channel in high:
                high_dict[channel] = 3.3
        return low_dict, high_dict

    def set_digital_level(self, low=None, high=None):
        """ Set low and/or high value of the provided digital channel.

        @param dict low: dictionary, with key being the channel and items being
                         the low values (in volt) for the desired channel.
        @param dict high: dictionary, with key being the channel and items being
                         the high values (in volt) for the desired channel.

        @return (dict, dict): tuple of two dicts where first dict denotes the
                              current low value and the second dict the high
                              value.

        If nothing is passed then the command will return two empty dicts.

        Note: After setting the high and/or low values of the device, retrieve
              them again for obtaining the actual set value(s) and use that
              information for further processing.

        The major difference to analog signals is that digital signals are
        either ON or OFF, whereas analog channels have a varying amplitude
        range. In contrast to analog output levels, digital output levels are
        defined by a voltage, which corresponds to the ON status and a voltage
        which corresponds to the OFF status (both denoted in (absolute) voltage)

        In general there is no bijective correspondence between
        (amplitude, offset) and (value high, value low)!
        """
        if low is None:
            low = {}
        if high is None:
            high = {}
        self.log.warning('PulseStreamer logic level cannot be adjusted!')
        return 0

    def get_active_channels(self,  ch=None):
        if ch is None:
            ch = {}
        d_ch_dict = {}
        if len(ch) < 1:
            for chnl in range(1, 9):
                d_ch_dict['d_ch{0}'.format(chnl)] = True
        else:
            for channel in ch:
                d_ch_dict[channel] = True
        return d_ch_dict

    def set_active_channels(self, ch=None):
        if ch is None:
            ch = {}
        d_ch_dict = {
            'd_ch1': True,
            'd_ch2': True,
            'd_ch3': True,
            'd_ch4': True,
            'd_ch5': True,
            'd_ch6': True,
            'd_ch7': True,
            'd_ch8': True}
        return d_ch_dict

    def get_loaded_asset(self):
        """ Retrieve the currently loaded asset name of the device.

        @return str: Name of the current asset, that can be either a filename
                     a waveform, a sequence ect.
        """
        return self.current_loaded_asset

    def get_uploaded_asset_names(self):
        """ Retrieve the names of all uploaded assets on the device.

        @return list: List of all uploaded asset name strings in the current
                      device directory. This is no list of the file names.

        Unused for digital pulse generators without sequence storage capability
        (PulseBlaster, FPGA).
        """
        names = list()
        return list()

    def get_saved_asset_names(self):
        """ Retrieve the names of all sampled and saved assets on the host PC.
        This is no list of the file names.

        @return list: List of all saved asset name strings in the current
                      directory of the host PC.
        """
        file_list = self._get_filenames_on_host()

        saved_assets = []
        for filename in file_list:
            if filename.endswith('.pstream'):
                asset_name = filename.rsplit('.', 1)[0]
                if asset_name not in saved_assets:
                    saved_assets.append(asset_name)
        return saved_assets

    def delete_asset(self, asset_name):
        """ Delete all files associated with an asset with the passed asset_name from the device memory.

        @param str asset_name: The name of the asset to be deleted
                               Optionally a list of asset names can be passed.

        @return int: error code (0:OK, -1:error)

        Unused for digital pulse generators without sequence storage capability
        (PulseBlaster, FPGA).
        """
        return 0

    def set_asset_dir_on_device(self, dir_path):
        """ Change the directory where the assets are stored on the device.

        @param str dir_path: The target directory

        @return int: error code (0:OK, -1:error)

        Unused for digital pulse generators without changeable file structure
        (PulseBlaster, FPGA).
        """
        return 0

    def get_asset_dir_on_device(self):
        """ Ask for the directory where the hardware conform files are stored on
            the device.

        @return str: The current file directory

        Unused for digital pulse generators without changeable file structure
        (PulseBlaster, FPGA).
        """
        return ''

    def get_interleave(self):
        """ Check whether Interleave is ON or OFF in AWG.

        @return bool: True: ON, False: OFF

        Unused for pulse generator hardware other than an AWG.
        """
        return False

    def set_interleave(self, state=False):
        """ Turns the interleave of an AWG on or off.

        @param bool state: The state the interleave should be set to
                           (True: ON, False: OFF)

        @return bool: actual interleave status (True: ON, False: OFF)

        Note: After setting the interleave of the device, retrieve the
              interleave again and use that information for further processing.

        Unused for pulse generator hardware other than an AWG.
        """
        return False

    def tell(self, command):
        """ Sends a command string to the device.

        @param string command: string containing the command

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def ask(self, question):
        """ Asks the device a 'question' and receive and return an answer from it.
a
        @param string question: string containing the command

        @return string: the answer of the device to the 'question' in a string
        """
        return ''

    def reset(self):
        """ Reset the device.

        @return int: error code (0:OK, -1:error)
        """
        self.pulser_off()
        return 0

    def has_sequence_mode(self):
        """ Asks the pulse generator whether sequence mode exists.

        @return: bool, True for yes, False for no.
        """
        return False

    def _get_dir_for_name(self, name):
        """ Get the path to the pulsed sub-directory 'name'.

        @param name: string, name of the folder
        @return: string, absolute path to the directory with folder 'name'.
        """
        path = os.path.join(self.pulsed_file_dir, name)
        if not os.path.exists(path):
            os.makedirs(os.path.abspath(path))
        return os.path.abspath(path)

    def _get_filenames_on_host(self):
        """ Get the full filenames of all assets saved on the host PC.

        @return: list, The full filenames of all assets saved on the host PC.
        """
        filename_list = [f for f in os.listdir(self.host_waveform_directory) if f.endswith('.pstream')]
        return filename_list

    def _convert_to_bitmask(self, active_channels):
        """ Convert a list of channels into a bitmask.
        @param numpy.array active_channels: the list of active channels like
                            e.g. [0,4,7]. Note that the channels start from 0.
        @return int: The channel-list is converted into a bitmask (an sequence
                     of 1 and 0). The returned integer corresponds to such a
                     bitmask.
        Note that you can get a binary representation of an integer in python
        if you use the command bin(<integer-value>). All higher unneeded digits
        will be dropped, i.e. 0b00100 is turned into 0b100. Examples are
            bin(0) =    0b0
            bin(1) =    0b1
            bin(8) = 0b1000
        Each bit value (read from right to left) corresponds to the fact that a
        channel is on or off. I.e. if you have
            0b001011
        then it would mean that only channel 0, 1 and 3 are switched to on, the
        others are off.
        Helper method for write_pulse_form.
        """
        bits = 0     # that corresponds to: 0b0
        for channel in active_channels:
            # go through each list element and create the digital word out of
            # 0 and 1 that represents the channel configuration. In order to do
            # that a bitwise shift to the left (<< operator) is performed and
            # the current channel configuration is compared with a bitwise OR
            # to check whether the bit was already set. E.g.:
            #   0b1001 | 0b0110: compare elementwise:
            #           1 | 0 => 1
            #           0 | 1 => 1
            #           0 | 1 => 1
            #           1 | 1 => 1
            #                   => 0b1111
            bits = bits | (1<< channel)
        return bits

    def set_pulse_ensemble(self, ensemble_name, ensemble):
        # Here we actually set up the pulse sequence on the PulseStreamer
        active_channels = [channel for channel, active in self.get_active_channels().items() if active]
        sq = self.pulse_streamer.createSequence()
        self._current_pulse_ensemble = ensemble

        # digital channel set up
        for channel in active_channels:
            rle = []
            try:
                channel_num = PulseStreamer.numeric_channel(channel)
                # TODO: check what the correct number of elements supplied is
                # n_elem = ensemble['number_of_elements']
                n_samples = ensemble['number_of_samples'] # total time in ns for PulseStreamer
                rising = ensemble['digital_rising_bins'][channel]
                falling = ensemble['digital_falling_bins'][channel]
                n_elem = len(rising)  # will serve for now

                # not all channels have pulses to configure
                if len(rising) + len(falling) == 0:
                    self.log.debug('No pulses on channel "{}"'.format(channel))
                    continue

                # a few sanity checks, just in case I missed something
                if len(rising) != n_elem:
                    self.log.warn('Number of rising edges {} does not match expected number {} on channel {}'.format(len(rising), n_elem, channel))
                    return False
                if len(falling) != n_elem:
                    self.log.warn('Number of falling edges {} does not match expected number {} on channel {}'.format(len(falling), n_elem, channel))
                    return False
                if falling[0] < rising[0]:
                    # starts with a falling edge?
                    # e.g. a sync pulse might only rise once, at the end
                    if falling[0] == 0:
                        # This is ok, just starts low
                        pass
                    else:
                        self.log.error('Pulse sequence for channel {} starts with a falling edge, unexpectedly'.format(channel))
                        return False

                # Now build the run length encoded sequence for this channel
                # it may start with a low
                if rising[0] > 0:
                    rle.append((rising[0], 0))

                # followed by alternating high and low pulses with some length. Total length is nsamples
                for i in range(0, n_elem):
                    # add HIGH pulse

                    # need to deal with the case that falling[0] == 0 (i.e. for a sync pulse). In this case, duration
                    # will end up being negative and the pulse will never be added
                    if i == (n_elem - 1) and falling[0] == 0:
                        duration = n_samples - rising[i]
                        self.log.debug('Adding inferred rising pulse of duration {} to channel {}'.format(duration, channel))
                    else:
                        duration = falling[i] - rising[i]
                    if duration > 0:
                        rle.append((duration, 1))

                    # add LOW pulse
                    if i+1 < n_elem:
                        duration = rising[i+1] - falling[i]
                        if duration > 0:
                            rle.append((duration, 0))
                    elif falling[i] < n_samples:
                        if i == (n_elem - 1) and falling[0] == 0:
                            self.log.debug('Ignoring final pulse of channel {} as it should be set at the start of the sequence'.format(channel))
                            continue
                        duration = n_samples - falling[i]
                        if duration > 0:
                            rle.append((duration, 0))

                # At this point should have the form the PulseStreamer API uses for pulse sequences.
                # Set up this channel
                self.log.debug('Setting pulse sequence on channel {}\n{}'.format(channel_num, rle))
                sq.setDigital(channel_num, rle)

            except KeyError:
                self.log.exception('Could not find pulse train description for channel "{}"'.format(channel))
                return False

            except ValueError:
                self.log.exception('Failed to extract channel number for channel "{}"'.format(channel))
                return False

        #TODO: add analogue channel configuration

        self._sequence = sq
        self.current_loaded_asset = ensemble_name

        return True

    def load_waveform(self, load_dict):
        self._wfm = load_dict

    def write_waveform(self, name, analog_samples, digital_samples, is_first_chunk, is_last_chunk,
                       total_number_of_samples):
        self.waveforms[name] = 1;
        return total_number_of_samples, [name]

    def get_waveform_names(self):
        return list(self.waveforms.keys())

    def delete_waveform(self, waveform_name):
        return []

    def load_sequence(self, sequence_name):
        pass

    def write_sequence(self, name, sequence_parameters):
        return []

    def delete_sequence(self, sequence_name):
        return []

    def get_sequence_names(self):
        return []

    def get_loaded_assets(self):
        asset = self.current_loaded_asset
        if asset is not None:
            return {asset: asset}, 'waveform'
        else:
            return {}, 'waveform'



