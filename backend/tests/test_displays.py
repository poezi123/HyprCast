import unittest

from hyprcast import displays, hypr


class DisplaysTest(unittest.TestCase):
    def test_common_mode_picks_largest_shared(self):
        laptop = {"availableModes": ["1920x1080@144.00Hz", "1920x1080@60.00Hz", "1280x720@144.00Hz"]}
        beamer = {"availableModes": ["1280x800@60.00Hz", "1280x720@60.00Hz", "1024x768@60.00Hz"]}
        self.assertEqual(displays.common_mode(laptop, beamer), "1280x720@144")

    def test_common_mode_prefers_full_hd(self):
        laptop = {"availableModes": ["1920x1080@60.00Hz", "1920x1080@144.00Hz"]}
        tafel = {"availableModes": ["3840x2160@60.00Hz", "1920x1080@60.00Hz"]}
        self.assertEqual(displays.common_mode(laptop, tafel), "1920x1080@144")

    def test_common_mode_none(self):
        self.assertIsNone(displays.common_mode({"availableModes": ["800x600@60Hz"]},
                                               {"availableModes": ["1024x768@60Hz"]}))

    def test_is_internal(self):
        self.assertTrue(displays.is_internal("eDP-1"))
        self.assertFalse(displays.is_internal("HDMI-A-1"))

    def test_lua_table_escapes(self):
        self.assertEqual(hypr.lua_table({"output": 'a"b', "disabled": True}),
                         '{ output = "a\\"b", disabled = true }')


if __name__ == "__main__":
    unittest.main()
