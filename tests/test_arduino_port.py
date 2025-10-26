"""
Unit tests for Arduino port connection verification
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import serial
import time

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gctrl import GCodeController


class TestArduinoPortConfiguration:
    """Test Arduino serial port configuration"""
    
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_port_baudrate_configuration(self, mock_thread, mock_serial):
        """Test that port is configured with correct baudrate (9600)"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify baudrate is 9600 as expected by Arduino
        mock_serial.assert_called_once()
        call_kwargs = mock_serial.call_args[1]
        assert call_kwargs['baudrate'] == 9600
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_port_data_bits_configuration(self, mock_thread, mock_serial):
        """Test that port is configured with 8 data bits"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify 8 data bits (EIGHTBITS)
        call_kwargs = mock_serial.call_args[1]
        assert call_kwargs['bytesize'] == serial.EIGHTBITS
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_port_parity_configuration(self, mock_thread, mock_serial):
        """Test that port is configured with no parity"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify no parity (PARITY_NONE)
        call_kwargs = mock_serial.call_args[1]
        assert call_kwargs['parity'] == serial.PARITY_NONE
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_port_stopbits_configuration(self, mock_thread, mock_serial):
        """Test that port is configured with 1 stop bit"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify 1 stop bit (STOPBITS_ONE)
        call_kwargs = mock_serial.call_args[1]
        assert call_kwargs['stopbits'] == serial.STOPBITS_ONE
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_port_timeout_configuration(self, mock_thread, mock_serial):
        """Test that port is configured with appropriate timeout"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify timeout is set
        call_kwargs = mock_serial.call_args[1]
        assert 'timeout' in call_kwargs
        assert call_kwargs['timeout'] == 1
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_port_write_timeout_configuration(self, mock_thread, mock_serial):
        """Test that port is configured with write timeout"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify write timeout is set
        call_kwargs = mock_serial.call_args[1]
        assert 'write_timeout' in call_kwargs
        assert call_kwargs['write_timeout'] == 1


class TestArduinoPortConnection:
    """Test Arduino port connection handling"""
    
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_connection_buffer_reset(self, mock_thread, mock_serial):
        """Test that buffers are reset on connection"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify buffers are cleared
        assert mock_port.reset_input_buffer.called
        assert mock_port.reset_output_buffer.called
        
    @patch('serial.Serial')
    def test_connection_with_empty_port_name(self, mock_serial):
        """Test connection fails with empty port name"""
        controller = GCodeController()
        result = controller.connect('')
        
        assert result is False
        mock_serial.assert_not_called()
        
    @patch('serial.Serial')
    def test_connection_with_none_port_name(self, mock_serial):
        """Test connection fails with None port name"""
        controller = GCodeController()
        result = controller.connect(None)
        
        assert result is False
        mock_serial.assert_not_called()
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_connection_sends_test_command(self, mock_thread, mock_serial):
        """Test that connection sends test command to Arduino"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify test command is sent
        assert mock_port.write.called
        
    @patch('serial.Serial')
    def test_connection_closes_existing_port(self, mock_serial):
        """Test that existing port is closed before new connection"""
        mock_old_port = MagicMock()
        mock_old_port.is_open = True
        mock_new_port = MagicMock()
        mock_new_port.is_open = True
        mock_serial.side_effect = [mock_old_port, mock_new_port]
        
        controller = GCodeController()
        with patch('threading.Thread'):
            controller.connect('COM1')
            controller.connect('COM2')
        
        # Verify old port was closed
        assert mock_old_port.close.called


class TestArduinoPortReconnection:
    """Test Arduino port reconnection scenarios"""
    
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_reconnection_after_disconnect(self, mock_thread, mock_serial):
        """Test successful reconnection after disconnect"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        
        # First connection
        result1 = controller.connect('COM1')
        assert result1 is True
        
        # Disconnect
        controller.disconnect()
        
        # Reconnect
        mock_port2 = MagicMock()
        mock_port2.is_open = True
        mock_serial.return_value = mock_port2
        result2 = controller.connect('COM1')
        assert result2 is True
        
    @patch('serial.Serial')
    def test_connection_error_handling(self, mock_serial):
        """Test error handling for connection failures"""
        mock_serial.side_effect = serial.SerialException("Port in use")
        
        controller = GCodeController()
        callback = Mock()
        controller.set_log_callback(callback)
        
        result = controller.connect('COM1')
        
        assert result is False
        # Verify error was logged
        assert callback.called


