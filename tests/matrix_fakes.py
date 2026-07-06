"""Test doubles for the matrix backend (mirrors the rgbmatrix graphics API)."""


class FakeFont:
    """Fixed-width fake of graphics.Font."""

    def __init__(self):
        self.path = None

    def LoadFont(self, path):
        self.path = path

    def CharacterWidth(self, _codepoint):
        return 4


class FakeColor:
    def __init__(self, r, g, b):
        self.rgb = (r, g, b)


class FakeGraphics:
    """Fake of the backend `graphics` module."""

    Font = FakeFont
    Color = FakeColor

    def DrawText(self, canvas, font, x, y, color, text):
        canvas.texts.append({"x": x, "y": y, "text": text, "color": color.rgb})
        return sum(font.CharacterWidth(ord(c)) for c in text)


class FakeCanvas:
    def __init__(self, width=32, height=32):
        self.width = width
        self.height = height
        self.pixels = {}
        self.texts = []

    def SetPixel(self, x, y, r, g, b):
        self.pixels[(x, y)] = (r, g, b)

    def Clear(self):
        self.pixels = {}
        self.texts = []

    def drawn_strings(self):
        return [t["text"] for t in self.texts]


class FakeMatrix:
    def __init__(self, width=32, height=32):
        self.width = width
        self.height = height
        self.cleared = False
        self.swapped_frames = 0

    def CreateFrameCanvas(self):
        return FakeCanvas(self.width, self.height)

    def SwapOnVSync(self, canvas):
        self.swapped_frames += 1
        return canvas

    def Clear(self):
        self.cleared = True
