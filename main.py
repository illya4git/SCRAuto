# main.py
from src.core.config import AutopilotConfig
from src.core.orchestrator import GameOrchestrator
from src.vision.ocr_processor import OCRProcessor
from src.vision.ui_detector import UIDetector
from src.control.controller import TrainController
from src.control.calibration import TrainCalibrator
from src.control.autopilot import AutopilotLogic


def main():
    print("=======================================")
    print("      SCR Autopilot Framework          ")
    print("=======================================")
    print("1. Autopilot Mode (Drive automatically)")
    print("2. Calibration Mode (Record offsets manually)")
    print("=======================================")

    mode = input("Select mode (1 or 2): ").strip()
    train_model = input("Enter the Train Model (e.g., 'Class 357 4-car'): ").strip()

    # 1. Initialize Configuration
    config = AutopilotConfig()

    # 2. Inject Config into Modules
    ocr = OCRProcessor(config)
    ui = UIDetector(config)
    controller = TrainController()

    calibrator = None
    pilot = None

    if mode == '2':
        calibrator = TrainCalibrator(train_model)
    else:
        pilot = AutopilotLogic(train_model)

    # 3. Spin up Orchestrator
    orchestrator = GameOrchestrator(
        config=config,
        ocr=ocr,
        ui=ui,
        controller=controller,
        mode=mode,
        pilot=pilot,
        calibrator=calibrator
    )

    orchestrator.run()


if __name__ == "__main__":
    main()