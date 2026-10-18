"""
AI-Powered Adaptive Vehicle Dashboard System
Main Application Entry Point

Author: Automotive Software Engineering Project
Version: 1.0.0
Description: Intelligent dashboard that adapts to driver cognitive state and driving behavior
"""

import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from modern_dashboard_ui import AdaptiveDashboardUI
from vehicle_simulator import VehicleSimulator
from driver_monitor import DriverMonitor
from behavior_analyzer import BehaviorAnalyzer
from decision_engine import AdaptiveDecisionEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dashboard_system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AdaptiveDashboardApplication:
    """
    Main application controller that orchestrates all system modules
    """
    
    def __init__(self):
        """Initialize the adaptive dashboard system"""
        logger.info("Initializing Adaptive Dashboard System...")
        
        # Initialize Qt Application
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("AI-Powered Adaptive Dashboard")
        
        # Initialize core modules
        self.vehicle_simulator = VehicleSimulator()
        # Use built-in camera detection to avoid iPhone camera on macOS
        builtin_camera_index = DriverMonitor.find_builtin_camera()
        self.driver_monitor = DriverMonitor(camera_index=builtin_camera_index)
        self.behavior_analyzer = BehaviorAnalyzer()
        self.decision_engine = AdaptiveDecisionEngine()
        
        # Initialize UI (last, as it connects to other modules)
        self.dashboard_ui = AdaptiveDashboardUI(
            vehicle_simulator=self.vehicle_simulator,
            driver_monitor=self.driver_monitor,
            behavior_analyzer=self.behavior_analyzer,
            decision_engine=self.decision_engine
        )
        
        # Connect signals between modules
        self._connect_signals()
        
        logger.info("System initialization complete")
    
    def _connect_signals(self):
        """Connect inter-module communication signals"""
        # Vehicle simulator updates
        self.vehicle_simulator.state_updated.connect(self.behavior_analyzer.process_vehicle_data)
        self.vehicle_simulator.state_updated.connect(self.decision_engine.update_vehicle_state)
        
        # Driver monitor updates
        self.driver_monitor.cognitive_state_updated.connect(self.decision_engine.update_driver_state)
        
        # Behavior analyzer updates
        self.behavior_analyzer.behavior_updated.connect(self.decision_engine.update_behavior_state)
        
        # Decision engine to UI
        self.decision_engine.ui_adaptation_required.connect(self.dashboard_ui.adapt_interface)
        self.decision_engine.alert_triggered.connect(self.dashboard_ui.show_alert)
        
        logger.info("Inter-module signals connected")
    
    def run(self):
        """Start the application"""
        logger.info("Starting Adaptive Dashboard System...")
        
        # Show the main dashboard window
        self.dashboard_ui.show()
        
        # Start monitoring and simulation
        self.vehicle_simulator.start()
        self.driver_monitor.start()
        
        # Enter Qt event loop
        return self.app.exec_()
    
    def shutdown(self):
        """Gracefully shutdown all modules"""
        logger.info("Shutting down system...")
        
        self.driver_monitor.stop()
        self.vehicle_simulator.stop()
        
        logger.info("System shutdown complete")


def main():
    """Main entry point"""
    try:
        # Create and run application
        app = AdaptiveDashboardApplication()
        exit_code = app.run()
        
        # Cleanup
        app.shutdown()
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