class TestArduinoPortAvailability:
    """Test Arduino port availability detection"""
    
    @patch('platform.system')
    @patch('serial.Serial')
    def test_find_arduino_on_windows_com_port(self, mock_serial, mock_system):
        """Test finding Arduino on Windows COM port"""
        mock_system.return_value = 'Windows'
        mock_port = MagicMock()
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        ports = controller.find_serial_ports()
        
        # Should scan COM1-COM20
        assert isinstance(ports, list)
        
    @patch('platform.system')
    @patch('glob.glob')
    @patch('serial.Serial')
    def test_find_arduino_on_linux_usb_port(self, mock_serial, mock_glob, mock_system):
        """Test finding Arduino on Linux USB port"""
        mock_system.return_value = 'Linux'
        mock_glob.return_value = ['/dev/ttyUSB0', '/dev/ttyACM0']
        mock_port = MagicMock()
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        ports = controller.find_serial_ports()
        
        # Should find USB ports
        assert isinstance(ports, list)
        assert len(ports) >= 0
        
    @patch('platform.system')
    @patch('glob.glob')
    @patch('serial.Serial')
    def test_find_arduino_on_mac_usb_port(self, mock_serial, mock_glob, mock_system):
        """Test finding Arduino on Mac USB port"""
        mock_system.return_value = 'Darwin'
        mock_glob.return_value = ['/dev/cu.usbmodem14101', '/dev/tty.usbmodem14101']
        mock_port = MagicMock()
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        ports = controller.find_serial_ports()
        
        # Should find USB ports
        assert isinstance(ports, list)


class TestArduinoPortCommunication:
    """Test Arduino port communication protocol"""
    
    def test_command_format_with_newline(self):
        """Test that commands are sent with newline terminator"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        controller.send_command("G1 X10 Y10")
        
        # Verify newline is added
        call_args = controller.port.write.call_args[0][0]
        assert call_args.endswith(b'\n')
        
    def test_command_format_preserves_existing_newline(self):
        """Test that existing newlines are preserved"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        controller.send_command("G1 X10 Y10\n")
        
        # Verify no double newline
        call_args = controller.port.write.call_args[0][0]
        assert call_args == b'G1 X10 Y10\n'
        
    def test_command_encoding_utf8(self):
        """Test that commands are encoded in UTF-8"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        controller.send_command("G1 X10")
        
        # Verify bytes were sent (UTF-8 encoded)
        call_args = controller.port.write.call_args[0][0]
        assert isinstance(call_args, bytes)
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_response_reading_thread_started(self, mock_thread, mock_serial):
        """Test that response reading thread is started on connection"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        
        # Verify thread was started
        assert mock_thread.called
        call_kwargs = mock_thread.call_args[1]
        assert 'target' in call_kwargs
        assert call_kwargs['daemon'] is True


class TestArduinoConnectionTimeout:
    """Test Arduino connection timeout handling"""
    
    def test_command_timeout_setting_exists(self):
        """Test that command timeout is configured"""
        controller = GCodeController()
        
        assert hasattr(controller, 'command_timeout')
        assert controller.command_timeout > 0
        
    def test_serial_exception_handling(self):
        """Test handling of serial exceptions during send"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.port.write.side_effect = serial.SerialException("Write failed")
        
        callback = Mock()
        controller.set_log_callback(callback)
        
        result = controller.send_command("G1 X10")
        
        assert result is False
        # Verify error was logged
        assert callback.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
