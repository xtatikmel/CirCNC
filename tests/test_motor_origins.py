"""
Unit tests for motor origin verification and configuration
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import serial

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gctrl import GCodeController


class TestMotorConfiguration:
    """Test motor configuration for L293D stepper motors"""
    
    def test_motor_x_axis_exists(self):
        """Test that X-axis motor configuration exists"""
        controller = GCodeController()
        
        # Verify machine limits include X axis
        assert 'x' in controller.machine_limits
        assert 'min' in controller.machine_limits['x']
        assert 'max' in controller.machine_limits['x']
        
    def test_motor_y_axis_exists(self):
        """Test that Y-axis motor configuration exists"""
        controller = GCodeController()
        
        # Verify machine limits include Y axis
        assert 'y' in controller.machine_limits
        assert 'min' in controller.machine_limits['y']
        assert 'max' in controller.machine_limits['y']
        
    def test_servo_z_axis_exists(self):
        """Test that Z-axis servo configuration exists"""
        controller = GCodeController()
        
        # Verify machine limits include Z axis (servo)
        assert 'z' in controller.machine_limits
        assert 'min' in controller.machine_limits['z']
        assert 'max' in controller.machine_limits['z']
        
    def test_motor_x_axis_range(self):
        """Test X-axis motor working range"""
        controller = GCodeController()
        
        # X axis should have 0-80mm range for Nema stepper
        assert controller.machine_limits['x']['min'] == 0
        assert controller.machine_limits['x']['max'] == 80
        
    def test_motor_y_axis_range(self):
        """Test Y-axis motor working range"""
        controller = GCodeController()
        
        # Y axis should have 0-80mm range for Nema stepper
        assert controller.machine_limits['y']['min'] == 0
        assert controller.machine_limits['y']['max'] == 80
        
    def test_servo_z_axis_range(self):
        """Test Z-axis servo working range"""
        controller = GCodeController()
        
        # Z axis (servo) should have limited range
        assert controller.machine_limits['z']['min'] == 0
        assert controller.machine_limits['z']['max'] == 5


class TestMotorOrigins:
    """Test motor origin setting and verification"""
    
    def test_initial_origin_not_set(self):
        """Test that origin is not set on initialization"""
        controller = GCodeController()
        
        assert controller.origin_set is False
        assert controller.homing_complete is False
        
    def test_origin_position_initialized_to_zero(self):
        """Test that origin position is initialized to (0,0,0)"""
        controller = GCodeController()
        
        assert controller.origin_position == {'x': 0, 'y': 0, 'z': 0}
        
    def test_set_origin_command_format(self):
        """Test that set origin sends correct G-code command"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 15, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.set_origin()
            
            # Verify G92 command is sent to set origin
            mock_send.assert_called_with("G92 X0 Y0 Z0")
            
    def test_origin_position_saved(self):
        """Test that origin position is saved when set"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 12.5, 'y': 18.3, 'z': 1.5}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.set_origin()
            
        assert controller.origin_position == {'x': 12.5, 'y': 18.3, 'z': 1.5}
        assert controller.origin_set is True
        
    def test_return_to_origin_command(self):
        """Test that return to origin sends correct commands"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.return_to_origin()
            
            # Verify commands sent
            calls = [str(call) for call in mock_send.call_args_list]
            assert any('M300 S50' in str(call) for call in calls)  # Pen up
            assert any('G90' in str(call) for call in calls)  # Absolute mode
            assert any('G1 X0 Y0 Z0' in str(call) for call in calls)  # Move to origin


class TestMotorHoming:
    """Test motor homing sequence and verification"""
    
    def test_homing_sequence_commands(self):
        """Test that homing sequence sends correct commands"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.perform_homing_sequence()
            
            # Verify homing commands
            calls = [str(call) for call in mock_send.call_args_list]
            assert any('G90' in str(call) for call in calls)  # Absolute mode
            assert any('G91' in str(call) for call in calls)  # Incremental mode
            assert any('$H' in str(call) or 'G28' in str(call) for call in calls)  # Home command
            
    def test_homing_sets_origin(self):
        """Test that homing sequence sets origin"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.perform_homing_sequence()
            
        assert result is True
        assert controller.origin_set is True
        assert controller.homing_complete is True
        
    def test_homing_resets_position(self):
        """Test that homing resets position to (0,0,0)"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 15, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.perform_homing_sequence()
            
        assert controller.position == {'x': 0, 'y': 0, 'z': 0}
        
    def test_home_after_homing_complete(self):
        """Test home command after homing is complete"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.homing_complete = True
        
        with patch.object(controller, 'send_command', return_value=True) as mock_send:
            controller.home()
            
            # Should send move to origin, not full homing
            calls = [str(call) for call in mock_send.call_args_list]
            assert any('G1 X0 Y0 Z0' in str(call) for call in calls)


