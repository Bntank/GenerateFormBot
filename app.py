# app.py - Bot Berita Acara Pro Wifi
import os
import logging
import asyncio
import threading
import time
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify
from telegram import Update
from bot_ba import BeritaAcaraBot

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WIFI_TEMPLATE_FOLDER_ID = os.environ.get("TEMPLATE_FOLDER_ID")  # Folder template Excel Wifi
WIFI_RESULT_FOLDER_ID = os.environ.get("RESULT_FOLDER_ID")     # Folder hasil Wifi
DATIN_TEMPLATE_FOLDER_ID = os.environ.get("DATIN_TEMPLATE_FOLDER_ID")  # Folder template Excel Datin
DATIN_RESULT_FOLDER_ID = os.environ.get("DATIN_RESULT_FOLDER_ID")       # Folder hasil Datin
GOOGLE_OAUTH_CLIENT_CONFIG = os.environ.get("GOOGLE_OAUTH_CLIENT_CONFIG")  # OAuth config


# Validate required environment variables
required_vars = {
    'BOT_TOKEN': BOT_TOKEN,
    'TEMPLATE_FOLDER_ID': WIFI_TEMPLATE_FOLDER_ID,
    'RESULT_FOLDER_ID': WIFI_RESULT_FOLDER_ID,
    'DATIN_TEMPLATE_FOLDER_ID': DATIN_TEMPLATE_FOLDER_ID,
    'DATIN_RESULT_FOLDER_ID': DATIN_RESULT_FOLDER_ID,
    'GOOGLE_OAUTH_CLIENT_CONFIG': GOOGLE_OAUTH_CLIENT_CONFIG
}


missing_vars = [var for var, value in required_vars.items() if not value]

if missing_vars:
    logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
    exit(1)

logger.info("✅ All required environment variables are set")
logger.info(f"📁 Template folder: {WIFI_TEMPLATE_FOLDER_ID}")
logger.info(f"📁 Template folder: {DATIN_TEMPLATE_FOLDER_ID}")
logger.info(f"📁 Result folder: {WIFI_RESULT_FOLDER_ID}")
logger.info(f"📁 Result folder: {DATIN_RESULT_FOLDER_ID}")

# Create Flask app
app = Flask(__name__)

# Global variables
bot = None
loop = None
loop_thread = None
bot_ready = False

def create_and_run_loop():
    """Create and run event loop in dedicated thread"""
    global loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("🔄 Event loop created and running")
        loop.run_forever()
    except Exception as e:
        logger.error(f"❌ Error in event loop: {e}")

def start_event_loop():
    """Start event loop in background thread"""
    global loop_thread
    loop_thread = threading.Thread(target=create_and_run_loop, daemon=True)
    loop_thread.start()
    
    # Wait for loop to be ready
    time.sleep(0.5)
    return loop is not None

async def initialize_bot_async():
    """Initialize bot asynchronously"""
    global bot, bot_ready
    try:
        logger.info("🤖 Creating BeritaAcaraBot instance...")
        form_configs = {
            'wifi': {
                'template_folder_id': WIFI_TEMPLATE_FOLDER_ID,
                'result_folder_id': WIFI_RESULT_FOLDER_ID
            },
            'datin': {
                'template_folder_id': DATIN_TEMPLATE_FOLDER_ID,
                'result_folder_id': DATIN_RESULT_FOLDER_ID
            }
        }

        bot = BeritaAcaraBot(
            token=BOT_TOKEN,
            form_configs=form_configs
        )
        
        logger.info("🔧 Initializing Telegram Application...")
        success = await bot.initialize_application()
        
        if success:
            bot_ready = True
            logger.info("✅ Bot fully initialized and ready")
            return True
        else:
            logger.error("❌ Failed to initialize bot application")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error initializing bot: {e}")
        return False

def initialize_bot():
    """Initialize bot synchronously"""
    if not loop:
        logger.error("❌ Event loop not available")
        return False
    
    try:
        future = asyncio.run_coroutine_threadsafe(initialize_bot_async(), loop)
        return future.result(timeout=60)  # Wait up to 60 seconds
    except Exception as e:
        logger.error(f"❌ Error initializing bot: {e}")
        return False

@app.route('/')
def index():
    system_info = {
        'status': 'running',
        'bot_ready': bot_ready,
        'loop_running': loop is not None and not loop.is_closed(),
        'message': 'Bot Berita Acara Pro Wifi & Datin',
        'config': {
            'wifi': {
                'template_folder_id': WIFI_TEMPLATE_FOLDER_ID,
                'result_folder_id': WIFI_RESULT_FOLDER_ID,
            },
            'datin': {
                'template_folder_id': DATIN_TEMPLATE_FOLDER_ID,
                'result_folder_id': DATIN_RESULT_FOLDER_ID,
            }
        },
        'services': {
            'drive': 'oauth2',
            'sheets': 'not_required'
        }
    }
    
    return jsonify(system_info)

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy' if bot_ready else 'initializing',
        'bot': 'ready' if bot_ready else 'not_ready',
        'loop': 'running' if loop and not loop.is_closed() else 'not_running'
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Check if bot is ready
        if not bot_ready or not bot:
            logger.warning("⚠️ Bot not ready, ignoring webhook")
            return jsonify({'status': 'bot_not_ready'}), 503
        
        # Check loop
        if not loop or loop.is_closed():
            logger.error("❌ Event loop not available")
            return jsonify({'status': 'loop_error'}), 503
        
        # Get and validate JSON data
        json_data = request.get_json(force=True)
        if not json_data:
            logger.error("❌ Empty JSON data received")
            return jsonify({'status': 'invalid_data'}), 400
        
        logger.info(f"📨 Processing webhook update")
        
        try:
            # Create Update object
            update = Update.de_json(json_data, bot.application.bot)
            
            # Schedule processing (don't wait for result)
            future = asyncio.run_coroutine_threadsafe(
                bot.process_update(update), 
                loop
            )
            
            logger.info("✅ Update queued successfully")
            return jsonify({'status': 'ok'})
            
        except Exception as parse_error:
            logger.error(f"❌ Error parsing update: {parse_error}")
            return jsonify({'status': 'parse_error'}), 400
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Application startup
def startup():
    global bot_ready
    
    logger.info("🚀 Starting Bot Berita Acara Pro Wifi...")
    
    # Start event loop
    logger.info("⚡ Starting event loop...")
    if not start_event_loop():
        logger.error("❌ Failed to start event loop")
        exit(1)
    
    # Wait a bit for loop to be ready
    time.sleep(2)
    
    # Initialize bot
    logger.info("🤖 Initializing bot...")
    if not initialize_bot():
        logger.error("❌ Failed to initialize bot")
        # Don't exit immediately, allow health checks
        bot_ready = False
    else:
        bot_ready = True
    
    logger.info("✅ Application startup complete!")

# Run startup
startup()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)