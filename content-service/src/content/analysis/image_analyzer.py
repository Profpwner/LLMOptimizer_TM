"""
Image content analysis for optimization.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import io
from enum import Enum

from pydantic import BaseModel, Field
from PIL import Image
import numpy as np


logger = logging.getLogger(__name__)


class ImageFormat(str, Enum):
    """Supported image formats."""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"


class ImageAnalysisResult(BaseModel):
    """Image analysis results."""
    # Basic properties
    format: ImageFormat
    width: int
    height: int
    aspect_ratio: float
    file_size_bytes: int
    
    # Technical properties
    color_mode: str  # RGB, RGBA, L, etc.
    has_transparency: bool = False
    bit_depth: int = 8
    dpi: Tuple[int, int] = (72, 72)
    
    # Quality metrics
    estimated_quality: int = Field(default=85, ge=0, le=100)
    is_optimized: bool = False
    optimization_potential: float = Field(default=0.0, ge=0, le=1)
    
    # Content analysis
    dominant_colors: List[str] = Field(default_factory=list)
    brightness: float = Field(default=0.5, ge=0, le=1)
    contrast: float = Field(default=0.5, ge=0, le=1)
    sharpness: float = Field(default=0.5, ge=0, le=1)
    
    # Accessibility
    has_text: bool = False
    text_contrast_ratio: Optional[float] = None
    
    # Recommendations
    optimization_suggestions: List[str] = Field(default_factory=list)
    accessibility_issues: List[str] = Field(default_factory=list)
    
    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class ImageAnalyzer:
    """
    Analyze images for optimization and accessibility.
    """
    
    # Optimal image dimensions for web
    OPTIMAL_DIMENSIONS = {
        "thumbnail": (150, 150),
        "small": (320, 240),
        "medium": (640, 480),
        "large": (1024, 768),
        "hero": (1920, 1080)
    }
    
    # Maximum recommended file sizes (bytes)
    MAX_FILE_SIZES = {
        "thumbnail": 50 * 1024,      # 50KB
        "small": 100 * 1024,         # 100KB
        "medium": 300 * 1024,        # 300KB
        "large": 500 * 1024,         # 500KB
        "hero": 1024 * 1024          # 1MB
    }
    
    async def analyze(
        self,
        image_data: bytes,
        format: Optional[str] = None
    ) -> ImageAnalysisResult:
        """
        Analyze image content.
        
        Args:
            image_data: Raw image bytes
            format: Image format (auto-detected if not provided)
        
        Returns:
            Image analysis results
        """
        try:
            # Open image
            image = Image.open(io.BytesIO(image_data))
            
            # Get basic properties
            width, height = image.size
            aspect_ratio = width / height if height > 0 else 0
            
            # Detect format
            if not format:
                format = image.format.lower() if image.format else "unknown"
            
            # Create result
            result = ImageAnalysisResult(
                format=ImageFormat(format) if format in ImageFormat._value2member_map_ else ImageFormat.JPEG,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                file_size_bytes=len(image_data),
                color_mode=image.mode,
                has_transparency=image.mode in ['RGBA', 'LA', 'PA'] or 'transparency' in image.info
            )
            
            # Get DPI
            if 'dpi' in image.info:
                result.dpi = image.info['dpi']
            
            # Analyze image quality and content
            self._analyze_quality(image, result)
            self._analyze_colors(image, result)
            self._analyze_optimization_potential(image, image_data, result)
            
            # Generate recommendations
            self._generate_recommendations(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            # Return minimal result
            return ImageAnalysisResult(
                format=ImageFormat.JPEG,
                width=0,
                height=0,
                aspect_ratio=0,
                file_size_bytes=len(image_data)
            )
    
    def _analyze_quality(self, image: Image.Image, result: ImageAnalysisResult):
        """Analyze image quality metrics."""
        # Convert to grayscale for analysis
        if image.mode != 'L':
            gray = image.convert('L')
        else:
            gray = image
        
        # Calculate brightness
        pixels = np.array(gray)
        result.brightness = np.mean(pixels) / 255.0
        
        # Calculate contrast (standard deviation)
        result.contrast = np.std(pixels) / 255.0
        
        # Estimate sharpness using edge detection
        # Simplified - in production use proper edge detection
        if pixels.shape[0] > 1 and pixels.shape[1] > 1:
            edges = np.abs(np.diff(pixels, axis=0)).mean() + np.abs(np.diff(pixels, axis=1)).mean()
            result.sharpness = min(1.0, edges / 100.0)
        
        # Estimate quality based on file size and dimensions
        pixels_total = result.width * result.height
        if pixels_total > 0:
            bytes_per_pixel = result.file_size_bytes / pixels_total
            
            # Higher compression = lower quality
            if result.format == ImageFormat.JPEG:
                if bytes_per_pixel < 0.1:
                    result.estimated_quality = 60
                elif bytes_per_pixel < 0.3:
                    result.estimated_quality = 75
                elif bytes_per_pixel < 0.5:
                    result.estimated_quality = 85
                else:
                    result.estimated_quality = 95
            elif result.format == ImageFormat.PNG:
                result.estimated_quality = 95  # PNG is lossless
    
    def _analyze_colors(self, image: Image.Image, result: ImageAnalysisResult):
        """Analyze image colors."""
        # Convert to RGB for color analysis
        if image.mode != 'RGB':
            if image.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                rgb_image = background
            else:
                rgb_image = image.convert('RGB')
        else:
            rgb_image = image
        
        # Get dominant colors
        # Simplified - in production use proper color clustering
        colors = rgb_image.getcolors(maxcolors=1000000)
        if colors:
            # Sort by frequency
            sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)[:5]
            result.dominant_colors = [
                f"#{r:02x}{g:02x}{b:02x}" 
                for count, (r, g, b) in sorted_colors
            ]
    
    def _analyze_optimization_potential(
        self,
        image: Image.Image,
        original_data: bytes,
        result: ImageAnalysisResult
    ):
        """Analyze potential for optimization."""
        # Check if already optimized
        result.is_optimized = self._is_optimized(image)
        
        # Estimate optimization potential
        current_size = len(original_data)
        
        # Estimate optimal size based on dimensions and format
        pixels = result.width * result.height
        
        if result.format == ImageFormat.JPEG:
            # JPEG: aim for 0.1-0.3 bytes per pixel
            optimal_size = pixels * 0.2
        elif result.format == ImageFormat.PNG:
            if result.has_transparency:
                # PNG with alpha: 0.5-1.0 bytes per pixel
                optimal_size = pixels * 0.75
            else:
                # PNG without alpha: consider JPEG conversion
                optimal_size = pixels * 0.2
        else:
            optimal_size = pixels * 0.3
        
        if current_size > optimal_size:
            result.optimization_potential = min(
                1.0,
                (current_size - optimal_size) / current_size
            )
    
    def _is_optimized(self, image: Image.Image) -> bool:
        """Check if image appears to be optimized."""
        # Check for optimization markers in metadata
        if 'optimize' in image.info or 'progression' in image.info:
            return True
        
        # Check for common optimization tools in metadata
        if 'Software' in image.info:
            software = image.info['Software'].lower()
            optimization_tools = ['imageoptim', 'jpegoptim', 'pngquant', 'tinypng']
            if any(tool in software for tool in optimization_tools):
                return True
        
        return False
    
    def _generate_recommendations(self, result: ImageAnalysisResult):
        """Generate optimization and accessibility recommendations."""
        # Size recommendations
        size_category = self._categorize_size(result.width, result.height)
        max_size = self.MAX_FILE_SIZES.get(size_category, 500 * 1024)
        
        if result.file_size_bytes > max_size:
            result.optimization_suggestions.append(
                f"Reduce file size from {result.file_size_bytes / 1024:.0f}KB "
                f"to under {max_size / 1024:.0f}KB"
            )
        
        # Format recommendations
        if result.format == ImageFormat.PNG and not result.has_transparency:
            result.optimization_suggestions.append(
                "Convert to JPEG format for better compression (no transparency needed)"
            )
        elif result.format == ImageFormat.BMP:
            result.optimization_suggestions.append(
                "Convert to JPEG or PNG format for web use"
            )
        
        # Dimension recommendations
        if result.width > 2000 or result.height > 2000:
            result.optimization_suggestions.append(
                f"Resize image from {result.width}x{result.height} to more web-friendly dimensions"
            )
        
        # Quality recommendations
        if result.format == ImageFormat.JPEG and result.estimated_quality > 85:
            result.optimization_suggestions.append(
                "Reduce JPEG quality to 85% for better file size with minimal visual impact"
            )
        
        # Optimization potential
        if result.optimization_potential > 0.3:
            potential_savings = result.file_size_bytes * result.optimization_potential
            result.optimization_suggestions.append(
                f"Image can be optimized to save ~{potential_savings / 1024:.0f}KB "
                f"({result.optimization_potential * 100:.0f}% reduction)"
            )
        
        # Accessibility recommendations
        if not result.has_text:
            result.accessibility_issues.append(
                "Add descriptive alt text for screen readers"
            )
        
        if result.brightness < 0.2:
            result.accessibility_issues.append(
                "Image is very dark - ensure important content is visible"
            )
        elif result.brightness > 0.8:
            result.accessibility_issues.append(
                "Image is very bright - ensure sufficient contrast for text overlay"
            )
        
        if result.contrast < 0.1:
            result.accessibility_issues.append(
                "Low contrast may make details hard to see"
            )
    
    def _categorize_size(self, width: int, height: int) -> str:
        """Categorize image by dimensions."""
        pixels = width * height
        
        if pixels <= 150 * 150:
            return "thumbnail"
        elif pixels <= 320 * 240:
            return "small"
        elif pixels <= 640 * 480:
            return "medium"
        elif pixels <= 1024 * 768:
            return "large"
        else:
            return "hero"