class TestMotorDirections:
    """Test motor direction verification"""
    
    def test_motor_x_positive_direction(self):
        """Test X-axis positive direction movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x+', 1.0)
            
        # Position should increase
        assert controller.position['x'] == 11
        
    def test_motor_x_negative_direction(self):
        """Test X-axis negative direction movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x-', 1.0)
            
        # Position should decrease
        assert controller.position['x'] == 9
        
    def test_motor_y_positive_direction(self):
        """Test Y-axis positive direction movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('y+', 1.0)
            
        # Position should increase
        assert controller.position['y'] == 11
        
    def test_motor_y_negative_direction(self):
        """Test Y-axis negative direction movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('y-', 1.0)
            
        # Position should decrease
        assert controller.position['y'] == 9
        
    def test_servo_z_positive_direction(self):
        """Test Z-axis (servo) positive direction movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('z+', 1.0)
            
        # Position should increase
        assert controller.position['z'] == 3
        
    def test_servo_z_negative_direction(self):
        """Test Z-axis (servo) negative direction movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('z-', 1.0)
            
        # Position should decrease
        assert controller.position['z'] == 1


class TestMotorStepCalculation:
    """Test motor step calculations and accuracy"""
    
    def test_position_tracking_initialization(self):
        """Test that position tracking is initialized to origin"""
        controller = GCodeController()
        
        assert controller.position == {'x': 0, 'y': 0, 'z': 0}
        
    def test_position_update_on_movement(self):
        """Test that position is updated after movement"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x+', 5.0)
            
        # Position should increase by 5mm
        assert controller.position['x'] == 15
        
    def test_motor_speed_slow(self):
        """Test slow motor speed (1mm)"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x+', 1.0)
            
        assert controller.position['x'] == 11
        
    def test_motor_speed_medium(self):
        """Test medium motor speed (5mm)"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x+', 5.0)
            
        assert controller.position['x'] == 15
        
    def test_motor_speed_fast(self):
        """Test fast motor speed (10mm)"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            controller.jog('x+', 10.0)
            
        assert controller.position['x'] == 20


class TestMotorLimitEnforcement:
    """Test motor limit enforcement for safety"""
    
    def test_x_axis_min_limit_enforcement(self):
        """Test that X-axis minimum limit is enforced"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 0, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('x-', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['x'] == 0
        
    def test_x_axis_max_limit_enforcement(self):
        """Test that X-axis maximum limit is enforced"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 80, 'y': 10, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('x+', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['x'] == 80
        
    def test_y_axis_min_limit_enforcement(self):
        """Test that Y-axis minimum limit is enforced"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 0, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('y-', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['y'] == 0
        
    def test_y_axis_max_limit_enforcement(self):
        """Test that Y-axis maximum limit is enforced"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 80, 'z': 2}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('y+', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['y'] == 80
        
    def test_z_axis_min_limit_enforcement(self):
        """Test that Z-axis minimum limit is enforced"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 0}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('z-', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['z'] == 0
        
    def test_z_axis_max_limit_enforcement(self):
        """Test that Z-axis maximum limit is enforced"""
        controller = GCodeController()
        controller.port = MagicMock()
        controller.port.is_open = True
        controller.position = {'x': 10, 'y': 10, 'z': 5}
        
        with patch.object(controller, 'send_command', return_value=True):
            result = controller.jog('z+', 1.0)
            
        # Movement should be blocked
        assert result is False
        assert controller.position['z'] == 5
        
    def test_soft_limits_can_be_disabled(self):
        """Test that soft limits can be disabled for special cases"""
        controller = GCodeController()
        controller.soft_limits_enabled = False
        
        # Should allow any position when disabled
        assert controller.check_limits(x=100, y=100, z=100) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
