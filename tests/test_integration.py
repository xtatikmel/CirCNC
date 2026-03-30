"""
Integration tests for GCodeController workflows
"""
import pytest
import time
from unittest.mock import Mock, MagicMock, patch, mock_open
import serial

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gctrl import GCodeController


class TestConnectionWorkflow:
    """Test complete connection workflow"""
    @patch('gctrl.serial')
    @patch('threading.Thread')
    def test_successful_connection(self, mock_thread, mock_serial_module):
        """Test successful connection workflow"""
        # Setup mock serial port
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial_module.Serial.return_value = mock_port

        controller = GCodeController()
        callback = Mock()
        controller.set_log_callback(callback)

        # Connect to port
        result = controller.connect('COM1')

        # Verify connection
        assert result is True
        assert controller.port_name == 'COM1'
        assert mock_port.reset_input_buffer.called
        assert mock_port.reset_output_buffer.called

    @patch('gctrl.serial')
    def test_connection_failure(self, mock_serial_module):
        """Test connection failure handling"""
        # Simulate connection error
        mock_serial_module.Serial.side_effect = Exception("Port not found")

        controller = GCodeController()
        callback = Mock()
        controller.set_log_callback(callback)

        # Try to connect
        result = controller.connect('COM10')

        # Verify failure handling
        assert result is False
        assert controller.port_name is None

    @patch('gctrl.serial')
    @patch('threading.Thread')
    def test_disconnect_workflow(self, mock_thread, mock_serial_module):
        """Test complete disconnect workflow"""
        # Setup connected controller
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial_module.Serial.return_value = mock_port

        controller = GCodeController()
        controller.connect('COM1')

        # Disconnect
        with patch.object(controller, 'return_to_origin'):
            controller.disconnect()

        # Verify cleanup
        assert controller.running is False
        assert mock_port.close.called


class TestGCodeExecutionWorkflow:
    """Test complete G-code execution workflow"""
    
    @patch('builtins.open', mock_open(read_data='G1 X10 Y10\nG1 X20 Y20\nG1 X0 Y0\n'))
    def test_load_and_stream_gcode(self):
        """Test loading and streaming G-code"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        # Load G-code
        result = controller.load_gcode('test.gcode')
        assert result is True
        assert len(controller.gcode) == 3
        
        # Start streaming
        with patch.object(controller, 'send_next_gcode_line', return_value=True):
            controller.start_streaming()
            
        assert controller.streaming is True
        assert controller.gcode_index == 0
        
    def test_pause_resume_workflow(self):
        """Test pause and resume workflow"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.gcode = ['G1 X10', 'G1 X20', 'G1 X30']
        
        # Start streaming
        with patch.object(controller, 'send_next_gcode_line'):
            controller.start_streaming()
            assert controller.streaming is True
            
            # Pause
            controller.pause_streaming()
            assert controller.paused is True
            
            # Resume
            controller.resume_streaming()
            assert controller.paused is False
            
    def test_stop_workflow(self):
        """Test stop workflow"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.gcode = ['G1 X10', 'G1 X20']
        controller.streaming = True
        controller.gcode_index = 1
        
        # Stop streaming
        with patch.object(controller, 'return_to_origin'):
            controller.stop_streaming()
            
        assert controller.streaming is False
        assert controller.gcode_index == 0


class TestManualControlWorkflow:
    """Test manual control (jog) workflows"""
    
    @patch('threading.Thread')
    def test_jog_within_limits(self, mock_thread):
        """Test jogging within machine limits"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.speed_var = Mock()
        controller.speed_var.get.return_value = "1"
        controller.position = {'x': 20, 'y': 20, 'z': 2}
        
        # Jog in positive X direction
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('x+', 1.0)
            
            # Execute thread
            args = mock_thread.call_args[1]
            args['target']()
            
        assert result is True
        assert controller.position['x'] == 21
        
    def test_jog_at_limit(self):
        """Test jogging at machine limit"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.speed_var = Mock()
        controller.speed_var.get.return_value = "3"  # Fast: 10mm
        controller.position = {'x': 35, 'y': 20, 'z': 2}
        
        # Try to jog beyond limit
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('x+', 10.0)
            
        # Should be blocked by limit check
        assert result is False
        assert controller.position['x'] == 35  # Position unchanged
        
    @patch('threading.Thread')
    def test_jog_all_directions(self, mock_thread):
        """Test jogging in all directions"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.speed_var = Mock()
        controller.speed_var.get.return_value = "1"
        controller.position = {'x': 20, 'y': 20, 'z': 2}
        
        directions = ['x+', 'x-', 'y+', 'y-', 'z+', 'z-']
        
        with patch.object(controller, 'send_command', return_value=True):
            for direction in directions:
                initial_pos = controller.position.copy()
                result = controller.jog(direction, 1.0)
                assert result is True
                
                # Execute thread
                args = mock_thread.call_args[1]
                args['target']()
                
                # Position should have changed
                assert controller.position != initial_pos


