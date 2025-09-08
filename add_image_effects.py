import numpy as np
import re
import os
from scipy.interpolate import RegularGridInterpolator
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

class ImageEffectsEngine:
    """
    A class to apply various effects to a PIL Image.
    Adapted from the video EffectsEngine.
    """
    def __init__(self):
        """
        Initializes the ImageEffectsEngine and the mapping of effect names to methods.
        """
        self.effects_map = {
            'look-up table': self.apply_lut,
            'Black & White': self.apply_black_and_white,
            'Color Saturation': self.apply_color_saturation,
            'Contrast / Brightness': self.apply_contrast_brightness,
            'Chromatic Aberration': self.apply_chromatic_aberration,
            'Pixelated Effect': self.apply_pixelated,
            'Invert Colors': self.apply_invert_colors,
            'Film Grain': self.apply_film_grain,
            'Glitch': self.apply_glitch,
            'Neon Glow': self.apply_neon_glow,
            'Cartoon / Painterly': self.apply_cartoon_painterly,
            'Vignette': self.apply_vignette,
            'Rotate': self.apply_rotate,
        }

    def apply_effects_in_sequence(self, image_path: str, effects: list, output_path: str) -> str:
        """
        Applies a list of effects to an image in the specified order.
        """
        img = Image.open(image_path).convert('RGB')
        
        for effect in effects:
            if isinstance(effect, tuple):
                effect_name, *params = effect
                if effect_name in self.effects_map:
                    img = self.effects_map[effect_name](img, *params)
            elif isinstance(effect, str):
                if effect in self.effects_map:
                    img = self.effects_map[effect](img)

        img.save(output_path, format='WEBP', quality=100, lossless=True, method=6, optimize=True, subsampling=0)
        img.close()
        return output_path

    # --- Effect Implementations for PIL Images ---

    @staticmethod
    def parse_cube_file(file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()
        lut_size = 0
        lut_data = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('LUT_3D_SIZE'):
                lut_size = int(line.split()[-1])
            elif re.match(r'^[0-9eE.+-]+\s+[0-9eE.+-]+\s+[0-9eE.+-]+', line):
                lut_data.append([float(c) for c in line.split()])
        if lut_size == 0 or not lut_data:
            raise ValueError("Invalid or unsupported .cube file format.")
        return np.array(lut_data).reshape((lut_size, lut_size, lut_size, 3)), lut_size

    def apply_lut(self, img: Image.Image, cube_file_path: str) -> Image.Image:
        lut_table, lut_size = self.parse_cube_file(cube_file_path)
        grid_points = np.linspace(0, 1, lut_size)
        interpolator = RegularGridInterpolator((grid_points, grid_points, grid_points), lut_table)

        frame = np.array(img)
        normalized_frame = frame.astype(np.float32) / 255.0
        pixels = normalized_frame.reshape(-1, 3)
        new_pixels = interpolator(pixels)
        new_frame = (np.clip(new_pixels, 0, 1) * 255).astype(np.uint8)
        return Image.fromarray(new_frame.reshape(frame.shape))

    def apply_black_and_white(self, img: Image.Image) -> Image.Image:
        return ImageOps.grayscale(img).convert('RGB')

    def apply_color_saturation(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        level_map = {'low': 1.3, 'medium': 1.7, 'high': 2.2}
        factor = level_map.get(level, 1.7)
        enhancer = ImageEnhance.Color(img)
        return enhancer.enhance(factor)

    def apply_contrast_brightness(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        # The user's values (0.2, 0.6, 1.0) are mapped to a multiplicative factor
        # where 1.0 is original. We'll make the effect more noticeable.
        contrast_map = {'low': 1.2, 'medium': 1.5, 'high': 1.8}
        factor = contrast_map.get(level, 1.5)
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    def apply_chromatic_aberration(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        level_map = {'low': 3, 'medium': 6, 'high': 10}
        shift = level_map.get(level, 6)
        frame = np.array(img)
        r, g, b = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
        r_shifted = np.roll(r, -shift, axis=1)
        b_shifted = np.roll(b, shift, axis=1)
        new_frame = np.stack([r_shifted, g, b_shifted], axis=-1).astype('uint8')
        return Image.fromarray(new_frame)

    def apply_pixelated(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        # For this effect, a lower number means MORE pixelation.
        level_map = {'low': 95, 'medium': 85, 'high': 75}
        pixel_size = level_map.get(level, 85)
        w, h = img.size
        img_small = img.resize((pixel_size, int(pixel_size * h/w)), Image.Resampling.BILINEAR)
        return img_small.resize(img.size, Image.Resampling.NEAREST)

    def apply_invert_colors(self, img: Image.Image) -> Image.Image:
        return ImageOps.invert(img)

    def apply_film_grain(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        level_map = {'low': 1, 'medium': 1.5, 'high': 2}
        strength = level_map.get(level, 1.5)
        frame = np.array(img)
        noise = np.random.randint(-25, 25, frame.shape) * strength
        new_frame = np.clip(frame + noise, 0, 255).astype('uint8')
        return Image.fromarray(new_frame)

    def apply_neon_glow(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        from scipy.ndimage import sobel
        level_map = {'low': 80, 'medium': 50, 'high': 30}
        threshold = level_map.get(level, 50)
        
        frame = np.array(img)
        gray = np.dot(frame[...,:3], [0.2989, 0.5870, 0.1140])
        sx = sobel(gray, axis=0, mode='constant')
        sy = sobel(gray, axis=1, mode='constant')
        edges = np.hypot(sx, sy)
        edges = (edges / np.max(edges) * 255)
        
        neon_color = np.array([0, 255, 255]) # Cyan glow
        neon_frame = np.zeros_like(frame)
        neon_frame[edges > threshold] = neon_color
        
        return Image.fromarray(neon_frame)

    def apply_cartoon_painterly(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        level_map = {'low': 5, 'medium': 15, 'high': 25}
        filter_size = level_map.get(level, 15)
        return img.filter(ImageFilter.MedianFilter(size=filter_size)).quantize(colors=64).convert('RGB')

    def apply_vignette(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        level_map = {'low': 0.5, 'medium': 1.0, 'high': 1.5}
        strength = level_map.get(level, 1.0)
        
        w, h = img.size
        Y, X = np.ogrid[:h, :w]
        center_y, center_x = h / 2, w / 2
        dist_from_center = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        radial_grad = dist_from_center / max_dist
        vignette_mask = 1 - (radial_grad**2) * strength
        
        frame = np.array(img)
        new_frame = (frame * vignette_mask[:, :, np.newaxis]).astype('uint8')
        return Image.fromarray(new_frame)

    def apply_glitch(self, img: Image.Image, level: str = 'medium') -> Image.Image:
        import random
        level_map = {'low': 30, 'medium': 50, 'high': 70} # Probability of a strip being glitched
        probability = level_map.get(level, 50)
        
        frame = np.array(img)
        h, w, _ = frame.shape
        
        # We can simulate a few glitches
        for _ in range(random.randint(1, 5)):
            if random.random() < probability:
                glitch_height = max(1, h // 20)
                y = random.randint(0, h - glitch_height)
                strip = frame[y:y+glitch_height, :, :].copy()
                displacement = random.randint(-w//4, w//4)
                strip = np.roll(strip, displacement, axis=1)
                if displacement > 0:
                    strip[:, :displacement] = 0
                else:
                    strip[:, displacement:] = 0
                frame[y:y+glitch_height, :, :] = strip
        
        return Image.fromarray(frame)

    def apply_rotate(self, img: Image.Image, level: str = 'high') -> Image.Image:
        level_map = {'low': 15, 'medium': 45, 'high': 90}
        angle = level_map.get(level, 90)
        return img.rotate(angle, expand=True)