"""
Unit tests for GCodeController class
"""
import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch, mock_open
import serial

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gctrl import GCodeController


class TestGCodeControllerInit:
    """Test GCodeController initialization"""
    
    def test_init_default_values(self):
        """Test that controller initializes with correct default values"""
        controller = GCodeController()
        
        assert controller.port is None
        assert controller.port_name is None
        assert controller.running is True
        assert controller.streaming is False
        assert controller.paused is False
        assert controller.gcode == []
        assert controller.gcode_index == 0
        assert controller.position == {'x': 0, 'y': 0, 'z': 0}
        
    def test_init_machine_limits(self):
        """Test that machine limits are correctly initialized"""
        controller = GCodeController()
        
        assert controller.machine_limits['x']['min'] == 0
        assert controller.machine_limits['x']['max'] == 40
        assert controller.machine_limits['y']['min'] == 0
        assert controller.machine_limits['y']['max'] == 40
        assert controller.machine_limits['z']['min'] == 0
        assert controller.machine_limits['z']['max'] == 5
        
    def test_init_origin_not_set(self):
        """Test that origin is not set by default"""
        controller = GCodeController()
        
        assert controller.origin_set is False
        assert controller.homing_complete is False


class TestLogCallback:
    """Test logging functionality"""
    
    def test_set_log_callback(self):
        """Test setting log callback"""
        controller = GCodeController()
        callback = Mock()
        
        controller.set_log_callback(callback)
        assert controller.log_callback == callback
        
    def test_log_with_callback(self):
        """Test logging with callback set"""
        controller = GCodeController()
        callback = Mock()
        controller.set_log_callback(callback)
        
        controller.log("Test message")
        callback.assert_called_once_with("Test message")
        
    def test_log_without_callback(self):
        """Test logging without callback doesn't raise error"""
        controller = GCodeController()
        # Should not raise any exception
        controller.log("Test message")


class TestSerialPortDiscovery:
    """Test serial port discovery functionality"""
    
    @patch('platform.system')
    @patch('serial.Serial')
    def test_find_serial_ports_windows(self, mock_serial, mock_system):
        """Test port discovery on Windows"""
        mock_system.return_value = 'Windows'
        mock_serial_instance = MagicMock()
        mock_serial.return_value = mock_serial_instance
        
        controller = GCodeController()
        ports = controller.find_serial_ports()
        
        # Should find some COM ports
        assert isinstance(ports, list)
        
    @patch('platform.system')
    @patch('glob.glob')
    @patch('serial.Serial')
    def test_find_serial_ports_linux(self, mock_serial, mock_glob, mock_system):
        """Test port discovery on Linux"""
        mock_system.return_value = 'Linux'
        mock_glob.return_value = ['/dev/ttyUSB0', '/dev/ttyACM0']
        mock_serial_instance = MagicMock()
        mock_serial.return_value = mock_serial_instance
        
        controller = GCodeController()
        ports = controller.find_serial_ports()
        
        assert isinstance(ports, list)
        assert len(ports) >= 0


class TestCheckLimits:
    """Test limit checking functionality"""
    
    def test_check_limits_within_bounds(self):
        """Test position within limits"""
        controller = GCodeController()
        
        assert controller.check_limits(x=20, y=20, z=2) is True
        assert controller.check_limits(x=0, y=0, z=0) is True
        assert controller.check_limits(x=40, y=40, z=5) is True
        
    def test_check_limits_out_of_bounds(self):
        """Test position outside limits"""
        controller = GCodeController()
        
        assert controller.check_limits(x=-1) is False
        assert controller.check_limits(x=41) is False
        assert controller.check_limits(y=-1) is False
        assert controller.check_limits(y=41) is False
        assert controller.check_limits(z=-1) is False
        assert controller.check_limits(z=6) is False
        
    def test_check_limits_partial_values(self):
        """Test checking limits with only some coordinates"""
        controller = GCodeController()
        
        assert controller.check_limits(x=20) is True
        assert controller.check_limits(y=20) is True
        assert controller.check_limits(z=2) is True
        
    def test_check_limits_disabled(self):
        """Test that limits can be disabled"""
        controller = GCodeController()
        controller.soft_limits_enabled = False
        
        # Should allow any position when disabled
        assert controller.check_limits(x=100, y=100, z=100) is True


