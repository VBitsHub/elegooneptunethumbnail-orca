import argparse
import base64
import platform
from argparse import Namespace
from array import array
from ctypes import CDLL
from os import path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

# VBits TODO
# Figure out why converting requires both QImage and Base64 PNG to
# display when files on Elegoo thumbnails only require QImage
# Then use delete function to delete the base64 png.
# Also convert
# - layer height
# - filament type
# - filament length
# - first layer height
# - total height
# - filament weight
# Completed
# + Add tags for neptune4max and plus
# + Add support for 300x300, 200x200, and 48x48
# + Add time support 
# + Add Layer support
# + Add support to delete existing base64 png image

class ElegooNeptuneThumbnails:
    """
    ElegooNeptuneThumbnails post processing script
    """

    OLD_MODELS: list[str] = ["NEPTUNE2", "NEPTUNE2D", "NEPTUNE2S", "NEPTUNEX"]
    NEW_MODELS: list[str] = ["NEPTUNE4", "NEPTUNE4PRO", "NEPTUNE3PRO", "NEPTUNE3PLUS", "NEPTUNE3MAX", "NEPTUNE4MAX", "NEPTUNE4PLUS"]

    def __init__(self):
        args: Namespace = self._parse_args()
        self._gcode: str = args.gcode
        self._printer_model: str = args.printer
        self._thumbnail: QImage = self._get_q_image_thumbnail()
        self._layercount: int = self._get_layercount()
        self._time: int = self._get_time()
        self._filamentUsed: float = self._get_filament_used()

        # Find printer model from gcode if not set
        if not self._printer_model or self._printer_model not in (self.OLD_MODELS + self.NEW_MODELS):
            self._printer_model = self._get_printer_model()

    @classmethod
    
    def _parse_args(cls) -> Namespace:
        """
        Parse arguments from prusa slicer
        """
        # Parse arguments
        parser = argparse.ArgumentParser(
            prog="ElegooNeptuneThumbnails-Orca",
            description="A post processing script to add Elegoo Neptune thumbnails to gcode")
        parser.add_argument("-p", "--printer", help="Printer model to generate for", type=str, required=False,
                            default="")
        parser.add_argument("gcode", help="Gcode path provided by OrcaSlicer", type=str)
        return parser.parse_args()

    def _get_base64_thumbnail(self) -> str:
        """
        Read the base64 encoded thumbnail from gcode file
        """
        # Try to find thumbnail
        found: bool = False
        base64_thumbnail: str = ""
        with open(self._gcode, "r", encoding="utf8") as file:
            for line in file.read().splitlines():
                if not found and (line.startswith("; thumbnail begin 300x300") or line.startswith("; thumbnail begin 600x600") or line.startswith("; thumbnail begin 200x200") or line.startswith("; thumbnail begin 48x48")):
                    found = True
                elif found and line == "; thumbnail end":
                    return base64_thumbnail
                elif found:
                    base64_thumbnail += line[2:]

        # If not found, raise exception
        raise Exception("Thumbnail is not present")
    
    def _get_layercount(self) -> int:
        found: bool = False
        templine: str = ""
        layers: int = 0
        with open(self._gcode, "r", encoding="utf8") as file:
            for line in file.read().splitlines():
                if not found and line.startswith("; total layer number:"):
                    templine = line.replace("; total layer number: ", "")
                    #print(templine)
                    layers = int(templine)
                    #print("Layer_count: " + str(layers))
                    found = True
                    
        return layers
    
    def _get_time(self) -> int:
        found:bool = False
        tempTime: int = 0
        tempNumber: int = 0
        tempLine: str = ""
        with open(self._gcode, "r", encoding="utf8") as file:
            for line in file.read().splitlines():
                if not found and line.startswith("; estimated printing time (normal mode) = "):
                    tempLine = line.replace("; estimated printing time (normal mode) = ", "")
                    x = tempLine.split(" ")
                    #print(x)
                    for item in x:
                        if "h" in item:
                            tempNumber = int(item.replace("h", ""))*3600
                            tempTime += tempNumber
                        elif "m" in item:
                           tempNumber = int(item.replace("m", ""))*60
                           tempTime += tempNumber
                        elif "s" in item:
                            tempNumber = int(item.replace("s", ""))
                            tempTime += tempNumber
                            #print("; TIME:" + str(tempTime))
    
        return tempTime
    
    def _get_filament_used(self) -> float:
        found: bool = False
        tempFilamentUsed: int = 0
        tempLine: str=""
        with open(self._gcode, "r", encoding="utf8") as file:
            for line in file.read().splitlines():
                if not found and line.startswith("; filament used [mm] = "):
                    tempLine = line.replace("; filament used [mm] = ", "")
                    tempFilamentUsed = float(tempLine)*0.001
                    print(tempFilamentUsed)
                            
        return tempFilamentUsed
                        
                    
    def _get_q_image_thumbnail(self) -> QImage:
        """
        Read the base64 encoded thumbnail from gcode file and parse it to a QImage object
        """
        # Read thumbnail
        base64_thumbnail: str = self._get_base64_thumbnail()

        # Parse thumbnail
        thumbnail = QImage()
        thumbnail.loadFromData(base64.decodebytes(bytes(base64_thumbnail, "UTF-8")), "PNG")
        return thumbnail

    def _get_printer_model(self) -> str:
        """
        Read the printer model from gcode file
        """
        # Try to find printer model
        with open(self._gcode, "r", encoding="utf8") as file:
            for line in file.read().splitlines():
                if line.startswith("; printer_model = "):
                    return line[len("; printer_model = "):]

        # If not found, raise exception
        raise Exception("Printer model not found")

    def is_supported_printer(self) -> bool:
        """
        Check if printer is supported
        """
        return self._is_old_thumbnail() or self._is_new_thumbnail()

    def _is_old_thumbnail(self) -> bool:
        """
        Check if an old printer is present
        """
        return self._printer_model in self.OLD_MODELS

    def _is_new_thumbnail(self) -> bool:
        """
        Check if a new printer is present
        """
        return self._printer_model in self.NEW_MODELS

    def _generate_gcode_prefix(self) -> str:
        """
        Generate a g-code prefix string
        """
        # Parse to g-code prefix
        gcode_prefix: str = ""
        if self._is_old_thumbnail():
            gcode_prefix += self._parse_thumbnail_old(self._thumbnail, 100, 100, "simage")
            gcode_prefix += self._parse_thumbnail_old(self._thumbnail, 200, 200, ";gimage")
        elif self._is_new_thumbnail():
            gcode_prefix += self._parse_thumbnail_new(self._thumbnail, 200, 200, "gimage")
            gcode_prefix += self._parse_thumbnail_new(self._thumbnail, 160, 160, "simage")
        if gcode_prefix:
            gcode_prefix += ';Thumbnail generated by the ElegooNeptuneThumbnails-Orca post processing script. Modified by VBits to support other resolutions, added new Neptune 4 printers, show correct time and layer in fluidd \r' \
                            ';Just mentioning "Cura_SteamEngine X.X" to trick printer into thinking this is Cura and not Orca gcode\r' \
                            ';Original code can be found @ https://github.com/Molodos/ElegooNeptuneThumbnails-Prusa\r\r'

        # VBits 
        # add gcode to display layer
        gcode_prefix += ";LAYER_COUNT:" + str(self._layercount) + "\r"
        if self._printer_model == "NEPTUNE4MAX":
            gcode_prefix += ";MINX: 0\r;MINY:0\r;MINZ:0\r;MAXX:420\r;MAXY:420\r;MAXZ:480\r"
            
        gcode_prefix += ";TIME:" + str(self._time) + "\r"
        gcode_prefix += ";Filament used: " + str(self._filamentUsed) + "m\r"
        # Return
        return gcode_prefix

    def add_thumbnail_prefix(self) -> None:
        """
        Adds thumbnail prefix to the gcode file if thumbnail doesn't already exist
        """
        # Get gcode
        g_code: str
        with open(self._gcode, "r", encoding="utf8") as file:
            g_code: str = file.read()

        # Remove mark of PrusaSlicer
        g_code = g_code.replace("PrusaSlicer", "CensoredSlicer")

        # Add prefix
        if ';gimage:' not in g_code and ';simage:' not in g_code:
            gcode_prefix: str = self._generate_gcode_prefix()
            with open(self._gcode, "w", encoding="utf8") as file:
                file.write(gcode_prefix + g_code)

    @classmethod
    def _parse_thumbnail_old(cls, img: QImage, width: int, height: int, img_type: str) -> str:
        """
        Parse thumbnail to string for old printers
        TODO: Maybe optimize at some time
        """
        img_type = f";{img_type}:"
        result = ""
        b_image = img.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio)
        img_size = b_image.size()
        result += img_type
        datasize = 0
        for i in range(img_size.height()):
            for j in range(img_size.width()):
                pixel_color = b_image.pixelColor(j, i)
                r = pixel_color.red() >> 3
                g = pixel_color.green() >> 2
                b = pixel_color.blue() >> 3
                rgb = (r << 11) | (g << 5) | b
                str_hex = "%x" % rgb
                if len(str_hex) == 3:
                    str_hex = '0' + str_hex[0:3]
                elif len(str_hex) == 2:
                    str_hex = '00' + str_hex[0:2]
                elif len(str_hex) == 1:
                    str_hex = '000' + str_hex[0:1]
                if str_hex[2:4] != '':
                    result += str_hex[2:4]
                    datasize += 2
                if str_hex[0:2] != '':
                    result += str_hex[0:2]
                    datasize += 2
                if datasize >= 50:
                    datasize = 0
            # if i != img_size.height() - 1:
            result += '\rM10086 ;'
            if i == img_size.height() - 1:
                result += "\r"
        return result

    @classmethod
    def _parse_thumbnail_new(cls, img: QImage, width: int, height: int, img_type: str) -> str:
        """
        Parse thumbnail to string for new printers
        TODO: Maybe optimize at some time
        """
        img_type = f";{img_type}:"
        sys: str = platform.system().lower()
        if "darwin" in sys:
            p_dll = CDLL(path.join(path.dirname(__file__), "libs", "libColPic.dylib"))
        elif "linux" in sys:
            p_dll = CDLL(path.join(path.dirname(__file__), "libs", "libColPic.so"))
        else:
            p_dll = CDLL(path.join(path.dirname(__file__), "libs", "ColPic_X64.dll"))

        result = ""
        b_image = img.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio)
        img_size = b_image.size()
        color16 = array('H')
        try:
            for i in range(img_size.height()):
                for j in range(img_size.width()):
                    pixel_color = b_image.pixelColor(j, i)
                    r = pixel_color.red() >> 3
                    g = pixel_color.green() >> 2
                    b = pixel_color.blue() >> 3
                    rgb = (r << 11) | (g << 5) | b
                    color16.append(rgb)

            # int ColPic_EncodeStr(U16* fromcolor16, int picw, int pich, U8* outputdata, int outputmaxtsize, int colorsmax);
            from_color16 = color16.tobytes()
            output_data = array('B', [0] * img_size.height() * img_size.width()).tobytes()
            result_int = p_dll.ColPic_EncodeStr(from_color16, img_size.height(), img_size.width(), output_data,
                                                img_size.height() * img_size.width(), 1024)

            data0 = str(output_data).replace('\\x00', '')
            data1 = data0[2:len(data0) - 2]
            each_max = 1024 - 8 - 1
            max_line = int(len(data1) / each_max)
            append_len = each_max - 3 - int(len(data1) % each_max)

            for i in range(len(data1)):
                if i == max_line * each_max:
                    result += '\r;' + img_type + data1[i]
                elif i == 0:
                    result += img_type + data1[i]
                elif i % each_max == 0:
                    result += '\r' + img_type + data1[i]
                else:
                    result += data1[i]
            result += '\r;'
            for j in range(append_len):
                result += '0'

        except Exception as e:
            raise e

        return result + '\r'


if __name__ == "__main__":
    """
    Init point of the script
    """
    thumbnail_generator: ElegooNeptuneThumbnails = ElegooNeptuneThumbnails()
    if thumbnail_generator.is_supported_printer():
        #thumbnail_generator._delete_base64_thumbnail()
        thumbnail_generator.add_thumbnail_prefix()
        