class TestHomingWorkflow:
    """Test homing workflow"""
    
    def test_perform_homing_sequence(self):
        """Test complete homing sequence"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.perform_homing_sequence()
            
        assert result is True
        assert controller.homing_complete is True
        assert controller.origin_set is True
        assert controller.position == {'x': 0, 'y': 0, 'z': 0}
        
    def test_home_after_homing_complete(self):
        """Test home command after homing is complete"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.homing_complete = True
        controller.position = {'x': 10, 'y': 15, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.home()
            
        assert result is True
        
    def test_set_origin_workflow(self):
        """Test setting custom origin"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 15, 'y': 20, 'z': 1}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.set_origin()
            
        assert result is True
        assert controller.origin_set is True
        assert controller.origin_position == {'x': 15, 'y': 20, 'z': 1}


class TestEmergencyWorkflow:
    """Test emergency stop workflow"""
    
    def test_emergency_during_streaming(self):
        """Test emergency stop during G-code execution"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.gcode = ['G1 X10', 'G1 X20', 'G1 X30']
        controller.streaming = True
        controller.gcode_index = 1
        
        with patch.object(controller, 'return_to_origin'):
            controller.emergency_stop()
            
        # Verify emergency stop
        controller.port.write.assert_called_with(b'\x18')
        assert controller.streaming is False
        assert controller.paused is False
        
    def test_emergency_during_manual_control(self):
        """Test emergency stop during manual control"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.streaming = False
        
        with patch.object(controller, 'return_to_origin'):
            controller.emergency_stop()
            
        # Verify emergency stop sent
        controller.port.write.assert_called_with(b'\x18')


class TestLimitTestingWorkflow:
    """Test limit testing workflow"""
    
    def test_test_limits_sequence(self):
        """Test the complete limits testing sequence"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.test_limits()
            
        # Verify that multiple commands were sent
        assert mock_send.call_count >= 10
        
        # Check that commands include various movements
        calls = [str(call) for call in mock_send.call_args_list]
        assert any('X' in str(call) for call in calls)
        assert any('Y' in str(call) for call in calls)
        assert any('Z' in str(call) for call in calls)


class TestCompleteWorkflow:
    """Test complete end-to-end workflow"""
    def test_complete_cnc_workflow(self):
        """Test complete workflow: connect, home, load, execute, disconnect"""
        # Use context managers for patches to keep decorator stack simple
        with patch('gctrl.serial') as mock_serial_module, \
             patch('threading.Thread') as mock_thread, \
             patch('builtins.open', mock_open(read_data='G1 X10 Y10\nG1 X20 Y20\nG1 X0 Y0\n')):
            # Setup
            mock_port = MagicMock()
            mock_port.is_open = True
            mock_serial_module.Serial.return_value = mock_port

            controller = GCodeController()
            callback = Mock()
            controller.set_log_callback(callback)

            # 1. Connect
            result = controller.connect('COM1')
            assert result is True

            # 2. Load G-code
            result = controller.load_gcode('test.gcode')
            assert result is True
            assert len(controller.gcode) == 3

            # 3. Start execution
            with patch.object(controller, 'send_next_gcode_line'):
                controller.start_streaming()
            assert controller.streaming is True

            # 4. Stop execution
            with patch.object(controller, 'return_to_origin'):
                controller.stop_streaming()
            assert controller.streaming is False

            # 5. Disconnect
            with patch.object(controller, 'return_to_origin'):
                controller.disconnect()
            assert controller.running is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