class TestGCodeLoading:
    """Test G-code file loading"""
    
    def test_load_gcode_success(self):
        """Test successful G-code loading"""
        controller = GCodeController()
        gcode_content = "G1 X10 Y10\nG1 X20 Y20\n; Comment line\nG1 X30 Y30\n"
        
        with patch('builtins.open', mock_open(read_data=gcode_content)):
            result = controller.load_gcode('test.gcode')
            
        assert result is True
        assert len(controller.gcode) == 3  # Comments should be filtered
        assert 'G1 X10 Y10' in controller.gcode
        assert 'G1 X20 Y20' in controller.gcode
        assert 'G1 X30 Y30' in controller.gcode
        
    def test_load_gcode_filter_comments(self):
        """Test that comments are filtered out"""
        controller = GCodeController()
        gcode_content = "G1 X10\n; This is a comment\n(Another comment)\nG1 X20\n"
        
        with patch('builtins.open', mock_open(read_data=gcode_content)):
            controller.load_gcode('test.gcode')
            
        assert len(controller.gcode) == 2
        for line in controller.gcode:
            assert not line.startswith(';')
            assert not line.startswith('(')
            
    def test_load_gcode_filter_empty_lines(self):
        """Test that empty lines are filtered out"""
        controller = GCodeController()
        gcode_content = "G1 X10\n\n\nG1 X20\n   \n"
        
        with patch('builtins.open', mock_open(read_data=gcode_content)):
            controller.load_gcode('test.gcode')
            
        assert len(controller.gcode) == 2
        
    def test_load_gcode_file_not_found(self):
        """Test loading non-existent file"""
        controller = GCodeController()
        
        with patch('builtins.open', side_effect=FileNotFoundError):
            with patch('tkinter.messagebox.showerror'):
                result = controller.load_gcode('nonexistent.gcode')
                
        assert result is False


class TestGCodeStreaming:
    """Test G-code streaming functionality"""
    
    def test_start_streaming_no_gcode(self):
        """Test starting stream with no G-code loaded"""
        controller = GCodeController()
        
        with patch('tkinter.messagebox.showwarning'):
            controller.start_streaming()
            
        assert controller.streaming is False
        
    def test_start_streaming_with_gcode(self):
        """Test starting stream with G-code loaded"""
        controller = GCodeController()
        controller.gcode = ['G1 X10', 'G1 X20']
        
        with patch.object(controller, 'send_next_gcode_line'):
            controller.start_streaming()
            
        assert controller.streaming is True
        assert controller.paused is False
        assert controller.gcode_index == 0
        
    def test_pause_streaming(self):
        """Test pausing stream"""
        controller = GCodeController()
        controller.streaming = True
        
        controller.pause_streaming()
        
        assert controller.paused is True
        
    def test_resume_streaming(self):
        """Test resuming stream"""
        controller = GCodeController()
        controller.streaming = True
        controller.paused = True
        controller.gcode = ['G1 X10']
        
        with patch.object(controller, 'send_next_gcode_line'):
            controller.resume_streaming()
            
        assert controller.paused is False
        
    def test_stop_streaming(self):
        """Test stopping stream"""
        controller = GCodeController()
        controller.streaming = True
        controller.gcode_index = 5
        
        with patch.object(controller, 'return_to_origin'):
            controller.stop_streaming()
            
        assert controller.streaming is False
        assert controller.paused is False
        assert controller.gcode_index == 0


class TestOriginControl:
    """Test origin setting and homing"""
    
    def test_set_origin(self):
        """Test setting current position as origin"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 15, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.set_origin()
            
        assert result is True
        assert controller.origin_set is True
        assert controller.origin_position == {'x': 10, 'y': 15, 'z': 2}
        
    def test_set_origin_no_connection(self):
        """Test setting origin without connection"""
        controller = GCodeController()
        controller.port = None
        
        result = controller.set_origin()
        
        assert result is False
        assert controller.origin_set is False
        
    def test_return_to_origin(self):
        """Test returning to origin"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.return_to_origin()
            
        assert result is True
        assert controller.position == {'x': 0, 'y': 0, 'z': 0}


class TestEmergencyStop:
    """Test emergency stop functionality"""
    
    def test_emergency_stop(self):
        """Test emergency stop"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.streaming = True
        
        with patch.object(controller, 'return_to_origin'):
            controller.emergency_stop()
            
        controller.port.write.assert_called_once_with(b'\x18')
        assert controller.streaming is False


class TestSendCommand:
    """Test command sending functionality"""
    
    def test_send_command_no_port(self):
        """Test sending command with no connection"""
        controller = GCodeController()
        controller.port = None
        
        result = controller.send_command("G1 X10")
        
        assert result is False
        
    def test_send_command_adds_newline(self):
        """Test that newline is added to command"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        controller.send_command("G1 X10")
        
        controller.port.write.assert_called_once()
        sent_data = controller.port.write.call_args[0][0]
        assert sent_data.endswith(b'\n')
        
    def test_send_command_already_has_newline(self):
        """Test command that already has newline"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        controller.send_command("G1 X10\n")
        
        controller.port.write.assert_called_once()
        sent_data = controller.port.write.call_args[0][0]
        # Should not add double newline
        assert sent_data == b'G1 X10\n'


class TestDisconnect:
    """Test disconnection functionality"""
    
    def test_disconnect_with_port(self):
        """Test disconnecting when connected"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.running = True
        
        with patch.object(controller, 'return_to_origin'):
            controller.disconnect()
            
        assert controller.running is False
        controller.port.close.assert_called_once()
        
    def test_disconnect_without_port(self):
        """Test disconnecting when not connected"""
        controller = GCodeController()
        controller.port = None
        controller.running = True
        
        controller.disconnect()
        
        assert controller.running is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
