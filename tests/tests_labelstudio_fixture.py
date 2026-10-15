"""Label Studio export fixture (SYNTHETIC) shared by tests."""


def ls_export(image_id="img1", w=2000, h=1000):
    res = [{"id": "r0", "from_name": "finding", "to_name": "image", "type": "rectanglelabels", "original_width": w, "original_height": h,
            "value": {"x": 10, "y": 20, "width": 5, "height": 10, "rectanglelabels": ["Caries"]}},
           {"id": "r0", "from_name": "tooth_fdi", "to_name": "image", "type": "choices", "value": {"choices": ["16"]}}]
    return [{"id": 1, "data": {"image": "http://x", "image_id": image_id}, "annotations": [{"completed_by": 1, "result": res}]}]
