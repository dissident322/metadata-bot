# Импортируем нужные библиотеки
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from PIL import Image
from PIL.ExifTags import TAGS
import exifread
import os
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Функция для конвертации GPS координат
def convert_to_degrees(value):
    """Конвертирует GPS координаты в градусы"""
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den) / 60.0
    s = float(value.values[2].num) / float(value.values[2].den) / 3600.0
    return d + m + s

# Функция для извлечения метаданных
async def extract_metadata(file_path):
    """Вытаскивает метаданные из фото"""
    metadata = {}
    
    try:
        # Открываем изображение
        image = Image.open(file_path)
        print(f"DEBUG: Изображение открыто, формат: {image.format}")
        
        metadata['Размер'] = f"{image.width}x{image.height} пиксели"
        metadata['Формат'] = image.format
        
        # Размер файла
        file_size = os.path.getsize(file_path)
        if file_size > 1024*1024:
            metadata['Размер файла'] = f"{file_size / (1024*1024):.2f} МБ"
        else:
            metadata['Размер файла'] = f"{file_size / 1024:.2f} КБ"
        
        # Читаем EXIF через exifread
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                print(f"DEBUG: Найдено EXIF тегов: {len(tags)}")
                print(f"DEBUG: Все теги: {list(tags.keys())}")
                
                # Маппинг нужных нам тегов
                tag_mapping = {
                    'EXIF DateTimeOriginal': 'Дата и время',
                    'Image Model': 'Модель камеры',
                    'Image Make': 'Производитель',
                    'EXIF ExposureTime': 'Выдержка',
                    'EXIF FNumber': 'Диафрагма (F-число)',
                    'EXIF ISOSpeedRatings': 'ISO',
                    'EXIF FocalLength': 'Фокусное расстояние',
                    'EXIF Flash': 'Вспышка',
                    'EXIF WhiteBalance': 'Баланс белого',
                    'EXIF LensModel': 'Модель линзы'
                }
                
                for exif_tag, readable_name in tag_mapping.items():
                    if exif_tag in tags:
                        metadata[readable_name] = str(tags[exif_tag])[:100]
                
                # GPS обработка
                gps_latitude = tags.get('GPS GPSLatitude')
                gps_latitude_ref = tags.get('GPS GPSLatitudeRef')
                gps_longitude = tags.get('GPS GPSLongitude')
                gps_longitude_ref = tags.get('GPS GPSLongitudeRef')
                
                print(f"DEBUG: GPS Latitude: {gps_latitude}")
                print(f"DEBUG: GPS Longitude: {gps_longitude}")
                
                if gps_latitude and gps_longitude:
                    try:
                        latitude = convert_to_degrees(gps_latitude)
                        longitude = convert_to_degrees(gps_longitude)
                        
                        if gps_latitude_ref and str(gps_latitude_ref) == 'S':
                            latitude = -latitude
                        if gps_longitude_ref and str(gps_longitude_ref) == 'W':
                            longitude = -longitude
                        
                        print(f"DEBUG: Latitude = {latitude}, Longitude = {longitude}")
                        
                        metadata['GPS Широта'] = f"{latitude:.6f}"
                        metadata['GPS Долгота'] = f"{longitude:.6f}"
                        
                        google_maps = f"https://maps.google.com/?q={latitude},{longitude}"
                        yandex_maps = f"https://maps.yandex.ru/?ll={longitude},{latitude}&z=15"
                        
                        metadata['🗺️ Google Maps'] = google_maps
                        metadata['🗺️ Яндекс Карты'] = yandex_maps
                    except Exception as e:
                        print(f"DEBUG: Ошибка парсинга GPS: {e}")
        
        except Exception as e:
            print(f"DEBUG: Ошибка exifread: {e}")
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        print(f"DEBUG: Ошибка: {e}")
    
    return metadata

