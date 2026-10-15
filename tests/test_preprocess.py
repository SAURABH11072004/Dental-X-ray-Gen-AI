import io
import unittest

import numpy as np
from PIL import Image

import helpers
from dentexmodel.data.features import handcrafted_embedding
from dentexmodel.data.preprocess import (ImageLimits, PreprocessConfig, ResizeTransform, load_gray, preprocess_image,
                                         validate_upload)
from dentexmodel.errors import ImageValidationError


def _png(arr8, mode="L"):
    buf = io.BytesIO()
    Image.fromarray(arr8, mode=mode).save(buf, "PNG")
    return buf.getvalue()


class UploadValidation(unittest.TestCase):
    L = ImageLimits(max_bytes=1_000_000, min_side=64, max_side=5000)

    def test_ok_png_and_jpeg(self):
        arr = (np.random.default_rng(0).random((128, 200)) * 255).astype("uint8")
        info = validate_upload(_png(arr), "a.png", self.L)
        self.assertEqual((info["width"], info["height"], info["format"]), (200, 128, "PNG"))
        buf = io.BytesIO(); Image.fromarray(arr).save(buf, "JPEG")
        self.assertEqual(validate_upload(buf.getvalue(), "x.JPG", self.L)["format"], "JPEG")

    def test_rejections(self):
        arr = np.zeros((128, 128), "uint8")
        cases = [(b"", "a.png", "empty_file"), (_png(arr), "a.gif", "unsupported_type"), (_png(arr), "a", "unsupported_type"),
                 (b"MZ" + b"\0" * 100, "a.png", "bad_signature"), (_png(arr)[:60], "a.png", "corrupt_image"),
                 (_png(np.zeros((16, 16), "uint8")), "a.png", "bad_dimensions"), (_png(arr), "../../etc/passwd.txt", "unsupported_type")]
        for data, name, code in cases:
            with self.assertRaises(ImageValidationError, msg=name) as cm:
                validate_upload(data, name, self.L)
            self.assertEqual(cm.exception.code, code)

    def test_size_limit(self):
        with self.assertRaises(ImageValidationError) as cm:
            validate_upload(_png(np.zeros((128, 128), "uint8")), "a.png", ImageLimits(max_bytes=10, min_side=8))
        self.assertEqual(cm.exception.code, "file_too_large")


class PreprocessTests(unittest.TestCase):
    def _img(self, tmp, w=800, h=400, mode="L", dtype="uint8"):
        p = tmp / "a.png"
        rng = np.random.default_rng(1)
        if dtype == "uint16":
            Image.fromarray((rng.random((h, w)) * 60000).astype("uint16")).save(p)
        elif mode == "RGB":
            Image.fromarray((rng.random((h, w, 3)) * 255).astype("uint8"), "RGB").save(p)
        else:
            Image.fromarray((rng.random((h, w)) * 255).astype("uint8"), "L").save(p)
        return p

    def test_aspect_ratio_and_transform(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            p = self._img(pathlib.Path(d))
            r = preprocess_image(p, PreprocessConfig(max_side=200))
            self.assertEqual(r.array.shape, (100, 200))
            self.assertAlmostEqual(r.transform.scale, 0.25)
            self.assertTrue(0.0 <= r.array.min() and r.array.max() <= 1.0)
            box = np.array([[100, 40, 300, 200]])
            np.testing.assert_allclose(r.transform.boxes_to_original(r.transform.boxes_to_processed(box)), box)
            self.assertEqual(r.metadata["original_size"], [800, 400])
            self.assertIn("grayscale", r.metadata["steps"])

    def test_no_upscaling_and_square_padding(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            p = self._img(pathlib.Path(d), 100, 50)
            r = preprocess_image(p, PreprocessConfig(max_side=1000, pad_to_square=True))
            self.assertEqual(r.array.shape, (100, 100))
            self.assertEqual((r.transform.pad_x, r.transform.pad_y), (0, 25))
            b = r.transform.boxes_to_processed([[10, 10, 20, 20]])
            np.testing.assert_allclose(b, [[10, 35, 20, 45]])

    def test_mask_follows_geometry(self):
        tf = ResizeTransform(orig_w=100, orig_h=50, scale=0.5, pad_x=0, pad_y=10, out_w=50, out_h=45)
        m = np.zeros((50, 100), bool); m[10:30, 20:60] = True
        out = tf.mask_to_processed(m)
        self.assertEqual(out.shape, (45, 50))
        ys, xs = np.where(out)
        self.assertEqual((ys.min(), ys.max(), xs.min(), xs.max()), (15, 24, 10, 29))

    def test_16bit_and_rgb(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            for kw in ({"dtype": "uint16"}, {"mode": "RGB"}):
                g = load_gray(self._img(pathlib.Path(d), **kw))
                self.assertEqual(g.dtype, np.float32)
                self.assertTrue(0 <= g.min() and g.max() <= 1)

    def test_clahe_reports_backend_or_skip(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            r = preprocess_image(self._img(pathlib.Path(d)), PreprocessConfig(clahe=True, max_side=200))
            self.assertIn("clahe_applied", r.metadata)
            self.assertEqual(r.metadata["clahe_applied"], r.metadata["clahe_backend"] is not None)

    def test_embedding(self):
        e = handcrafted_embedding(np.random.default_rng(0).random((100, 200)).astype("float32"))
        self.assertAlmostEqual(float(np.linalg.norm(e)), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
