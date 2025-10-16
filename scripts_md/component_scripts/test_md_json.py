import json

test_data = {
    "images": [
        {
            "file": "Z:/East/Camera Trap Images (raw)/site1/2024-12-12_2025-01-31/BTCF100/IMG_0001.JPG",
            "detections": [
                {
                    "category": "1",
                    "conf": 0.99,
                    "bbox": [0.1, 0.1, 0.5, 0.5]
                }
            ]
        }
    ]
}

with open("md_test.json", "w") as f:
    json.dump(test_data, f, indent=2)