# Обработчик фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото"""
    await update.message.reply_text("⏳ Анализирую фото...")
    
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_path = "photo.jpg"
        await file.download_to_drive(file_path)
        
        metadata = await extract_metadata(file_path)
        
        if metadata:
            message = "📸 **МЕТАДАННЫЕ ФОТО:**\n\n"
            for key, value in metadata.items():
                if key.startswith('🗺️'):
                    message += f"[{key}]({value})\n"
                else:
                    message += f"• {key}: `{value}`\n"
        else:
            message = "⚠️ Метаданные не найдены"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        try:
            os.remove(file_path)
        except:
            pass
    
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# Обработчик файлов
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка файлов"""
    await update.message.reply_text("⏳ Анализирую файл...")
    
    try:
        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        
        file_ext = os.path.splitext(document.file_name)[1].lower()
        file_path = f"photo{file_ext}"
        
        await file.download_to_drive(file_path)
        
        metadata = {}
        
        # Размер файла
        file_size = os.path.getsize(file_path)
        if file_size > 1024*1024:
            metadata['Размер файла'] = f"{file_size / (1024*1024):.2f} МБ"
        else:
            metadata['Размер файла'] = f"{file_size / 1024:.2f} КБ"
        
        # Размер изображения
        try:
            image = Image.open(file_path)
            metadata['Размер'] = f"{image.width}x{image.height} пиксели"
            metadata['Формат'] = image.format or 'HEIC'
        except:
            pass
        
        # EXIF теги
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                
                # Основные теги
                tag_mapping = {
                    'Image DateTime': 'Дата и время',
                    'Image Make': 'Производитель',
                    'Image Model': 'Модель камеры',
                    'EXIF ExposureTime': 'Выдержка',
                    'EXIF FNumber': 'Диафрагма',
                    'EXIF ISOSpeedRatings': 'ISO',
                    'EXIF FocalLength': 'Фокусное расстояние',
                    'EXIF Flash': 'Вспышка',
                    'EXIF WhiteBalance': 'Баланс белого',
                    'EXIF LensModel': 'Модель линзы',
                }
                
                for exif_tag, readable_name in tag_mapping.items():
                    if exif_tag in tags:
                        metadata[readable_name] = str(tags[exif_tag])[:100]
                
                # GPS
                gps_lat = tags.get('GPS GPSLatitude')
                gps_lon = tags.get('GPS GPSLongitude')
                gps_lat_ref = tags.get('GPS GPSLatitudeRef')
                gps_lon_ref = tags.get('GPS GPSLongitudeRef')
                
                if gps_lat and gps_lon:
                    try:
                        latitude = convert_to_degrees(gps_lat)
                        longitude = convert_to_degrees(gps_lon)
                        
                        if gps_lat_ref and str(gps_lat_ref) == 'S':
                            latitude = -latitude
                        if gps_lon_ref and str(gps_lon_ref) == 'W':
                            longitude = -longitude
                        
                        metadata['GPS Широта'] = f"{latitude:.6f}"
                        metadata['GPS Долгота'] = f"{longitude:.6f}"
                        metadata['🗺️ Google Maps'] = f"https://maps.google.com/?q={latitude},{longitude}"
                        metadata['🗺️ Яндекс Карты'] = f"https://maps.yandex.ru/?ll={longitude},{latitude}&z=15"
                    except:
                        pass
        except:
            pass
        
        # Удаляем файл
        try:
            os.remove(file_path)
        except:
            pass
        
        # Отправляем результат
        if metadata:
            message = "📸 **МЕТАДАННЫЕ:**\n\n"
            for key, value in metadata.items():
                if key.startswith('🗺️'):
                    message += f"[{key}]({value})\n"
                else:
                    message += f"• {key}: `{value}`\n"
        else:
            message = "⚠️ Метаданные не найдены"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для извлечения метаданных фото.\n\n"
        "📤 Отправьте фото или файл и я покажу:\n"
        "📍 GPS координаты\n"
        "📅 Дату съёмки\n"
        "📷 Модель камеры\n"
        "⚙️ Технические параметры"
    )

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    print("✅ Бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()