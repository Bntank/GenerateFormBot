# bot_ba.py - Bot Berita Acara Pro Wifi (FIXED)
import os
import re
import asyncio
import logging
import tempfile
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from PIL import Image as PILImage, ImageDraw
from PIL import Image

from services.google_ba_service import GoogleBAService
from services.session_ba_service import SessionBAService
from services.photo_handler import PhotoHandler
from config.ba_config import BeritaAcaraConfig

# States untuk ConversationHandler
(MAIN_MENU, FORM_SECTION, INPUT_DATA, CONFIRM_SECTION, 
 UPLOAD_PHOTO, INPUT_PHOTO_DESC, FINAL_CONFIRMATION,
 SIGNATURE_UPLOAD, PHOTO_MENU, PHOTO_CONFIRM_DELETE) = range(10)

logger = logging.getLogger(__name__)

class BeritaAcaraBot:
    def __init__(self, token, form_configs):
        self.token = token
        self.form_configs = form_configs
        self.application = None
        
        # Initialize services - will be created per form type
        logger.info("Initializing services...")
        self.google_services = {}
        for form_type, config in form_configs.items():
            self.google_services[form_type] = GoogleBAService(
                config['template_folder_id'], 
                config['result_folder_id']
            )
            # Authenticate each service
            if not self.google_services[form_type].authenticate():
                raise Exception(f"Failed to authenticate Google APIs for {form_type}")
        
        self.session_service = SessionBAService()
        self.ba_config = BeritaAcaraConfig()
        self.photo_handler = PhotoHandler(self.google_services, self.session_service)
        

    async def initialize_application(self):
        """Initialize Telegram Application"""
        try:
            logger.info("Building Telegram Application...")
            
            # Build application
            self.application = Application.builder().token(self.token).build()
            
            # Setup handlers
            self._setup_handlers()
            
            # Initialize application
            logger.info("Initializing Telegram Application...")
            await self.application.initialize()
            
            logger.info("Telegram Application initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram Application: {e}")
            return False

    def _generate_filename(self, form_data):
        """Generate filename based on form data"""
        try:
            # Get jenis layanan and WO/AO from form data
            jenis_layanan = ""
            wo_ao = ""
            
            # Check tanggal_layanan section
            tanggal_section = form_data.get('tanggal_layanan', {})
            if tanggal_section:
                jenis_layanan = tanggal_section.get('JENIS LAYANAN', '').strip()
            
            # Check identitas section  
            identitas_section = form_data.get('identitas', {})
            if identitas_section:
                wo_ao = identitas_section.get('NO WO / AO', '').strip()
            
            # Clean filename components
            if jenis_layanan:
                jenis_layanan = re.sub(r'[^\w\s-]', '', jenis_layanan).strip()
                jenis_layanan = re.sub(r'[\s]+', '_', jenis_layanan)
            else:
                jenis_layanan = "Layanan"
            
            if wo_ao:
                wo_ao = re.sub(r'[^\w\s-]', '', wo_ao).strip()
                wo_ao = re.sub(r'[\s]+', '_', wo_ao)
            else:
                wo_ao = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            filename = f"BeritaAcara_{jenis_layanan}_{wo_ao}"
            return filename
            
        except Exception as e:
            logger.error(f"Error generating filename: {e}")
            return f"BeritaAcara_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current form status"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text(
                    "Status Formulir\n\n"
                    "Tidak ada formulir yang sedang dikerjakan.\n\n"
                    "Silakan buat formulir baru."
                )
                return MAIN_MENU
            
            form_data = session.get('form_data', {})
            sections_status = self.ba_config.get_sections_status(form_data)
            
            status_text = "Status Formulir Saat Ini\n\n"
            
            completed_sections = sum(1 for status in sections_status.values() if status)
            total_sections = len(sections_status)
            
            status_text += f"Progress: {completed_sections}/{total_sections} bagian selesai\n\n"
            
            form_type = session.get('form_type', 'wifi')
            available_sections = self.ba_config.get_sections_for_form_type(form_type)
            for section_id, section_info in available_sections.items():
                status_icon = "✅" if sections_status.get(section_id, False) else "❌"
                status_text += f"{status_icon} {section_info['name']}\n"
            
            keyboard = [
                [InlineKeyboardButton("📝 Lanjut Isi Form", callback_data="new_form")],
                [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if not status_text or status_text.strip() == "":
                status_text = "📋 Status Formulir\n\nData tidak tersedia."

            await self.safe_edit_message(query, status_text, reply_markup=reply_markup)

            
            return MAIN_MENU
            
        except Exception as e:
            logger.error(f"Error in show_status: {e}")
            try:
                if query and query.message:
                    await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Terjadi kesalahan. Silakan /start ulang."
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
            return ConversationHandler.END

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        try:
            query = update.callback_query
            
            help_text = (
                "Bantuan Bot Berita Acara\n\n"
                "Cara Penggunaan:\n"
                "1. Pilih 'Formulir Baru' untuk memulai\n"
                "2. Isi bagian-bagian formulir sesuai kebutuhan\n"
                "3. Setiap bagian memiliki template yang harus diikuti\n"
                "4. Status ✅ = sudah diisi, ❌ = belum diisi\n"
                "5. Review data sebelum generate Excel\n"
                "6. Excel akan disimpan ke folder hasil\n\n"
                "Bagian Formulir:\n"
                "• Tanggal & Jenis Layanan (Wajib)\n"
                "• Identitas Teknisi & Pelanggan (Wajib)\n"
                "• Perangkat\n"
                "• Type ONT (Jenis Paket & Material)\n"
                "• Baru/Existing (Material PT 1)\n"
                "• SN Yang Digunakan\n"
                "• Test Jaringan\n"
                "• Keterangan Tambahan\n"
                "• Tanda Tangan\n"
                "• Foto Eviden\n\n"
                "Tips:\n"
                "• Minimal isi bagian wajib untuk generate Excel\n"
                "• Gunakan format yang tepat saat input data\n"
                "• Foto eviden akan disimpan terpisah di folder\n"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.safe_edit_message(query, help_text, reply_markup=reply_markup)
            
            return MAIN_MENU
            
        except Exception as e:
            logger.error(f"Error in show_help: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END

    async def handle_photo_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo upload for evidence"""
        try:
            result = await self.photo_handler.handle_photo_upload(update, context)
            
            # PERBAIKAN: Pastikan tetap dalam UPLOAD_PHOTO state
            if result == UPLOAD_PHOTO:
                return UPLOAD_PHOTO
            elif result:
                # Jika berhasil upload, tetap dalam mode upload
                return UPLOAD_PHOTO
            else:
                # Jika gagal, tetap dalam mode upload untuk retry
                return UPLOAD_PHOTO
            
        except Exception as e:
            logger.error(f"Error in handle_photo_upload: {e}")
            await self.safe_send_message(
                context, 
                update.effective_chat.id, 
                "❌ Terjadi kesalahan saat upload foto. Silakan coba lagi."
            )
            return UPLOAD_PHOTO

    async def handle_photo_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input in photo upload state"""
        try:
            result = await self.photo_handler.handle_photo_text_input(update, context)
            
            # PERBAIKAN: Handle return value dengan cleanup yang benar
            if result == "form_menu":
                # Clear upload mode sepenuhnya
                context.user_data.pop('photo_upload_mode', None)
                return await self.show_form_menu(update, context)
            elif result == FORM_SECTION:
                # Clear upload mode sepenuhnya
                context.user_data.pop('photo_upload_mode', None)
                return await self.show_form_menu(update, context)
            else:
                # Tetap dalam mode upload untuk menerima foto berikutnya
                return UPLOAD_PHOTO
                
        except Exception as e:
            logger.error(f"Error in handle_photo_text: {e}")
            return UPLOAD_PHOTO

    async def handle_photo_evidence_section(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo evidence section"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            reply_markup, menu_text = await self.photo_handler.show_photo_menu(update, context, user_id)
            
            if reply_markup:
                await self.safe_edit_message(query, menu_text, reply_markup=reply_markup)

                return FORM_SECTION
            else:
                await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi.")
                return FORM_SECTION
                
        except Exception as e:
            logger.error(f"Error in handle_photo_evidence_section: {e}")
            await update.callback_query.edit_message_text("❌ Terjadi kesalahan.")
            return FORM_SECTION

    async def handle_photo_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo description input"""
        # Redirect to form menu for now  
        return await self.show_form_menu(update, context)

    async def handle_final_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle final form confirmation"""
        # This will be used for final Excel generation confirmation
        return await self.show_form_menu(update, context)

    def _setup_handlers(self):
        """Setup conversation handlers"""
        logger.info("Setting up conversation handlers...")
        
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self.start)
            ],
            states={
                MAIN_MENU: [
                    CallbackQueryHandler(self.handle_main_menu)
                ],
                FORM_SECTION: [
                    CallbackQueryHandler(self.handle_form_section),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_section_input)
                ],
                INPUT_DATA: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_data_input)
                ],
                CONFIRM_SECTION: [
                    CallbackQueryHandler(self.handle_section_confirmation)
                ],
                UPLOAD_PHOTO: [
                    MessageHandler(filters.PHOTO, self.handle_photo_upload),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_photo_text),
                    CommandHandler('selesai', self.finish_photo_upload)  # PERBAIKAN: Tambah handler /selesai
                ],
                INPUT_PHOTO_DESC: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_photo_desc)
                ],
                FINAL_CONFIRMATION: [
                    CallbackQueryHandler(self.handle_final_confirmation)
                ],
                SIGNATURE_UPLOAD: [
                    CallbackQueryHandler(self.handle_signature_upload),
                    MessageHandler(filters.PHOTO, self.handle_signature_photo),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_signature_text)
                ],
                PHOTO_MENU: [
                    CallbackQueryHandler(self.handle_photo_callback)
                ],
                PHOTO_CONFIRM_DELETE: [
                    CallbackQueryHandler(self.handle_photo_callback)
                ]
            },
            fallbacks=[
                CommandHandler('start', self.start),
                CommandHandler('cancel', self.cancel),  # PERBAIKAN: Tambahkan cancel handler
            ],
            allow_reentry=True
        )
        
        self.application.add_handler(conv_handler)
        
        # PERBAIKAN: Tambahkan handler untuk command cancel
        self.application.add_handler(CommandHandler('cancel', self.cancel))
        
        logger.info("Handlers setup complete")
        
    async def handle_photo_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo-related callback queries"""
        try:
            return await self.photo_handler.handle_photo_callback(update, context)
        except Exception as e:
            logger.error(f"Error in handle_photo_callback: {e}")
            await update.callback_query.edit_message_text("❌ Terjadi kesalahan")
            return FORM_SECTION
        
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation and return to main menu"""
        await update.message.reply_text(
            "Operasi dibatalkan. Kembali ke menu utama.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await self.start(update, context)

    async def handle_signature_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input in signature upload state"""
        try:
            message_text = update.message.text
            
            if message_text.lower() in ['kembali', 'batal', 'cancel']:
                return await self.show_form_menu(update, context)
            else:
                await update.message.reply_text(
                    "Silakan kirim foto tanda tangan atau pilih 'kembali' untuk membatalkan."
                )
                return SIGNATURE_UPLOAD
                
        except Exception as e:
            logger.error(f"Error in handle_signature_text: {e}")
            return SIGNATURE_UPLOAD

    async def process_update(self, update):
        """Process incoming update"""
        try:
            if not self.application:
                logger.error("Application not initialized")
                return
                
            user_id = update.effective_user.id if update.effective_user else 'Unknown'
            logger.info(f"Processing update for user: {user_id}")
            
            # Process the update
            await self.application.process_update(update)
            logger.info("Update processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            
            # Try to send error message
            try:
                if update.effective_chat and self.application:
                    await self.application.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Terjadi kesalahan sistem. Silakan coba lagi dengan /start"
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        try:
            user_id = update.effective_user.id
            logger.info(f"User {user_id} started bot")
            
            # Create new session
            self.session_service.create_session(user_id)
            
            return await self.show_form_type_selection(update, context)
            
            welcome_text = (
                "Bot Berita Acara Pro Wifi\n\n"
                "Bot ini akan membantu Anda mengisi formulir Berita Acara "
                "berdasarkan template Excel yang sudah disediakan.\n\n"
                "Fitur Utama:\n"
                "• Input data per bagian/section\n"
                "• Edit bagian tertentu\n" 
                "• Upload foto eviden\n"
                "• Generate Excel dari template Excel\n\n"
                "Silakan pilih menu:"
            )
            
            keyboard = [
                [InlineKeyboardButton("📝 Formulir Baru", callback_data="new_form")],
                [InlineKeyboardButton("📋 Lihat Status", callback_data="view_status")],
                [InlineKeyboardButton("ℹ️ Bantuan", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                welcome_text,
                reply_markup=reply_markup
            )

            return MAIN_MENU
            
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
            return ConversationHandler.END
        
    async def show_form_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show form type selection menu"""
        try:
            welcome_text = (
                "Bot Berita Acara Pro Wifi & Datin\n\n"
                "Bot ini akan membantu Anda mengisi formulir Berita Acara "
                "berdasarkan template Excel yang sudah disediakan.\n\n"
                "Silakan pilih jenis formulir:"
            )
            
            keyboard = [
                [InlineKeyboardButton("📶 Form Provisioning Wifi", callback_data="form_type_wifi")],
                [InlineKeyboardButton("🌐 Form Provisioning Datin", callback_data="form_type_datin")],
                [InlineKeyboardButton("ℹ️ Bantuan", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await self.safe_edit_message(update.callback_query, welcome_text, reply_markup=reply_markup)
            else:
                await self.safe_send_message(
                    context,
                    update.effective_chat.id,
                    welcome_text,
                    reply_markup=reply_markup
                )
            
            return MAIN_MENU
            
        except Exception as e:
            logger.error(f"Error in show_form_type_selection: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi.")
            return ConversationHandler.END

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            if query:
                await query.answer()
            else:
                return await self.show_form_menu(update, context)
            
            user_id = update.effective_user.id
            data = query.data
            
            if data == "new_form":
                return await self.show_form_menu(update, context)
            elif data == "view_status":
                return await self.show_status(update, context)
            elif data == "help":
                return await self.show_help(update, context)
            elif data.startswith("form_type_"):
                form_type = data.replace("form_type_", "")
                
                # Store form type in session
                self.session_service.update_session(user_id, {'form_type': form_type})
                
                # Show form menu for selected type
                return await self.show_form_menu(update, context)

            elif data == "back_main":
                return await self.start(update, context)
            elif data == "back_form":
                return await self.show_form_menu(update, context)
            else:
                # PERBAIKAN: Default kembali ke start untuk callback yang tidak dikenali
                return await self.start(update, context)
                
        except Exception as e:
            logger.error(f"Error in handle_main_menu: {e}")
            await self.safe_edit_message(query, "❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END

    async def show_form_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # Clear any leftover context data dengan safe method
            keys_to_remove = ['current_section', 'current_signature_type']
            for key in keys_to_remove:
                if key in context.user_data:
                    del context.user_data[key]
            
            user_id = update.effective_user.id
            query = update.callback_query
            
            # Get session
            session = self.session_service.get_session(user_id)
            if not session:
                if query:
                    await query.edit_message_text("❌ Session tidak ditemukan. Silakan /start ulang.")
                else:
                    await update.message.reply_text("❌ Session tidak ditemukan. Silakan /start ulang.")
                return ConversationHandler.END
            
            # Get section completion status
            form_type = session.get('form_type', 'wifi')  # default to wifi
            form_type_name = self.ba_config.get_form_type_display_name(form_type)

            # Get section completion status for specific form type
            excel_generated = session.get('excel_generated', False)
            form_data = session.get('form_data', {})
            sections_status = self.ba_config.get_sections_status(form_data, form_type)
            available_sections = self.ba_config.get_sections_for_form_type(form_type)

            # PERBAIKAN: Validasi khusus untuk tanda tangan
            tanda_tangan_data = form_data.get('tanda_tangan', {})
            has_both_signatures = (
                bool(tanda_tangan_data.get('TTD TEKNISI')) and 
                bool(tanda_tangan_data.get('TTD PELANGGAN'))
            )
            
            # Update status tanda tangan
            if 'tanda_tangan' in sections_status:
                sections_status['tanda_tangan'] = has_both_signatures
            
            form_text = f"Formulir {form_type_name}\n\n"
            
            if excel_generated:
                form_text += "📊 **Status:** Excel sudah digenerate\n"
                form_text += "📁 Folder sudah dibuat, siap untuk upload foto\n\n"
            else:
                form_text += "Pilih bagian yang ingin diisi:\n\n"
            
            keyboard = []
            
            # PERBAIKAN: Create buttons for each section dengan akses objek yang benar
            for section_id, section_info in available_sections.items():
                status_icon = "✅" if sections_status.get(section_id, False) else "❌"
                
                # PERBAIKAN: Akses name sebagai atribut objek, bukan dictionary
                section_name = section_info.name
                
                # Tampilkan status detail untuk tanda tangan
                if section_id == 'tanda_tangan':
                    ttd_teknisi = "✅" if tanda_tangan_data.get('TTD TEKNISI') else "❌"
                    ttd_pelanggan = "✅" if tanda_tangan_data.get('TTD PELANGGAN') else "❌"
                    button_text = f"{status_icon} {section_name} ({ttd_teknisi}Tek/{ttd_pelanggan}Pel)"
                else:
                    button_text = f"{status_icon} {section_name}"
                
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"section_{section_id}")])
            
            # Add photo evidence section
            photo_data = self.photo_handler.get_photo_section_data(user_id)
            photo_status_icon = "✅" if photo_data['has_photos'] else "❌"
            photo_button_text = f"{photo_status_icon} 📷 Foto Eviden"
            if photo_data['has_photos']:
                photo_button_text += f" ({photo_data['photo_count']} foto)"
            keyboard.append([InlineKeyboardButton(photo_button_text, callback_data="section_photo_evidence")])
            
            if excel_generated:
                keyboard.append([InlineKeyboardButton("📤 Selesaikan Laporan", callback_data="finish_report")])
                keyboard.append([InlineKeyboardButton("❌ Batalkan Form", callback_data="cancel_report")])
            else:
                keyboard.append([InlineKeyboardButton("👁️ Review Semua Data", callback_data="review_all")])
                if any(sections_status.values()) or photo_data['has_photos']:
                    keyboard.append([InlineKeyboardButton("📤 Generate Excel", callback_data="generate_excel")])
            
            keyboard.append([InlineKeyboardButton("🔙 Menu Utama", callback_data="back_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query and query.message:
                await self.safe_edit_message(query, form_text, reply_markup=reply_markup)
            else:
                # Jika tidak ada query (misal dari command), kirim message baru
                await self.safe_send_message(
                    context,
                    update.effective_chat.id,
                    form_text,
                    reply_markup=reply_markup
                )

            return FORM_SECTION
            
        except Exception as e:
            logger.error(f"Error in show_form_menu: {e}")
            if query:
                await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            else:
                await update.message.reply_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error in show_form_menu: {e}")
            if query:
                await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            else:
                await update.message.reply_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END


    async def handle_form_section(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle form section selection"""
        try:
            query = update.callback_query
            if query:
                await query.answer()
            else:
                return await self.show_form_menu(update, context)
            
            user_id = update.effective_user.id
            data = query.data
            
            if data.startswith("select_"):
                selected_value = data.replace("select_", "")
                return await self.handle_dropdown_selection(update, context, selected_value)
            if data == "back_main":
                return await self.start(update, context)
            elif data == "back_form":
                return await self.show_form_menu(update, context)
            elif data == "review_all":
                return await self.review_all_data(update, context)
            elif data == "generate_excel":
                return await self.generate_excel_form(update, context)
            elif data == "upload_photos_after_excel":
                await self.photo_handler.start_photo_upload_mode(update, context, user_id)
                return UPLOAD_PHOTO
            elif data == "finish_report":
                return await self.finish_report(update, context)
            elif data == "cancel_report":
                return await self.cancel_report(update, context)
            elif data == "upload_new_photo":
                await self.photo_handler.start_photo_upload_mode(update, context, user_id)
                return UPLOAD_PHOTO
            elif data == "section_photo_evidence":
                reply_markup, menu_text = await self.photo_handler.show_photo_menu(update, context, user_id)
                if reply_markup:
                    await query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode='Markdown')
                    # PERBAIKAN: Return FORM_SECTION agar callback dari photo menu bisa ditangani
                    return FORM_SECTION
            elif data == "confirm_delete_photos":
                success, message = await self.photo_handler.confirm_delete_photos(update, context, user_id)
                # Photo handler already handles the UI update, just return to FORM_SECTION
                return FORM_SECTION
            elif data == "cancel_delete_photos" or data == "section_photo_evidence":
                # Handle both cancel and direct navigation to photo evidence menu
                reply_markup, menu_text = await self.photo_handler.show_photo_menu(update, context, user_id)
                if reply_markup:
                    await query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode='Markdown')
                return FORM_SECTION
            elif data == "cancel_delete_photos":
                # Kembali ke menu foto evidence
                return await self.handle_photo_evidence_section(update, context)

            elif data == "view_photos":
                photo_list = await self.photo_handler.view_uploaded_photos(update, context, user_id)
                
                keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="section_photo_evidence")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    photo_list,
                    reply_markup=reply_markup
                )
                return FORM_SECTION
            elif data == "confirm_cancel":
                return await self.confirm_cancel_report(update, context)
            elif data == "delete_all_photos":
                success, message = await self.photo_handler.delete_all_photos(update, context, user_id)
                
                # Jika success dan message adalah "confirm_pending", biarkan photo_handler handle confirmation
                if success and message == "confirm_pending":
                    return FORM_SECTION  # Stay in FORM_SECTION to handle confirmation callbacks
                elif success and message == "no_photos_to_delete":
                    return FORM_SECTION  # Already handled by photo_handler, stay in FORM_SECTION
                else:
                    # Handle error case
                    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="section_photo_evidence")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        f"❌ {message}",
                        reply_markup=reply_markup
                    )
                    return FORM_SECTION
            elif data.startswith("section_"):
                section_id = data.replace("section_", "")
                if section_id == "photo_evidence":
                    return await self.handle_photo_evidence_section(update, context)
                else:
                    return await self.show_section_form(update, context, section_id)
            else:
                # PERBAIKAN: Default kembali ke form menu untuk callback yang tidak dikenali
                return await self.show_form_menu(update, context)
                
        except Exception as e:
            logger.error(f"Error in handle_form_section: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END
        
    async def handle_dropdown_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, selected_value):
        """Handle dropdown selection"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            current_section = context.user_data.get('current_section')
            current_field = context.user_data.get('current_field')
            
            if not current_section or not current_field:
                await query.edit_message_text("❌ Context error. Silakan pilih section ulang.")
                return await self.show_form_menu(update, context)
            
            # Save selection ke session
            existing_data = self.session_service.get_form_section(user_id, current_section) or {}
            existing_data[current_field] = selected_value
            
            success = self.session_service.update_form_section(user_id, current_section, existing_data)
            
            if success:
                await self.safe_edit_message(
                    query,
                    f"✅ {current_field} berhasil dipilih: {selected_value}\n\n"
                    "Data telah disimpan ke formulir."
                )
                
                # Clear context
                context.user_data.pop('current_section', None)
                context.user_data.pop('current_field', None)
                
                # Kembali ke form menu
                return await self.show_form_menu(update, context)
            else:
                await self.safe_edit_message(
                    query,
                    "❌ Gagal menyimpan pilihan. Silakan coba lagi."
                )
                return FORM_SECTION
                
        except Exception as e:
            logger.error(f"Error in handle_dropdown_selection: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan.")
            return FORM_SECTION
        
    async def finish_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finish the current report and end session"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            # Hapus session data tetapi biarkan folder tetap ada
            self.session_service.delete_session(user_id)
            
            await self.safe_edit_message(
                query,
                "✅ Laporan berhasil diselesaikan!\n\n"
                "Semua file telah disimpan ke Google Drive. "
                "Session telah diakhiri."
            )
            
            # Kembali ke menu utama
            return await self.start(update, context)
            
        except Exception as e:
            logger.error(f"Error in finish_report: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan saat menyelesaikan laporan.")
            return FORM_SECTION

    async def cancel_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the report and delete all created folders"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Session tidak ditemukan.")
                return await self.start(update, context)
            
            # Konfirmasi pembatalan
            keyboard = [
                [InlineKeyboardButton("✅ Ya, Hapus Semua", callback_data="confirm_cancel")],
                [InlineKeyboardButton("❌ Tidak, Kembali", callback_data="back_form")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.safe_edit_message(
                query,
                "⚠️ **Konfirmasi Pembatalan**\n\n"
                "Anda yakin ingin membatalkan form ini?\n"
                "Semua folder dan file yang sudah dibuat akan dihapus!\n\n"
                "Tindakan ini tidak dapat dibatalkan.",
                reply_markup=reply_markup
            )
            
            return FORM_SECTION
            
        except Exception as e:
            logger.error(f"Error in cancel_report: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan.")
            return FORM_SECTION
        
    async def finish_photo_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finish photo upload mode"""
        try:
            user_id = update.effective_user.id
            
            # Clear photo upload mode
            context.user_data.pop('photo_upload_mode', None)
            
            # Remove keyboard
            from telegram import ReplyKeyboardRemove
            await update.message.reply_text(
                "✅ Upload foto selesai!", 
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Get photos count
            photos = self.session_service.get_photos(user_id)
            
            success_text = f"✅ **Upload Foto Selesai**\n\n"
            success_text += f"📊 Total foto terupload: {len(photos)} foto\n\n"
            google_service = self.get_current_google_service(user_id)
            
            if photos:
                session = self.session_service.get_session(user_id)
                evidence_folder_id = session.get('evidence_folder_id')
                if evidence_folder_id:
                    folder_link = google_service.get_folder_link(evidence_folder_id)
                    success_text += f"📁 **Link folder:** {folder_link}\n\n"
            
            success_text += "Foto eviden berhasil disimpan ke Google Drive."
            
            await self.safe_send_message(
                context, 
                update.effective_chat.id, 
                success_text, 
                parse_mode='Markdown'
            )
            
            # Kembali ke form menu
            return await self.show_form_menu(update, context)
            
        except Exception as e:
            logger.error(f"Error in finish_photo_upload: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan.")
            return UPLOAD_PHOTO

    async def confirm_cancel_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and execute report cancellation"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            google_service = self.get_current_google_service(user_id)
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Session tidak ditemukan.")
                return await self.start(update, context)
            
            # Hapus folder dari Google Drive jika ada
            folder_ids = [
                session.get('evidence_folder_id'),
                session.get('ba_form_folder_id'), 
                session.get('report_folder_id')
            ]
            
            deleted_count = 0
            for folder_id in folder_ids:
                if folder_id:
                    try:
                        google_service.service_drive.files().delete(fileId=folder_id).execute()
                        deleted_count += 1
                        logger.info(f"🗑️ Deleted folder: {folder_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not delete folder {folder_id}: {e}")
            
            # Hapus session
            self.session_service.delete_session(user_id)
            
            await self.safe_edit_message(
                query,
                f"✅ Form berhasil dibatalkan!\n\n"
                f"🗑️ {deleted_count} folder telah dihapus.\n"
                f"Session telah direset."
            )
            
            # Kembali ke menu utama
            return await self.start(update, context)
            
        except Exception as e:
            logger.error(f"Error in confirm_cancel_report: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan saat membatalkan form.")
            return FORM_SECTION

    async def show_section_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE, section_id):
        """Show specific section form for input"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Session tidak ditemukan. Silakan /start ulang.")
                return ConversationHandler.END
            
            form_type = session.get('form_type', 'wifi')
            available_sections = self.ba_config.get_sections_for_form_type(form_type)
            section_info = available_sections.get(section_id)
            
            if not section_info:
                await query.edit_message_text("❌ Section tidak ditemukan.")
                return FORM_SECTION
            
            # TAMBAHAN: Handle section dengan single dropdown field
            if section_id == 'ont_type_wifi':
                field_config = list(section_info.fields.values())[0]  # Ambil field pertama
                field_name = list(section_info.fields.keys())[0]     # Ambil nama field pertama
                if field_config.field_type == 'dropdown':
                    return await self.show_section_dropdown(update, context, section_id, field_name, field_config.options)
            
            elif section_id == 'ont_selection':
                field_config = list(section_info.fields.values())[0]
                field_name = list(section_info.fields.keys())[0]
                if field_config.field_type == 'dropdown':
                    return await self.show_section_dropdown(update, context, section_id, field_name, field_config.options)
            
            # Store current section in context
            context.user_data['current_section'] = section_id
            
            # Khusus untuk section tanda tangan
            if section_id == 'tanda_tangan':
                return await self.handle_signature_section(update, context, section_info)
            
            # Get current data for this section
            form_data = session.get('form_data', {})
            section_data = form_data.get(section_id, {})
            
            # Generate form template
            form_template = self.ba_config.generate_section_template(section_id, form_type, section_data)
            
            section_text = f"{section_info.name}\n\n"
            section_text += f"```\n{form_template}\n```"
            
            # Create cancel keyboard
            keyboard = [[KeyboardButton("❌ Kembali ke Menu Formulir")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            if not section_text or section_text.strip() == "":
                section_text = "📋 Silakan isi data formulir"

            try:
                await self.safe_edit_message(query, section_text)
            except Exception as edit_error:
                logger.warning(f"Edit message failed, sending new: {edit_error}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=section_text
                )

            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📝 Silakan kirim data sesuai format di atas:",
                reply_markup=reply_markup
            )
            context.user_data['last_input_message'] = message.message_id
            
            return INPUT_DATA
            
        except Exception as e:
            logger.error(f"Error in show_section_form: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END
        
    async def safe_send_message(self, context, chat_id, text, **kwargs):
        """Safe method to send messages with empty text validation"""
        if not text or text.strip() == "":
            text = "📋 Data tidak tersedia"
        
        try:
            return await context.bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None

    async def safe_edit_message(self, query, text, **kwargs):
        """Safe method to edit messages with validation"""
        if not text or text.strip() == "":
            text = "📋 Data diperbarui"
        
        try:
            if query and query.message:
                return await query.edit_message_text(text, **kwargs)
            elif 'chat_id' in kwargs and 'message_id' in kwargs:
                # Handle case where we have chat_id and message_id instead of query
                return await self.application.bot.edit_message_text(
                    chat_id=kwargs['chat_id'],
                    message_id=kwargs['message_id'],
                    text=text,
                    **{k: v for k, v in kwargs.items() if k not in ['chat_id', 'message_id']}
                )
            return False
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            return False

    async def handle_signature_section(self, update: Update, context: ContextTypes.DEFAULT_TYPE, section_info):
        """Handle signature section specifically - hanya template saja"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            # Buat template tanda tangan kosong
            template_path = self.create_signature_template()
            
            if template_path:
                # Kirim template kepada pengguna tanpa instruksi berlebihan
                with open(template_path, 'rb') as template_file:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=template_file,
                        caption=f"{section_info.name}"
                    )
            
            signature_text = f"{section_info.name}\n\nSilakan pilih jenis tanda tangan:"
            
            keyboard = [
                [InlineKeyboardButton("📷 Upload TTD Teknisi", callback_data="upload_teknisi")],
                [InlineKeyboardButton("📷 Upload TTD Pelanggan", callback_data="upload_pelanggan")],
                [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_form")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.safe_edit_message(query, signature_text, reply_markup=reply_markup)

            
            # Bersihkan file template sementara
            if template_path and os.path.exists(template_path):
                os.remove(template_path)
                
            return SIGNATURE_UPLOAD
            
        except Exception as e:
            logger.error(f"Error in handle_signature_section: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END
        
    def create_signature_template(self):
        """Create signature template with guidelines"""
        try:
            # Ukuran template: 365x380 pixels (sesuai dengan kebutuhan Excel)
            width, height = 365, 380
            
            # Buat gambar putih dengan border
            img = PILImage.new('RGB', (width, height), 'white')
            
            # Simpan template sementara dengan DPI yang benar
            temp_dir = tempfile.gettempdir()
            template_path = os.path.join(temp_dir, f"signature_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            
            img.save(template_path, 'PNG', dpi=(301, 301))
            return template_path
            
        except Exception as e:
            logger.error(f"Error creating signature template: {e}")
            return None

    async def handle_signature_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle signature photo upload"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            data = query.data
            
            if data == "back_form":
                return await self.show_form_menu(update, context)
            elif data in ["upload_teknisi", "upload_pelanggan"]:
                # Set signature type in context
                signature_type = "TTD TEKNISI" if data == "upload_teknisi" else "TTD PELANGGAN"
                context.user_data['current_signature_type'] = signature_type
                await query.edit_message_text(
                    f"Silakan kirim foto tanda tangan untuk {signature_type}."
                )
                
                # Set state untuk menerima foto
                return SIGNATURE_UPLOAD
            else:
                # PERBAIKAN: Default kembali ke form menu
                return await self.show_form_menu(update, context)
                
        except Exception as e:
            logger.error(f"Error in handle_signature_upload: {e}")
            await self.safe_edit_message(query, "❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END

    async def handle_signature_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle signature photo upload"""
        try:
            user_id = update.effective_user.id
            logger.info(f"Processing signature for user: {user_id}")
            
            # Get current signature type from temp data
            signature_type = context.user_data.get('current_signature_type')
            logger.info(f"Current signature type: {signature_type}")
            
            if not signature_type:
                await self.safe_send_message(context, update.effective_chat.id, "❌ Tidak ada jenis tanda tangan yang dipilih. Silakan pilih ulang.")
                return
            
            # Send processing message
            processing_msg = await self.safe_send_message(context, update.effective_chat.id, "⏳ Memproses tanda tangan...")
            
            # Get the photo with highest resolution
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # Create temporary file with proper cleanup handling
            temp_file = None
            try:
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                await file.download_to_drive(temp_file.name)
                temp_file.close()
                
                # Process and resize the signature image
                processed_path = await self.process_signature_image(temp_file.name)
                
                if processed_path:
                    # Get existing signature data
                    existing_data = self.session_service.get_form_section(user_id, 'tanda_tangan') or {}
                    
                    # Add new signature
                    existing_data[signature_type] = f"SIGNATURE_IMAGE:{processed_path}"
                    
                    # Save to session
                    success = self.session_service.update_form_section(
                        user_id, 'tanda_tangan', existing_data
                    )
                    
                    if success:
                        # PERBAIKAN: Beri tahu jika masih ada tanda tangan yang belum diisi
                        current_data = self.session_service.get_form_section(user_id, 'tanda_tangan') or {}
                        has_teknisi = bool(current_data.get('TTD TEKNISI'))
                        has_pelanggan = bool(current_data.get('TTD PELANGGAN'))
                        
                        completion_message = ""
                        if not has_teknisi or not has_pelanggan:
                            missing = []
                            if not has_teknisi:
                                missing.append("TTD Teknisi")
                            if not has_pelanggan:
                                missing.append("TTD Pelanggan")
                            completion_message = f"\n\n⚠️ Masih perlu: {', '.join(missing)}"
                        # Update processing message
                        if processing_msg:
                            await self.safe_edit_message(
                                None,  # Tidak ada query di sini, jadi None
                                f"✅ Tanda tangan {signature_type} berhasil disimpan!{completion_message}\n\n"
                                "Silakan lanjutkan mengisi form atau pilih 'Lihat Form' untuk melanjutkan.",
                                chat_id=update.effective_chat.id,
                                message_id=processing_msg.message_id
                            )
                        
                        # Clear temp data
                        context.user_data.pop('current_signature_type', None)
                        
                        # Show form menu
                        return await self.show_form_menu(update, context)
                    else:
                        if processing_msg:
                            await self.safe_edit_message(
                                None,
                                "❌ Gagal menyimpan tanda tangan. Silakan coba lagi.",
                                chat_id=update.effective_chat.id,
                                message_id=processing_msg.message_id
                            )
                else:
                    if processing_msg:
                        await self.safe_edit_message(
                            None,
                            "❌ Gagal memproses gambar tanda tangan. Pastikan gambar jelas dan terang.",
                            chat_id=update.effective_chat.id,
                            message_id=processing_msg.message_id
                        )
                    
            finally:
                # Always clean up the original temp file
                try:
                    if temp_file and os.path.exists(temp_file.name):
                        os.remove(temp_file.name)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Could not clean up temp file: {cleanup_error}")
                    
        except Exception as e:
            logger.error(f"Error processing signature image: {e}")
            await self.safe_send_message(context, update.effective_chat.id, "❌ Terjadi kesalahan saat memproses tanda tangan.")
            return SIGNATURE_UPLOAD

    async def process_signature_image(self, image_path):
        """Process signature image with specific resolution requirements"""
        try:
            # Open and process the image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Target size for Excel: 365x380 pixels
                target_width, target_height = 365, 380
                
                # Resize to exact target dimensions
                img = img.resize((target_width, target_height), Image.LANCZOS)
                
                # Set DPI metadata (301 DPI)
                img.info['dpi'] = (301, 301)
                
                # Create output path
                temp_dir = tempfile.gettempdir()
                output_filename = f"signature_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                output_path = os.path.join(temp_dir, output_filename)
                
                # Save as PNG to preserve quality and metadata
                img.save(output_path, 'PNG', dpi=(301, 301))
                
                return output_path
                
        except Exception as e:
            logger.error(f"Error processing signature image: {e}")
            # Clean up if any file was created
            try:
                if 'output_path' in locals() and os.path.exists(output_path):
                    os.remove(output_path)
            except:
                pass
            return None

    async def handle_data_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle data input for sections"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            logger.info(f"User {user_id} input data: {message_text[:50]}...")
            logger.info(f"Current section: {context.user_data.get('current_section')}")
            
            # Remove reply keyboard first
            remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True)
            await update.message.reply_text(".", reply_markup=remove_keyboard)
            
            if message_text == "❌ Kembali ke Menu Formulir":
                return await self.show_form_menu(update, context)
            
            current_section = context.user_data.get('current_section')
            if not current_section:
                await update.message.reply_text("❌ Section tidak ditemukan. Kembali ke menu.")
                return await self.show_form_menu(update, context)
            
            # Parse input data
            session = self.session_service.get_session(user_id)
            form_type = session.get('form_type', 'wifi') if session else 'wifi'
            parsed_data = self.ba_config.parse_section_input(current_section, form_type, message_text)
            
            if not parsed_data:
                await update.message.reply_text(
                    "❌ Format data tidak valid. Silakan periksa template dan coba lagi."
                )
                return INPUT_DATA
            
            # Save data to session
            session = self.session_service.get_session(user_id)
            if not session:
                await update.message.reply_text("❌ Session error. Silakan /start ulang.")
                return ConversationHandler.END
            
            # Update form data
            form_data = session.get('form_data', {})
            form_data[current_section] = parsed_data
            
            self.session_service.update_session(user_id, {'form_data': form_data})
            
            # Show confirmation
            return await self.show_section_confirmation(update, context, current_section, parsed_data)
            
        except Exception as e:
            logger.error(f"Error in handle_data_input: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END
        
    def get_current_google_service(self, user_id):
        """Get Google service based on current form type"""
        session = self.session_service.get_session(user_id)
        form_type = session.get('form_type', 'wifi') if session else 'wifi'
        return self.google_services.get(form_type)


    async def show_section_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, section_id, data):
        """Show section data confirmation"""
        try:
            # Remove reply keyboard first
            remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True)
            await update.message.reply_text(".", reply_markup=remove_keyboard)
            
            # Get session and form type
            user_id = update.effective_user.id
            session = self.session_service.get_session(user_id)
            form_type = session.get('form_type', 'wifi') if session else 'wifi'
            available_sections = self.ba_config.get_sections_for_form_type(form_type)
            section_info = available_sections.get(section_id)
            
            if not section_info:
                await update.message.reply_text("❌ Section tidak ditemukan.")
                return ConversationHandler.END
            
            confirmation_text = f"Konfirmasi {section_info.name}\n\n"
            confirmation_text += "Data yang akan disimpan:\n\n"
            
            # Format data for display
            for field, value in data.items():
                if value:  # Only show filled fields
                    confirmation_text += f"{field}: {value}\n"
            
            keyboard = [
                [InlineKeyboardButton("✅ Simpan Data", callback_data=f"save_{section_id}")],
                [InlineKeyboardButton("✏️ Edit Ulang", callback_data=f"edit_{section_id}")],
                [InlineKeyboardButton("🔙 Menu Formulir", callback_data="back_form")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Remove reply keyboard
            remove_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True)
            await update.message.reply_text(".", reply_markup=remove_keyboard)
            
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                confirmation_text,
                reply_markup=reply_markup
            )

            return CONFIRM_SECTION
            
        except Exception as e:
            logger.error(f"Error in show_section_confirmation: {e}")
            await update.message.reply_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END

    async def handle_section_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle section confirmation actions"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            
            if data == "back_form":
                return await self.show_form_menu(update, context)
            elif data.startswith("save_"):
                section_id = data.replace("save_", "")
                await self.safe_edit_message(query, "✅ Data berhasil disimpan!")
                
                # Clear current section from context
                context.user_data.pop('current_section', None)
                
                return await self.show_form_menu(update, context)
            elif data.startswith("edit_"):
                section_id = data.replace("edit_", "")
                # Set current section again
                context.user_data['current_section'] = section_id
                return await self.show_section_form(update, context, section_id)
            else:
                # PERBAIKAN: Default kembali ke form menu
                return await self.show_form_menu(update, context)
                
        except Exception as e:
            logger.error(f"Error in handle_section_confirmation: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END

    async def handle_section_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle section input from menu"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            logger.info(f"Text input in FORM_SECTION state: {message_text}")
            
            # PERBAIKAN: Handle text dari photo upload yang masuk ke FORM_SECTION state
            if message_text in [
                "✅ Selesai Upload Foto", 
                "🔙 Kembali ke Form", 
                "❌ Kembali ke Menu Formulir",
                "⚠ Kembali ke Menu Formulir",
                "🔙 Kembali ke Menu Formulir"
            ]:
                # Clear upload mode sepenuhnya
                context.user_data.pop('photo_upload_mode', None)
                
                # Remove keyboard dengan ReplyKeyboardRemove
                from telegram import ReplyKeyboardRemove
                await update.message.reply_text("Kembali ke menu...", reply_markup=ReplyKeyboardRemove())
                return await self.show_form_menu(update, context)
            
            # If user sends other text, guide them back
            elif message_text and not message_text.startswith("/"):
                await update.message.reply_text(
                    "Silakan gunakan menu di atas untuk memilih section formulir."
                )
            
            return FORM_SECTION
            
        except Exception as e:
            logger.error(f"Error in handle_section_input: {e}")
            return FORM_SECTION

    async def show_section_dropdown(self, update: Update, context: ContextTypes.DEFAULT_TYPE, section_id, field_name, options):
        """Show dropdown selection for specific field"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            session = self.session_service.get_session(user_id)
            form_type = session.get('form_type', 'wifi') if session else 'wifi'
            available_sections = self.ba_config.get_sections_for_form_type(form_type)
            section_info = available_sections.get(section_id)
            
            if not section_info:
                await query.edit_message_text("❌ Section tidak ditemukan.")
                return FORM_SECTION
            
            # Store context untuk section dan field yang sedang dipilih
            context.user_data['current_section'] = section_id
            context.user_data['current_field'] = field_name
            
            selection_text = f"{section_info.name}\n\n"
            selection_text += f"Pilih {field_name}:"
            
            # Create keyboard dari options
            keyboard = []
            for option in options:
                keyboard.append([InlineKeyboardButton(f"✅ {option}", callback_data=f"select_{option}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_form")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.safe_edit_message(query, selection_text, reply_markup=reply_markup)
            return FORM_SECTION
            
        except Exception as e:
            logger.error(f"Error in show_section_dropdown: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan.")
            return FORM_SECTION

    async def review_all_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show review of all entered data"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Session tidak ditemukan. Silakan /start ulang.")
                return ConversationHandler.END
            
            form_data = session.get('form_data', {})
            
            review_text = "Review Data Berita Acara\n\n"
            
            form_type = session.get('form_type', 'wifi')
            available_sections = self.ba_config.get_sections_for_form_type(form_type)
            for section_id, section_info in available_sections.items():
                section_data = form_data.get(section_id, {})
                status_icon = "✅" if section_data else "❌"
                
                # PERBAIKAN: Akses name sebagai atribut objek
                section_name = section_info.name
                
                review_text += f"{status_icon} {section_name}\n"
                
                if section_data:
                    filled_count = sum(1 for v in section_data.values() if v)
                    total_count = len(section_data)
                    review_text += f"   📊 {filled_count}/{total_count} field terisi\n"
                else:
                    review_text += "   ⚠️ Belum ada data\n"
                
                review_text += "\n"
            
            keyboard = [
                [InlineKeyboardButton("📝 Edit Form", callback_data="back_form")],
                [InlineKeyboardButton("📤 Generate Excel", callback_data="generate_excel")],
                [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.safe_edit_message(query, review_text, reply_markup=reply_markup)
            
            # PERBAIKAN: Kembalikan state FORM_SECTION agar callback handler bekerja
            return FORM_SECTION
            
        except Exception as e:
            logger.error(f"Error in review_all_data: {e}")
            await query.edit_message_text("❌ Terjadi kesalahan. Silakan /start ulang.")
            return ConversationHandler.END

    async def generate_excel_form(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate Excel from form data with organized folder structure"""
        try:
            query = update.callback_query
            user_id = update.effective_user.id
            
            session = self.session_service.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Session tidak ditemukan. Silakan /start ulang.")
                return ConversationHandler.END
            
            form_data = session.get('form_data', {})
            
            # Validasi kedua tanda tangan wajib diisi
            tanda_tangan_data = form_data.get('tanda_tangan', {})
            has_teknisi_signature = bool(tanda_tangan_data.get('TTD TEKNISI'))
            has_pelanggan_signature = bool(tanda_tangan_data.get('TTD PELANGGAN'))
            
            if not has_teknisi_signature or not has_pelanggan_signature:
                missing_signatures = []
                if not has_teknisi_signature:
                    missing_signatures.append("TTD Teknisi")
                if not has_pelanggan_signature:
                    missing_signatures.append("TTD Pelanggan")
                
                await self.safe_edit_message(
                    query,
                    f"❌ Tanda tangan wajib diisi:\n"
                    f"• {'❌' if not has_teknisi_signature else '✅'} Tanda Tangan Teknisi\n"
                    f"• {'❌' if not has_pelanggan_signature else '✅'} Tanda Tangan Pelanggan\n\n"
                    f"Silakan lengkapi kedua tanda tangan terlebih dahulu."
                )
                return FORM_SECTION
            
            # Check if we have minimum required data
            required_sections = ['tanggal_layanan', 'identitas', 'tanda_tangan']
            has_required = all(form_data.get(section) for section in required_sections)
            
            if not has_required:
                await self.safe_edit_message(
                    query,
                    "❌ Data belum mencukupi untuk generate Excel.\n"
                    "Minimal isi bagian:\n"
                    "• Tanggal & Jenis Layanan\n"
                    "• Identitas Teknisi & Pelanggan\n"
                    "• Tanda Tangan (Teknisi dan Pelanggan)"
                )
                return FORM_SECTION
            
            # Show processing message
            await query.edit_message_text("⏳ Sedang memproses dan membuat Excel dengan struktur folder...")
            
            # Generate filename from form data
            filename = self._generate_filename(form_data)
            
            # Process Excel with organized folder structure
            google_service = self.get_current_google_service(user_id)
            form_type = session.get('form_type', 'wifi')
            success, result = await google_service.process_excel_only(
                form_data, filename, self.ba_config, form_type
            )
            
            if success:
                # Extract folder information from result
                result_info = result
                
                success_text = (
                    f"✅ Excel Berhasil Dibuat!\n\n"
                    f"📄 File: {filename}.xlsx\n"
                    f"📁 Struktur Folder:\n"
                    f"   • 📂 Laporan Utama: {result_info.get('report_folder_link', 'N/A')}\n"
                    f"   • 📁 Form BA: {result_info.get('ba_form_folder_link', 'N/A')}\n"
                    f"   • 📷 Evidence: {result_info.get('evidence_folder_link', 'N/A')}\n\n"
                    f"File Excel telah disimpan ke folder Form BA."
                )
                
                # Update session with folder IDs for evidence uploads
                self.session_service.update_session(user_id, {
                    'evidence_folder_id': result_info.get('evidence_folder_id'),
                    'report_folder_id': result_info.get('report_folder_id'),
                    'ba_form_folder_id': result_info.get('ba_form_folder_id'),
                    'excel_generated': True,  # Flag bahwa Excel sudah digenerate
                    'form_data': form_data  # Jangan hapus form data, simpan untuk referensi
                })
                
                await self.safe_send_message(context, update.effective_chat.id, success_text)
                
                # Tampilkan opsi lanjutan
                keyboard = [
                    [InlineKeyboardButton("📷 Upload Foto Eviden", callback_data="upload_photos_after_excel")],
                    [InlineKeyboardButton("✅ Selesaikan Laporan", callback_data="finish_report")],
                    [InlineKeyboardButton("❌ Batalkan Form (Hapus Semua)", callback_data="cancel_report")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await self.safe_send_message(
                    context,
                    update.effective_chat.id,
                    "Pilih tindakan selanjutnya:",
                    reply_markup=reply_markup
                )
                
                return FORM_SECTION
            else:
                await self.safe_send_message(context, update.effective_chat.id, f"❌ Gagal membuat Excel: {result}")
                return FORM_SECTION
                
        except Exception as e:
            logger.error(f"Error in generate_excel_form: {e}")
            await self.safe_send_message(context, update.effective_chat.id, "❌ Terjadi kesalahan saat membuat Excel. Silakan coba lagi.")
            return FORM_SECTION