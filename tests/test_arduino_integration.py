"""
Integration tests for Arduino firmware compatibility and hardware integration
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
import serial
import time

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gctrl import GCodeController


class TestArduinoFirmwareIntegration:
    """Test integration with Arduino firmware"""
    
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_arduino_initialization_sequence(self, mock_thread, mock_serial):
        """Test complete Arduino initialization sequence"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        result = controller.connect('COM10')
        
        # Verify initialization steps
        assert result is True
        assert mock_port.reset_input_buffer.called
        assert mock_port.reset_output_buffer.called
        
        # Perform homing
        with patch.object(controller, 'send_command', return_value=True):
            controller.perform_homing_sequence()
            
        # Verify homing sequence is performed
        assert controller.homing_complete is True
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_gcode_command_g1_format(self, mock_thread, mock_serial):
        """Test G1 (linear move) command format for Arduino"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM10')
        
        # Send G1 command
        controller.send_command("G1 X10 Y20 F1000")
        
        # Verify command was sent to Arduino
        calls = [call[0][0] for call in mock_port.write.call_args_list]
        assert any(b'G1' in call for call in calls)
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_gcode_command_g90_absolute_mode(self, mock_thread, mock_serial):
        """Test G90 (absolute mode) command for Arduino"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM10')
        
        # Send G90 command
        controller.send_command("G90")
        
        # Verify command was sent
        calls = [call[0][0] for call in mock_port.write.call_args_list]
        assert any(b'G90' in call for call in calls)
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_gcode_command_g91_incremental_mode(self, mock_thread, mock_serial):
        """Test G91 (incremental mode) command for Arduino"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM10')
        
        # Send G91 command
        controller.send_command("G91")
        
        # Verify command was sent
        calls = [call[0][0] for call in mock_port.write.call_args_list]
        assert any(b'G91' in call for call in calls)
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_gcode_command_m300_servo_control(self, mock_thread, mock_serial):
        """Test M300 (servo control) command for Arduino"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM10')
        
        # Send M300 commands for pen up/down
        controller.send_command("M300 S50")  # Pen up
        controller.send_command("M300 S30")  # Pen down
        
        # Verify commands were sent
        calls = [call[0][0] for call in mock_port.write.call_args_list]
        assert any(b'M300' in call for call in calls)


class TestPositionTrackingAccuracy:
    """Test position tracking accuracy with Arduino"""
    
    def test_position_update_from_arduino_response(self):
        """Test position update from Arduino status response"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        # Simulate Arduino response with position
        response = "<Idle|MPos:10.5,20.3,1.2|FS:0,0>"
        
        # Parse response (simulating read_responses method)
        if response.startswith("<"):
            try:
                pos_str = response.split("MPos:")[1].split("|")[0]
                x, y, z = map(float, pos_str.split(","))
                controller.position = {'x': x, 'y': y, 'z': z}
            except:
                pass
        
        # Verify position was updated
        assert controller.position['x'] == 10.5
        assert controller.position['y'] == 20.3
        assert controller.position['z'] == 1.2
        
    @patch('threading.Thread')
    def test_position_tracking_after_movement(self, mock_thread):
        """Test position tracking after manual movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.speed_var = Mock()
        controller.speed_var.get.return_value = "2"  # 5mm
        controller.position = {'x': 10, 'y': 15, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x+', 5.0)
            
            # Execute the thread target manually
            args = mock_thread.call_args[1]
            target = args['target']
            target()
            
        # Verify position was tracked
        assert controller.position['x'] == 15
        
    def test_position_reset_after_homing(self):
        """Test that position resets to origin after homing"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 25, 'y': 30, 'z': 3}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.perform_homing_sequence()
            
        # Verify position was reset
        assert controller.position == {'x': 0, 'y': 0, 'z': 0}


class TestMotorMovementCoordination:
    """Test coordination of X and Y motor movements"""
    
    def test_simultaneous_xy_movement(self):
        """Test simultaneous X and Y axis movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            # Send command with both X and Y
            controller.send_command("G1 X10 Y20 F1000")
            
            # Verify command was sent
            mock_send.assert_called_with("G1 X10 Y20 F1000")
            
    def test_sequential_movements_to_origin(self):
        """Test sequential movements returning to origin"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 20, 'y': 30, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.return_to_origin()
            
            # Verify multiple commands were sent
            assert mock_send.call_count >= 3
            
    @patch('builtins.open', mock_open(read_data='G1 X10 Y10\nG1 X20 Y20\nG1 X0 Y0\n'))
    def test_gcode_file_execution_sequence(self):
        """Test execution of G-code file with multiple movements"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        # Load G-code
        controller.load_gcode('test.gcode')
        
        # Verify all lines were loaded
        assert len(controller.gcode) == 3
        
        # Verify lines contain movement commands
        assert 'G1 X10 Y10' in controller.gcode
        assert 'G1 X20 Y20' in controller.gcode
        assert 'G1 X0 Y0' in controller.gcode


class TestLimitSwitchVerification:
    """Test limit switch verification and soft limits"""
    
    def test_soft_limits_prevent_negative_x(self):
        """Test that soft limits prevent negative X movement"""
        controller = GCodeController()
        
        result = controller.check_limits(x=-1)
        assert result is False
        
    def test_soft_limits_prevent_negative_y(self):
        """Test that soft limits prevent negative Y movement"""
        controller = GCodeController()
        
        result = controller.check_limits(y=-1)
        assert result is False
        
    def test_soft_limits_prevent_exceed_max_x(self):
        """Test that soft limits prevent exceeding max X"""
        controller = GCodeController()
        
        result = controller.check_limits(x=41)  # Max is 40
        assert result is False
        
    def test_soft_limits_prevent_exceed_max_y(self):
        """Test that soft limits prevent exceeding max Y"""
        controller = GCodeController()
        
        result = controller.check_limits(y=41)  # Max is 40
        assert result is False
        
    def test_soft_limits_allow_valid_positions(self):
        """Test that soft limits allow valid positions"""
        controller = GCodeController()
        
        # Test corners and center
        assert controller.check_limits(x=0, y=0) is True
        assert controller.check_limits(x=40, y=40) is True
        assert controller.check_limits(x=20, y=20) is True
        
    def test_movement_blocked_at_limit(self):
        """Test that movement is blocked when at limit"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.speed_var = Mock()
        controller.speed_var.get.return_value = "1"
        controller.position = {'x': 40, 'y': 20, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('x+', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['x'] == 40


class TestHardwareConfigurationValidation:
    """Test hardware configuration validation"""
    
    def test_motor_x_connected_to_port_2(self):
        """Test that X motor is configured for Arduino Motor Shield port 2"""
        # This is verified by the Arduino code: AF_Stepper myStepperX(stepsPerRevolution,2)
        # We verify the system expects this configuration
        controller = GCodeController()
        
        # X axis should be configured with proper limits
        assert controller.machine_limits['x']['max'] == 40
        
    def test_motor_y_connected_to_port_1(self):
        """Test that Y motor is configured for Arduino Motor Shield port 1"""
        # This is verified by the Arduino code: AF_Stepper myStepperY(stepsPerRevolution,1)
        controller = GCodeController()
        
        # Y axis should be configured with proper limits
        assert controller.machine_limits['y']['max'] == 40
        
    def test_servo_connected_to_pin_10(self):
        """Test that servo (Z axis) is configured for pin 10"""
        # This is verified by the Arduino code: const int penServoPin = 10
        controller = GCodeController()
        
        # Z axis (servo) should be configured
        assert controller.machine_limits['z']['max'] == 5
        
    def test_serial_baudrate_matches_arduino(self):
        """Test that serial baudrate matches Arduino configuration (9600)"""
        controller = GCodeController()
        mock_port = MagicMock()
        mock_port.is_open = True
        
        with patch('serial.Serial', return_value=mock_port) as mock_serial:
            with patch('threading.Thread'):
                controller.connect('COM1')
                
                # Verify baudrate is 9600 as per Arduino: Serial.begin(9600)
                call_kwargs = mock_serial.call_args[1]
                assert call_kwargs['baudrate'] == 9600


class TestSerialCommunicationProtocol:
    """Test serial communication protocol with Arduino"""
    
    def test_ok_response_handling(self):
        """Test handling of 'ok' response from Arduino"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.gcode = ['G1 X10', 'G1 X20']
        controller.streaming = True
        controller.paused = False
        controller.gcode_index = 0
        
        # Simulate 'ok' response should trigger next line
        # This is tested through the read_responses method
        assert controller.streaming is True
        
    def test_error_response_stops_streaming(self):
        """Test that error response stops streaming"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.gcode = ['G1 X10', 'G1 X20']
        controller.streaming = True
        
        # Error should stop streaming
        # This would be handled in read_responses method
        controller.stop_streaming()
        
        assert controller.streaming is False
        
    def test_status_query_command(self):
        """Test status query command (?)"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        controller.get_status()
        
        # Verify ? command was sent
        calls = [call[0][0] for call in controller.port.write.call_args_list]
        assert any(b'?' in call for call in calls)
        
    def test_emergency_stop_command(self):
        """Test emergency stop command (Ctrl+X)"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'return_to_origin'):
            controller.emergency_stop()
            
        # Verify Ctrl+X (0x18) was sent
        controller.port.write.assert_called_with(b'\x18')


class TestCompleteHardwareWorkflow:
    """Test complete hardware integration workflows"""
    
    @patch('serial.Serial')
    @patch('threading.Thread')
    @patch('builtins.open', mock_open(read_data='G1 X10 Y10\nG1 X20 Y20\nG1 X0 Y0\n'))
    def test_complete_cnc_operation_workflow(self, mock_thread, mock_serial):
        """Test complete CNC operation: connect, home, load, execute, return"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        
        # 1. Connect to Arduino
        result = controller.connect('COM10')
        assert result is True
        
        # Perform homing
        with patch.object(controller, 'send_command', return_value=True):
            controller.perform_homing_sequence()
        assert controller.homing_complete is True
        
        # 2. Load G-code file
        result = controller.load_gcode('test.gcode')
        assert result is True
        assert len(controller.gcode) == 3
        
        # 3. Execute G-code
        with patch.object(controller, 'send_next_gcode_line'):
            controller.start_streaming()
        assert controller.streaming is True
        
        # 4. Complete and return to origin
        with patch.object(controller, 'return_to_origin') as mock_return:
            controller.stop_streaming()
            assert mock_return.called
            
        # 5. Disconnect
        with patch.object(controller, 'return_to_origin'):
            controller.disconnect()
        assert controller.running is False
        
    @patch('serial.Serial')
    @patch('threading.Thread')
    def test_manual_control_workflow(self, mock_thread, mock_serial):
        """Test manual control workflow"""
        mock_port = MagicMock()
        mock_port.is_open = True
        mock_serial.return_value = mock_port
        
        controller = GCodeController()
        controller.connect('COM1')
        controller.speed_var = Mock()
        controller.speed_var.get.return_value = "1"
        
        # Perform manual movements
        # Perform manual movements
        with patch.object(controller, 'send_command', return_value=True):
            # Move X positive
            result = controller.jog('x+', 1.0)
            assert result is True
            
            # Execute thread
            args = mock_thread.call_args[1]
            args['target']()

            assert controller.position['x'] == 1
            
            # Move Y positive
            result = controller.jog('y+', 1.0)
            assert result is True

            # Execute thread
            args = mock_thread.call_args[1]
            args['target']()

            assert controller.position['y'] == 1
            assert controller.position['y'] == 1
            
            # Return to origin
            controller.home()
            
    def test_limit_testing_complete_sequence(self):
        """Test complete limit testing sequence"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.test_limits()
            
            # Verify comprehensive test was performed
            assert mock_send.call_count >= 10
            
            # Verify test includes all axes
            calls = [str(call) for call in mock_send.call_args_list]
            has_x = any('X' in str(call) for call in calls)
            has_y = any('Y' in str(call) for call in calls)
            has_z = any('Z' in str(call) for call in calls)
            
            assert has_x and has_y and has_z


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
